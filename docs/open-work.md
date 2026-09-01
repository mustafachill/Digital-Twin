# Open work — snapshot of 2026-09-01

**Status: SNAPSHOT.** This is not a tracker and must not become one.

Charter §11 says the home of *"what is being worked on right now"* is the issue tracker and
explicitly **not** a document. No tracker is configured for this repository, and the working
list has been living in a session that ends. This file exists so that the list survives that
ending, and it is written as a **dated snapshot** for a successor session.

**It goes stale the moment work resumes.** Every item below names the command, file or record
that reproduces it; check that, never this file. If an item here disagrees with
`./scripts/doctor`, with a record in [`docs/adr/`](adr/README.md), or with a campaign in
[`docs/measurements/`](measurements/README.md), those are right and this is wrong.

**When a real tracker exists, delete this file rather than maintaining it.** A second place
where open work is written down is a P1 violation waiting to happen, and this file's only
defence is that it is dated and says so.

---

## Where the repository stood when this was written

`main` at `3725af5`, clean and pushed. Reproduce each figure rather than quoting it from here.

| | | Command |
|---|---|---|
| Environment | 25 passed, 0 failed, 1 skipped | `./scripts/doctor` |
| Packages | 11 first-party, 23 with the imported vendor tree | `find workspace/src -name package.xml \| wc -l` |
| L0 model | 1 zone, 7 types, 15 assets, 5 stations, 15 files | `./scripts/validate-model` |
| Decision records | 52 indexed | `./scripts/doctor`, `ADR index` line |
| Measurement campaigns | 10 | `find docs/measurements -mindepth 1 -maxdepth 1 -type d \| wc -l` |
| Charter | v1.12, 2026-09-01 | `what-we-are-doing.md` header |
| Shipped collision geometry | `convex_hull` | `model/assets/types/robots/xarm5.yaml` |

Phase 1 is closed (charter §8, exit criterion MET 2026-08-28). Phase 2 has split into 2.A and
2.B; 2.A's bring-up mechanism exists and **closes no clause** of the Phase 2 exit criterion.

---

## How to read the four groups

The grouping is by **what kind of work the item is**, because that decides who can do it and
what "done" means:

- **Measurement debts** — nothing is known to be broken; something is *unknown*. Done means a
  published campaign with thresholds registered before the first trial.
- **Known defects** — reproduced or computed, with a record. Done means a fix plus a
  regression test that fails without it.
- **Structural** — correct today, wrong on the next robot type, gripper or backend. Done means
  the shape changes, not the value.
- **Instrument honesty** — the tools that decide whether anything else is true. Every one of
  these misled this project at least once.

---

## 1. Measurement debts

### #49 — Link-versus-environment clearance under hull geometry is measured by nothing
ADR-0028's 484-configuration audit covered only the **34 arm-internal** link pairs. No audit has
ever paired hull geometry with the environment, and the generated planning scene holds four
40×40×120 mm beam housings, three conveyors, three pedestals and two tables.

**Bounded on one side, and this is what keeps it from being alarming.** The safety audit
verified over 20,000 random directions on all 13 hulls that the hull's support function exceeds
the source's by **+0.000000 mm** — the hull adds zero outward extent, so nothing approaching a
link convexly from outside can newly collide. All added material is inside a concavity. Per link
the hull can eat at most its concavity depth: `link2` 61.75 mm, `link3` 60.27 mm, `link_base`
33.25 mm, `link4` 21.76 mm, gripper base 14.07 mm, fingers 9.82 mm.

**Measured clean:** at the SRDF's two named group states (`home`, `hold-up`), all three arms,
every hull-to-scene clearance equals the vendor's to 0.00 mm.

**Not settled:** the arm at the configurations the cell actually reaches, which needs IK and a
running `move_group`. The consequence if it bites is a station approach pose newly refused by
`ValidateSolution`, surfacing as a `MoveTo` planning failure naming nothing about geometry — and
the pick already does this on `table_pick` under vendor geometry (ADR-0027).

