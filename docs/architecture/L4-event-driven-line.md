# L4 — The event-driven line (parked)

- **Status:** `DESIGNED` — **the implementation was removed from the main tree** by
  [ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) on
  2026-10-01 and runs, frozen, as `projects/01-three-arm-event-driven-line` (its `./run`
  and `./scripts/scenario continuous_line`, both run from that folder, whose README is the
  runbook; [ADR-0068](../adr/0068-keep-proven-milestones-as-frozen-snapshots.md)). L4 stays in the
  target architecture (charter §7). **Every "built", "tested" or "in CI" below, and every
  file path under `cite_orchestration`, describes the tree before ADR-0069**; nothing in the
  main tree today builds, tests or runs any of it.
- **Status before 2026-10-01, kept as the design record:** `BUILT — parked`.
  **Parked** means: kept at its current paths, still built by `./scripts/build`, still tested
  by `./scripts/test` and CI, and no longer the way the cell is meant to be run. The cell is
  moving to a fixed-sequence program; this structure is kept for a future joystick or teleop
  input. The snapshot is the git tag `event-driven-line-v1` (commit `b5a0bc9`).
  **Evidence:** `./scripts/scenario continuous_line` starts the cell with `line:=true` and
  asserts that work-pieces travel from the pick area to accumulation. It is the only
  end-to-end evidence for the line, and in CI it runs as an **advisory** step
  (`continue-on-error: true` in `.github/workflows/ci.yml`). `./scripts/scenario bringup`
  (blocking) covers the cell the line runs on and the `MoveTo(home)` path it uses, but it does
  not start the line. `cite_orchestration`'s own tests (`test_line_logic`, `test_line_nodes`,
  `test_conveyor_index`, `test_indexed_belts`, `test_recovery_ordering`, `test_station_reset`
  and others) use fake arms, so they prove sequence, ownership and the stop, and not motion.
  **How strong that evidence is lives in [CLAUDE.md §2](../../CLAUDE.md)** (the
  `continuous_line` and `bringup` bullets and the separate `cell_b` CI record). Read it there;
  the counts are not copied here. Nothing automated runs the **paired** line that
  `./scripts/demo` shows.
- **Related:** [L4](L4-orchestration.md), [L3](L3-capabilities.md),
  [L5](L5-twin-synchronization.md), [ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md),
  [ADR-0024](../adr/0024-handoff-split-between-l3-and-l4.md),
  [ADR-0027](../adr/0027-pilz-planning-pipeline.md),
  [ADR-0032](../adr/0032-index-the-belt.md),
  [ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md),
  [ADR-0037](../adr/0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0038](../adr/0038-stop-the-line-without-ending-the-process.md),
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md),
  [ADR-0057](../adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md),
  [ADR-0059](../adr/0059-pair-cell-b-and-leave-cell-a-single.md),
  [ADR-0060](../adr/0060-take-the-ik-solution-nearest-the-arm.md),
  [ADR-0065](../adr/0065-the-cell-says-what-it-holds.md)

Everything below was read from source at `event-driven-line-v1`. It names files and symbols
and avoids line numbers, which go stale.

## 1. Summary

In the event-driven line, a work-piece's arrival is what starts the work. A Gazebo break
beam reports a level. The bridge carries that level into ROS. The L3 detection server turns
each change of level into a typed `DetectionEvent`. The L4 `line_orchestrator` reacts to
that event. It builds one behaviour-tree subtree per station from the L0 topology, and each
subtree waits on its station's trigger and then calls L3 skills as actions: `Detect`,
`Pick`, `Place` and `MoveTo(home)`. L4 also owns the belt setpoint. The whole line is
controlled from `/cite/line/*`, and a fault branch stops every belt and waits for an
operator reset. Nothing in the chain sleeps, and no step branches on being in simulation.

