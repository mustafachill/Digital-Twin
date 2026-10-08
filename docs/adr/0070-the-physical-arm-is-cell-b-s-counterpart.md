# ADR-0070: The physical xArm 5 is `cell_b`'s counterpart

- **Status:** Accepted 2026-10-05 by the project owner (amended 2026-10-05, 2026-10-06 (owner decisions: opt-in from .env; registration order; physical grip and physical arm arrival executed, not judged), 2026-10-08 (owner decision: initialize as in Studio and home before the program): see "Amendment — what was built" at the end)
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

## Amendment — what was built (2026-10-05)

The decision stands. Review found that several items, as first written, were narrower than
what the decisions require, or wrong about the vendor. This section records what was built,
so the record says what the tree does. The text above is kept as written.

- **Owner decisions taken after the record was written.** ADR-0070 was accepted, and with it
  CLAUDE.md §2's binding rule now names `physical-plant-on-paired-zone`, not ADR-0048
  clause 1. On the P2 escalation (an adapter, not a plugin, serves the track and gripper
  names), the owner chose to keep the adapters ("no over-engineering; keep the working
  system"), and CLAUDE.md P2 now says that only what serves the names differs.
- **Item 1: the sides differ in more than the plugin line.** Every difference is named and
  asserted by the side-parity tests (`tools/tests/test_generate.py`,
  `tools/tests/test_per_side_artifacts.py`). The counterpart's description also differs in:
  - the `robot_ip` argument;
  - the collision URI scheme;
  - the side's own `<parameters>` path;
  - no track `<ros2_control>` block and no Gazebo plugin block.

  Its controller configuration also differs: it has no gripper controller and no track
  controller, and it gains a vendor-driver block that enables exactly the services the side's
  nodes call. The plan names the counterpart's own files, controllers and vendor names.
- **Item 2: the address is an environment reference of a declared kind**
  (`{env: CITE_XARM_IP, kind: ip_address}`). A literal value on a physical backend is a
  validator error. `hardware.launch.py` resolves the reference and checks its kind, and never
  logs the value. The hardware opt-in comes from the shell only, never from `.env`.
  *2026-10-06, owner decision:* this reverses the shell-only rule. For `./scripts/program`,
  `./scripts/sim --pair` and `./scripts/enter hardware` the opt-in is read shell > repository-root
  `.env` > `0`, resolved once by `resolve_hardware_opt_in` in `scripts/_lib.sh` and passed to
  every container command explicitly. `.env` is read fail closed: only one well-formed
  `CITE_ALLOW_HARDWARE=1` line arms, and any other line naming the key resolves to `0` with a
  warning naming its line number. Test, scenario, lint, build and CI never read it from `.env`
  — except when run inside `./scripts/enter hardware`, which carries the resolved value.
- **Item 3: the track adapter commands bounded segments, not the final point.** The command
  carries its start and target. The vendor speed is never above the commanded speed (rounded
  down to the vendor's 1 mm/s resolution). Moves are
  sent in segments of `segment_s` (declared in L0), so a lost stop limits the overrun. A
  program cancel is a hold at each side's own position, which the adapter turns into a stop.
  The program also confirms the counterpart's carriage arrived, through the boundary's
  `TrackArrived` service.
- **Item 4: the vendor gripper action is in drive-joint units (0 to 0.85) and is always
  served.** Its state service reports pulses. The relay refuses a new goal while a vendor goal
  runs, because vendor cancel does nothing. The vendor action is reachable on the physical
  domain without the relay's gate; this is a residual, stated in `cite_hardware`'s README.
- **Item 5: the deadman holds the arm through the vendor's state.** It asserts STOP on every
  tick unless the side is HEALTHY. It enables the arm only on the AWAITING to HEALTHY edge,
  and that enable is atomic with respect to a trip. It trips if the vendor driver disappears
  or restarts. When tripped, it latches and re-sends every stop on every tick. It also stops
  the arm on SIGINT/SIGTERM. The heartbeat carries its boundary's id, and its period and every
  deadman timing value are declared once in L0, with validator relations between them.
  **The 0.5 s timeout is not backed by a measurement.** The heartbeat stays on this host; the
  Wi-Fi probe in *Context* says nothing about it.
- **Item 6: the hardware launch runs an event-driven sequence:**
  1. refuse unless the side is physical and opted in, and resolve the address;
  2. start the deadman;
  3. start the vendor controller manager, with the vendor's absolute
     `/controller_manager/*` service names remapped to the side's own (L0-declared);
  4. start the adapters;
  5. pass a hold gate that requires an acknowledged STOP;
  6. start the controllers, MoveIt and the skills, then print the readiness token.

  The token means held, not enabled. Any of these processes exiting brings the whole side
  down, and nothing respawns. `simulation.launch.py` refuses a physical side whatever the
  opt-in says. The boundary refuses VALIDATED until the deadman is HEALTHY with the arm
  enabled and the side's state is fresh, and it re-checks this whenever VALIDATED is asserted
  again.
- **Item 7: on a physical side, `./scripts/program` requires an explicit `--speed-scale`,**
  checked before bring-up. Before each cycle it asks the operator to place the part. Between
  cycles it puts the twin in SIM; the arm stays enabled and still, and the prompt says so.
- **What remains unverified without the arm** is listed in
  [`../open-work.md`](../open-work.md) and in `cite_hardware`'s README. In particular: the
  firmware's behaviour when its TCP stream ends, whether segments blend or stutter, and what
  the hardware E-stop cuts. The hardware E-stop is the only stop independent of these
  processes.
- **Later on 2026-10-05, after the pre-first-motion audit:**
  - **Track step.** Through the twin, a track step asks `TrackArrived` first. It fails ("home
    it") when the plant's carriage is at the target and another side's is not, so a physical
    carriage is never left unchecked because the plant was already there.
  - **Carriage agreement.** A mode that commands a physical side is refused, finally and not
    as "not ready", while a physical carriage heard fresh stands outside the track's goal
    tolerance of the plant's; the program checks this before the operator prompt, after waiting
    for the carriage to be heard. A carriage not heard fresh is part of the waited-on readiness.
  - **Speed write.** The track adapter writes the speed explicitly (`set_linear_motor_speed`,
    now on the vendor allow-list) before a move whose speed differs from the last one the
    vendor acknowledged, and sends the move only on `ret == 0`. The vendor SDK caches the
    speed and ignores the result of its own write.
  - **Speed floor.** A move slower than the slowest the adapter can carry out is refused, never
    sped up. The program derives the matching minimum `--speed-scale` from the adapter's
    generated parameters and refuses a lower one before bring-up.
  - **Hold order.** A move accepted before a hold is never sent after it.
  - **The module enforces the rules itself.** `python3 -m cite_bringup.program` applies the
    explicit-speed-scale rule. It asks the operator's go-ahead only once it has read the twin
    in SIM, and a failed return to SIM at the end of a run fails the run. `./scripts/program`
    hands it the terminal and is the supported entry point.
- **2026-10-06, owner decision: registration order.** Registration
  ([`../operations/calibration-and-registration.md`](../operations/calibration-and-registration.md))
  is **not** required before the program's joint-space motion on the physical side, run
  supervised with the hardware E-stop tested and in hand. It **is** required before any
  Cartesian motion on the physical side, any claim about the physical side that depends on the
  planning scene, and any divergence number.
- **2026-10-06, owner decision: the physical side's grip is executed, not judged, as the real
  program does.** A close expecting a part on the physical side succeeds once the gripper command
  completes; ADR-0052's grasp-evidence predicate is still evaluated, reported in `holding` and
  logged there, but does not fail the step. A relay refusal (deadman gate included), vendor
  abort or timeout still fails it. The plant keeps its judgement unchanged. The skill server's
  `gripper_judges_grasp` carries it, from the plan's per-side hardware fact
  (`cite_bringup.side_launch.skill_parameters`); `cite_skills::grasp_verdict` decides. Prompted by
  the first physical run, whose step 11 failed with the real box held (commanded 60.9 mm,
  reached 62.8 mm, `stalled=false`).
- **2026-10-06, owner decision: the physical side's arm arrival is executed, not judged, as the
  real program does.** On the physical side the xArm's own controller executes the motion; an
  execution that ADR-0037's classification finds at the trajectory's last point, with the
  `joint_trajectory_controller` not reporting the goal met, succeeds there and the classification
  is logged as information. Every other outcome still fails on every side: an arm at the start,
  part-way (a path-tolerance abort included) or unreadable, a MoveIt timeout, a cancel or
  preemption, a planning failure, a deadman refusal, a controller not active. The plant keeps its
  judgement unchanged. No tolerance, `goal_time` or L0 value changes, so CLAUDE.md §2's "never
  widen an execution tolerance" is untouched: the AT_GOAL test still uses the arm's own goal
  tolerance, and what is withdrawn is only the simulator-tuned controller's verdict on the
  physical arm. The grip's parameter is generalised to one, `side_judges_outcome` (formerly
  `gripper_judges_grasp`), from the same plan fact; `cite_skills::execution_failure_stands`
  decides. Prompted by the first physical run's step 1 ("move to zero"), failed with "the arm
  reached the trajectory's last point, but the controller did not report the goal met (MoveIt
  error code -4)".
- **2026-10-08, owner decision: the physical arm is initialized as the operator does in UFACTORY
  Studio, and both arms are brought home, before the program.** The second supervised paired run
  stopped at its first track move on vendor code 82 (`LINEAR_MOTOR_NOT_INIT`): the track had not
  found its zero, and nothing in this repository enabled or homed it, which the operator does by
  hand in Studio before running the program. A lifecycle node on the physical side,
  `cite_hardware`'s initializer, serves `cite_interfaces/srv/InitializeAsset` under
  `/cite/<zone>/<asset>/initialize`: it enables the track motor and the gripper and, only where
  `get_linear_motor_on_zero` reads 0, homes the track (sent once, behind the deadman's gate, and
  followed by a stop when it is refused or does not finish within L0's
  `vendor_axis.initialize_deadline_s`). Four vendor services join the allow-list for it
  (`set_linear_motor_enable`, `set_gripper_enable`, `get_linear_motor_on_zero`,
  `set_linear_motor_back_origin`); no `clean_error`. `cite_bringup.program.home` calls it on
  each physical side and then sends the program's own first arm move and first track move through
  the twin to both sides; `./scripts/program` runs both before its first cycle, and
  `./scripts/home` runs them against a pair already up. Not yet run on the physical arm.