**The cheap settlement, and it needs no campaign:** replay the joint trajectories the existing
`pick_and_place` and `continuous_line` scenarios produce under vendor geometry, and report
per-waypoint minimum distance from every link to every planning-scene object under both
geometries.

**Never widen a ceiling or a tolerance to absorb a planning refusal that appears after the hull
promotion.**

### #20 — Following error under `gz_ros2_control` has never been sampled
The path tolerance is **not** known to be inert: it demonstrably fires against mock hardware
under an injected fault, in ADR-0036's launch test. What is unestablished is its behaviour under
`gz_ros2_control`, **in both directions** — neither firing on a genuine obstruction nor staying
quiet on a healthy run has been shown there.

Why it is a real question: in simulation the position command interface is not a position servo.
`GazeboSimSystem::write()` computes `target_vel = -position_proportional_gain * error *
update_rate` (`gz_system.cpp:790-806`; default gain 0.1, update rate 150), a first-order lag with
τ ≈ 67 ms. Reaching the 1.0 rad path tolerance would mean the plugin commanding roughly 15 rad/s,
about 5× the joint's 3.14 rad/s URDF limit — and that command is computed **inside** the plugin,
downstream of `enforce_command_limits`, so nothing clamps it.

So the detector may never fire in CI while being live on hardware, which is a **P2 asymmetry in
the direction this project cares about**.

**Instrument note, now partly out of date.** This task was recorded as blocked on the absence of
a fixture that can hold a joint part-way. `cite_test_hardware::JointStopSystem` (ADR-0040) now
exists and does exactly that, and the 2026-09-01 grasp campaign drove it. Re-read the blocker
before assuming it still holds.

### #30 — Re-derive the six scenario wall-clock ceilings
**Partly answered.** The 2026-08-29 campaign measured all six appropriate at a full allocation,
margins 3.8–9.9, none too tight and none too loose. **Still open:** the under-load figure.

Two things have moved since this was written and both need folding in: the world now carries
ADR-0043's throttle, and the shipped collision geometry is hulls, which the 2026-09-01 capacity
campaign measures as materially cheaper. Ceilings derived on vendor meshes may now be loose.

**Change no ceiling without the measurement, and never widen one to absorb a failure.**

### #17 — Pilz checks collisions every 0.1 s and can step past a beam housing
Pilz does not search the planning scene; `ValidateSolution` is the sole environment-collision
gate, and it calls `PlanningScene::isPathValid`, which checks the trajectory's **waypoints** and
interpolates nothing between them. Waypoint spacing is Pilz's sampling time, 0.1 s — a C++
default argument (`TrajectoryGenerator::generate(..., double sampling_time = 0.1)`, called with
three arguments by `PlanningContextBase::solve`) with **no ROS parameter**, so it cannot go into
L0 and cannot be set from a generated file.

The arithmetic: at 0.1 s a waypoint step exceeds the 40 mm beam housing whenever the tool point
exceeds 0.40 m/s, and this arm's 3.14 rad/s ceiling at 0.35 velocity scaling permits roughly
0.077 m per step at 0.7 m reach. There are four beam housings in the scene.

Both obvious levers are cell-wide behaviour changes on a blocking CI gate — lower
`max_velocity_scaling`, or change the layout. A third worth weighing: **densify the trajectory
before validation** rather than slowing the arm.

This is a gap in the **only** environment-collision gate the cell has, so it should not sit
unowned — but it is narrow (thin objects, high tool speed) and closing it wrongly costs cycle
time everywhere.

### #41 — ADR-0043's real-time requirement
**Substantially overtaken and kept open deliberately.** ADR-0049 restated the requirement as
capacity plus a clock-deficit budget rather than relaxing it, the owner ratified that decision
on 2026-08-31, and the 2026-09-01 capacity campaign measures the shipped configuration
**clearing the 1.0 floor**.

What is still open is what this task was always about: **ADR-0049 sets neither of its two
thresholds**, and both ADR-0043 and ADR-0049 remain `Proposed`. Clearing a bare floor is not a
margin. Nothing in `workspace/`, `tools/`, `tests/` or `scripts/` measures either quantity
during a run — the only instrument is a frozen campaign harness no bring-up, scenario or CI step
reaches.