```
 Gazebo world (generated: worlds/cell_b.sdf)
   cite_simulation::BreakBeam ──gz.msgs.Boolean──► /cite/cell_b/infeed_beam/detection   (gz side)
                                                          │ ros_gz_bridge parameter_bridge
                                                          ▼  remapped in ROS to
                                          /cite/cell_b/infeed_beam/detection_level  (std_msgs/Bool)
 L3 cite_skills detection_server  (ns /cite/cell_b/detection)
   BeamEdgeDetector::observe ── Edge ──► DetectionEvent on /cite/cell_b/infeed_beam/detection
   action server  /cite/cell_b/detection/detect  (Detect)                │
                                                                         │ (two subscribers)
 L4 cite_orchestration line_orchestrator  (ns /cite/line)                ▼
   TopologyWait ◄── /cite/line/topology (LineTopology, latched; cite_facility topology_server)
   plan_line ─► LinePlan ─► line_tree_xml ─► root Fallback{ Parallel(stations), fault Sequence }
   per station: trees/line_station.xml
     AwaitTrigger (TriggerWatch) ─► DetectAt ─► TakeCustody ─► PickAt ─► … ─► PlaceAt
       ─► CompleteHandoff ─► ResumeBelt ─► MoveToHome
   ConveyorIndex: run_all() at start; stop(belt) on a trigger edge; re-send on subscriber match
   LineMaintenance ─► LineState on /cite/line/state
                │ actions (one goal at a time per arm)
                ▼
 L3 skill_server  (ns /cite/cell_b/picker)
   move_to / pick / place / grasp / transfer ─► MoveIt (Pilz PTP, OMPL fallback)
   ─► picker_joint_trajectory_controller, picker_gripper_controller
   RobotState on /cite/cell_b/picker/state ─► grasp_hold_bridge ─► GraspHold plugin (sim only)
 L4 ConveyorIndex ─► /cite/cell_b/transfer_belt/command (std_msgs/Float64) ─► bridge
   ─► cite_simulation::Conveyor
```

## 2. The chain, end to end

### 2.1 Sensor to ROS

- **Beam.** `cite_simulation::BreakBeam` (`cite_simulation/src/break_beam.cpp`) is declared
  once per L0 `break_beam` instance in the generated `worlds/cell_b.sdf`. It publishes a level
  on its `<state_topic>` over Gazebo transport, for example `/cite/cell_b/infeed_beam/detection`.
- **Bridge.** In `cite_bringup/launch/simulation.launch.py`, `_bridge` starts
  `ros_gz_bridge`'s `parameter_bridge`, and `_bridge_topics` builds its arguments from the
  plan. Each sensor is bridged GZ→ROS as `gz.msgs.Boolean` → `std_msgs/msg/Bool` and remapped
  from its `detection_topic` to its `level_topic`. For `cell_b` these are
  `/cite/cell_b/{infeed,outfeed}_beam/detection_level`. The remapping keeps the raw level off
  the name that carries typed events. Each conveyor is bridged ROS→GZ on `command_topic`
  (`Float64` → `gz.msgs.Double`) and GZ→ROS on `state_topic`. The bridge carries the side's
  `GZ_PARTITION`.

### 2.2 L3 detection: level to event

- `_detection` starts one `cite_skills` `detection_server` per zone, in the plan's
  `detection.namespace` (`/cite/cell_b/detection`). `_detection_parameters` passes each
  sensor's `state_topic` (the level), `event_topic` (the detection topic) and `frame_id`.
- `cite_skills/src/detection_server.cpp` (`DetectionServer`) subscribes to each level on the
  SENSOR profile and folds every sample through `cite_skills::BeamEdgeDetector::observe`
  (`include/cite_skills/detection.hpp`). A sample is reported as `None` (the level is
  unchanged, so nothing is published), `Initial` (the first sample, published with
  `state == previous_state`) or `Edge`. It publishes a `DetectionEvent` on the EVENT profile.
- It also serves the `Detect` action at `/cite/cell_b/detection/detect`. With break beams
  only, the pose it returns is explicitly **unobserved**. `PickAt` refuses an unobserved pose
  through `cite_skills::pose_is_observed` and picks at the station's L0 frame instead. That
  is the normal path here, not a fallback (see the comment above `DetectAt` in
  `trees/line_station.xml`).

### 2.3 L4: topology to tree

- **Topology.** `cite_facility/topology_server.py` (`TopologyServer`, a lifecycle node)
  publishes `LineTopology` once, on activate, on `LineTopology.TOPIC` = `/cite/line/topology`
  with the LATCHED profile. `line_orchestrator.cpp`'s `TopologyWait` subscribes with
  `cite::qos::latched()` and waits up to `topology_deadline_s` (30 s). It refuses a topology
  whose `zone` does not match its own `zone` parameter.
- **Plan.** `cite_orchestration::plan_line` (`line_plan.hpp`) turns the topology into a
  `LinePlan`: `stations` (only those with a robot actor), `sinks`, `resources` and
  `refusals`. Any refusal stops the process before anything moves. A station's
  `inbound_via_asset_id` is the `via` of its inbound edge. `main` adds one more refusal: a
  belt that is indexed but has no declared drive.
