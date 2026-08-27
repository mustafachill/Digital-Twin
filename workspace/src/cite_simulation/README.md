# cite_simulation

Gazebo Harmonic system plugins that make the simulated cell behave like the physical
one where a rigid-body simulator would otherwise behave unusably. They are **simulation
fidelity aids, not control paths**.

**The property that must not be eroded:** nothing above `ros2_control` knows these exist.
They speak Gazebo transport only. There is no sim-only branch in any skill, no `if
simulation` anywhere, and no ROS interface that exists on one path and not the other —
which is what keeps [ADR-0005](../../../docs/adr/0005-ros2-control-sim-real-boundary.md)
and P2 intact. On hardware the physical world does these jobs and no plugin is loaded.

## What is here

| Plugin | Scope | Replaces | Rationale |
|---|---|---|---|
| `cite_conveyor` | world (one per belt) | transporting a part by belt friction | header of `src/conveyor.cpp` |
| `cite_break_beam` | world (one per sensor) | an optical through-beam | header of `src/break_beam.cpp` |

There was a third, `cite_grasp_attachment`, which welded a work-piece to a finger with a
`DetachableJoint` instead of letting friction hold it. It is **removed** by
[ADR-0029](../../../docs/adr/0029-simulated-grasping-by-friction.md), which supersedes
ADR-0023. The 84-trial campaign in
[`docs/measurements/2026-08-25-friction-grasp/`](../../../docs/measurements/2026-08-25-friction-grasp/results.md)
measured it firing at first pad contact, before any contact force could develop, so the jaws
then closed through the part feeling nothing and `Pick` failed while the weld carried the
part anyway. In the friction arm of the same campaign the gripper stalled on the part and
held it every time it was asked to. **Grasping in this cell is now plain friction, with no
simulation-side aid at all.** The figures are in `results.md` and are not restated here (P1).

The belts and the beams are **world** systems rather than model plugins, and that is
forced rather than chosen: every authored body in the scene is joined to the cell root by
a fixed joint, and URDF-to-SDF conversion lumps fixed-jointed links into their parent, so
no `conveyor_1` or `beam_c1_out` model exists in the spawned world to attach to. Their
poses therefore arrive as data, resolved by the generator from the same L0 frames that
place their geometry.

## Configuration is data

Nothing here is instantiated by hand. `tools/cite_tools/generate/world.py` emits one
`<plugin>` element per conveyor and per sensor in the L0 model. Which objects a belt
carries, which belt runs how fast, how long a beam is, and every topic name come from
`model/`. No link name, model name or topic is written in C++.

Two of those values are *derived* rather than declared, because they are already stated
somewhere else and a second copy is a second place to be wrong (P1): a belt's footprint is
read from the belt type's own collision box, and its carry height — how far above the
surface a part still counts as resting on it — is the height of the tallest type in
`facility.workpiece_models`, since that is a fact about the part rather than about the belt.
A part at rest sits half its own height up, so the volume holds it centrally and lets go
once it has been lifted higher than it is tall.

To change what the aids do, edit `model/` and run `./scripts/validate-model --write`.

## Interfaces

Gazebo transport, below the ROS boundary. `<zone>` and `<asset_id>` come from the model.

| Topic | Type | Direction |
|---|---|---|
| `/cite/<zone>/<asset_id>/command` | `gz.msgs.Double` (m/s) | into the belt |
| `/cite/<zone>/<asset_id>/state` | `gz.msgs.Double` (m/s) | out of the belt, commanded speed |
| `/cite/<zone>/<asset_id>/detection` | `gz.msgs.Boolean` | out of the beam, true when broken |

**These names now have a ROS side, and it is generated rather than written.**
`simulation.launch.py::_bridge_topics` runs one `ros_gz_bridge parameter_bridge` process
carrying `/clock` plus **every aid topic the plan declares** — a command ROS→Gazebo and a
state Gazebo→ROS per conveyor, and a detection Gazebo→ROS per sensor. In `cell_a` that is
three belts and four beams, so ten aid topics. Not one of the names is written in the launch
file; they are read from `cell_a_plan.yaml`, which is generated from L0. Bridging them by
hand is no longer necessary and would put a second publisher on a live topic.

**A beam's level and a beam's events are two different interfaces, and the bridge keeps them
apart.** The plugin's `gz.msgs.Boolean` lands in ROS on the plan's `level_topic`
(`…/detection_level`), applied as a remapping — the Gazebo side of the argument has to stay
the name the plugin advertises. The plan's `detection_topic` (`…/detection`) is left for the
typed `DetectionEvent` that `cite_skills`' detection server publishes from that level, which
is the name a station's trigger subscribes to. Landing the raw boolean on it would give one
topic two publishers of two types.

**Something reads them.** `cite_skills/src/detection_server.cpp` subscribes to every
`level_topic` and turns it into `DetectionEvent`; in `cite_orchestration`, `TriggerWatch`
starts a station on that event and `conveyor_index.hpp` stops the belt on it and commands
every belt's setpoint ([ADR-0032](../../../docs/adr/0032-index-the-belt.md)).

## Fidelity costs, stated rather than hidden