---

## 2. Known defects

### #36 — The grasp predicate: decided, specified, not implemented
**This is the most actionable item in the file.** The owner chose **option F** on 2026-09-01 —
judge the grasp against the part rather than against the commanded width — and
[ADR-0052](adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) is `Accepted` with the
mechanism specified in its 2026-09-01 amendment, §A.1–A.11.

Both error directions are now measured
([`2026-09-01-grasp-discrimination`](measurements/2026-09-01-grasp-discrimination/ANALYSIS.md)):
a real grasp reported empty, and a stall on nothing reported as a grasp.

**What the implementing change must carry**, from the amendment:
- The predicate reads the **interval of declared work-piece widths**, never "the part" —
  `Pick.Goal.workpiece_id` is an instance id minted by `WorkpieceRegistry::mint_id`, and
  `WorkpieceRecord` carries no type. Option F's own text claimed otherwise and is corrected.
- The band's admissible interval is measured; **no value is picked**, because the campaign
  reports every width metric unresolved at its own resolution. The binding constraint instead:
  **F's admitting set at the shipped default command must be a subset of today's.**
- `default-grasp-width-never-closes` keeps its number and changes its job; two new ERROR rules
  are specified.
- The caller door half-closes: a supplied width can no longer move the band, but a wider one
  still ends the close on goal tolerance.
- **P2 is a constraint, not a caveat.** The campaign establishes nothing about the physical
  gripper — there is no `GripperActionController` on that path at all.

The promotion gate is written in the amendment and is cheap to satisfy: the campaign's harness
produces the false-negative figure on every close and its `JointStopSystem` rig produces the
false-positive side.

### #25 — A gripper controller over plain mock hardware reports a grasp on empty air
`mock_components::GenericSystem::read()` never writes the velocity state when the command
interfaces are position-only, which is what every generated arm here declares. The generated JTC
config declares `state_interfaces: [position, velocity]`, so a controller reading velocity over
that plugin gets a permanent zero from cycle one.

Harmless for the trajectory controller. **Not harmless for the gripper:**
`position_controllers/GripperActionController` is configured with `allow_stalling: true` and
`stall_velocity_threshold: 0.05`, so it decides "held" from the velocity state — and since
ADR-0029 removed the attachment plugin, `stalled=true, reached_goal=false -> holding` is the
**sole** evidence anywhere in this project that a part is actually grasped.

Both production backends write velocity, so the running cell is fine. The hazard is a future
launch test standing the gripper controller up over plain `GenericSystem`.

**A hazard, not a defect — no test does this today.** The minimum action is one sentence in
`docs/architecture/cross-cutting-testing.md` beside the existing "What tests are not allowed to
do" list. Note that the 2026-09-01 campaign refuted a related prediction: over plain mock the
jaws stall at exactly `stall_timeout × ramp rate`, so a control designed to test free air tested
the ramp instead.

### #19 — The `station_transfer_1` dead end: fixed, and the records stay `Proposed`
Cause established: a wall-clock gripper deadline supervising a simulation-time process; on expiry
`Pick` returned `TIMEOUT` without recording custody or cancelling the goal, and the retry's
`MoveToHome` carried the part off its own trigger beam. Fixed and merged — the deadline is
L0-declared and counted in the node's clock, the goal is cancelled, L3 latches custody-unknown,
and L4 refuses a retry while a station still names a work-piece.

**ADR-0045 and ADR-0046 stay `Proposed` deliberately.** The promotion condition for each is a
`continuous_line` run on a CI runner **in which the gripper fails to answer and the line reports
it**. A run in which the gripper answers quickly shows nothing. What is evidenced is the
mechanism, forced in both directions locally; not the outcome.

Two things recorded and open: whether a friction grasp survives the cancel is unmeasured
(`set_hold_position` holds width and stops squeezing, and ADR-0029 leaves the grasp to friction
alone); and after a missed grasp `MoveToHome` no longer runs, so the arm stops inside the fixture
and nothing in software reopens the jaws.

