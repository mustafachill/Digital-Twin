# ADR-0026: Plan to joint-space goals obtained by solving IK on the exact pose

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** Phase 1.C review fan-out (debugger measurement, architect and reviewer findings), remediated in `cite_skills`
- **Related:** [ADR-0006](0006-moveit2-motion-planning.md), [ADR-0010](0010-typed-ros-interfaces.md), [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md), CLAUDE.md §3 (P2, P5, P9)
- **See also:** a **pending** ADR on the planning *pipeline* — station-to-station motion moves to the Pilz Industrial Motion Planner, with OMPL retained as a fallback. That is a separate decision, taken separately, and this record does not depend on it. The two are easy to confuse and should be read together.

## Context

**This ADR is about how a motion goal is *specified*, not about which planner searches for
the path.** The two are independent, and the distinction matters because a separate decision
— to plan station-to-station motion with Pilz rather than OMPL — was taken at almost the same
moment. A deterministic point-to-point planner handed a 6-DOF pose goal on a 5-DOF arm still
has to resolve that goal, and Pilz's PTP resolves it through IK exactly once, which is the
behaviour measured at 8/8 below. Neither decision substitutes for the other.

Every motion in `cite_skills` was commanded with `MoveGroupInterface::setPoseTarget()` — a
full 6-DOF Cartesian pose goal. `./scripts/scenario pick_and_place` failed with `Pick`
aborting on `PLANNING_FAILED`, intermittently rather than always. No pose goal has ever
succeeded in this repository: every path that works today is joint-space (`MoveTo` with
`named_configuration: home`, and the raw `FollowJointTrajectory` goal the bring-up scenario
sends), which is why the `bringup` scenario's seven assertions could not have caught it.

**The arm cannot do what the goal asks.** The xArm 5 is J1 base yaw, then J2/J3/J4 three
*parallel* pitch joints, then J5 a pure roll about the tool axis. Forward kinematics
confirms that sweeping q5 leaves both the TCP position and the tool axis exactly invariant.
Everything from J2 outward therefore lies in one vertical plane through the base axis, and
the tool axis can only ever lie inside that plane. The set of orientations reachable at a
given point is a one-parameter family — a measure-zero manifold inside SO(3).

**MoveIt satisfies a pose goal by sampling.** A pose goal becomes a position constraint
plus an orientation constraint, and the goal sampler draws *random* poses from inside those
tolerances and runs IK on each draw. Almost every draw perturbs the tool axis out of the
arm's plane, IK fails, the goal sampler returns empty, and the planner reports it in its own
words: `RRTConnect: Unable to sample any valid states for goal tree`.

Measured in an isolated `move_group` rig — no Gazebo, no controllers, no behaviour tree,
driven through `compute_ik` and `plan_kinematic_path` — at the exact approach point the
skill asks for.

The first table is a property of **the arm**: it is IK on this kinematic chain, and it is
true under any planner, any pipeline and any tolerance. The second is a property of
**OMPL's goal sampling**: it is what a sampling planner does when asked to satisfy a pose
goal, and a reader running a non-sampling pipeline should expect those numbers to change
while the first table's do not.

| perturbation of the requested orientation (a property of the arm) | IK result |
|---|---|
| none | 8/8 |
| **0.001° out of the arm's plane** | **0/8** |
| 0.5° out of the arm's plane | 0/8 |
| 0.5° **inside** the arm's plane | 8/8 |

