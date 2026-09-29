# ADR-0022: Drive the gripper through `ros2_control`, not a separate action server

- **Status:** Accepted — the decision stands. Two supporting claims in this record were
  false and are corrected below; nothing that was decided is withdrawn. See the
  section "Correction — 2026-08-25: the 'known wart' was not harmless", immediately
  after this block.
- **Date:** 2026-08-24
- **Related:** ADR-0005, ADR-0006, ADR-0023, [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md)

## Correction — 2026-08-25: the "known wart" was not harmless

Two statements in this record are false as configured. They are marked where they stand
rather than deleted: the record of an inference that turned out wrong is the useful part.

**What was written.** The Context said the five finger joints are "ordinary URDF joints
carrying `<mimic>` tags, which `ros2_control` resolves natively", and the *Known wart* note
said the vendor's five Gazebo Classic mimic-plugin blocks are "harmless because the
`<mimic>` tags carry the behaviour".

**What is true.** Nothing carried the behaviour. The five finger joints were coupled by no
mechanism at all in simulation, from the day this record was written until the patch
described below is applied.

**Why neither mechanism resolved them.** Measured on 2026-08-25:

- **`ros2_control` cannot.** It resolves mimics declared *inside* the `<ros2_control>`
  block, not URDF `<mimic>` tags elsewhere in the description — and the vendor's gripper
  block declares exactly one joint. Verified against
  `xarm_description/urdf/gripper/xarm_gripper.ros2_control.xacro` at the SHA pinned in
  `external/cite.repos`: it contains a single `<joint name="${prefix}drive_joint">` and no
  other. `/opt/ros/jazzy/lib/libhardware_interface.so` carries the string
  `Mimic joint '{}' not found in <ros2_control> tag`, which is what it emits for a mimic it
  is asked to resolve and cannot find there.
- **Gazebo cannot either, and the description is not at fault.** `gz sdf -p` *does*
  correctly translate a URDF `<mimic multiplier="1" offset="0"/>` into a native SDF 1.11
  `<axis><mimic>` constraint carrying `<multiplier>`, `<offset>` and `<reference>` —
  verified on 2026-08-25 by converting a two-joint URDF in the container image and reading
  the output. The constraint is then dropped by the physics engine. dartsim is the default
  engine and the one this cell runs — `cite_generated/worlds/cell_a.sdf` loads
  `gz-sim-physics-system` with no `<engine>` override — and it does not implement
  `SetMimicConstraintFeature` in gz-physics 7. `nm -DC` finds **0** mimic symbols in
  `libgz-physics7-dartsim-plugin.so` against **285** in
  `libgz-physics7-bullet-featherstone-plugin.so`. `gz-sim` says so out loud:
  `src/systems/physics/Physics.cc` on the `gz-sim8` branch logs at `gzerr` "Attempting to
  create a mimic constraint for joint [...] but the chosen physics engine does not support
  mimic constraints, so no constraint will be created."
- **The Classic plugin fails to load, exactly as this record predicted** — 15 errors per
  run, five mimic joints on each of three arms. The five are five
  `mimic_joint_plugin_gazebo` invocations in
  `xarm_description/urdf/gripper/xarm_gripper_macro.xacro` at the pinned SHA.

**The measured consequence.** Across the whole gripper stroke the right finger moves
**1.5 mm**, and that is gravity sag rather than actuation: the right-hand chain is
unconstrained and free-hanging, so it does not even reach its own open position. **The
gripper never grasped anything.** Every lift observed during Phase 1.C came from the
attachment plugin of [ADR-0023](0023-simulated-grasping-via-attachment.md) instead — see
that record's own correction, which holds the detail.

**What survives, unchanged.** The decision. `position_controllers/GripperActionController`
on `drive_joint` was and remains the right interface, and `stalled` is real, reachable and
correctly reported when the drive joint is physically blocked — demonstrated directly on
2026-08-25. The controller was never the problem, and nothing in the Decision section is
withdrawn beyond the one sentence marked in it.