### #26 — `bringup`'s `MoveTo` fails when a run is slow, and the split is perfectly disjoint
In the teardown campaign's 30 pre-fix `bringup` runs, five exited non-zero; two are teardown-only
and three failed `bringup`'s own `MoveTo` assertion — the functional half of a blocking CI gate.

**Duration is the discriminator and it separates cleanly.** Clean runs took 32–47 s; the three
failing runs took 94, 95 and 254 s. Runs 12 and 14 show suite times of 91.677 and 91.759 s, which
is a normal suite minus the `MoveTo` test **plus exactly** `TRAJECTORY_CEILING_S = 60.0`. Run 29
blew `SKILL_CEILING_S = 120.0`.

So the mechanism is severe slowness starving MoveIt past fixed ceilings — not a race, not a
rejection. **What causes a run to be twice as slow is the open question.**

Two traps in the evidence: the message *"the goal was never accepted"* is **misleading** — it is
a timeout, not an acceptance check, and that wording caused a wrong common-cause hypothesis once
already. And *"Command of at least one joint is out of limits"* appears in **all 30** runs
including the 25 clean ones, so it has zero discriminating power.

### #37 — `line_orchestrator` timed out waiting for `LineTopology` at bring-up
Seen once on 2026-08-29, on a run that was **restarted rather than analysed**, so it is one event
with no log kept. Nothing in the tree records this failure mode.

Candidates worth separating before calling it a flake: a QoS or latching mismatch on the topology
topic (CLAUDE.md §10's first bullet — a compatible pair still delivers nothing to a subscriber
that matched late); the publisher creating its publisher and publishing in the same callback (the
defect class that cost this project a belt setpoint for ten commits); or genuine slow bring-up.

**If it recurs, capture the log before restarting.**

### #55 — A paired bring-up failed on the plant side
The counterpart announced readiness; the plant never did. The plant's `planning_scene_loader.py`
for `arm_1` exited 1 with *"move_group refused the planning scene diff for zone 'cell_a'"*,
**14 ms after** that same `move_group` logged *"Unknown frame: cite_world"*. The node is
`required`, so the plant's launch shut down, and per ADR-0047 a side that ends ends the pair.

**Why it reads as a race and not a bad scene:** the counterpart brought the identical
configuration up cleanly at the same moment, on the same machine, in the same trial.

One event in eleven paired and twelve solo bring-ups, **not attributed**. Full evidence:
`docs/measurements/2026-09-01-capacity-on-shipped-main/raw/PAIR_HULL_FREE_3.console`, which
carries both sides' output.

**Why one event matters more than usual here:** it fails a `required` node and takes the whole
pair down, and **no test covers paired bring-up at all** — `launch_test` with
`IncludeLaunchDescription` holds one context on one domain, so a paired scenario cannot take
today's shape. A regression here fails nothing.

P4 is the lens: if the scene load depends on a frame becoming resolvable, that is a sequencing
question and the answer is an event, never a retry or a sleep.

---

## 3. Structural — correct today, wrong on the next type

### #50 — The hull measured-range constant is one gripper's property applied to every type
`NARROWEST_MEASURED_WORKPIECE_M = 0.050` in `tools/cite_tools/validate/physical.py` is the width
at which **the xArm parallel gripper's** pad plane sits 0.41 mm proud of **its** hull's relief
wedges. The rule that reads it is facility-wide: it compares the facility's narrowest declared
work-piece against one module-level global, for every type that binds a derived set, with no
reference to whether the type carries an end effector or which one.

Wrong in both directions. A second robot type declaring its own `convex_hull` set — with no
campaign behind it — **passes silently**, so the rule that exists to say "you are outside the
evidence" says nothing exactly when there is no evidence. And a second gripper with different pad
geometry is **passed** at 50 mm on evidence taken for a different gripper.

Suggested direction from two independent reviews: key the floor by the derived set's identity
(`CollisionMeshSet` already carries `package` + `root`) and make "no entry for this set" a
refusal rather than a pass. That keeps the number out of author-editable L0 — which is correct,
because deriving it from L0 would reduce the check to `narrowest >= narrowest`, a check that
cannot fail.