- **Context.** `main` fills one `LineContext` (`line_nodes.hpp`) for the whole line:
  `WorkpieceRegistry`, `HandoffLedger`, `ResourceArbiter`, `TriggerWatch`, `ConveyorIndex`,
  the `StationRuntime` map, `LineFault`, `handoff_timeout` and `retry_budget`. There is one
  copy of each, because ADR-0024 puts ownership in one place.
- **Root tree.** `cite_orchestration::line_tree_xml` (`line_tree.hpp`) generates the root:

  ```
  Fallback "line"
    Parallel "stations" (success_count=-1, failure_count=1)
      SubTree LineStation × N   (all names passed as static remaps from the plan)
    Sequence   OnFault → StopAll → AwaitReset → AwaitReArm
  ```

  The station subtree is a file written by hand; the root is generated from the plan.
- **Station subtree** (`trees/line_station.xml`, `LineStation`), `Repeat` forever over a
  `Fallback`:
  - `nominal`: `Parallel{AwaitTrigger, AcceptOffers}` → `SetStationState(2)` → `ClaimReach` →
    `DetectAt` → `TakeCustody` → `PickAt` → `ReleaseClaim(inbound_buffer)` →
    `ClaimBufferSlot` → `OfferHandoff` → `AwaitHandoffConfirmed` → `PlaceAt` →
    `CompleteHandoff` → `ResumeBelt` → `ReleaseClaim` ×2 → `MoveToHome` →
    `SetStationState(0)`.
  - `recover`: `RecoverFromFailure` **first** (ADR-0037: classify before any motion) →
    `ReleaseStationClaims` → `MoveToHome`. An `ESCALATE` or `STOP_LINE` answer fails the
    subtree, which fails the root `Parallel`, and the fault branch runs.
- **Leaves.** The skill leaves (`MoveToHome`, `PickAt`, `PlaceAt`, `DetectAt`, `TransferTo`,
  all `SkillNode<Action>`) are in `skill_nodes.hpp`. The protocol leaves (`AwaitTrigger`,
  `AcceptOffers`, `TakeCustody`, `ClaimReach`, `ClaimBufferSlot`, `ReleaseClaim`,
  `ReleaseStationClaims`, `OfferHandoff`, `AwaitHandoffConfirmed`, `CompleteHandoff`,
  `ResumeBelt`, `SetStationState`, `RecoverFromFailure`) are in `line_nodes.hpp`. The fault
  leaves (`OnFault`, `StopAll`, `AwaitReset`, `AwaitReArm`) are in `line_fault.hpp`.
  `AwaitTrigger` consumes edges through `TriggerWatch`, which subscribes to the station's
  `DetectionEvent` topic on the EVENT profile.
- **Sinks.** A sink has no actor and no subtree. `LineMaintenance::confirm_for_sinks` accepts
  handoffs on the sink's behalf, and `retire_at_sinks` counts a completion **when the
  upstream arm lets go**, not when the part arrives (see finding 5d).
- **Tick loop.** `tree.tickOnce()` and `LineMaintenance::run()` run under a mutex that is
  shared with `StationReset` (the `/cite/line/reset_station` service). `LineState` is
  published every `state_period_ms` (200 ms) on `/cite/line/state`. `tick_period_ms` (50 ms)
  caps latency; it is not a schedule. On exit, `haltTree()` cancels outstanding goals, and a
  latched fault makes the process exit 1.

### 2.4 L3 skills

`MoveToHome`, `PickAt` and `PlaceAt` call the arm's `skill_server`
(`cite_skills/src/skill_server.cpp`, namespace `/cite/cell_b/picker`). The action names come
from the plan's `skills:` block: `/cite/cell_b/picker/{move_to,pick,place,grasp,transfer}`.
The line does not call `grasp` or `transfer`.

- **One goal at a time.** Every action server claims through `ExclusiveGoal`
  (`include/cite_skills/exclusive_goal.hpp`, member `gate_`). A second goal is refused while
  one is in flight. This is why `line:=true` is off by default: a running line holds the arm.
- **`MoveTo`.** `execute_move_to` accepts `named_configuration == "home"` and nothing else.
  `"home"` resolves to the plan's `home_rad`; any other name is refused. `MoveToHome` sends
  `"home"`.
