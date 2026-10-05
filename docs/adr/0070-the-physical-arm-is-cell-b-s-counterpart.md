# ADR-0070: The physical xArm 5 is `cell_b`'s counterpart

- **Status:** Proposed
- **Date:** 2026-10-05
- **Deciders:** Project owner
- **Related:** lifts [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) clause 1
  by building its clause 2; keeps [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)
  Decision 3; builds the hardware path [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md)
  decision 5 left unimplemented; [ADR-0053](0053-index-hardware-params-by-backend.md),
  [ADR-0054](0054-key-the-hardware-opt-in-on-a-declared-fact.md),
  [ADR-0057](0057-start-the-twin-boundary-from-the-pair-supervisor.md); charter §8 Phase 2.B;
  [`../open-work.md`](../open-work.md) #38, #65, #74

## Context

Phase 2.B replaces the virtual counterpart of the paired zone `cell_b` with the physical
xArm 5 on its UFACTORY linear track, so that one command drives the real arm and the Gazebo
arm together, both running the real robot's program. The project owner decided on 2026-10-05
that the physical arm takes the **counterpart** slot and the plant stays simulated. That is
the encoding ADR-0041 Decision 3 already names (`counterpart_backend: real`), and
`physical-plant-on-paired-zone` stays as it is.

Facts read in this checkout (base `2701729`):

- `divergent-counterpart-backend` (`tools/cite_tools/validate/referential.py`) refuses any
  counterpart whose backend differs from the plant's, because the generator hands the
  counterpart the plant's description and controller configuration (open-work #38). ADR-0048
  clause 2 fixes the shape that lifts it and is not built.
- `track-backend-differs-from-its-arm` requires the track to share the arm's
  `(backend, counterpart_backend)`. `ufactory_linear_motor` declares only `sim`.
- The vendor hardware plugin `uf_robot_hardware/UFRobotSystemHardware` (pinned
  `xarm_ros2`) exports joint1..5 only. It embeds the vendor driver, which serves the
  linear track **only** as `xarm_api` services (`set_linear_motor_pos`,
  `get_linear_motor_pos`, `set_linear_motor_stop`, …; each off by default in
  `xarm_api/config/xarm_params.yaml`). It serves the gripper **only** as
  `control_msgs/GripperCommand` at `<prefix>xarm_gripper/gripper_action`, in the vendor's
  units, and emits no gripper `ros2_control` block for this plugin. Those are the same
  calls the program's `set_line_track` and `gripper_set` blocks make on the real controller.
- The robot's address must not be committed (owner decision, 2026-10-05). It lives in the
  gitignored `.env`.
- Nothing stops dispatched motion if the twin boundary dies (open-work #74). With a physical
  side that is a safety gap, not a backlog item.
- The arm's controller is reached over the lab's Wi-Fi. A probe on 2026-10-05 (not a
  campaign) put the 99th percentile round trip at a few controller periods of the 150 Hz
  update rate.

## Options considered

### Option A: the physical arm as the plant
This is what the phase item literally says. It reverses ADR-0041 Decision 3, the mode routing
in `cite_twin/routing.py` and the hardware gate, and it makes the side CI drives physical.
The owner chose against it.

### Option B: the physical arm as the counterpart, with thin real-side adapters (chosen)
The generator emits per-side artifacts exactly as ADR-0048 clause 2 fixed. The real side
presents the same names the simulated side presents, and translates them to the vendor calls
above.

## Decision

**`picker` and `picker_track` declare `counterpart_backend: real`. The generator emits
per-side artifacts as ADR-0048 clause 2 fixed, and `divergent-counterpart-backend` is
deleted. The real side presents names byte-identical to the simulated side's, through the
vendor plugin plus two adapters and a deadman.**

1. **Per-side artifacts (ADR-0048 clause 2, as written).** Only the description and the
   controller configuration become per-side, and the side goes in the file path, never in a
   name. A side whose backend equals the plant's gets no second artifact. A test asserts that
   the counterpart differs from the plant only on `ros2_control_plugin` lines (description)
   and `use_sim_time` (controllers), plus what item 4 removes. The three generator sites of
   open-work #38 read the side's own backend. Open-work #65 closes with a test that the
   declared plugin is the plugin each side's description loads.
2. **The address is a reference, not a value.** `picker.hardware.params.real.robot_ip` holds
   an environment reference (`{env: CITE_XARM_IP}`). The generated plan carries the
   reference. `cite_bringup` resolves it at launch, and an unset variable is a refusal. No
   address appears in L0, in a generated artifact or in a log line written to the tree.
3. **The track gets a `real` backend** (`commands_physical_hardware: true`). On the real side
   a track adapter subscribes the same `command_topic` the simulated
   `picker_track_trajectory_controller` serves. It commands the final point through
   `set_linear_motor_pos` and publishes `picker_track_joint` position from
   `get_linear_motor_pos` onto the side's joint states. The unit conversion (vendor
   millimetres to metres) is the only arithmetic it does.
4. **The gripper is relayed, not modelled.** On the real side a relay serves
   `GripperCommand` at the same `gripper_action` name the plan names. It maps the drive-joint
   position between `gripper_open_position` and `gripper_closed_position` onto the vendor's
   range declared in the gripper type, forwards to the vendor action and maps the result
   back. The real side runs no `picker_gripper_controller`. Its controller list differs from
   the simulated side's by exactly that entry, and item 1's test allows exactly that.
5. **A deadman before any motion.** The twin boundary publishes a heartbeat. On the real side
   a watchdog cancels active goals and calls the vendor stop (`set_state` stop,
   `set_linear_motor_stop`) when the heartbeat is absent past a timeout. The timeout is
   declared in L0 and is above the link's observed spikes. It is tested against a fake
   boundary. This closes open-work #74 for the physical side.
6. **A side launch per backend.** `pair.py` selects the launch from the side's backend. The
   real side's launch starts `ros2_control_node` with the vendor plugin, the adapters and the
   watchdog, and no Gazebo. It prints the same readiness token. `CITE_ALLOW_HARDWARE=1` stays
   the only door (ADR-0054), and the container now receives it and `CITE_XARM_IP`.
7. **Gazebo-only program steps are skipped on a physical side, and say so.**
   `scripts/program` spawns no box and reads no `ModelPoses` there; a person places the part.
   The belt stays untwinned (ADR-0067).

## Consequences

### What this gets us
The first run in this project where one command moves a physical arm and its twin together,
and the hardware path of every asset the real program touches. The P2 claim becomes a diff
that a test takes. Open-work #38, #65 and #74 (physical side) close.

### What this costs us
- Two adapters of vendor-specific code in L2, which a different robot type would replace
  (P9 holds: they sit behind the same names).
- The track's state comes from service polling, not from a `ros2_control` state interface,
  so its rate and age are the adapter's, not the controller manager's.
- On a confirmed grasp failure, the stall question ADR-0063 left unestablished on the SDK
  stays unestablished. The relay reports what the vendor reports.
- The real side runs over Wi-Fi by the owner's choice. A late servo packet becomes a stutter,
  not an unsafe motion, but nothing here bounds it.

### What we will have to revisit
- If the first motion over Wi-Fi stutters, move to a wired link before tuning anything.
  Widening a tolerance is never the answer (CLAUDE.md §2).
- If a second physical asset arrives, check whether its vendor exposes the track or gripper
  through `ros2_control`. If it does, the adapters are deleted, not generalised.