### #51 — The unconditional vendor-mesh ERROR leaves a genuine-collision-mesh vendor no valid model
`_vendor_collision_is_declared` now fires an unconditional ERROR on any vendor-described type
whose selected set is `vendor_meshes`, and its hint states an xArm-specific fact as if general.

Many vendors — UR, Franka — ship collision geometry genuinely distinct from their visual
geometry. Under the promotion such a type has **no valid model at all**: `vendor_meshes` is a hard
error and the only other kind is `convex_hull`, which requires the vendor checkout, a
`cite-model hulls` run, committed assets and a campaign. Adding a robot type is P9's primary swap
axis and this makes it strictly more expensive, as a CI-blocking error.

The rule's real assertion is *"this type's collision geometry **is** its visual geometry"*, which
is a model fact, not a consequence of the word `vendor_meshes`.

The same defect from the other side: `emits_vendor_description` tests `provider == "xacro_macro"
and category == "robot"`, so a future vendor-described end effector with `vendor_integrated:
false`, or a vendor-described fixture or sensor, would collide against its visual meshes and get
no finding of any severity.

**Note the coupling with the escape hatch:** the vendor set must remain selectable when the range
rule fires, so these two rules' conditions are already linked and should be designed together.

### #38 — The generator cannot render 2.B
Exactly three generator call sites branch on a backend: `ResolvedAsset.ros2_control_plugin` (into
the description), `control.py:236` (`use_sim_time`) and `bringup.py:363` (`hosted_by`). **All
three read the plant's backend.**

In 2.A that is harmless — a paired zone's plant must be `sim`, the counterpart writes no
`counterpart_backend`, so all three answer identically for both sides. In 2.B it is wrong:
`counterpart_backend: real` today yields a plan saying `counterpart_backend: real` beside
`hosted_by: simulator`, and one controller config carrying `use_sim_time: true` for a side that
has no simulator.

**Needs an ADR before 2.B** — either the three sites become per-side, or the schema refuses the
combination until they are.

### #45 — ADR-0048 clause 3 is overdue
ADR-0048 decided `hosted_by` should be **removed** from the bring-up plan rather than duplicated
per side, because it is a total function of a value the plan already carries per side and nothing
reads it — verified by grep: a dataclass field, a parser, two test fixtures, and
`simulation.launch.py` never mentions it. Clause 1 promoted 2026-08-31; clause 3 did not land, and
the status block records it as **OVERDUE** rather than pending, which is the right word.

Removing it moves the plan schema, `cite_bringup.plan`, its tests, the committed generated tree
and `MODEL_HASH` — coherent, just larger than clause 1's scope.

Also: `test_two_sides_with_the_same_name_are_refused` copies the plant side and appends it,
producing three sides on a paired checkout. It passes in both states because the duplicated-name
refusal fires either way — **it passes for a partly accidental reason** and belongs on
`_solo_document()` with the rest.

### #40 — Fourteen `test_plan.py` tests break on a paired checkout
Pre-existing on `main`, not the pair branch's debt — but a paired checkout is how a pair gets
brought up at all, so it is a state developers will be in. All fourteen fail the same way:
`_document()["plan"]["sides"].append(_counterpart(...))` producing two sides named `counterpart`.

The conversion is mechanical: `test_plan.py` now carries `_paired_document()` and
`_solo_document()` from the three that were fixed. A reviewer measured it — flip the model to
`sides: pair`, regenerate, and `test_plan.py` gives 17 failures while `test_pair.py`,
`test_simulation_launch.py` and `test_readiness_witness.py` stay clean, because the same fixture
guard was applied there.

**The class is: a test that reads the live generated plan instead of building its own document.**

**Possibly already fixed — verify by running, not by grep.** `test_plan.py` now holds 76 tests
including paired ones. Only a run against a paired model settles it.

### #47 — Five L5 review findings, with their content
Recorded here because they were once sent as bare identifiers and an agent correctly refused to
guess.

