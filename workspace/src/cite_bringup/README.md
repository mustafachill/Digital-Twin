# cite_bringup

The launch entry point for the cell, and the reader for the generated bring-up plan.

**This package holds mechanism only.** What to start, in what order, and with what parameters
is data — `cite_generated/bringup/<zone>_plan.yaml`, generated from the L0 model. Adding a
fourth arm changes that plan, not this code (P5). There is no asset name, no controller name,
no topic and no frame written in this package.

## The property that must not be eroded

**There is not one `TimerAction` in `launch/simulation.launch.py`, and there must never be.**

v1 sequenced its bring-up with sleeps — twelve seconds per robot, a number raised whenever
startup failed rather than because it meant anything — which put the third robot's controllers
at t = 31 s and worked only on a machine fast enough. P4 exists because of that, and this
package is where P4 is either kept or lost. The distinction that makes it possible:

> Waiting on a condition with a deadline that **fails** is event-driven.
> Waiting a fixed duration and proceeding regardless is not.

`ros_gz_sim create` blocks on the world's create service and on the latched description, then
exits — a real completion event. `controller_manager spawner` blocks on `list_controllers` and
exits non-zero on expiry. `planning_scene_loader.py` exits when the scene it applied has been
read back. Every `*_DEADLINE_S` constant in the launch file is a deadline: no correct behaviour
depends on its value, and expiry stops bring-up with a diagnosis.

The second half is easier to lose: **every link in the chain is gated, including the last
one.** An event-gated chain whose final link is ungated brings the system up half-built and
reports success — which is the defect that was there. Every long-running process also carries
`_fatal_on_exit`, so a node dying mid-run tears the launch down instead of leaving a cell that
answers some interfaces and not others.

## What is here

| File | What it is |
|---|---|
| `cite_bringup/plan.py` | reads and checks the generated plan; pure logic, no ROS runtime |
| `launch/simulation.launch.py` | the launch description built from that plan |

The split is so the plan reader can be unit-tested. A launch file is awkward to test; a
function that turns YAML into dataclasses is not, and most of what can go wrong — a missing
controller, a stage out of order, a `package://` URI that does not resolve — is in that half.

### What bring-up starts, in order

The order is a real dependency chain, not a preference
([`cross-cutting-lifecycle.md`](../../../docs/architecture/cross-cutting-lifecycle.md)).

1. `gz sim`, and one `ros_gz_bridge parameter_bridge`.
2. The scene: `robot_state_publisher` plus `ros_gz_sim create`.
3. One `robot_state_publisher` and one `create` per arm — **one Gazebo model per arm**,
   because `gz_ros2_control` attaches to a model and the controller manager it creates claims
   every `ros2_control` component in that model's description. With all three arms in one
   model, all three managers claimed all eighteen joints and wrote to them every cycle.
4. The facility's managed nodes (`cite_facility`), which depend on nothing above and come up
   alongside the simulator.
5. Controllers, stage by stage — **one chain across every manager**, not one chain per arm.
   Three managers performing a state switch simultaneously while physics runs made bring-up
   intermittent: a scenario that passed and then failed on the very next run. The single chain
   is still entirely event-gated, so it is as fast as the machine allows; it simply no longer
   races itself.
6. One `move_group` per arm, started unconditionally — it waits for `/joint_states` itself, and
   gating it would add an ordering constraint the system does not have.
7. One `planning_scene_loader` per arm, chained.
8. The zone's detection server (with the facility nodes, since it commands no motion).
9. The skill servers, and the L4 coordinator if `line:=true`.

### The bridge

`_bridge_topics` builds one `parameter_bridge` argument list carrying `/clock` plus **every
aid topic the plan declares** — a command ROS→Gazebo and a state Gazebo→ROS per conveyor, and
a detection Gazebo→ROS per sensor. In `cell_a` that is three belts and four beams, so ten aid
topics. Not one name is written here. Until this existed, `/clock` was bridged and nothing
else, so the plan advertised interfaces the running system did not provide and the
sensor-driven line could not be driven by its sensors.

**A beam's level and a beam's events are two different interfaces.** The bridge lands the
plugin's raw `gz.msgs.Boolean` on the plan's `level_topic` via a remapping, and leaves
`detection_topic` for the typed `DetectionEvent` that `cite_skills` publishes from it — which
is the name a station's trigger subscribes to. Landing the boolean there would put two
publishers of two types on one topic. `plan.py` refuses a sensor that names the same topic for
both.

## Interfaces

This package advertises nothing of its own. Its interface is the launch arguments and the
plan.

| Launch argument | Default | Meaning |
|---|---|---|
| `headless` | `true` | run the simulator without a GUI. Required on macOS and in CI |
| `zone` | `cell_a` | which zone of the facility model to bring up |
| `line` | `false` | start the L4 line coordinator |

`line` is off by default and that is a real constraint rather than caution: a skill server
admits one goal at a time per arm, so a running coordinator holds all three arms and any other
client — a scenario, an operator, a diagnostic — has its goals refused by a server that is
busy working.

| Environment variable | Effect |
|---|---|
| `CITE_ALLOW_HARDWARE=1` | permits a plan naming a non-`sim` backend to start |
| `CITE_PHYSICS_SEED` | passed to `gz sim --seed`; a malformed value is refused, not ignored |

**`CITE_PHYSICS_SEED` does not make a scenario reproducible, and must not be described as
doing so.** `gz sim --seed` seeds sensor noise and the transport RNG. It does not seed the
physics solver, and it has nothing to do with OMPL, which is the stochastic component that
decides whether two runs produce the same trajectory. See
[`cross-cutting-testing.md`](../../../docs/architecture/cross-cutting-testing.md) and
[ADR-0027](../../../docs/adr/0027-pilz-planning-pipeline.md).

