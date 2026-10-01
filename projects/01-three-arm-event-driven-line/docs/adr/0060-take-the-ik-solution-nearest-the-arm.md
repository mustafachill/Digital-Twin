# ADR-0060: Take the IK solution nearest the arm, not the first one that plans

- **Status:** Proposed
- **Date:** 2026-09-21
- **Deciders:** Project owner, on a defect he watched happen
- **Related:** [ADR-0006](0006-moveit2-motion-planning.md),
  [ADR-0026](0026-joint-space-goals-on-under-six-dof-arms.md) (amended by this record),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [ADR-0036](0036-execution-side-trajectory-tolerances.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md), CLAUDE.md §3 (P8, P9)

## Context

**The project owner watched the cell run and said the arm was doing something absurd**: it
picked the box off the table and, instead of turning a little through the front to hand it to
the belt, swung almost all the way round the back. He was right, and the measurement is
`joint1 = 5.253 rad` — **301°** — at a place pose that is reachable at `-1.030 rad`, **-59°**.
The same tool pose. Five times the travel.

**Why it happens, read at `6a39eae`.** Every pose goal in the first-party tree funnels through
one IK call, `skill_server.cpp:1671`. `joint1` and `joint5` are declared `[-2π, +2π]` because
the L0 model sets `limited: false`, so **every reachable pose has a solution and a wound twin
360° away, and both are legal** — legal in the model, to `setFromIK`, to
`setJointValueTarget`, and to the runtime command limiter. `cite_skills::plan_to_pose` returns
on the **first seed that plans** and compares nothing. Seed 0 is the arm's current state;
seeds 1–7 are `setToRandomPositions`, uniform over the full ±2π; and `KDLKinematicsPlugin`
performs its own random restarts inside its 0.05 s timeout, so **even seed 0 can come back
wound**. Nothing anywhere prefers the nearer of two identical postures.

**ADR-0026 already owns this, and names it as a cost rather than a defect**: *"The seed order
is a behavioural choice. Seeding from the current state biases towards the nearest branch,
which is usually what an operator expects and is not always the branch with the shortest path.
**It is a policy, and it is now ours rather than MoveIt's.**"* This record changes that policy.

**What the long way cost, on the run that prompted this.** The 301° sweep aborted part-way —
`GOAL_TOLERANCE_VIOLATED`, the arm outside the 0.010 rad band and past its goal-time — and
`Place` opens its jaws *after* the descent, so the arm was left clamped on the part while the
line escalated and `StopAll` stopped the belt beneath it. **This record does not claim the
winding caused that abort.** A campaign measures it
(`docs/measurements/2026-09-21-place-abort-and-the-held-part/`), with the honest possibility,
registered before its first trial, that the abort does not reproduce at all.

## Options considered

### Option A — narrow the joint limits (`limited: true` in L0)
Makes the wound solution structurally illegal in one line.

**Rejected, on three counts.** It would put the arm's **current** state out of bounds, so
MoveIt would refuse to plan from it at all and a wound arm would be stranded — it breaks
exactly the case it is meant to rescue. It is type-level, so it changes the archived three-arm
`cell_a` too. And it silently deletes range the arm physically has: the vendor macro's
`limited` branch also narrows **joint3 from [-3.927, 0.19198] to [-3.1101, 0.19198]**, 0.817 rad
of elbow, unasked for and unrelated to this defect.

### Option B — choose the least-travel solution among the seeds that plan
Strictly more capable in principle: it also chooses between genuinely different branches — the
elbow flip and the `joint1 + π` shoulder flip — which this record's decision cannot.

**Not chosen, and kept in the drawer.** It does not give what was asked for. Nothing guarantees
that any of the eight seeds returns the near representative, so it lowers the probability of
the long way round without removing it, and the owner asked for the arm to turn through the
front, not to usually turn through the front. It also costs up to eight IK calls on the happy
path where seed 0 solves immediately — six legs a cycle — and it reintroduces run-to-run
non-determinism into branch choice, which ADR-0026 deliberately removed.

### Option C — a different IK solver, or a solver parameter
`solve_type` is TRAC-IK's, not KDL's; the generated kinematics file carries solver, search
resolution and timeout and has no slot for a preference. TRAC-IK's `Distance` mode minimises
distance from the seed *among solutions found inside its budget* — again probabilistic.

**Rejected.** A new external dependency under ADR-0008, to fix arithmetically what arithmetic
fixes exactly. ADR-0026 Option C already rejected replacing the solver.

### Option D — normalise toward `home` rather than toward the current state
Would give a globally unwound arm as a genuine invariant.

**Rejected.** It would force a long swing whenever the arm is legitimately wound, and it
contradicts the sentence in ADR-0026 this record is amending rather than discarding. Current
state is the weaker and safer commitment.

## Decision

**An IK solution is taken to the turn nearest the configuration the arm is standing in, before
it is offered to the planner.**

For each active joint in the group that is **revolute, not continuous, and declared over a
span strictly greater than 2π**, the solution's value is shifted by whole multiples of 2π
toward the current value, for as long as that stays inside the joint's own declared limits.
The wrapped state is then **verified by forward kinematics** and discarded in favour of the raw
solution if the tool pose moved. Solutions that normalise onto one already offered in this pass
are not offered twice.

The rule is driven by each joint's own declared limits and type, so there is no robot-type
branch anywhere (P9), and a joint with a span of 2π or less is inert by construction.

## Consequences