- **R-13** — `twin_endpoints()` is a hand-maintained mirror of what L5 owns, and the disjointness
  test reads its set **from that function** rather than from the `create_publisher` /
  `create_service` / `ActionServer` calls. Removing an entry leaves 12/12 green because the
  checked set merely shrinks. Assert its length and each named constant, or derive it from the node.
- **R-15** — two nodes named `twin_boundary` in one process collide on the rosout publisher
  registry. `rcl` warns, and because `stop()` destroys the plant's node first, anything the
  counterpart logs during teardown never reaches `/rosout`; counterpart-context log lines also ride
  the plant's domain rosout publisher, which is defensible but undocumented.
- **R-16** — `TestTheAssetNamespaceIsReadOffTheModel` cannot distinguish a derivation from a
  composition: replacing `manager.node.rpartition` with a literal f-string leaves 12/12 green. The
  test pins agreement with today's plan, not the mechanism its docstring names.
- **R-17** — two untested boundaries in `divergence.py` (`<= pairing_window_s` and `> bound_s` both
  survive flipping), and term 3's comparison is one-sided, so a **negative** deficit — a side
  running above real time — passes any bound. Wants an `abs()` or an explicit note when the
  instrument lands.
- **R-18** — the latched-mode launch test reads `modes[0]` from a class-level accumulator and
  passes only because alphabetically-earlier tests spin before any transition publishes. Create a
  throwaway subscriber inside the test, so that a late joiner is what tests late joining.

---

## 4. Instrument honesty

Every item here misled this project at least once, including in the session that wrote this file.

### #52 — CI's scenario verdict answers the cycle only; teardown is unread, not clean
`scenario_verdict()` in `scripts/_lib.sh` returns 0 — and the caller prints `Scenario 'X' passed`
— when `cycle_failures` is 0, `teardown_failures` is greater than 0, and the policy is
`advisory`. **CI passes `--teardown-advisory` to all three scenarios.**

So the line everyone reads out of a CI log answers the **cycle** and says nothing about teardown.
This matters because the split is deliberate and load-bearing: `scripts/scenario` exists to answer
two questions in one exit code, and the instrument collapses them back into one word — in the
opposite direction from the one the split was designed for.

On record: CLAUDE.md §2's *"Teardown passed in all six"* is scoped to the first six runs, read by
a different method; teardown for the newer rows is **unread**. And the hull promotion was merged
on a CI run reporting four scenario runs passed — that is four **cycle** passes.

**The real fix is a verdict line that reports both phases.** Re-grepping JUnit XML rescues one
reading; an instrument that prints one word for two questions will be misread again.

**Do not respond by making teardown blocking in CI.** That was decided deliberately and
separately; this is about the instrument's honesty, not its policy.

### #53 — Two ADRs assert `cite_twin` does not exist, inside verification tables marked "still true"
`docs/adr/0041-*.md` lines 31, 66 and 139 — line 139 inside a **verification table** marked
*"still true"*. `docs/adr/0044-*.md` line 40, and line 125's verification table, same marker.

Both false: `workspace/src/cite_twin/package.xml` is on disk, `twin_boundary.py` serves
`SetMode`, and `routing.py` keys on `MODE_VIRTUAL_LEAD`.

**Worse than ordinary prose drift:** a verification-table row saying "still true" is a claim that
someone re-checked it, and those tables exist so a reader can trust them without re-deriving. Two
are now lying in exactly the place this project put its trust.

The precedent for the fix is already in the tree — ADR-0050 line 75 carries the correction row
`` `cite_twin` does not exist | **False.** It exists ``.

**The question worth asking while fixing it:** how many other verification-table rows across the
52 records say "still true" about something that has since moved? A row verified once and never
re-read is a count with a date on it.

### #56 — Charter §7 lists four packages that do not exist, and §8 does not know `cite_twin` landed
Reported by the charter v1.12 agent and **not edited** — the owner's authorization covered two
corrections and not these. Each needs its own owner decision under CLAUDE.md §12.