## The hardware gate

`plan.py::require_hardware_opt_in` refuses a plan that declares any backend other than `sim`
unless `CITE_ALLOW_HARDWARE=1` is set, and `simulation.launch.py` calls it before it builds
anything.

It is an **allowlist**, not a denylist: `sim` is the one backend that cannot reach a physical
machine, so a backend nobody anticipated is refused rather than permitted.
[`cross-cutting-safety.md`](../../../docs/architecture/cross-cutting-safety.md) requires that
a hardware path is never reachable by omission, and a denylist is reachable by omission by
construction.

The equivalent shell check in `scripts/_lib.sh` guards `./scripts/enter hardware` and nothing
else. Every other route into the ROS graph — a launch file run directly, a scenario, CI, an
editor — arrives at this one instead.

**What this is not.** Refusing to start is the only enforceable form of the rule until Phase 2
builds the safety layer. It does not change *what* is commanded on either path (P2); it stops
a physical machine being commanded by accident. There is no hardware launch file in this
package at this commit, and every backend in `cell_a_plan.yaml` is `sim`.

## What it deliberately does not do

- **It does not sequence anything by time.** See above.
- **It does not compose a name.** Every action, topic, frame, controller and file path comes
  from the plan or from a message constant (`LineState::TOPIC`). A name built here would be a
  second place a name is made, outside the reach of `ids.py` and the tests that cover it.
- **It does not default a value the plan omits.** `_gripper` passes through exactly the keys
  the plan carries. A zero manufactured here would override the server's declared defaults
  with a number the model never stated — which is how `gripper_max_width_m` came to be
  delivered while eleven real values were not, and the node ran on compiled defaults that
  happened to equal the L0 values. It worked, and only for as long as two copies agreed.
  `GRIPPER_KEYS` describes itself as holding the keys "under the exact name the skill server
  declares it"; that is true of eleven of the twelve. `gripper_max_drive_rate_rad_s` is
  delivered and is not declared by `skill_server.cpp`, so it is an unused node override — the
  drive rate reaches the gripper through the generated `*.urdf.xacro` instead.
- **It does not resolve `package://` at generation time.** The plan is committed to git, so an
  absolute path in it would be wrong on every machine but the one that generated it. URIs are
  resolved at launch.

## How to run it

```bash
./scripts/sim --headless                 # the cell, without the L4 coordinator
./scripts/sim --headless line:=true      # with it
./scripts/scenario bringup               # headless, asserted, and a blocking CI gate
```

Invoke `./scripts/sim` rather than `ros2 launch` (CLAUDE.md §7): it routes to the right
environment, and on a machine without ROS it re-executes itself inside the container.

## How it fails

Every refusal produces `BRING-UP FAILED: <reason>` and a `Shutdown`, rather than a partially
started cell.

| Symptom | Cause |
|---|---|
| `no bring-up plan at <path>` | the plan is generated. Run `./scripts/validate-model --write`, then `./scripts/build` |
| `<uri>: package X is not on the ament index` | the workspace was not built, or the overlay not sourced |
| `zone 'cell_a' declares a hardware backend for ...` | the opt-in gate. Confirm the cell is clear, then set `CITE_ALLOW_HARDWARE=1` deliberately — see [`safety-procedures.md`](../../../docs/operations/safety-procedures.md) |
| `controller manager for X lists no controllers` | bring-up would report success having activated nothing |
| a sensor names one topic for both its level and its events | the bridge would publish `std_msgs/Bool` on the topic a station reads `DetectionEvent` from |
| a zone declares sensors and no `detection:` block | the beams would be bridged into ROS and read by nobody |
| `BRING-UP FAILED before <step>: the previous step exited N` | a gated step failed. If it timed out, the node it waits on never appeared, or a controller's joint names do not match the description — run `./scripts/validate-model` |
| `<node> could not reach 'active'` | a managed node's `on_configure` or `on_activate` returned FAILURE or raised. The node logged why immediately above; nothing downstream of it is started |
| a spawner times out on a service | usually `gz_ros2_control-system` failed to load, so no controller manager was ever created. The launch appends `GZ_SIM_SYSTEM_PLUGIN_PATH` for exactly this reason |
| `move_group` logs "No 3D sensor plugin(s) defined for octomap updates" | accurate — no depth sensor feeds this cell. It goes away when Phase 3 brings depth sensing, not before |

The `TEARDOWN_SIGTERM_S`/`TEARDOWN_SIGKILL_S` ceilings are ceilings on a failure, not a
schedule: a process that exits immediately is not delayed. They do **not** order shutdown —
launch broadcasts SIGINT to every process in one event dispatch.

## Tests

```bash
./scripts/test --packages-select cite_bringup
```

Both are pytest and neither starts a process; they run in milliseconds.

* `test_plan.py` — the plan reader: what it accepts, and every error message it produces.
* `test_simulation_launch.py` — the launch description itself: what it refuses to start and
  what it stops on. Both halves are needed and neither substitutes for the other — **a
  perfectly correct `require_hardware_opt_in` that nothing calls is exactly the defect this
  file exists to catch, and it is the defect that was there.**

The bridge argument list is built by `_bridge_topics` rather than inline in the `Node`, so it
can be read back: `launch_ros` hides a node's arguments behind a private attribute, and a test
reaching into the action would be testing launch's internals rather than this file's
decisions — a direction reversed, a name misspelled, a level landed on the topic the line acts
on.

Whether the cell actually comes up is `./scripts/scenario bringup`, which is a blocking CI
gate run twice per CI run.
