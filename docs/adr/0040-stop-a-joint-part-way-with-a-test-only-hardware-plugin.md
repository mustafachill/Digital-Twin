# ADR-0040: Stop a joint part way with a test-only hardware plugin, so an abort reaches L3 on demand

- **Status:** Proposed (corrected 2026-08-28), 2026-08-28. Written before the
  implementation, which is the point ([CLAUDE.md §12](../../CLAUDE.md)). Every "will" below
  was a commitment when it was written; the section "What was measured on it" at the end is
  the only part written after.
  **The decision stands and the implementation is unchanged.** Four supporting claims are
  false or misleading — the mechanism that kills the velocity state, both unreachability
  arguments in decision 2, and how one mutation row reads. See the section
  "Correction — 2026-08-28: the velocity mechanism, two unreachability arguments, and how one
  mutation row reads", immediately below. It stays `Proposed`: whether the charter records
  this package is a user decision that has not been taken.
- **Date:** 2026-08-28
- **Deciders:** Coder agent, on the gap
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md) records in its correction
  to decision 8
- **Related:** [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0034](0034-process-lifecycle-mechanism-in-cite-runtime.md) (the precedent for a new
  package with an admission test),
  [ADR-0036](0036-execution-side-trajectory-tolerances.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [cross-cutting-testing.md](../architecture/cross-cutting-testing.md),
  charter §4 (P1, P2, P4, P5, P6, P9)

## Correction — 2026-08-28: the velocity mechanism, two unreachability arguments, and how one mutation row reads

An architecture review and an independent reproduction went over this record after it was
written. **The decision stands and not one line of the implementation changed.** Everything
in "What was measured on it" reproduced — 21 packages, 9 ROS packages at 0 failures, six
independent runs reading `0.000000000 rad/s` on every joint at the instant the result
arrived, the instrument non-vacuous at 0.78-1.59 rad/s during the healthy motion, and all
four mutation rows. What was wrong is the *reason* given in three places, and the way one
measured row is presented. Four items follow; the last says how they survived.

### 1. The generated arms do not declare a position-only command interface, and that is not why the velocity state is dead

Context claims the velocity state is never written "with a position-only command interface —
which is what every generated arm in this cell declares". Both halves are wrong.

**The descriptions declare both.**
`xarm_description/urdf/xarm5/xarm5.ros2_control.xacro` gives every joint a
`<command_interface name="position">` *and* a `<command_interface name="velocity">` — lines
31-38 for `joint1`, identically for the other four. The position-only declaration is in the
**controller configuration**: `cite_generated/control/cell_a_arm_1_controllers.yaml` declares
`command_interfaces: [position]` against `state_interfaces: [position, velocity]`.

**The mechanism is not skipping.** Against `hardware_interface` 4.45.2,
`generic_system.cpp:89-92` builds `skip_interfaces_` from the first
`calculate_dynamics_ ? 3 : 1` entries of
`standard_interfaces_ = {position, velocity, acceleration, effort}`. `calculate_dynamics_`
defaults false, so **`skip_interfaces_ = {position}` and velocity is not skipped**. The
loopback loop at line 500 tests membership at 502-507, does not `continue` for velocity, and
because the description *does* declare a velocity command interface the `has_command` guard
at 510 passes too — so `mirror_command_to_state` is called for velocity on every cycle.

It writes nothing, and that is the real mechanism: **no controller ever writes the velocity
command.** The JTC does not claim that interface, so the handle holds NaN, and
`mirror_command_to_state` (the lambda at line 339) has an explicit NaN branch that returns
without touching the state — `// NaN - do nothing. Command might not be set yet` at line 356.
The velocity state therefore holds its initial value for the life of the process.

**Same conclusion, different cause, and the difference is load-bearing.** As written, the
record sends a future contributor to the description, where the problem is not. The
condition that kills the channel is that **no controller claims the velocity command** — a
controller-configuration property, reviewed in a different file from the one this record
named. Adding `velocity` to any `command_interfaces:` list would revive the channel on plain
mock hardware.

**That would not defeat this fixture, and it is worth saying why rather than leaving a
reader to assume either way.** `JointStopSystem::read` delegates to the base class and then
overwrites the velocity state with its own first difference — deliberately last, so that it
differentiates the clamped position — so a velocity command written by the base mirror is
overwritten rather than obeyed. What such a change *would* silently alter is the Context
argument above, that "sampling `/joint_states` velocity on the existing rig measures
nothing", and any future rig built on plain `GenericSystem` that reads a velocity to decide
something. The live instance of that hazard is the gripper's `stall_velocity_threshold`,
which decides whether a part is held; it is now named in `cross-cutting-testing.md`'s list of
what tests are not allowed to do.

**And it is now measured rather than reasoned.** Plain `mock_components/GenericSystem`,
commands **enabled**, no stops: the arm rotated the full 1.6 rad and finished at
`+1.599999586` while the velocity channel read `0.000000 rad/s` across **1019 joint states**.
That is the strongest evidence there is for decision 1's velocity requirement — the obvious
way to answer question 2 would have returned "static" for a moving arm.

### 2. The first unreachability argument is about the generator, not the model

Decision 2 says the fixture's parameters "have no home in L0". The model already carries the
field that repeals it.

`model/schema/asset_instances.schema.json:191-218` gives `HardwareSelection` a free-form
`params` map; `asset_type.schema.json`'s `HardwareBackend.instance_params` is its per-backend
allowlist; `tools/cite_tools/validate/referential.py:237-243` already enforces one against
the other; and `model/assets/types/robots/xarm5.yaml:90-92` **already declares
`instance_params: [robot_ip, report_type]`** for the `real` backend, against Phase 2.

What is true is narrower, and it belongs to the generator:
`tools/cite_tools/generate/description.py:161` binds
`instance.hardware.ros2_control_plugin` and nothing else, and `hardware.params` appears
nowhere under `tools/cite_tools/generate/`. So the argument is a property of the
**description generator**, one function away from being false — and the Phase 2 wiring that
would falsify it is the reason `instance_params` exists at all.

It is pinned now. `tools/tests/test_hardware_params_unbound.py` declares `hardware.params` on
an arm and asserts the names and values reach no generated description, with the backend's
own plugin string as a positive control proving the search is not blind. Phase 2 fails that
test at the moment a reviewer needs to see it.

### 3. The `BUILD_TESTING` argument is real in principle and inert in this repository

Decision 2's second structural argument is correct about CMake and says nothing about any
build this project performs. colcon defaults `BUILD_TESTING` to `ON`, and
`grep -rn BUILD_TESTING scripts/ .github/ infra/` returns nothing. So in **every** build this
repository performs, `cite_test_hardware`'s library is compiled, installed, and on
`AMENT_PREFIX_PATH` for every controller manager the workspace starts — `./scripts/sim`
included.

**No `-DBUILD_TESTING=OFF` CI job was added, and that was a judgement rather than an
omission.** Such a job would make this argument true of the configuration it tests and of no
other, while the configuration everyone actually runs — including `./scripts/sim` — still has
the class loadable. It would certify the safe build and leave the real one unexamined, which
is a worse record than saying plainly that the argument is inert. The gate that matters in
the build we perform already exists: `cite_test_hardware/test/test_unreachable.py`.

**Of the three mechanisms decision 2 offers, exactly one is load-bearing today: the `on_init`
refusal.** It is unconditional, fail-closed, runs in the build everyone performs, and is
unit-tested with a passing control beside it (`cite_test_hardware/test/test_refusal.cpp`).
The `test_unreachable.py` guard is a second real gate in that same build. The `BUILD_TESTING`
argument is a third that currently carries no weight, and decision 2's ordering — which
presents it as structural and the guard test as merely "checked" — has it backwards.

### 4. The `disable_commands` mutation row reports one outcome; the run produced three failures

The row is exact about what it claims and silent about the rest of the run. Under that
mutation `test_1`'s control motion **also** aborts and classifies 2; `test_2` then fails with
*"test 1 did not run; nothing was recorded"*; and `test_3` gives the quoted answer. Two
separate `Position Error` aborts in one run, three failing assertions. Nothing in the
classification claim is wrong — but the row reads as though one assertion moved, and a reader
reproducing it should expect a three-failure red.

**The `1.001344` following error in "The fixture does what it claims" is not a fingerprint.**
Clean-tree runs gave 1.000007, 1.000769, 1.001173, 1.001787 and 1.001838; `1.001344`
reproduces only under the `disable_commands` mutation. It is one sample of a spread, and no
reader should treat it as a signature of anything.

### How these survived

Each is an inference checked in the wrong place, and none of them could fail.

- **Item 1** was read off the controller configuration and attributed to the description,
  because both say "position" and no assertion anywhere in the rig reads the description's
  command-interface list. The conclusion was true for a different reason, so nothing ever
  went red. The check that settles it — plain `GenericSystem` with commands enabled — was
  never run precisely because the answer was already believed.
- **Item 2** inferred an absence in L0 from the generator's binding table, without opening
  the schema that the generator does not consult. An argument about what the model *cannot*
  express was verified only in the code that consumes it.
- **Item 3** described a CMake guard by what it would do in a configuration nobody selects,
  and nobody grepped for whether it is ever selected.
- **Item 4** recorded the assertion the mutation was aimed at and dropped the two it knocked
  over on the way, which is what a mutation table invites unless it is written as a run log.

The pattern in the first three is one thing: **a supporting claim was sited in the layer the
author was already reading.** Only item 2 was cheap to convert into a test, and it now is.

**Provenance, so no number above is read as more than it is.** The source citations —
`xarm5.ros2_control.xacro`, `generic_system.cpp` at 4.45.2, the L0 schemas,
`referential.py`, `description.py`, and the `BUILD_TESTING` grep — were re-verified against
this checkout while writing this correction. The **run** figures were not re-run here: the
1019-sample `GenericSystem` reproduction in item 1, the 13-run race measurement quoted in
`test_abort_classification_launch.py`, and the three-failure account and following-error
spread in item 4 are the reproducing agent's measurements, on one machine, with no
thresholds registered in advance. They are recorded because they are the only measurements
of these things that exist, not because they have been replicated.


## Context

ADR-0037 corrects its own decision 8 and states the gap in one sentence:

> **no fixture in this repository drives a genuine abort into L3 on demand.**

Four separate pieces of work are blocked on that fixture, and the first two are what this
record's implementation answers:

1. `cite_skills::classify_execution_failure` — the function that decides whether L4 retries
   a station unattended or stops it for an operator — has never been reached by a real
   abort. Every row of it is unit-tested; nothing drives it end to end.
2. Decision 3's central claim, that the joint state is **static** when `execute()` returns,
   is reasoned and not measured. ADR-0037 names the measurement as outstanding and says what
   it would cost if the answer is no: "the classification is sampling a moving quantity and
   the decision's central advantage is gone."

The two others — whether the ADR-0036 path tolerance can fire under `gz_ros2_control` at
all, and the `ValidateSolution` waypoint-resolution gap — are measurements with their own
thresholds and are **out of scope here**.

### Why the existing rig cannot carry it, and neither reason is fixable in it

`cite_bringup/test/test_trajectory_constraints_launch.py` is the closest thing and fails
twice over. Both reasons are read out of that file:

- **It injects mistracking with `mock_components/GenericSystem`'s `disable_commands`**,
  which makes `read()` return before propagating anything. The joint state never leaves
  `initial_value`, so an abort leaves the arm exactly at the trajectory's *first point*. The
  classifier answers `AT_START` → `EXECUTION_FAILED`: the one answer that is **not**
  `MOTION_INTERRUPTED`, and the opposite of the case the classifier exists for.
- **It never reaches L3.** It launches `robot_state_publisher` and `ros2_control_node` and
  sends goals straight to `follow_joint_trajectory`. There is no `move_group` and no skill
  server, so nothing it produces passes through `classify_execution_failure` at all.

### A second fact, established while scoping this, that makes the measurement harder than it looks

**On mock hardware the velocity state interface is never written.**
`GenericSystem::read()` mirrors commands to states interface by interface; with a
position-only command interface — which is what every generated arm in this cell declares —
nothing ever writes velocity, so it holds its initial value for the life of the process.
**[Corrected 2026-08-28 — see the Correction section above. The arms declare a velocity
command interface too; what is position-only is the controller configuration, and the state
stays dead because the velocity *command* is never written, not because the interface is
skipped.]**

The generated `JointTrajectoryController` configuration declares
`state_interfaces: [position, velocity]`, so the controller and `joint_state_broadcaster`
both read that permanently-zero number. **Sampling `/joint_states` velocity on the existing
rig therefore measures nothing**: it would answer "static" for an arm travelling at any
speed whatever. A fixture that is to answer question 2 has to produce a velocity that is a
function of the joint's motion.

### Constraints that are not up for debate

1. **P2.** Nothing may change in production code merely to make testing possible, and
   nothing may change what a real backend does. ADR-0005 puts the whole sim/real difference
   in one place — the loaded `ros2_control` hardware plugin — and this fixture must live
   inside that one place or not exist.
2. **P4.** The hold is a *state* the fixture is put into, never a duration it waits for.
3. **P1/P5.** Any position, joint name or tolerance the fixture or its test names comes from
   the L0 model, the generated artifacts, or the test's own data — never from a constant in
   production code.
4. **P6.** The fixture's own discrimination is the deliverable. A rig that reports an abort
   it did not cause is worse than no rig, so it must be shown to fail when it should and
   pass when it should.
5. **The fixture must not be reachable from a production launch path**, and that has to be
   structurally true rather than conventionally true. A test double a real bring-up can load
   is a hazard, not a fixture.

## Options considered

### Option A — Extend the existing mock rig so `disable_commands` engages on a trigger

The obvious minimal change: keep `mock_components/GenericSystem` and make its
`command_propagation_disabled_` flag settable at run time instead of at start-up.

Genuinely plausible — the *behaviour* wanted here is exactly "`disable_commands`, engaged
part way" — and it is what the brief that produced this record listed first.

**Not chosen, and it is not close.** `command_propagation_disabled_` is a **private** member
of `GenericSystem`, set once in `on_init` from a hardware parameter. There is no setter, no
ROS interface, and no protected accessor, so reaching it means editing
`hardware_interface` — third-party source. The only sanctioned route for that is a patch
file against the pinned manifest (`external/`, §7), which would mean patching a vendor
package so that our tests can run. That is a heavier and more permanent commitment than
writing 150 lines of our own, and it puts a test affordance into the same library the
production `gz_ros2_control` path links.

It also would not have answered question 2: `disable_commands` freezes the state interfaces,
which leaves the velocity interface exactly as unwritten as it already is.

### Option B — A Gazebo-side obstruction

Put a fixed body in the world where the arm is going, run a scenario, and let physics stall
the joint.

Plausible, and it is the only option that produces a *physically caused* abort with real
contact dynamics. **Not chosen.** It fails the demand requirement in the way ADR-0037
already names: "a scenario cannot be made to fail on demand, and one that could would be
asserting the simulator rather than the policy." It would also need the obstruction to come
from the L0 model to exist at all (P1), which means a production world gains a body whose
only purpose is to be crashed into. And a scenario is the most expensive test in the tree,
for a question about a fifteen-line classification.

Worth keeping in view for a different question: whether the path tolerance can fire under
`gz_ros2_control` at all is a question about the *plugin's* command conversion, and only
Gazebo can answer it. That is item 3 in the brief and it is out of scope here.

### Option C — Drive `follow_joint_trajectory` directly and stub L3

Keep the existing rig's shape, and stand up something that calls `classify_execution_failure`
on the result.

**Not chosen**: it re-tests the free function that is already unit-tested and proves nothing
new. The whole content of the gap is that the abort has to travel `controller` →
`move_group` → `MoveGroupInterface::execute()` → `execute_plan` → the classifier, through
three funnels that ADR-0037 documents. A test that skips the funnels tests the half that was
never in doubt.

### Option D — A first-party `ros2_control` system plugin that tracks normally until a declared hard stop

Chosen. Detailed below.

## Decision

### 1. A new package, `cite_test_hardware`, holding one `SystemInterface` plugin

`cite_test_hardware::JointStopSystem`, deriving from `mock_components::GenericSystem`. It is
`GenericSystem` in every respect except two, and both are declared in the description rather
than compiled in:

- **A pair of hard stops on one named joint.** The plugin is given `stop_joint`,
  `stop_lower_rad` and `stop_upper_rad` as `<hardware>` parameters. After the base class has
  mirrored commands to states, that joint's *position state* is clamped into
  `[stop_lower_rad, stop_upper_rad]`. Every other joint is untouched.
- **A velocity state that is a function of motion.** For every joint that declares a
  velocity state interface, the plugin writes the first difference of that joint's position
  state over the control period. Without this the rig cannot answer question 2 at all, for
  the reason given in Context.

**The stop is two-sided and absolute** rather than a single threshold plus a direction. A
single threshold has to know which way the joint is travelling, and where the arm goes is
decided by an IK solve — so a solver that picks the equivalent branch on the other side of
zero would leave the stop un-hit and the rig silently green. Two stops in joint coordinates
cannot be missed by a sign.

**Why a clamp rather than a latch-and-freeze.** A latch that freezes the joint wherever it
stood when the trigger fired steps the state backwards by up to one cycle's travel at the
moment it engages, which is a spurious negative velocity sample injected into the exact
measurement this fixture exists to take. A clamp is monotone: the joint approaches the stop,
reaches it, and stays, with no discontinuity and with the resting position known in advance
to the value the description declares.

**This is P4 by construction.** The hold is a position, not a delay. Nothing in the fixture
reads a clock to decide when to engage, and a slower machine engages it at the same joint
angle.

### 2. It refuses to initialise unless it is being used as a fixture

`on_init` returns `ERROR` unless `stop_joint` names a joint the description declares with
both a position command interface and a position state interface, and unless
`stop_lower_rad` and `stop_upper_rad` are finite with `lower < upper`. `read` returns `ERROR`
on its first cycle if the joint is already outside its stops, because clamping from outside
would manufacture an abort the fixture did not cause — which is precisely the failure P6
names as worse than having no rig.

This is what makes "not reachable from a production launch path" **structural**, and it is
worth being precise about which parts are structural and which are merely checked:

- **Structural, first:** the parameters have no home in L0. Every `<ros2_control>` block in
  this repository is emitted by the generator from the facility model; the model has no
  concept of a hard stop at a joint angle, so a generated description cannot carry
  `stop_joint`, and a plugin that refuses to start without it cannot be a backend.
  **[Corrected 2026-08-28 — see the Correction section above. L0 already has
  `HardwareSelection.params` and its per-backend allowlist; the property is the description
  generator's, and it is now pinned by `tools/tests/test_hardware_params_unbound.py`.]**
- **Structural, second:** the library, its install rule and its pluginlib export all sit
  inside `if(BUILD_TESTING)`. A build with `-DBUILD_TESTING=OFF` produces a package
  containing no loadable class at all, so the class name does not resolve.
  **[Corrected 2026-08-28 — see the Correction section above. No build this repository
  performs sets it OFF, so the class is loadable in all of them; this argument is inert and
  the `on_init` refusal is the one that is load-bearing.]**
- **Checked, not structural:** the plugin class name appears nowhere in `model/`, nowhere in
  `workspace/src/cite_generated/`, and in no `launch/` directory. A hand edit that put it
  there would already be a Critical finding under ADR-0021 and would already fail
  `./scripts/validate-model`, which byte-diffs the generated tree against a fresh generator
  run — but "already covered by another gate" is not the same as tested, so a guard test
  asserts it directly.

### 3. The rig runs the real stack, and reads every number it can from the generated tree

One arm, in the arm's own namespace, running `robot_state_publisher`, a real
`ros2_control_node` loading the generated controller configuration **unmodified**, the
generated controllers, a real `move_group`, and the real `cite_skills` skill server. The
abort therefore travels the whole path ADR-0037 documents.

The robot description is the **generated** one, expanded with `xacro` and then altered in
exactly two ways, both asserted: the `<ros2_control>` hardware plugin is replaced, and the
stop parameters are added. Everything else — link geometry, joint limits, interface
declarations, the SRDF, kinematics, planning pipelines, MoveIt controllers, and every skill
server parameter — is read from `cite_generated` and from the generated bring-up plan. The
parameters `move_group` and the skill server receive are built by `simulation.launch.py`'s
own functions, so a rig that passes cannot be passing on a configuration the real bring-up
does not use.

`use_sim_time` is `false` on every node in the rig and there is no simulator, which is
consistent rather than mixed. That is a rig override, stated in the rig, and it changes
nothing about what is under test: the classification compares joint positions against a
trajectory's endpoints, and no part of it is derived from a clock.

### 4. Discrimination is in the commanded motion, not in a second rig

**One rig, one hardware configuration.** The stop stands where it stands; whether it is hit
is decided by the goal the test sends. A motion that stays clear of the stop must succeed; a
motion that drives through it by more than the generated path tolerance must abort and
classify `MOTION_INTERRUPTED`. This is a stronger discrimination statement than two rigs
side by side, because the two cases differ in *nothing* but the goal.

The velocity channel gets its own positive control, and it needs one: a measurement
instrument that reads zero is indistinguishable from an instrument that reads nothing. The
test asserts a non-zero sampled velocity **during** a healthy motion before it reports the
residual velocity at the end of an aborted one.

## Consequences

### What this gets us

- The gap ADR-0037 records is closed for the two cheapest questions: a real abort reaches
  `classify_execution_failure` through the real funnels, and the residual velocity at
  `execute()`'s return becomes a number instead of an argument.
- A reusable instrument. Any future question of the form "what does L3 do when the arm
  cannot get where it was sent" now has somewhere to be asked, at launch-test cost rather
  than at scenario cost.
- The whole sim/real difference stays where ADR-0005 put it. The fixture is a hardware
  plugin, which is the one thing that is *supposed* to differ between backends, so P2 is
  preserved by construction rather than by care.
- **No production code changes at all.** If this record had required a hook in the skill
  server, ADR-0037's own reasoning and the brief that produced this ADR both make that an
  `ESCALATE`. It did not.

### What this costs us

- **An eighth first-party package**, for a test double. `cite_runtime` (ADR-0034) is the
  precedent for adding one with an explicit admission rule, and the rule here is narrow:
  this package holds `ros2_control` test doubles, contains no domain knowledge, and is
  depended on by nothing that is not a test.
- **The plant is a perfect follower, and every number this rig produces is scoped by that.**
  Mock hardware mirrors a command to its state with no dynamics, so the velocity the fixture
  differentiates is the rate of change of the controller's own command stream. This rig can
  therefore say whether the *commanded* motion has stopped when `execute()` returns. It
  cannot say whether a real arm has stopped coasting, and no report may let the second read
  off the first.
- **The specific risk decision 3 names stays unmeasured.** That risk is an abort very early
  in the path where a *decelerating* arm is still within tolerance of the start and
  classifies as "never moved". A plant with no deceleration cannot produce it. Naming it as
  unmeasured is the honest answer; inventing a deceleration model in the fixture would be
  measuring the model.
- **A new launch test that stands up `move_group` and a skill server**, which is among the
  more expensive tests in the tree. It is one arm rather than three, and it runs no
  simulator.
- **The fixture is one more thing to keep in step with the generated description.** It reads
  the expanded generated URDF and asserts the shape it expects; a change to the backend
  declared in L0 will fail that assertion rather than be silently accepted. That is the
  intended behaviour and it is still maintenance.

### What we will have to revisit

- **If the answer to question 2 on a real plant ever matters more than it does today**, the
  measurement belongs in a scenario under Gazebo, whose command conversion has a real 67 ms
  lag (ADR-0036's correction). That is a different campaign with its own thresholds.
- **If a second test double is ever needed**, the admission rule for this package is the
  thing to re-read before adding it. A package that accumulates "things tests need" stops
  having a boundary.
- **If `BUILD_TESTING` ever stops being the switch that decides what a production build
  installs**, the second structural argument in decision 2 weakens to a convention and the
  guard test becomes the only thing holding it.
- **If the L0 model ever gains a hardware-plugin selector richer than the backend it has
  today**, the first structural argument has to be re-checked: what makes the fixture
  unreachable is that the model cannot express its parameters, and a more expressive model
  is exactly what would change that.

## What was measured on it

Written after the implementation, and deliberately separate from everything above.

**This is not a campaign and there is no directory for it in `docs/measurements/`.** Five
runs of one launch test, by the implementing agent, in one isolated freshly built tree, on
one machine, on 2026-08-28 — three standalone and two under `./scripts/test`, which runs
several packages' tests at once and is the loaded case. No thresholds were registered before
the first trial. Read it as the size of the evidence, not as a result.

### The fixture does what it claims

`launch_test cite_bringup/test/test_abort_classification_launch.py` and `./scripts/test`,
five runs, all four assertions passing in each, plus the post-shutdown check.

- The abort is genuine and it is the controller's. `joint_trajectory_controller` logged
  `State tolerances failed for joint 0: Position Error: 1.001344, Position Tolerance:
  1.000000` mid-motion — the ADR-0036 path tolerance, at the value L0 declares.
  **[Corrected 2026-08-28 — see the Correction section above. `1.001344` is one sample of a
  spread, not a fingerprint, and it reproduces only under the `disable_commands` mutation.]**
- L3 answered **`MOTION_INTERRUPTED` (10)**, with the classifier's `PART_WAY` wording rather
  than its unreadable-arm wording. That distinction is asserted, because `UNKNOWN` answers
  with the same code and is the opposite claim.
- The stopped joint came to rest at `+0.100000000` rad, the stop the description declared,
  while the other four had travelled — so the abort was the fixture's doing and the motion
  was not a pure rotation of the stopped joint.

### The discrimination, by mutation

Two mutations, one run each, everything else identical:

| Mutation | Result |
|---|---|
| Stops moved to ±100 rad, unreachable by the commanded motion | The same goal **succeeded** — `SUCCESS (0)`. Only the abort assertion failed. The abort in the baseline is the fixture's and not something ambient in the rig. |
| Fixture replaced by `mock_components/GenericSystem` with `disable_commands: true` — the mechanism the existing rig uses | The same goal produced a genuine path-tolerance abort classified **`EXECUTION_FAILED` (2)**, *"the arm is still within its goal tolerance of the trajectory's first point"*. **[Corrected 2026-08-28 — see the Correction section above. Exact as a classification claim, but the run fails three assertions, not one.]** |

Two further mutations, on the guarantees rather than on the measurement:

| Mutation | Result |
|---|---|
| `stop_joint` removed from the description | `on_init` **refused**: *"This is a TEST FIXTURE and refuses to run as a hardware backend"*, and the controller manager reported `Failed to initialize hardware`. This is the shape a generated description would have, because L0 cannot express a stop. |
| The fixture's own name added to `simulation.launch.py` | Both guard tests in `test_unreachable.py` **failed**, naming the file. |

The second row of the first table is worth more than the fixture is. ADR-0037's correction to decision 8 says
`disable_commands` produces the endpoint case by construction; that was read out of the
source, and this is the first time anything has **driven it through the classifier and
watched it answer**. It does.

### Question 2 — is the joint state static when `execute()` returns?

**On this rig, yes, and the qualification matters more than the answer.**

| Run | Largest joint speed when the result arrived | Last moving sample before it | Still samples after it |
|---|---|---|---|
| 1 | 0.000000000 rad/s | 61.4 ms | 9 |
| 2 | 0.000000000 rad/s | 48.4 ms | 7 |
| 3 | 0.000000000 rad/s | 71.6 ms | 11 |
| 4 (under `./scripts/test`) | 0.000000000 rad/s | 67.1 ms | 10 |
| 5 (under `./scripts/test`) | 0.000000000 rad/s | 60.7 ms | 9 |

655-659 joint states arrived during each aborted motion at a median interval of 6.7-6.8 ms,
so the "still" window is seven to eleven distinct samples and not one lucky one. The
instrument is not vacuous: the same channel read a peak of **0.70-2.63 rad/s** during the
healthy motion in the same runs — the low end is the loaded case — which the test asserts
before it reports anything above.

**What that does and does not establish.** The sampling instant is when the action result
reached the caller, which is strictly *after* `execute()` returned — `getCurrentState`, the
classification itself and the result's trip over the wire sit between them. So 48-72 ms is an
upper bound on the elapsed time and the stillness is measured over a window that includes the
one decision 3 cares about. What it establishes is that **the commanded motion has stopped**,
because on this plant the state is a mirror of the command. It establishes nothing about a
plant that coasts, and the specific risk decision 3 names — an abort early in the path where
a *decelerating* arm is still within tolerance of the start — remains unmeasured and is not
measurable here.