- **`Pick`** (`execute_pick`): open the jaws to the full stroke → approach pose
  (`offset_along_tool_z` by `approach_distance_m`) → grasp pose → close to the grasp width →
  judge the grasp with `cite_skills::gripper_is_holding` → set `holding_ = true` and
  `publish_state()` → retreat (`offset_along_world_z` by `retreat_distance_m`).
- **`Place`** (`execute_place`): refused if `require_holding` is set and the arm is not
  holding → approach → release pose (corrected by the pad offset) → `release_jaws`, which
  confirms the release instead of assuming it → set `holding_ = false` and `publish_state()`
  → retreat. `Place.Result.still_holding` is filled on every exit.
- **Planning.** Each pose move plans with the preferred planner, Pilz PTP. It falls back to
  OMPL only on a planning failure, and never for a Cartesian request
  (`cite_skills::fallback_is_allowed`). See
  [ADR-0027](../adr/0027-pilz-planning-pipeline.md). The IK solution is shifted by whole
  turns toward the current configuration (`unwind_whole_turns`, `cite_skills::nearest_turn`).
  See [ADR-0060](../adr/0060-take-the-ik-solution-nearest-the-arm.md).
- **Gripper to simulation.** `skill_server` publishes `RobotState` on
  `/cite/cell_b/picker/state` (LATCHED). `cite_bringup/grasp_hold_bridge.py`, which only
  `simulation.launch.py` starts (`_grasp_hold_bridges`, once per side), turns each change of
  `gripper_holding` into an empty message on the plan's `attach_topic` or `detach_topic` for
  the `cite_simulation::GraspHold` plugin. See
  [ADR-0065](../adr/0065-the-cell-says-what-it-holds.md) (`Proposed`).

### 2.5 The belt

`ConveyorIndex` (`conveyor_index.hpp`) is the only thing that writes a belt setpoint
(ADR-0032).

- `index_on(topic, state, asset)` subscribes to a station's trigger and stops `asset` on
  every edge into `state`. It returns immediately, and indexes nothing, when `asset` is
  empty.
- `run_all()` is called once, after the tree is built. It commands every declared belt to
  its `installed_speed_mps`.
- `ResumeBelt` (after `CompleteHandoff`) calls `run(belt)`. It returns `SUCCESS` and does
  nothing when `belt` is empty.
- `on_subscriber_matched` re-sends the belt's current setpoint when a subscriber matches.
  This fixes a publish that a reliable publisher would otherwise deliver to nobody
  ([CLAUDE.md §10](../../CLAUDE.md), QoS).
- The beam is placed downstream of the pick point so that a part's centre is at the pick
  point when it breaks the beam. The offset is derived in
  `cite_tools.model.resolve.index_offset_m`. See
  [ADR-0033](../adr/0033-derive-the-index-standoff-from-the-workpiece.md).
- The belts run open-loop: nothing publishes `ConveyorState`.

### 2.6 Fault branch and line state

When a station escalates, the root `Parallel` fails and the `Fallback` runs
`OnFault` (latches `LineFault`) → `StopAll` (commands every belt to 0) → `AwaitReset` (waits
for `ResetStation` on `/cite/line/reset_station`) → `AwaitReArm`. The coordinator stays
alive to serve the reset. See [ADR-0038](../adr/0038-stop-the-line-without-ending-the-process.md)
(`Proposed`). `LineMaintenance::publish` emits `LineState` on `/cite/line/state`.

## 3. Parameters and launch

- **`line:=true`**. `simulation.launch.py` declares `line` with a default of `false`.
  `_bring_up` adds `_line(plan)` to the gate that starts after the planning scene is applied,
  alongside the skill servers and the grasp-hold bridges.
- **`_line`** starts `cite_orchestration` `line_orchestrator` in namespace `/cite/line`.
  **`_line_parameters`** builds its parameters, all from the plan: `zone`, `station_tree`
  (`package://cite_orchestration/trees/line_station.xml`), `line_state_topic`,
  `skill_assets` and the parallel arrays `move_to_actions`, `pick_actions`, `place_actions`,
  `transfer_actions` and `detect_actions` (the zone's single `Detect` action for every
  asset), plus `conveyor_assets`, `conveyor_command_topics`, `conveyor_speeds_mps` and
  `use_sim_time`. It returns `None` (no line) when no arm has skills or the zone has no
  detection block. The node's own defaults are `topology_deadline_s` 30, `handoff_timeout_s`
  120, `skill_deadline_s` 180, `cancel_deadline_s` 30, `retry_budget` 2, `tick_period_ms` 50
  and `state_period_ms` 200.