### What this gets us
- **The arm turns through the front**, deterministically, because the shift is arithmetic
  rather than a search. **Measured on a running cell on 2026-09-21**, over a full pick-and-place
  cycle sampled at the joint-state topic — 20 626 samples, one machine, one run:

  | joint | min | max | range |
  |---|---|---|---|
  | `picker_joint1` | **-59.0°** | **+57.7°** | **116.8°** |

  Those two extremes are the pick and place azimuths the L0 layout puts the table and the belt
  at, so the arm is crossing between them directly. **Before this change `joint1` stood at
  +301°.** The widest excursion of any joint from zero was 147.7°, inside half a turn. **One
  run, one machine, nothing registered in advance — that is not a rate.**
- **A 2π shift is exact, not an approximation.** `R(axis, q ± 2π) ≡ R(axis, q)` for any
  revolute joint; the residual is about 1e-16 relative, eleven orders below the IK solver's own
  convergence epsilon. The FK check makes that a measured number rather than an argument (P8).
- **It closes a case nobody had noticed**: a 50 mm approach-to-grasp descent could, today,
  return a 2π-shifted `joint1` and become a full base revolution. That is impossible now.
- **The multi-seed retry loses no posture variety.** Solutions 2π apart are the same posture;
  the branches the retry exists to explore — elbow flip, shoulder flip — are **π** apart and
  are untouched.

### What this costs us
- **It does not guarantee an unwound arm, and must never be written as though it did.** What it
  guarantees is **per-move minimal travel**. A cell whose stations all sat at negative
  arm-frame angles could keep an arm wound indefinitely, every individual move still minimal.
  What actually unwinds this cell's arm is `MoveToHome` — `joint1 = 0`, absolute, never routed
  through IK — which the station tree runs at **both ends of every cycle**.
- **One forward-kinematics evaluation per motion leg**, which is negligible against a planning
  call and is the price of verifying rather than asserting.
- **The swept path changes.** Two 2π-separated solutions are the same posture but Pilz draws a
  different joint-space straight line to each, so a front sweep can collide where a back sweep
  did not, or the reverse. What makes that safe to take rather than reckless is that Pilz
  cannot drive through furniture silently: `ValidateSolution` is the sole environment-collision
  gate, it checks every waypoint, and a refused plan falls back to OMPL, which routes. **The
  waypoint-sampling residual ADR-0027 records is unchanged** — and a shorter motion means more
  waypoints per radian, so if anything it tightens.
- **Acceptance cannot regress, and this is the invariant to keep pinned.** The wrapped value is
  substituted only when it is also in bounds, so the vector handed to `setJointValueTarget` is
  in bounds exactly when the raw one was. A test asserts precisely that.

### What we will have to revisit
- **When branch choice, rather than turn choice, is measured to matter.** Option B is the
  answer then, and it composes with this decision rather than replacing it.
- **When a 6-DOF or 7-DOF arm joins the fleet.** The rule is expressed over declared limits and
  joint type, so it should carry — but a redundant arm has a continuum of solutions and the
  nearest-turn question becomes a nearest-*configuration* question.
- **When a prismatic joint enters a planning group.** It is excluded by type today, deliberately;
  a rail or lift is the case that would otherwise have been shifted 6.283 m.
- **If the front sweep is measured to collide** on some layout. The answer is the layout or the
  planner, not a return to the long way round.

## What review changed before this shipped, recorded because the record would otherwise read as though it arrived correct

- **The first implementation of the bounds rule was wrong, and a reviewer found it by compiling
  the function rather than reading it.** Each outward walk tested only the bound it was walking
  toward, so an input more than a whole turn outside the interval could be answered with a
  candidate also outside it: `nearest_turn(20.0, 13.7, -2π, +2π)` returned **13.716815** against
  an upper bound of 6.283185. Nothing unsafe followed, because `setJointValueTarget` rejects an
  out-of-limit target downstream — but the header stated the invariant unconditionally and in
  capitals, and only a check it did not mention prevented consequence. The walks were replaced
  by an O(1) computation testing **both** bounds on every candidate, which removed a second
  defect with it: the walk did not terminate above about `2^53` turns, where subtracting a turn
  rounds to a no-op.
- **The verification this record originally specified could not fire.** It compared the tool
  point before and after the rewrite. A whole-turn shift of a revolute joint is an exact
  forward-kinematics identity for **every** model, so the check was vacuous — and on `joint5`,
  whose axis passes through the tool point, it was blind twice over. What is verified now is
  what is actually claimed: that every per-joint delta is a whole multiple of 2π.
- **Nothing pinned the behaviour this record exists to produce.** The unit tests covered the
  arithmetic; no test observed that the target handed to the planner is the near twin, so a
  regression turning the rewrite into a no-op would have passed every gate and shown up only as
  the long sweep returning on the cell. `tests/scenarios/pick_and_place.py` now requires that no
  joint leaves [-π, π] across a whole run, which ADR-0006 permits as a constraint on an outcome
  and which fails against the code this record replaces.

## What this record does not decide

- **It does not decide the layout.** The pick and the place sit 117.7° apart on this cell
  because the table and the belt are on opposite sides of the arm. That is a real question and
  a separate one; this decision makes the arm cross that angle the short way.
- **It does not attribute the aborted `Place`.** `docs/open-work.md` #60 records the cause as
  unestablished and this record leaves it there.
- **It does not touch what happens to a part still in the jaws.** ADR-0038 decision 5.
- **It does not close the two collision-coverage gaps the short arc newly exercises**, and they
  are recorded rather than fixed, by the project owner's decision not to build simulation
  machinery for a simulation problem. Both are in `docs/open-work.md`. In short: the held
  work-piece is attached to nothing, so the collision gate checks the arm's links and nothing at
  all against the part; and the new arc crosses the azimuth of the 40 mm break-beam housing,
  which is the object ADR-0027's waypoint-sampling residual is about. **Neither is a predicted
  collision — both are regions newly entered and unmeasured**, and what checks them today is
  that the scenarios assert where the work-piece ends up.