**The resolution**, chosen by measuring three candidates rather than by inference: declare
the five finger joints as mimics **inside** the vendor's `<ros2_control>` block, through a
patch file in `external/patches/` per
[ADR-0008](0008-external-dependencies-via-vcstool.md) — the same remedy this record already
named for the load noise, applied now for a far larger reason. `gz_ros2_control` 1.2.19
(the version in the container image) honours `HardwareInfo::mimic_joints`: `gz_system.cpp`
lines 841-867 run a per-mimic-joint proportional velocity servo, commanding
`velocity_sp = -(position_mimic - position_mimicked * multiplier) * update_rate` on each
mimic joint every update. P7 applies to this paragraph: it records the decision, and the
patch is what makes it true.

Two alternatives were measured and rejected:

- **A first-party Harmonic mimic plugin.** Mechanically identical to the servo above,
  about **35 % worse real-time factor** during contact, and roughly **120 lines** of ours
  to maintain for as long as the project exists. It buys nothing the upstream servo does
  not already give.
- **Switching the physics engine to bullet-featherstone.** It has the mimic feature, and
  it failed outright: the pads closed, but contact drove the joint *backwards* past its
  command, the arm was displaced **10-43 mm**, and the action never returned a result. A
  larger change than the defect, and it did not work.

**Upstream limitation, recorded so it is not rediscovered.** That servo uses `multiplier`
and ignores the mimic `offset` term — `gz_system.cpp` line 853 computes the position error
from the multiplier alone, and `offset` appears only in a configuration-time log line. All
five of our mimic joints declare `offset="0"`, verified in
`xarm_description/urdf/gripper/xarm_gripper.urdf.xacro` at the pinned SHA, so it changes
nothing today. Given what this record is being corrected for: **"harmless today" is a claim
with an expiry date, not a dismissal.** It expires the moment an end-effector with a
non-zero mimic offset is described, and whoever describes one owns this.

**How the error survived, which is the part worth carrying forward.** "`ros2_control`
resolves `<mimic>` natively" is true of mimics declared inside the `<ros2_control>` block.
It was generalised to the URDF's `<mimic>` tags and written down as a settled fact without
a test that any finger moved. The "harmless" label then did active harm: it pre-authorised
the only symptom the system emitted — fifteen plugin load errors at every start-up — as
known noise, so the single available signal had already been explained away in writing.
Nothing asserted on a finger's position until 2026-08-25.

## Context

[`L2-control-and-hal.md`](../architecture/L2-control-and-hal.md) leaves an open question:

> **Gripper control interface.** Whether the gripper is a `ros2_control` controller or a
> separate action server. Affects how L3's `Grasp` skill is shaped.

It has to be answered before the `Pick` skill is written in Phase 1.C, because the answer
determines what `Pick` commands and therefore what its interface looks like.

What the vendor stack actually provides was verified on 2026-08-24 by expanding
`xarm_description`'s `xarm_device` macro with `add_gripper:=true` and
`ros2_control_plugin:=gz_ros2_control/GazeboSimSystem`. The expansion emits a **second,
separate `<ros2_control>` block** for the gripper, carrying one actuated joint —
`<prefix>drive_joint` — with `position` and `velocity` command and state interfaces. The
five remaining finger joints are ordinary URDF joints carrying `<mimic joint="drive_joint">`
tags, which `ros2_control` resolves natively.
**[Corrected 2026-08-25 — see the Correction section above.]**

So the gripper is already presented to us as a `ros2_control` hardware component with one
degree of freedom, in both the simulated and the vendor-hardware configurations. That is
the fact that makes this decision easy, and it was not knowable from the documentation
alone.

The binding constraint is P2: whatever `Pick` commands in simulation must be the identical
call on hardware, with only the loaded plugin differing.

## Options considered

### Option A — A separate `cite_hardware` gripper action server
A node that owns the gripper, talks to the vendor gripper API directly on hardware, and to
Gazebo in simulation.

Rejected, and it is worth being precise about why, because it is the option that looks
simpler. It creates a **second command path to an actuator that does not traverse the
`ros2_control` boundary.** [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)
requires that no command reaches a hardware interface without passing the safety layer, and
the safety layer's enforcement point is at that boundary. A gripper is an actuator that can
crush a hand. Giving it its own path means either duplicating the safety layer or leaving
it unguarded, and the second is what would actually happen.

### Option B — `JointTrajectoryController` on `drive_joint`
Symmetrical with the arm: same controller type, same action type. Rejected as the primary
interface: a trajectory is the wrong shape for a gripper. A grasp is "close to this width
with at most this effort, and tell me if you stalled" — which is a state a trajectory
controller cannot report, because stalling against an object is exactly what makes a
trajectory fail to track.

