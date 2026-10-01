# cite_facility

Runtime access to the artifacts generated from the L0 facility model. It turns files in
`cite_generated` into things the running graph can use: static transforms, the model
version, and each arm's planning scene.

**This package never opens anything under `model/`.**
[L0](../../../docs/architecture/L0-facility-model.md) is explicit that a running system does
not read the model — it reads what was *generated* from it. That boundary is what lets the
model be validated on a laptop with no ROS, and lets the robot run with no model present at
all. `cite_tools` turns the model into artifacts, on any machine, with no ROS; this package
turns those artifacts into runtime facts, in the robot, with no model. `test/test_artifacts.py`
exists to defend that line, and `cite_facility/artifacts.py` is the only module that touches
the filesystem.

## What is here

Three executables, plus the library modules they share.

| Node | Kind | What it does |
|---|---|---|
| `frame_server.py` | managed (lifecycle) | publishes the static transforms for everything that is not a robot link — zone origins, station frames, each arm's mount |
| `model_info.py` | managed (lifecycle) | publishes `ModelVersion` and serves `GetModelVersion` |
| `planning_scene_loader.py` | **one-shot process** | puts the cell's furniture into one arm's planning scene, verifies it arrived, and exits |

`artifacts.py` locates and reads the generated files. `transforms.py` holds the one
roll-pitch-yaw to quaternion conversion on the ROS side, using the same intrinsic Z-Y-X
convention the generator uses — the two agreeing is what makes a pose mean the same thing in
both.

## Interfaces

| Name | Type | Direction | Profile |
|---|---|---|---|
| `/tf_static` | `tf2_msgs/TFMessage` | out of `frame_server` | as `StaticTransformBroadcaster` sets it |
| `/cite/facility/model_version` | `cite_interfaces/ModelVersion` | out of `model_info` | `LATCHED` |
| `/cite/facility/get_model_version` | `cite_interfaces/GetModelVersion` | served by `model_info` | — |
| `apply_planning_scene`, `get_planning_scene` | `moveit_msgs` services | called by the loader, relative to the arm's namespace | — |

**`LATCHED` is not a preference.** A consumer that starts after `model_info` has published
must receive the model version immediately. A `VOLATILE` publisher would connect to it
silently and deliver nothing — the failure CLAUDE.md §10 names first.

The process-topology server that published `LineTopology` left the main tree with the
event-driven line it served
([ADR-0069](../../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md));
it runs in `projects/01`.

## What it deliberately does not do

- **It does not read `model/`.** Stated at the top because it is the property most easily
  eroded and most expensive to lose.
- **It does not plan.** The planning-scene loader speaks MoveIt's collision-object contract
  through `moveit_msgs` and `shape_msgs` only; nothing here links against `move_group`.
- **It does not put the neighbouring arms into a planning scene.** Only the authored
  furniture is loaded. An articulated robot frozen at one pose is confidently wrong wherever
  it actually is, and coordinating arms needs the live scene, which is L4's problem.
- **The loader does not stay alive.** It is a one-shot process like `ros_gz_sim create` and
  `controller_manager spawner`: it does one thing, proves it happened, and exits. Its exit is
  a real completion event that bring-up gates the skill servers on, which is what P4 asks
  for. Nothing can tell when a publisher has been *received*.
- **The loader does not trust `ApplyPlanningScene`.** Success there means `move_group`
  accepted the diff, not that the objects are in the world: an object in a frame TF cannot
  resolve is accepted and then dropped. So the scene is read back and the object names
  compared. The difference between those two outcomes is a robot planning through a table.

## How to run it

All three are started by `cite_bringup` as part of the cell, and that is the normal way to
run them:

```bash
./scripts/sim --headless
```

The two managed nodes come up alongside the simulator — none of them depends on it — and
bring-up drives each through `configure` then `activate`, stopping the launch if either
transition fails. The loader is chained after the controllers and before the skill servers.

To inspect a running cell:

```bash
ros2 topic echo /cite/facility/model_version --once
ros2 service call /cite/facility/get_model_version cite_interfaces/srv/GetModelVersion
ros2 topic echo /tf_static --once
```

## How it fails

Every failure here is meant to stop bring-up with a diagnosis rather than produce a cell that
answers some interfaces and not others.

| Symptom | Cause |
|---|---|
| `cite_generated is not on the ament index` | the generated package was never built. Run `./scripts/validate-model --write`, then `./scripts/build` |
| `no generated artifact at <path>` | the artifact is missing. Regenerate; if it is still missing, no generator emits it |
| `frame_server` refuses to configure with "more than one transform for X" | the generated frame table declares a duplicate child. Two publishers for one transform make TF alternate between them, which is intermittent and very hard to attribute, so it is refused rather than published |
| `frame_server` refuses to configure on an empty table | activating with nothing would leave every consumer waiting on a transform that never arrives, which reports as nothing at all |
| `no move_group answered 'apply_planning_scene'` | `move_group` is not running for that arm. Every plan for it would otherwise be computed against an empty world |
| `move_group accepted the diff but [...] are not in its world` | the collision objects' frame cannot be resolved by TF, so they were dropped. This is the case the read-back exists to catch |
| a skill goal fails with a TF lookup error naming frames | `frame_server` never published. It is a managed node; check that it reached `active` |

The deadline in the loader (`SERVICE_DEADLINE_S`) is a deadline, not a schedule. Nothing
about correct behaviour depends on its value; it exists so that a `move_group` which never
appears is reported rather than waited on forever.

## Tests

```bash
./scripts/test --packages-select cite_facility
```

Two pytest suites, none of which needs a ROS graph or a simulator:

* `test_artifacts.py` — the artifact reader, and the boundary: this package must never read
  `model/`.
* `test_planning_scene_loader.py` — building MoveIt collision objects: the shape type, the
  number of dimensions, the pose convention and the frame. `pose` in the generated artifact
  is the pose of the primitive's **centre**, which is what MoveIt's `primitive_poses` means,
  while an L0 body's pose names the point it stands on. The generator applies the half-height
  difference; these tests assert the result rather than reapplying it.

The service call itself is not unit-tested. It is exercised every time the cell comes up: the
loader exits non-zero if the scene was not applied and verified, and `simulation.launch.py`
gates the skill servers on that exit, so the failure stops bring-up rather than reaching a
scenario. No test in this package drives a `move_group`.
