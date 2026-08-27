# v1 lessons

What the first iteration of this project cost us to learn, written down before the tree
that taught it is deleted. Charter §12 schedules `legacy/` for deletion at the end of
Phase 1 and requires the knowledge to be captured first; this page is that capture.

- **Related:** [ADR-0001](../adr/0001-rebuild-rather-than-migrate.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §2, `legacy/README.md`

This is not a list of v1's mistakes. It is a list of **what to do instead**, each one
anchored to the code that proves the problem was real. The test a section has to pass is
whether an engineer hitting the same wall in Phase 2 or Phase 3 finds the answer here.

> **How this page was verified — 2026-08-26.** Every claim below was read out of the tree
> at commit `d68838b`: the `legacy/` sources named in each *Evidence* line, and the
> current-tree files named beside them. Nothing was run — no build, no container, no
> simulation — so every claim is a claim about **what the code says**, and the few places
> where the runtime consequence is inferred rather than observed are marked
> `not observed`. Where `legacy/`'s own documentation contradicts `legacy/`'s code, both
> are given and the contradiction is the lesson.
>
> **Second pass — 2026-08-26, at commit `2380c66`.** The section
> [The requirement, as first written](#the-requirement-as-first-written) was added by a
> reader going back through `legacy/` for what the first pass did not carry. Its quotation
> and the two commits that date it were read with `git show`; the topology, the refusal in
> `plan_line` and the scenario it names were read out of the current tree. Nothing was run
> here either.

> **Why `legacy/` paths here are code spans and not links.** This document is written to
> outlive the tree it describes. `./scripts/lint` resolves every relative Markdown link and
> fails on a dead one, so a link into `legacy/` would turn the scheduled deletion into a
> lint failure. Cite these paths as text; a reader who needs the file can recover it from
> git history, which ADR-0001 keeps.

## How to read this

| If you are about to… | Read |
|---|---|
| Bring up the vendor xArm stack, or move to real hardware | [1. xArm integration](#1-xarm-integration--what-the-vendor-stack-actually-required) |
| Touch controllers, joint limits, or a gripper | [2. `ros2_control`](#2-ros2_control--what-surprised-v1) |
| Change how a belt moves anything | [3. Conveyor mechanics](#3-conveyor-plugin-mechanics) |
| Add a robot, or a fourth arm | [4. Multi-robot spawning](#4-multi-robot-spawning) |
| Argue that something is "already working" | [5. What did not scale](#5-what-did-not-scale) |
| Write about what this project was asked to do, or scope a handoff | [The requirement, as first written](#the-requirement-as-first-written) |

## The requirement, as first written

**Everything else on this page is engineering. This is not.** `legacy/urls.txt` ends with a
note recording what the project was asked for, in the words it was asked in. It is the
earliest statement of that requirement anywhere in the repository, and it is the one thing
in `legacy/` whose value is not a lesson about ROS 2. It is reproduced here because the
file holding it is deleted at the end of Phase 1.

> dr mize dedi ki birden fazla robot olacak ve senkron çalışacaklar. mesela bir bant üzerinde malzeme yürüyecek, bir robot alacak öbür robota gidecek öbür robot bunu alacak

**English rendering.** "Our Dr. told us there will be more than one robot and they will work
in synchrony. For example, material will travel on a belt, one robot will pick it up, it
will go to the other robot, the other robot will take it."

Two notes on that rendering, the second of which decides how the rest of this section
reads. *Dr.* is an academic title, and who it refers to is not recorded anywhere in the
tree. And the subject of *gidecek* — "will go" — is unstated in the Turkish: what goes to
the other robot could be the material or the robot carrying it. **The sentence does not say
by what means the part crosses between the two arms**, and it should not be read as
settling that either way.

**Where it came from.** The last line of `legacy/urls.txt`, whose own header calls it "the
earliest written statement of the multi-robot synchronisation requirement that this project
exists to satisfy". That file's first four lines — a vendor explainer on digital twins and
three `docs.ros.org/en/humble/` pages — were committed on 2025-11-25 in `10663a1`, the
repository's second commit; the note was appended in `1cc35d6`, 2025-12-10. The note itself
carries no date and may have been written earlier. 2025-12-10 is the earliest date the tree
can prove.

**Why the Turkish is kept, and must not be "corrected".**
[ADR-0015](../adr/0015-english-only.md) governs the artifacts this project writes, and this
page is one of them: it is in English. The block above is a quotation of a primary source,
and a translated primary source stops being one — the citation would survive the deletion
in name and not in substance. The English rendering sits beside it so that a reader who
does not read Turkish loses nothing, which is what ADR-0015 asks for when it lists
"publishable and shareable without a translation pass" among its benefits. It is the only
passage of non-English prose on this page, and it is quoted data rather than something this
project wrote.

### Which half of it is built

The resemblance between this sentence and what Phase 1.D produced is close enough to be
worth recording and close enough to overclaim, so both halves are stated.

**Built: the belt, the pick, and the next robot taking it.** The generated process topology
`workspace/src/cite_generated/topology/cell_a_flow.yaml` describes this line and nothing
else — `station_transfer_1` (actor `arm_1`) picks at `cell_a__table_pick__surface` and
places at `cell_a__conveyor_1__infeed`; `station_transfer_2` (`arm_2`) picks at
`cell_a__conveyor_1__outfeed` and places at `conveyor_2`'s infeed; `station_transfer_3`
(`arm_3`) does the same again into `conveyor_3`. Every transfer station carries a beam
trigger, and every edge between two robots is declared `via` a conveyor.
`./scripts/scenario continuous_line` is the test of that claim. Material travelling on a
belt, one robot picking it up, the next robot taking it: the requirement's first clause and
its last are the same thing the topology declares. Note that the requirement itself opens
with a belt — the conveyor is not a substitution introduced by the rebuild.

**Not built: the crossing, if it was meant to be arm to arm.** Every edge in the model is
conveyor-mediated, and L4 refuses a direct one at plan time rather than leaving it
unimplemented. `plan_line`, in
`workspace/src/cite_orchestration/include/cite_orchestration/line_plan.hpp`, records a
refusal for any outbound edge whose receiving station has a robot actor and whose
`via_asset_id` is empty. [ADR-0031](../adr/0031-refuse-direct-handoff-without-orientation-certainty.md)
carries the decision and its 2026-08-26 correction, and the correction is the part that
matters here: what makes the *permitted* conveyor edge safe is the receiving gripper
squaring a free part up as it closes on it, and a direct handoff denies precisely that,
because a part still clamped by the giving gripper cannot rotate into alignment with the
receiving one. Read that ADR before writing anything about either topology; its numbers are
not restated here.

**"Synchronously" is the least settled word in the sentence.** The three arms are
coordinated by `line_orchestrator`, which instantiates one behaviour subtree per station
from that same generated topology. What that has been *measured* to do — over how many
runs, on whose machine, under what CI status, and what its own tests do and do not prove
about motion — is recorded in [`../../CLAUDE.md`](../../CLAUDE.md) §2, which calls the line
completing the newest and least-settled claim in that file. It is not copied here (P1).
Read it there before treating this clause as delivered.

**Nothing in this section signs anything off.** The belt, the picks and the next robot
taking the part exist and are exercised by a scenario. The crossing between two arms is
*answered* rather than delivered — refused, deliberately, with the reason written down. The
synchrony is measured rather than settled. The charter, not this note, is the authority on
what 1.D must deliver — [`../../what-we-are-doing.md`](../../what-we-are-doing.md) §8.

**On the four links above the note.** Three point at ROS 2 Humble documentation, which
[ADR-0002](../adr/0002-ros2-jazzy.md) supersedes; [toolchain.md](toolchain.md) carries the
Jazzy and Gazebo Harmonic equivalents, with each pin verified. The fourth, a vendor
explainer on what a digital twin is, has no direct successor in `docs/reference/`, and the
judgement here is that it does not need one: [literature.md](literature.md) carries
Kritzinger and the ISO 23247 material, which cover the same ground as sources this project
can cite in a report. Recorded so the deletion is made knowingly rather than silently.

## 0. What this rebuild rediscovered on its own

This is the strongest evidence on the page, and the charter did not anticipate it. The
following failures were hit **twice**: once by v1, and again by the rebuild, by people who
had the v1 tree available and still walked into the same wall. A lesson that recurs under
different people, a different ROS distribution and a different simulator is a property of
the problem, not an accident of v1.

| Failure | v1 | Rebuild |
|---|---|---|
| A git submodule's contents do not arrive, and the build dies somewhere unrelated | `legacy/README.md` records `gazebo_ros2_control` as a gitlink with no `.gitmodules` entry, resolving to an empty directory on any fresh clone | `scripts/bootstrap` lines 96-108 needs `vcs import --recursive` for `xarm_ros2`'s `xarm_sdk/cxx`, "without it that directory arrives empty and the build fails on `xarm_sdk`" |
| One model holding several arms gives every controller manager every joint | not reached — v1 spawned separately, and failed on names instead (§4) | `workspace/src/cite_bringup/test/test_plan.py` lines 68-77: "With all three arms in a single model, every controller manager claimed all eighteen joints and wrote to them each cycle" |
| Neither simulator offers a surface-velocity primitive, so "the belt moves things" has to be faked, and the fake is easy to describe wrongly | the belt link genuinely moves, in a 10 mm sawtooth (§3) | `workspace/src/cite_simulation/src/conveyor.cpp` lines 26-37: an earlier draft claimed `SetLinearVelocity` "keeps the surface where it is"; it moves the link |
| A command issued unconditionally every step is a command that is never withdrawn | the plugin drives `belt_joint_` on every world update whether or not the belt is enabled (§3) | `conveyor.cpp` lines 63-75: `LinearVelocityCmd` is zeroed but never removed, so a part carried once sat under a standing zero command for the rest of the run |
| The vendor gripper's follower joints are resolved by nothing | the mimic plugin is commented out of the build, and the gripper is on by default (§2) | [ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md): not by `ros2_control`, not by dartsim, not by the Classic plugin |
| A model that hardcodes its own ROS topic cannot be instantiated twice | the break-beam model hardcodes `<namespace>station</namespace>` (§5) | `conveyor.cpp` lines 17-24, rejecting `conveyor_sim_ros2`: "a hardcoded global topic cannot be instantiated three times under `/cite/<zone>/<asset_id>`" |

**The operative lesson:** having the losing tree on disk did not stop anyone repeating it.
A lesson only transfers if it is written where the next person is already looking — a
generator, a test name, a schema, a `doctor` check. Which is why v1's fatal submodule bug
is now a check in `scripts/doctor` (lines 299-309, "gitlink(s) with NO `.gitmodules` —
clone will lose them") rather than a paragraph anybody has to remember to read.

## 1. xArm integration — what the vendor stack actually required

### The vendor's controller YAML is per robot *type*, never per robot *instance*

**Do this:** generate one controller configuration file per arm instance, with the arm's
prefix already baked into every controller name and every joint name. Never hand the
vendor's file to more than one controller manager.

**What v1 found:** the vendor description prefixes its joints —
`legacy/xarm_ros2/xarm_description/urdf/gripper/xarm_gripper.ros2_control.xacro` line 9
declares `<joint name="${prefix}drive_joint">` — but the vendor's controller YAML does
not. `legacy/xarm_ros2/xarm_controller/config/xarm5_controllers.yaml` declares a
controller called `xarm5_traj_controller` over joints `joint1`…`joint5`, and
`xarm_gripper_controllers.yaml` declares `xarm_gripper_traj_controller` over `drive_joint`.
Unprefixed, both. The file is passed through untouched:
`legacy/xarm_ros2/xarm_description/urdf/common/common.gazebo.xacro` line 28 embeds it as
`<parameters>${ros2_control_params}</parameters>`, with no templating anywhere in the
chain.

So a prefixed multi-arm deployment is caught between two impossibilities. Ask for the
prefixed controller name and the file the controller manager was loaded with never
declares it. Ask for the unprefixed name and its joint list does not match the prefixed
joints in the URDF. v1 chose the first: all three of its launch files ask for
`{prefix}xarm5_traj_controller` (`legacy/assembly_line_bringup/launch/three_robots.launch.py`
lines 161-167, `legacy/fleet_manager/launch/fleet.launch.py` lines 184-196,
`legacy/fleet_manager/launch/multi_robot_test.launch.py` lines 283-295) while
`three_robots.launch.py` lines 43-46 hands the controller manager the vendor's unmodified
`xarm5_controllers.yaml`.

*The mismatch between the two files is verified. That the spawner therefore fails is
`not observed` — nothing was run.*

**Where the rebuild put the answer:** `workspace/src/cite_generated/control/` holds one
file per arm, and its names are prefixed at generation —
`/cite/cell_a/arm_1/controller_manager`, `arm_1_joint_trajectory_controller`,
`arm_1_joint1`…`arm_1_joint5`. The generated header states the reason plainly: "these are
the same controller and joint names the physical arm will use, because there is nowhere
else for them to come from." That is P2 made structural rather than promised.

### The vendor tree carries a git submodule, and it is not optional

**Do this:** fetch with `--recursive`, and make the absence detectable rather than
mysterious.

`legacy/xarm_ros2/.gitmodules` declares `xarm_sdk/cxx` from
`github.com/xArm-Developer/xArm-CPLUS-SDK.git`. v1's separate and fatal case was
`gazebo_ros2_control`, carried as a gitlink with **no** `.gitmodules` entry at all — so a
fresh clone produced an empty directory and, with it, the local patch that made controllers
load in the first place. `legacy/README.md` records that this tree "cannot be built from a
clean checkout by anyone," and records the upstream commit so the patch could be
re-derived. See [ADR-0008](../adr/0008-external-dependencies-via-vcstool.md) for the rule
this produced, and [toolchain.md](toolchain.md) for how the pin is verified today.

## 2. `ros2_control` — what surprised v1

### Declared joint limits do nothing unless you switch enforcement on

**Do this:** set `enforce_command_limits: true` in the controller manager's parameters, and
keep the limit *values* only in the description.

**What v1 found — or rather did not:** a search of `legacy/` on 2026-08-26 for
`enforce_command_limits` returned no occurrences. `ros2_control` defaults it to false, so
every limit v1's descriptions declared was inert, and nothing said so. The rebuild's
generated controller configuration sets it and explains why the numbers must not be
repeated beside the flag — `workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml`,
the `enforce_command_limits` block.

*That v1's limits were consequently unenforced follows from the default; `not observed`.*

### The gripper's follower joints are resolved by nobody, and the arm working proves nothing

**Do this:** before believing a gripper closes, name the component that actually couples
the follower joints, and check it is loaded.

**What v1 found:** `legacy/xarm_ros2/xarm_gazebo/CMakeLists.txt` lines 49-57 comment the
mimic joint plugin out of the build, with the note *"mimic_joint_plugin disabled due to
controller_interface header compatibility / This plugin is only needed for gripper
simulation, xArm 5 works without it."* `legacy/docs/WORK_LOG.md` (2025-12-02) records the
same decision. Then `three_robots.launch.py` lines 221-225 declare `add_gripper` with
`default_value='true'`, and the launch spawns a gripper controller for every arm. The
gripper's five follower joints — `legacy/xarm_ros2/xarm_description/urdf/gripper/xarm_gripper_macro.xacro`
lines 28-47 invoke `mimic_joint_plugin_gazebo` five times — had nothing left to drive them.

The comment is the interesting part. *"xArm 5 works without it"* is true and irrelevant:
the arm does work without the plugin, and the gripper is what the plugin was for. A
capability was signed off on evidence from a different capability.

**The rebuild reached the same place by a different route.**
[ADR-0022](../adr/0022-gripper-as-ros2-control-controller.md) works through it in full —
`ros2_control` resolves mimics declared inside the `<ros2_control>` block and not URDF
`<mimic>` tags elsewhere; dartsim implements no mimic constraint; and the Classic plugin
cannot load under Harmonic at all. Read that ADR, including its correction section, before
writing anything about mimic joints. Do not restate its findings; it is the source.

### Publishing a trajectory to a topic is not commanding a motion

**Do this:** use the `FollowJointTrajectory` action, and implement the cancellation and
preemption paths, not only the happy one.

**What v1 found:** `legacy/robot_interface/robot_interface/robot_node.py` lines 109-114
publishes `JointTrajectory` straight at the controller's topic. There is no goal handle, no
feedback, no result and no way to cancel — so the node cannot tell whether the arm moved,
and fell back to waiting out a duration instead (§5). The other v1 attempt got this right:
`legacy/multi_robot_coordinator/multi_robot_coordinator/coordinator_node.py` line 33
imports `FollowJointTrajectory` and uses an `ActionClient`. Two packages in one workspace,
two different ways of commanding the same arm.

## 3. Conveyor plugin mechanics

### Neither simulator gives you a moving surface. Decide which lie you are telling.

Gazebo Classic's ODE `fdir1`/`motion1` pair could fake one; Gazebo Harmonic's dartsim has
no equivalent, verified against the installed headers and recorded in
`workspace/src/cite_simulation/src/conveyor.cpp` lines 26-37. So a belt is always a
workaround, and the two iterations chose opposite ones:

| | v1 | Rebuild |
|---|---|---|
| What moves | the belt link, really | the carried part |
| Mechanism | `belt_joint_->SetVelocity(0, belt_velocity_)` every world update; `SetPosition(0, 0)` when the prismatic joint passes its 10 mm upper limit | a `LinearVelocityCmd` written onto each part inside the belt's carry volume, and **removed** the moment it leaves |
| Transport | frictional — the part is dragged by contact | kinematic — the part is commanded |
| Cost | a belt surface that resets every 10 mm of travel, and a real moving body under the payload | no slip, no tumble, no jam, no accumulation pressure |

**Do this:** whichever you pick, write the fidelity cost next to the mechanism, in the
plugin. `conveyor.cpp` lines 45-49 does: "No claim about belt handling, accumulation
pressure or singulation can rest on this plugin." A belt that carries things smoothly and
does not say why is a belt somebody will eventually cite in a report.

**Evidence for the v1 column:**
`legacy/ifra_conveyor_belt/ros2_conveyorbelt/src/ros2_conveyorbelt_plugin.cpp`, `OnUpdate`;
`legacy/conveyor_system/models/long_conveyor_belt/model.sdf`, which is where the 10 mm
travel comes from (`belt_joint`, `<upper>0.01</upper>`).

### A stopped belt should be inert, not held at zero

v1's `OnUpdate` calls `SetVelocity` on every world update unconditionally, including when
the belt is stopped — a stopped belt is a joint actively driven to zero, not a joint left
alone. That is the same shape of error the rebuild made and had to fix in a different
place: a velocity *component* that was zeroed each step but never removed, leaving parts
that "could not fall, could not be pushed and could not be lifted", visible only as a part
sinking at about 12 mm/s instead of falling (`conveyor.cpp` lines 63-75). *v1 is not
claimed to have shown that symptom; the shared property is the unconditional, unwithdrawn
command.*

### Units on the wire are part of the contract

**Do this:** put the unit in the type, or in a schema that rejects a wrong one.

**What v1 found:** `legacy/ifra_conveyor_belt/conveyorbelt_msgs/msg/ConveyorBeltState.msg`
documents `power` as a **percentage**, and the plugin computes
`belt_velocity_ = max_velocity_ * (power_ / 100)`. `legacy/start_conveyors.sh` calls the
service with `power: 0.3`. With the models' `<max_velocity>0.5</max_velocity>` that is
0.0015 m/s, not the 0.15 m/s that 30% of the maximum gives — a factor of a hundred,
landing at a speed hard to tell from a stopped belt.

The same script asks belt 2 for `power: -0.3` to reverse it. `SetConveyorPower` accepts
only `req->power >= 0 && req->power <= 100`; anything else sets `res->success = false` and
changes nothing. That belt never runs. And because the failure is a *field of the response*
rather than an exit status, `ros2 service call` still exits 0 and the script's `set -e`
cannot see it — after which the script prints `All conveyors started successfully!`.

**Two rules fall out.** A typed, unit-bearing contract would have made the first bug
unrepresentable — [ADR-0010](../adr/0010-typed-ros-interfaces.md). And a success flag that
nothing checks is not error handling: assert the postcondition, not the call. The rebuild
carries `ConveyorState` in `cite_interfaces` for exactly the first reason, and
[`../../CLAUDE.md`](../../CLAUDE.md) §2 records honestly that nothing publishes it yet.

For what a belt is *for* in this architecture — stopping on a sensor edge rather than
running open-loop — see [ADR-0032](../adr/0032-index-the-belt.md) and
[ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md).

## 4. Multi-robot spawning

Three separate things must all be right, and it is worth insisting they are separate:
(a) and (b) look like one problem, and v1 solved (a) in two of its three launch files while
solving (b) in none of them — which is only possible because they are independent. (c) is
the one the rebuild found on its own.

### (a) The controller manager must be in the arm's namespace

The vendor's `gazebo_ros2_control` block only emits `<ros><namespace>` when
`ros_namespace` is non-empty — `common.gazebo.xacro` lines 22-26, defaulting to `''` at
`xarm_device.urdf.xacro` line 49.

- `legacy/fleet_manager/launch/fleet.launch.py` line 75 and
  `legacy/fleet_manager/launch/multi_robot_test.launch.py` lines 86 and 103 pass
  `ros_namespace:={robot_id}`. Correct.
- `legacy/assembly_line_bringup/launch/three_robots.launch.py` never passes it — line 55
  sets `hw_ns='xarm'`, which is a different argument. So all three descriptions carry a
  controller manager with no namespace, while lines 169-182 spawn controllers against
  `/xarm1/controller_manager`, `/xarm2/…`, `/xarm3/…`.

### (b) The controller *names* must be per-instance

All three launch files ask for `{prefix}xarm5_traj_controller` from a controller manager
configured by an unprefixed vendor YAML. See §1 — none of them escapes this one, including
the two that got (a) right.

### (c) One Gazebo model per arm

v1 spawned each arm as its own entity, so it did not reach this. The rebuild did:
`workspace/src/cite_bringup/test/test_plan.py` lines 68-77 exists because with all three
arms in a single model, "every controller manager claimed all eighteen joints and wrote to
them each cycle. Nothing reports that; it would surface much later as motion nobody can
account for."

**Do this:** derive (a), (b) and (c) from one declaration of the cell, so they cannot drift
apart — [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md),
[ADR-0021](../adr/0021-generated-artifacts-are-committed.md). And keep a test whose *name*
carries the reason, the way `test_each_arm_has_its_own_description` does; that is what
makes the lesson reach the next person without them reading this page.

### Startup was sequenced by stopwatch, in every attempt

`legacy/assembly_line_bringup/launch/assembly_line.launch.py` line 71 starts the
coordinator at `period=35.0`, commented *"Wait for all robots to spawn and controllers to
load."* Four v1 launch files sequence startup this way — `three_robots.launch.py`,
`assembly_line.launch.py`, `fleet.launch.py` and `multi_robot_test.launch.py` — with delays
built as `i * 3.0`, `controller_delay + 1.0`, `+ 2.0`, `+ 3.0`. Every one of those numbers
is a guess about a machine, and every one of them gets worse as the cell grows.

This is the standing prohibition in [`../../CLAUDE.md`](../../CLAUDE.md) §4 and the whole
of P4; the design that replaces it is in
[`../architecture/cross-cutting-lifecycle.md`](../architecture/cross-cutting-lifecycle.md),
which already cites `multi_robot_test.launch.py` directly.

## 5. What did not scale

### The main entry point did not do what every document said it did

**This is the most important paragraph on the page.**
`legacy/assembly_line_bringup/launch/digital_twin.launch.py` is named by
`legacy/docs/WORK_LOG.md` (2025-12-04) as "the primary entry point" for the digital twin.
It declares exactly two modes — line 64, `choices=['single', 'dual']` — and each one
delegates wholesale to a vendor launch file: `xarm5_moveit_gazebo.launch.py` for single,
`_dual_robot_beside_table_gazebo.launch.py` for dual. It sets `GAZEBO_MODEL_PATH` so the
conveyor and sensor models are *findable*, and then spawns none of them. No conveyor, no
break beams, no coordinator, and no third arm.

Meanwhile `legacy/docs/PROJECT_CONTEXT.md` opens with a three-robot, three-belt,
three-sensor, three-camera assembly line drawn as the system architecture, and lists "3x
xArm 5 Robot Arms" and a "Sensor Network" including RealSense D435 cameras among its core
components. The camera claim is checkable and false in two directions at once:
`legacy/assembly_line_sensors/models/` contains only `break_beam_sensor` and
`proximity_sensor`, and `three_robots.launch.py` line 61 passes
`add_realsense_d435i='false'`.

`legacy/README.md` — v1's own retrospective — says v1 "reached a working single-robot
simulation." **The code agrees with the retrospective and contradicts the contemporaneous
documentation.** The gap between them is roughly the whole of the project as described.

**Do this:** tie the status of a capability to something that fails when the capability
does. This is what P7 is, why [`../../CLAUDE.md`](../../CLAUDE.md) §2 reads the way it does,
why layer documents carry `DESIGNED`/`PARTIAL`/`BUILT` with the evidence named, and why
numbers live in [`../measurements/`](../measurements/README.md) with their thresholds
registered before the first trial rather than in prose.

### The work log recorded interfaces that were never created

`legacy/docs/WORK_LOG.md` (2025-12-04) lists, as files touched,
`src/robot_interface/msg/RobotStatus.msg`, `HandoffRequest.msg`, `HandoffResponse.msg`,
`srv/RequestHandoff.srv`, `src/fleet_manager/srv/SpawnRobot.srv`, `RemoveRobot.srv`,
`GetFleetStatus.srv`, and a `CMakeLists.txt` for each package.
`legacy/docs/SCALABLE_ARCHITECTURE.md` §3.2 goes further and specifies three message types
field by field — `RobotStatus`, `RobotCommand` and `HandoffRequest`.

None of them exist. A survey of `legacy/` on 2026-08-26 for `*.msg`, `*.srv` and `*.action`
outside `legacy/xarm_ros2/` found exactly two files, both belonging to the third-party IFRA
conveyor package. Both `legacy/robot_interface/` and `legacy/fleet_manager/` are
`ament_python` packages with `setup.py` and no `CMakeLists.txt` — they could not have
generated an interface even if the files had been written.

What went over the wire instead was `std_msgs/String` carrying `str()` of a Python dict —
`robot_node.py` lines 245-253 and `handoff_coordinator.py` lines 276-289. That wire format
is Python's `repr`: single-quoted, rejected by `json.loads`, and recoverable only with a
Python-literal parser such as `ast.literal_eval`. A consumer in another language has to
reimplement one. See [ADR-0010](../adr/0010-typed-ros-interfaces.md) and
[`../architecture/L7-presentation.md`](../architecture/L7-presentation.md); they already
carry this and it is not restated here.

**Do this:** a design document describes a design. Only the tree says what exists. When the
two disagree, the tree is right — and a work log that records intentions in the past tense
is how they came to disagree.

### The same fact, written down repeatedly, never twice the same

**Do this:** [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md). What follows
is what the alternative actually looks like, which the ADR does not have room for.

Where the three arms stand was written down three times and read from none of them:

- `legacy/assembly_line_bringup/config/robot_positions.yaml` places them at `x=-0.5`,
  `y=-1.2/0.0/1.2`, `yaw=1.5708`.
- `legacy/assembly_line_bringup/launch/three_robots.launch.py` lines 68-72 hardcodes the
  same numbers as a Python list. It imports `yaml` at line 16 and never parses anything
  with it.
- `legacy/fleet_manager/config/fleet_config.yaml` places them somewhere else entirely —
  `x=-2.2/-0.75/0.8`, `y=-0.5/0.8/-0.5`, `yaw=0.0`.

A search on 2026-08-26 for readers of `robot_positions.yaml` found one reference in the
whole tree: its own line in `WORK_LOG.md`. **Nothing reads it.** A configuration file that
no code loads is not configuration; it is a comment that looks authoritative.

`fleet_config.yaml` then disagrees with *itself*. Its `conveyors:` block puts belt 1 at
`x=-2.0` with `exit_point: [-2.0, 1.0, 0.8]`; the comments in its own `topology:` block put
belt 1 at `x=-1.5` and its end at `x=-1.0`; and `sensors.belt_1_end_sensor` sits at
`[-1.0, 1.0, 0.85]` — placed against the comment, a metre from where the file's own data
puts the belt.

And the loader reads none of it. `legacy/fleet_manager/fleet_manager/config_loader.py`
line 174 calls `data.get('conveyor', {})` while the file writes `conveyors:`, so every belt
silently falls back to hardcoded defaults — length 4.0 against the file's 2.0, and
`entry_point`/`exit_point` of `[0.0, ∓1.8, 0.8]` against everything above.
[`../architecture/L0-facility-model.md`](../architecture/L0-facility-model.md) already uses
this exact mismatch to justify `additionalProperties: false`, and is the place to read
about it. One thing it does not mention is worth adding here: `FleetConfig` holds a single
`conveyor: ConveyorConfig` field, so even with the key spelled correctly the dataclass
could represent **one** belt where the file describes three. The typo hid a structural
mismatch behind it.

The process topology was written down three times too, and the three do not describe the
same factory. `fleet_config.yaml` routes every transfer through a belt. But
`legacy/robot_interface/config/robot_interface.yaml` has robot 1 place directly to robot 2
at `[0.35, 0.0, 0.15]` — arm-to-arm, no belt. And
`legacy/multi_robot_coordinator/config/pick_place_poses.yaml` gives joint-space poses that
carry identical values for all three arms — the same five joint angles for `home`,
`pick_approach`, `pick_grasp`, `place_approach` and `place_release` under `xarm1`, `xarm2`
and `xarm3` alike, which cannot be right for three arms standing in different places facing
different directions.

The break beam's topic has three names and the model can produce none of them.
`legacy/assembly_line_sensors/models/break_beam_sensor/model.sdf` hardcodes
`<namespace>station</namespace>`, so every instance publishes to `/station/break_beam` —
which is why `WORK_LOG.md` (2025-12-04) records "Fixed world file issues (sensor namespace
conflicts)". `legacy/assembly_line_sensors/config/sensor_topics.yaml` names them
`/station1/break_beam`, `/station2/…`, `/station3/…`; `fleet_config.yaml` names them
`/sensors/belt_1_end/break_beam`. Its detection threshold is written in `sensor_topics.yaml`
as `0.4`, and read by `coordinator_node.py` line 147 from somewhere else.

### Three coordination attempts, none of which finished

`legacy/README.md` describes "three mutually incompatible attempts at a multi-robot
architecture", and the packages bear that out: `multi_robot_coordinator` (central state
machine, `FollowJointTrajectory` actions, `Range` from break beams),
`fleet_manager` + `robot_interface` (config-driven spawn, per-robot node, peer-to-peer
handoff over `std_msgs/Bool` and `String`), and `digital_twin.launch.py` (delegate to the
vendor demo). None was removed when the next was begun, so the tree ends up offering three
answers to "how does a part get from one arm to the next" and no way to tell which is live.

The handoff never closed the loop. `handoff_coordinator.py` lines 141-146 creates
publishers on `/{robot}/handoff/execute`; a search on 2026-08-26 for that topic across
`legacy/` returns those two lines and nothing else. **There is no subscriber.** The
negotiation completed, the command went out, and no arm was listening.
[ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md) and
[ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md) carry the design conclusions;
[`../architecture/L4-orchestration.md`](../architecture/L4-orchestration.md) carries the
architecture.

Two smaller things in the same package are worth naming because they will bite again.
`robot_interface.yaml` has a `timing:` block — `pick_duration: 2.0`, `place_duration: 2.0`
— which is what a node does when it cannot tell whether a motion finished; see
[ADR-0006](../adr/0006-moveit2-motion-planning.md). And `handoff_coordinator.py` measures
its timeouts with `time.time()` (lines 51, 216, 258) — wall clock. The launch files that
bring up the arms set `use_sim_time: True` on them
(`legacy/fleet_manager/launch/multi_robot_test.launch.py` lines 89 and 229;
`three_robots.launch.py` on the state publishers and spawners), and
`legacy/robot_interface/launch/robot_interface.launch.py` sets it nowhere. So the component
timing the handoff and the components performing it were on two different clocks. That is
the mixed-time system [`../../CLAUDE.md`](../../CLAUDE.md) §10 warns about, and its output
is plausible and wrong rather than obviously broken.

### Nothing was tested, so nothing could be known

A survey of `legacy/` on 2026-08-26 — excluding the vendored `legacy/xarm_ros2/` — for
`test/` directories, `test_*` files and `*_test.py` files returned **none**. Seven
first-party `CMakeLists.txt` files carry the `ament_lint_auto` block from the package
template, and there is nothing for it to run.

This is the root of §5 rather than an item in it. Every other failure on this page —
the entry point that ran the vendor demo, the interfaces recorded as built, the topic with
no subscriber, the belt running at 1.5 mm/s, the config file nothing loaded — is the kind
of thing one test would have caught on the day it was introduced. See
[`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md) and
[`../../CLAUDE.md`](../../CLAUDE.md) §9.

## Cross-cutting decisions this tree produced

Recorded elsewhere, listed here so the connection is not lost when `legacy/` goes. Do not
restate their reasoning; follow the link.

| v1 experience | Decision |
|---|---|
| Built on Gazebo Classic, which is end-of-life — the ADR carries the date and its source | [ADR-0003](../adr/0003-gazebo-harmonic.md) |
| Unbuildable from a clean checkout, in two ways at once | [ADR-0008](../adr/0008-external-dependencies-via-vcstool.md) |
| No environment definition; the quick start in `PROJECT_CONTEXT.md` begins `cd ~/Desktop/Digital-Twin` | [ADR-0009](../adr/0009-docker-primary-environment.md) |
| Turkish and English mixed across the tree — `SCALABLE_ARCHITECTURE.md`'s headings, `digital_twin.launch.py`'s docstring, `PROJECT_CONTEXT.md`'s component list, and a file named `HIZLITEST.md` | [ADR-0015](../adr/0015-english-only.md) |
| Called itself a digital twin with no hardware interface at all | [ADR-0011](../adr/0011-twin-maturity-model-and-modes.md) |
| Pick and place were two-second timers | [ADR-0006](../adr/0006-moveit2-motion-planning.md) |
| Migrate or rebuild | [ADR-0001](../adr/0001-rebuild-rather-than-migrate.md) |

## What this page does not capture

Stated so that the deletion is made with the gaps visible.

- **The `gazebo_ros2_control` patch itself.** It is not in this repository and never was —
  `legacy/README.md` records the upstream commit and describes what the patch did, and that
  description is all that survives. It applies to Gazebo Classic and is of historical
  interest only.
- **The vendor meshes and the vendor stack.** Not lost: `xarm_ros2` is pinned by commit SHA
  in `external/cite.repos`, and `legacy/xarm_ros2/` is a copy of it. Deleting the copy
  removes nothing the manifest cannot restore.
- **The v1 world and model geometry.** Deliberately not carried forward. The layout in
  `model/` is `PROVISIONAL` and engineered; v1's coordinates were engineered too, and
  disagreed with themselves in the ways §5 sets out. Reusing them would import the
  disagreement.
- **Whether any of these failures reproduce.** Everything here is read from source at
  `d68838b`. The tree targets ROS 2 Humble and Gazebo Classic, neither of which this
  project's container provides, so nothing on this page was run and nothing on it should be
  cited as an observed run.
