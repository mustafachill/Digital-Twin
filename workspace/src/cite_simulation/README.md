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
| `cite_grasp_attachment` | model (each arm) | holding a box by friction | [ADR-0023](../../../docs/adr/0023-simulated-grasping-via-attachment.md) |
| `cite_conveyor` | world (one per belt) | transporting a part by belt friction | header of `src/conveyor.cpp` |
| `cite_break_beam` | world (one per sensor) | an optical through-beam | header of `src/break_beam.cpp` |

The belts and the beams are **world** systems rather than model plugins, and that is
forced rather than chosen: every authored body in the scene is joined to the cell root by
a fixed joint, and URDF-to-SDF conversion lumps fixed-jointed links into their parent, so
no `conveyor_1` or `beam_c1_out` model exists in the spawned world to attach to. Their
poses therefore arrive as data, resolved by the generator from the same L0 frames that
place their geometry.

## Configuration is data

Nothing here is instantiated by hand. `tools/cite_tools/generate/world.py` emits one
`<plugin>` element per conveyor and per sensor in the L0 model, and
`generate/description.py` emits the grasp plugin per arm. Which objects are graspable,
which belt runs how fast, how long a beam is, and every topic name come from `model/`.
No link name, model name or topic is written in C++.

To change what the aids do, edit `model/` and run `./scripts/validate-model --write`.

## Interfaces

Gazebo transport, below the ROS boundary. `<zone>` and `<asset_id>` come from the model.

| Topic | Type | Direction |
|---|---|---|
| `/cite/<zone>/<asset_id>/command` | `gz.msgs.Double` (m/s) | into the belt |
| `/cite/<zone>/<asset_id>/state` | `gz.msgs.Double` (m/s) | out of the belt, commanded speed |
| `/cite/<zone>/<asset_id>/detection` | `gz.msgs.Boolean` | out of the beam, true when broken |

The grasp plugin has no topic at all. It logs its attach and detach transitions; the
scenario asserts on the work-piece's pose, because a component reporting success proves
only that the component thinks so.

**The ROS side of these names does not exist yet.** `cite_bringup` starts no
`ros_gz_bridge` for them, so `ros2 topic list` does not show them even though
`cell_a_plan.yaml` declares them — see the handoff in this branch's fix report. Bridging
them by hand is one command:

```
ros2 run ros_gz_bridge parameter_bridge \
  "/cite/cell_a/conveyor_1/command@std_msgs/msg/Float64]gz.msgs.Double" \
  "/cite/cell_a/conveyor_1/state@std_msgs/msg/Float64[gz.msgs.Double" \
  "/cite/cell_a/beam_c1_out/detection@std_msgs/msg/Bool[gz.msgs.Boolean"
```

## Fidelity costs, stated rather than hidden

Both aids replace a physical interaction with a deterministic one, and both flatter us.

* **Grasping** holds a part that would slip in reality (ADR-0023).
* **Transport** is kinematic, not frictional: a part inside a belt's carry volume is
  commanded along the belt. A part that would slip, tumble, jam against a neighbour or
  fail to be driven at all is carried smoothly here. No claim about belt handling,
  accumulation pressure or singulation can rest on this package.

P8 applies to both: any claim about grasp or transport reliability needs a measurement
against hardware, and this package cannot provide one.

## How it fails

| Symptom | Cause |
|---|---|
| a grasp never holds | the plugin logged `has no link` at start-up — the named link was lumped away by URDF-to-SDF conversion |
| a belt reports state but carries nothing | nobody commanded it; an uncommanded belt is inert by design |
| a belt carries nothing while commanded | the part is not in the carry volume, or its model name is not in `facility.workpiece_models` |
| a beam never trips | the part's model name is not watched, or the beam does not reach across the belt |
| nothing loads at all | `GZ_SIM_SYSTEM_PLUGIN_PATH` does not include this package's `lib` — the environment hook in `hooks/` sets it |

## Tests

`./scripts/test --packages-select cite_simulation`. The decision rules — whether a
contact is a grasp, whether a part is on a belt, whether a beam is broken — are pure and
are unit-tested without a simulator, which is where every defect found in review actually
lived. The generator side is covered by `tools/tests/test_generate_world.py`.