| goal form for the same target (a property of OMPL's goal sampler) | plan result |
|---|---|
| pose goal, `pos 1e-4 / ori 1e-3` (`MoveGroupInterface` defaults) | 3/8 |
| pose goal, `pos 1e-4 / ori 1e-2` (a *looser* tolerance) | **0/8** |
| **the same target as a joint-space goal** | **8/8** |

A looser tolerance planning *worse* is the fingerprint of this failure, and it is a
fingerprint of the *sampler* rather than of the arm: widening the tolerance widens the
random orientation draw, and every extra degree of freedom in that draw is off-manifold.

The same rig was rebuilt independently to check the decision before it was implemented,
this time driving the *shipped* skill server rather than the services directly. Over 24
trials at the same target: the pose goal planned 14/24 at the tight tolerance and 0/24 at
the loose one, while the skill server planning to an IK solution produced a trajectory
24/24.

Ruled out by the same measurement, and recorded here so they are not re-investigated:
reach (`compute_ik` 8/8 on the exact pose), the target being in collision (10/10 with
`avoid_collisions=true`; at the time of writing nothing in the repository publishes a
`CollisionObject` or a `PlanningScene` — a generated collision-scene artifact exists but has
no consumer — so the scene holds only the arm), the tip link and the SRDF (`link_tcp`
and `link_eef` both 8/8), and the yaw the skill computed for a top-down grasp (exactly
reachable, q5 = 0).

Two constraints on any answer are fixed and not up for debate. **P2**: whatever is
commanded in simulation must be the identical call on hardware, so the fix must be
planning-side only and must not branch on the backend. **The L3 interface is task-space**
([L3](../architecture/L3-capabilities.md)): `MoveTo`, `Pick` and `Place` take a pose in a
named frame, and a joint-space *goal field* in an action would leak the robot's kinematics
upward. Whatever we choose has to leave the action definitions untouched.

## Options considered

### Option A — Keep pose goals and tighten the goal tolerance
Shrink the orientation tolerance so fewer draws land off-manifold.

Rejected by measurement. The reachable set is measure-zero: no positive tolerance makes a
random draw land on it with probability 1, and the trend runs the wrong way — the
system already fails 5/8 at the tightest tolerance `MoveGroupInterface` offers. It would
convert a reproducible failure into a rarer one, which is worse than the failure.

### Option B — Express the arm's freedom as an orientation constraint
Send a goal whose orientation tolerance is wide about the tool's own axis (which J5 supplies
freely) and tight about the other two.

Rejected as not expressible. MoveIt's `OrientationConstraint` states tolerances about the
*goal frame's* x/y/z axes. The direction the arm cannot tilt in is the normal of the arm's
vertical plane — a direction that depends on where the target is, and that is not one of
those three axes for a general target. The out-of-plane component would still be sampled,
which is precisely the component measured at 0/8 at one thousandth of a degree.

### Option C — Replace the IK solver
Swap `KDLKinematicsPlugin` for an analytic or 5-DOF-aware solver.

Rejected because it addresses the wrong half. IK on the *exact* pose already succeeds 8/8.
What fails is IK on the sampler's *perturbed* poses, and those are genuinely unsolvable —
a better solver returns the same answer faster.

### Option D — Solve IK once on the exact pose, then plan to that joint configuration
`setJointValueTarget(pose, link)` runs `setFromIK` on the exact pose and installs a
**joint-space goal**, which is the case measured at 8/8. The action interface is unchanged:
the goal that arrives at L3 is still a pose, and the conversion happens inside the skill,
below the interface. Chosen.

## Decision

**A skill never hands MoveIt a Cartesian pose goal.** It resolves the requested pose into
the planning frame, solves IK on that exact pose, and plans to the resulting joint
configuration. This applies to every motion a skill commands — `MoveTo`, and the approach,
grasp/release and retreat legs of `Pick` and `Place`.

**This holds whatever pipeline is configured.** It is a rule about the goal, not about the
search. Under OMPL it removes the random goal draw that this arm cannot satisfy; under Pilz
it hands PTP the joint configuration PTP would have had to derive anyway. Changing the
pipeline does not reopen this decision, and this decision does not settle the pipeline.

**IK is attempted from several seeds before the skill reports failure.** A joint-space goal
commits to one IK branch. The first seed is the arm's current state, which keeps the chosen
branch close to where the arm already is; subsequent seeds are random within the joint
limits. Each solved branch is planned to in turn, so a branch with no collision-free path
is not mistaken for an unreachable pose.

**Reachability failure and planning failure are separate results.** "No IK solution exists
for this pose on this arm" and "IK succeeded but the planner found no path" are different
diagnoses with different recoveries, and a single message covering both sent three separate
investigations to the wrong place. They must not share a result code, and neither of their
messages may claim a collision when the planning scene contains only the arm.

At the time of writing they still do share one, because `ResultCode.msg` has no constant for
reachability and `cite_interfaces` was outside the change that implemented this decision.
The messages are distinct and the code carries a single named alias, so adding
`uint8 UNREACHABLE` and pointing that alias at it is the whole of the follow-up. Until then
L4 cannot tell the two apart from the code alone, and this record says so rather than
implying the split is complete (P7).