- **Pair.** `./scripts/sim --zone cell_b --pair line:=true` hands the pair to
  `cite_bringup.pair`. `_flags` turns `line:=true` into the supervisor's option, and
  `side_specs` starts `simulation.launch.py` twice, once with `side:=plant` and once with
  `side:=counterpart`, **each with `line:=true`**, on its own `ROS_DOMAIN_ID` and
  `GZ_PARTITION`. `boundary_spec` then starts `cite_twin`'s `twin_boundary.py` on the join
  (ADR-0057).
- **`./scripts/demo`** runs `./scripts/sim --zone <paired zone> --pair [--headless]
  line:=true` and waits for `CITE_BOUNDARY_READY`. It then runs
  `python3 -m cite_bringup.demo`, which spawns one work-piece on each side's pick table and
  watches both until they reach the outfeed. It asserts nothing and commands nothing (see
  `cite_bringup/demo.py`'s module docstring).

## 4. L0 sources

- `model/topology/flow_cell_b.yaml`: flow `cell_b_pick_and_place`, with edges
  `b_infeed → b_transfer_1` (`via: null`, buffer 6) and
  `b_transfer_1 → b_accumulation` (`via: transfer_belt`, buffer 4).
- `model/topology/stations.yaml`, `cell_b` block:
  - `b_infeed`: `source_station`.
  - `b_transfer_1`: `transfer_station`, actor `picker`, `pick_from: infeed_table/surface`,
    `place_to: transfer_belt/infeed`, trigger `infeed_beam` blocked.
  - `b_accumulation`: `sink_station`, trigger `outfeed_beam` blocked.
- `model/assets/instances/`: `arms.yaml` (`picker`, including `home_rad`), `sensors.yaml`
  (`infeed_beam` on `infeed_table/surface`, `outfeed_beam` on `transfer_belt/outfeed`),
  `conveyors.yaml` (`transfer_belt`) and `fixtures.yaml`.
- Generated (never edit by hand, ADR-0021): `workspace/src/cite_generated/topology/cell_b_flow.yaml`
  (what `topology_server` publishes) and `workspace/src/cite_generated/bringup/cell_b_plan.yaml`
  (the skills, sensors, conveyors, detection, grasp-hold topics and sides that the launch
  reads).

## 5. Findings

These describe the code at `event-driven-line-v1` as it is (P7).

**a. The pair runs two independent lines, not one signal driving two arms.** With `--pair
line:=true`, each side starts its **own** `line_orchestrator` on its own ROS domain. Each one
reacts to its own side's beams and commands its own side's arm and belt. `cite_bringup/demo.py`
and `scripts/demo` send no goal and no `SetMode` through `/cite/twin/...`. The twin boundary
(`cite_twin/twin_boundary.py`, [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md)) is
started, serves `SetMode` on `/cite/twin/set_mode`, and routes `move_to`, `pick`, `place`,
`grasp` and `transfer` to both sides in `VALIDATED` and `VIRTUAL_LEAD`
(`cite_twin/routing.py`). Nothing in the line uses it. It routes neither `Detect` nor belt
commands — true at tag `event-driven-line-v1`; changed by
[ADR-0066](../adr/0066-run-the-cell-from-a-fixed-program.md), after which the boundary forwards
belt setpoints (still not `Detect`). Two sides finishing alike therefore means two copies of
the same program finished alike. It is not evidence that one command reached both.

**b. On `cell_b` the belt is never indexed on a beam edge.** `b_transfer_1`'s inbound edge is
`via: null` (the part sits on `infeed_table`, not on a belt). So `inbound_via_asset_id` is
empty, `ConveyorIndex::index_on` returns without indexing anything, and `ResumeBelt` is a
no-op. `transfer_belt` feeds only the sink, and no station indexes a belt that feeds a sink.
It therefore runs at `installed_speed_mps` (0.15) from `run_all()` until `StopAll` or process
exit. The stop-on-edge mechanism described in 2.5 is exercised only on `cell_a`, which CI no
longer drives ([ADR-0056](../adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md)).

**c. The approach and release geometry is not in L0.** These are BT port defaults in
`skill_nodes.hpp`:
- `PickAt`: `workpiece_height_m` 0.025, `approach_m` 0.10, `retreat_m` 0.12,
  `grasp_width_m` 0.045.
- `PlaceAt`: `release_height_m` 0.04, `approach_m` 0.10, `retreat_m` 0.12.
- `DetectAt`: `region_m` 0.60.

`line_station.xml` sets none of them. `grasp_width_m` duplicates L0's `default_grasp_width_m`,
and the comment above that port in `skill_nodes.hpp` names it as a duplicate.

**d. The sink's beam drives nothing in L4.** `b_accumulation` declares `outfeed_beam` as its
trigger, and the topology carries it. `SinkPlan` has no trigger field, however, and no sink
calls `index_on`. `detection_server` publishes `outfeed_beam` events, but L4 does not consume
them. Completions are counted in `retire_at_sinks` when the arm releases the part.

**e. `MoveTo` knows one named configuration.** `execute_move_to` refuses any
`named_configuration` other than `"home"` — true at tag `event-driven-line-v1`; changed by
[ADR-0066](../adr/0066-run-the-cell-from-a-fixed-program.md), after which it also accepts each
pose L0 declares in `configuration.poses_rad`.

## 6. How to run it again

Nothing here needs a code change at `event-driven-line-v1`:

- One side: `./scripts/sim --zone cell_b line:=true` (add `--headless` for no window).
- Both sides, as the demo does: `./scripts/sim --zone cell_b --pair line:=true`.
- Watch it: `./scripts/demo` (`--headless` optional; `--zone` defaults to the paired zone).
- Check it: `./scripts/scenario continuous_line` (drives `cell_b` by default,
  `tests/scenarios/_cell.py`).

After a work-piece is spawned on `cell_b__infeed_table__surface`, it breaks `infeed_beam`,
and the station runs its cycle.

## 7. What stays in place, and what guards it

These stay at their current paths and stay built and tested:

- **`cite_orchestration`**: `src/line_orchestrator.cpp`, `src/line_coordinator.cpp`,
  `trees/line_station.xml`, `trees/station_cycle.xml`, the `line_*.hpp` headers
  (`line_nodes`, `line_plan`, `line_tree`, `line_fault`, `line_maintenance`),
  `conveyor_index.hpp` and `skill_nodes.hpp`.
- **`cite_skills`**: `src/detection_server.cpp`.
- **`cite_bringup`**: `simulation.launch.py` `_line` and `_line_parameters`, and
  `cite_bringup/demo.py`.
- **Scripts and scenarios**: `scripts/demo` and `tests/scenarios/continuous_line.py`.

Guards:

- The git tag `event-driven-line-v1`.
- The CI step `Simulation-in-the-loop scenario — continuous_line (advisory)`.
- A host test, `tools/tests/test_event_driven_line_is_kept.py`, which fails if a listed file
  disappears.

## 8. Design note: where a joystick or teleop input would plug in (NOT BUILT)

**Nothing in this section exists.** It records where such an input fits the layer rules.

- **As an L4-level producer of skill goals.** A teleop node would be one more client of the
  same L3 actions the line calls. It would respect the one-goal gate, so it cannot share an
  arm with a running `line_orchestrator`. Either the line is off (`line:=false`) or the line
  gains an operator hand-over state, which would be a new L4 decision and need an ADR.
- **Through the twin boundary.** In `VALIDATED` or `VIRTUAL_LEAD`, a goal sent to
  `/cite/twin/cell_b/picker/<skill>` reaches both sides (ADR-0050). This is the path that
  would make "one input, two arms" true, which finding (a) says the line is not.
- **Continuous jogging.** The skills above take discrete goals; they do not accept a velocity
  stream. The imported `xarm_ros2` tree has a vendor package, `xarm_moveit_servo`, with
  `src/xarm_joystick_input.cpp` and `src/xarm_keyboard_input.cpp`. Both files were present in
  the development checkout's `workspace/src/external/xarm_ros2/` on 2026-09-28. The package
  is built with the rest of the imported tree: a committed build log,
  `docs/measurements/2026-09-02-option-f-regions/raw/logs/build.log`, shows it built with an
  `xarm_joystick_input_node` executable. No first-party file references it: `git grep
  moveit_servo` matches only that log. It is **unused and unevaluated** here. Using it would put a second
  commander on the arm's trajectory controller beside the skill server. That is an L2/L3
  decision and needs an ADR.