1. **§8's Phase 2.A blockquotes predate `cite_twin`.** They still describe 2.A's L5 deliverable
   with no marker that the boundary process exists. After v1.12, §14's marked v1.9 row is the
   **only** place in the charter that mentions the mode server, so a reader of §8 alone cannot tell
   that L5's package is in the tree. The correction is the same two-sided sentence the v1.9 marker
   carries: the boundary exists, **and** nothing starts it, it refuses on a `single` zone, `valid`
   is false in every sample it can produce, and ADR-0050 is `Proposed`.
2. **§7 says four packages exist that do not.** Its preamble states *"Directories that carry no
   marker exist now"*, and `cite_hardware/`, `cite_control/`, `cite_telemetry/` and `cite_safety/`
   carry no marker and are not on disk. The parent carries `(Phase 1.B)`, so a generous reading is
   that the marker is inherited — but Phase 1.B is closed and these are Phase 2 and Phase 4
   packages, which makes the inheritance reading wrong rather than the entries.
3. **§8's Phase 2 scope sentence** promises *"The twin monitor publishing live divergence
   metrics"* with no status note, while `DivergenceMetrics.valid` is false in every sample the
   shipped package can produce.

**When editing the charter, the five exit criteria must stay byte-identical.** Their combined
sha256 over `grep "^> \*\*Exit criterion:\*\*" what-we-are-doing.md` is
`c2de0d872adfca9ea16fd8f899e5a1f554715049a4f013341e33bce9d0458454`, verified before and after
v1.12. Check it before and after any charter change.

---

## 5. The one large composite item

### #6 — Phase 1.E: documentation, quality gates, legacy retirement
Most of this is done or overtaken; what remains is genuinely open and worth naming separately
rather than leaving inside a stage ticket.

**Still open:**
- **Walk `docs/onboarding/getting-started.md` from a genuinely clean clone** and fix whatever does
  not work. That walk is the Phase 1 exit criterion in miniature, and it has already proved its
  point twice — `./scripts/build` failed from a clean checkout for weeks because two packages
  installed an untracked empty `include/`, and `bootstrap` once silently skipped a patch in a
  worktree. The 2026-08-27 walk stopped at `lint` **without launching the cell**.
- **Interface reference generated** from the `.msg`/`.srv`/`.action` files; per-package READMEs.
- **`resolve.py:135` and `moveit.py:91` hardcode `"drive_joint"`** instead of reading
  `drive_joint_suffix` — a P1 duplication.
- **ADR-0022's correction cites candidate-comparison numbers that live only in an agent
  transcript**, not in a committed file. P8 says a fidelity claim is backed by a published metric.
- **The 0.0005 timestep block of the grasp-plane campaign reached 4 of 20 planned trials** before a
  session limit. Committed as data, not as a result.

**Overtaken since this was written:** the Pilz pipeline is implemented; convex hulls are
implemented, promoted and shipped; `_collision_is_not_a_visual_mesh`'s vendor blindness is closed
by ADR-0028 decision 4; L0 now carries a work-piece type with dimensions. **Re-read each line
before acting on it.**

---

## What is NOT in this list, and is still owed

- **No vendor-described link's mass or inertia tensor is validated by anything.** The validator
  reads `description.body`; vendor-described types leave it unset. A 2026-08-31 audit read all 27
  links by hand and found 0 violations — one pass by one reader, not a check. This is the same
  structural blindness ADR-0028 closed for collision geometry, still open for inertia, and **it has
  no record of its own.**
- **The self-collision matrix is the vendor's, computed against vendor geometry**, now paired with
  hull geometry. Sized rather than closed: 44 of 78 geometry-bearing pairs are disabled and
  unaudited; four interpenetrate as hulls where the vendor metal is 1.57–31.77 mm apart. No runtime
  consequence today — MoveIt's ACM excludes them and Gazebo computes no same-model self-contacts —
  but the shipped configuration now depends on the vendor's disable list to hide it. ADR-0028's
  named interim check was **considered and declined**, with reasoning, in its 2026-09-01 amendment.
- **Enabling `<self_collide>` would jam the gripper.** On hull geometry `left_inner_knuckle` and
  `left_outer_knuckle` interpenetrate at every one of 200 drive angles. Guarded in the generator;
  the guard is the only thing standing between an ordinary fidelity improvement and a gripper that
  cannot close.