**The rule is not conditioned on the robot type in code.** L3 encodes mechanism, never
which robot is present (P5, P9); the skill server applies this path to whatever arm it was
given, and the multi-seed retry is what recovers, for a redundant arm, the branch freedom a
pose goal would have had.

**`feasible_grasp()` is removed.** It rewrote the requested yaw for a top-down grasp on the
premise that a 5-DOF arm "cannot choose the rotation about a downward tool axis freely".
That premise is inverted: with the tool pointing down, the rotation about the tool axis is
exactly what J5 *does* supply freely, and the measurement confirms the yaw it computed was
reachable. It was never the constraint, and its comment must not be carried forward.

## Consequences

### What this gets us
- The failing case is removed at its cause: the planner is asked only for goals the arm can
  reach, and the measured success rate on the exact target goes from 3/8 to 8/8 — 14/24 to
  24/24 on the independent re-measurement against the shipped server.
- The stochastic component disappears from goal *satisfiability*. Sampling-based planning
  remains stochastic in the path it finds (ADR-0006), which is the randomness we accepted;
  a goal that is only sometimes representable is not.
- Failures name themselves. A pose the arm cannot reach reports a reachability failure, so
  L4 can choose a different recovery from the one it chooses for a blocked path.
- The action interfaces are untouched, so L3 stays task-space and P2 is unaffected: the
  planning-side change is identical in simulation and on hardware, and there is no
  backend branch anywhere.

### What this costs us
- **One IK branch instead of all of them.** A pose goal lets the planner reach the target
  through any IK solution; a joint goal names one. The multi-seed retry buys most of that
  back but not all of it, and it costs one IK call plus one planning attempt per seed on the
  unlucky path — a slower failure than before.
- **The seed order is a behavioural choice.** Seeding from the current state biases towards
  the nearest branch, which is usually what an operator expects and is not always the
  branch with the shortest path. It is a policy, and it is now ours rather than MoveIt's.
- **Goal tolerance stops absorbing pose error.** A pose goal accepts anything inside its
  tolerance; a joint goal reproduces the IK solution. Any error between the requested pose
  and the reached pose is now the IK solver's residual, which is why `MoveTo` reports
  `position_error_m` as a measurement (P8) rather than leaving it zero.
- **A straight-line Cartesian move is not covered by this decision.** `computeCartesianPath`
  interpolates poses and solves IK at each of them; on this arm every interpolated pose
  that leaves the arm's plane is unsolvable, so a general straight line is not achievable
  and a plausible-looking partial path would be worse than a refusal.
  `MoveTo.Goal.cartesian_path` therefore returns `NOT_IMPLEMENTED` until a decision is
  taken about what a straight line means on an arm that cannot draw one (P7).

### What we will have to revisit
- **When the planning pipeline changes under it.** Station-to-station motion is moving to
  Pilz (a separate, pending ADR). Pilz plans **point to point and fails on a collision
  rather than routing around it**, so a joint-space goal that OMPL would have reached by an
  arc is either reachable in a straight joint interpolation or it is not. That interaction
  becomes visible the moment the planning scene stops being empty — a generated
  collision-scene artifact now exists and nothing consumes it yet — and the honest place to
  discover it is a scenario, not a review. Until then the OMPL fallback is what covers the
  cases Pilz refuses, and the multi-seed retry here is what gives the fallback more than one
  configuration to try.
- **When a 6-DOF or 7-DOF arm joins the fleet.** Arm heterogeneity is a charter goal, and a
  6-DOF arm does not have this constraint: for it, a pose goal is strictly more capable, and
  applying this decision blindly would degrade its motion quality for no reason. The
  revisit must not turn into a robot-type branch inside L3. The DOF count and the goal form
  it implies are facts about the robot type, so they belong in the **L0 model**, delivered
  to the skill server as a generated parameter, in the same way the planning group and the
  tip link already are (P1, P5). Until such an arm exists, adding that parameter would be a
  field with one value and no second reader.
- **If a planning scene ever gains obstacles.** The multi-seed retry currently discovers
  a blocked branch only by planning to it. With a populated scene it is worth validating
  each IK solution against the scene before planning, which needs a planning-scene monitor
  the skill server does not have today.
- **If IK residual becomes visible in the reached pose.** The IK solver's tolerance now sets
  the accuracy of a `MoveTo`. `position_error_m` is the metric that will show it; if it
  grows, the answer is a tighter solver tolerance, not a return to pose goals.