Transport replaces a physical interaction with a deterministic one, and it flatters us.

* **Transport** is kinematic, not frictional: a part inside a belt's carry volume is
  commanded along the belt, and handed back to physics the moment it leaves — it keeps the
  speed the belt gave it and coasts, which is what leaving a belt looks like. A part that
  would slip, tumble, jam against a neighbour or fail to be driven at all is carried
  smoothly here. No claim about belt handling, accumulation pressure or singulation can
  rest on this package.
  **This is now measured rather than argued from the source.** A ride down `conveyor_1`
  changes a part's yaw by nothing at all, at every starting angle from square to 45° and in
  both belt modes — 36 trials, with a negative control that discriminates. A belt here does not
  re-seat, square up or disturb what it carries; it translates it. The campaign is
  [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](../../../docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md)
  and its numbers stay there.
* **Detection** is an intersection between the beam and the work-piece's collision body,
  which is what a through beam measures: it breaks on a part's leading edge and stays
  broken until the trailing edge is past, at any height the part reaches. The shapes come
  from the simulator rather than from a dimension declared to the plugin, so a part whose
  size changes in L0 changes what the beam sees with nothing to keep in step.
  **This used to be a point test on the model origin, and it was wrong in two directions.**
  A beam reported a part only once its *centre* crossed the beam's volume, which with the
  old 0.040 m width gave the sensor a window of part-centre heights — it saw a part between
  20 mm and 100 mm tall and missed everything outside that, while a physical beam sees all
  of it. Along the belt the same lateness cost the line its pick position: `beam_c1_out`
  reported the 50 mm cube 25 mm after its leading edge arrived, the indexed belt stopped on
  that edge, and every piece parked 69 mm short of `arm_2`'s grasp. `continuous_line`
  stopped at milestone 4 of 10, four runs out of four.
  The remaining bound is a real one and holds identically on hardware: a beam mounted
  0.030 m above the belt cannot see a part shorter than about 30 mm, because the part
  passes under it. `beam-cannot-see-workpiece` in `cite_tools.validate.geometric` rejects
  that pairing in the model rather than leaving it to be found at run time. There is no
  upper bound at all.

P8 applies: any claim about transport reliability needs a measurement against hardware,
and this package cannot provide one. Grasping is no longer in this list because no plugin
assists it — but the same caution applies for a different reason. The friction grasp is
measured *in simulation only*, and it is repeatable in **position** and not in
**orientation**: the part rolls between the jaws, about the pad-to-pad axis. The physics
timestep changes how often the large rotations occur, so a change to `max_step_size` moves
grasp quality and has to be re-measured rather than assumed. A third campaign adds the
counterpart about yaw: jaws closing on a part that is **yawed** rotate it into alignment, so
a part is carried square and released with a residual. That squaring-up is a rigid-body
contact result with no friction declared on the pads, and it is the largest sim/real
divergence risk currently on the books. The campaigns are in
[`docs/measurements/`](../../../docs/measurements/README.md); their numbers live there.
Nothing here evidences how any of it behaves on the physical arm.

## How it fails

| Symptom | Cause |
|---|---|
| a grasp never holds | the commanded width is not narrower than the part, so the pads never stall — a grasp is evidenced by *failing* to reach the command |
| a belt reports state but carries nothing | nobody commanded it; an uncommanded belt is inert by design |
| a belt carries nothing while commanded | the part is not in the carry volume, or its model name is not in `facility.workpiece_models`. The belt matches on the **Gazebo model name**: a part spawned as `box` or `cube` is invisible to a belt that carries `workpiece`, and the belt reports the commanded speed either way |
| a beam never trips | the part's model name is not watched, the beam does not reach across the belt, the part is shorter than the beam's mounting height and passes under it, or the part has no collision geometry for the segment to intersect — see the fidelity note above |
| a part that left a belt will not fall, will not be pushed, and cannot be lifted | fixed: the belt used to leave a velocity command on every part it had touched, and Gazebo re-applies it — as zero — every step forever. `test_conveyor_carry` locks this down |
| a part is grasped off a *running* belt and it fights the gripper | the belt commands the velocity of any free body in its carry volume, and a friction-held part is still a free body. Stop the belt before picking from it — which is what a real line does |
| nothing loads at all | `GZ_SIM_SYSTEM_PLUGIN_PATH` does not include this package's `lib` — the environment hook in `hooks/` sets it |

## Tests

`./scripts/test --packages-select cite_simulation`. Two levels, because the defects live at
both:

* `test_zone_rules` — the decision rules, without a simulator. Whether a part is on a belt
  and whether a beam is broken are pure geometry.
* `test_conveyor_carry` — the belt with a part on it and physics running, through
  `gz::sim::TestFixture`: in-process, headless, and stepped a counted number of 1 ms steps
  rather than run for a wall-clock duration. It commands the belt, measures how far the
  part travelled, watches the beam break as the part passes, stops the belt, and then
  carries the part off the end and asserts that it *falls*. That last assertion is the one
  that matters: until it existed, nothing at any level commanded a belt and then looked at
  a part, and a belt that never let go of what it carried passed every test in the
  repository.

The generator side is covered by `tools/tests/test_generate_world.py`.