### Option C — `GripperActionController` on `drive_joint`
`position_controllers/GripperActionController` from `ros2_controllers`, exposing
`control_msgs/action/GripperCommand`: a target position and a maximum effort, returning
reached position, current effort, and a `stalled` flag. It is also the interface MoveIt
expects for a gripper. Chosen.

## Decision

The gripper is a `ros2_control` controller. Each arm instance generates a
`<asset_id>_gripper_controller` of type `position_controllers/GripperActionController`
bound to `<asset_id>_drive_joint`, alongside its `<asset_id>_joint_trajectory_controller`.
Both are generated from the L0 model, so both names are identical in simulation and on
hardware.

L3's `Grasp` skill is an action server that commands `GripperCommand` and nothing else. It
holds the grasp *policy* — target width, effort limit, what a stall means for this
work-piece — and translates it into one controller goal. It never touches a vendor API and
never talks to the simulator.

The mimic-joint coupling of the remaining five finger joints is left to the URDF `<mimic>`
tags that `ros2_control` already resolves.
**[Corrected 2026-08-25 — see the Correction section above.]** It does not resolve them;
the coupling is declared inside the `<ros2_control>` block instead. What survives is the
part that was the actual decision: we add no coupling *mechanism* of our own.

**Known wart, recorded rather than hidden:** the vendor expansion also emits five
`<gazebo><plugin filename="libgazebo_mimic_joint_plugin.so">` blocks. That is a Gazebo
Classic plugin and will not load under Harmonic; the upstream README says as much. It is
harmless because the `<mimic>` tags carry the behaviour, but it produces a load error per
gripper at start-up.
**[Corrected 2026-08-25 — see the Correction section above.]** It was not harmless:
nothing carried the behaviour.
If that noise ever obscures a real fault, the fix is a patch file in
`external/patches/` per [ADR-0008](0008-external-dependencies-via-vcstool.md) — never an
edit inside the checked-out dependency.

## Consequences

### What this gets us
- One command path to every actuator, through the `ros2_control` boundary, so the safety
  layer has exactly one place to stand.
- P2 holds for the gripper for free: the controller name, the action name and the joint
  name are generated from L0 and identical on both paths.
- `stalled` and `reached_goal` come back from the controller, so `Grasp` can report a
  structured `result_code` instead of guessing whether it holds anything.
- MoveIt's gripper integration works without adaptation.

### What this costs us
- **The Phase 2 hardware path now has a requirement.** The vendor's real gripper must be
  exposed as a `ros2_control` component with a `drive_joint`. `xarm_ros2` appears to do
  this, but it has not been verified against physical hardware, and if it turns out the
  vendor drives the gripper only through its own service API, we owe a hardware interface
  wrapper. That work is created by this decision.
- Grasp force control is limited to what `GripperCommand`'s `max_effort` expresses. Anything
  richer — force profiles, slip detection — needs a different controller later.
- A stall is reported, not interpreted. Deciding whether a stall means "holding the object"
  or "closed on nothing" is `Grasp`'s job and needs a real width check, which is a genuine
  piece of Phase 1.C work rather than a free consequence.
- **`GripperCommand.position` is in the joint's own units, not metres.** The controller
  passes it straight through, and this gripper's `drive_joint` is *revolute*: 0 rad fully
  open, 0.85 rad fully closed. A skill sending a width in metres would therefore command an
  angle — `0.085` reads as nearly-open when it was meant as 85 mm — and nothing anywhere
  reports it, because 0.085 is a perfectly valid joint position. Found on 2026-08-24, with
  the visible symptom being a gripper that closed on nothing and a `Pick` that failed at the
  stall check.
  The `Grasp` action stays in task space, as this ADR intends; the mapping from a width to
  the joint's units is declared in the L0 end-effector type and applied in the skill server.
  It is linear across the stroke, which is an approximation for a linkage gripper — but a
  stated approximation with its numbers in the model, rather than a unit confusion buried in
  code.

### What we will have to revisit
When a non-parallel end-effector arrives — the vacuum gripper the charter names as
pluggable — `GripperCommand` stops fitting, since suction has no position. At that point
the end-effector type in L0 must select the controller type and the `Grasp` skill must
dispatch on capability rather than assume a width. Design `Grasp`'s interface now so that
this is an addition rather than a rewrite.
