# Naming and namespaces

- **Status:** `DESIGNED` — the scheme is defined; the generator that enforces it is Phase 1.B.
- **Related:** [ADR-0004](../adr/0004-facility-model-single-source-of-truth.md), [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [L0](L0-facility-model.md)

Naming looks like a style question. In this project it is a correctness question: P2 says
simulation and hardware are interchangeable, and **that guarantee is made of names.** A
single name that differs between the two paths breaks it, invisibly, until someone runs on
hardware.

## The scheme

```
/cite/<zone>/<asset_id>/<interface>
```

| Element | Rule | Example |
|---|---|---|
| `cite` | Fixed root. Isolates this system from anything else on the network. | `cite` |
| `<zone>` | Facility zone from the L0 model. `lower_snake_case`. | `cell_a` |
| `<asset_id>` | Unique asset instance from the L0 model. | `arm_1` |
| `<interface>` | Topic, service, or action name. | `joint_states` |

```
/cite/cell_a/arm_1/joint_states
/cite/cell_a/arm_1/joint_trajectory_controller/follow_joint_trajectory
/cite/cell_a/conveyor_1/state
/cite/cell_a/sensor_belt_1_end/detection
```

## Frames

TF frames use the same identity, flattened because TF has no hierarchy:

```
<zone>__<asset_id>__<link>
cell_a__arm_1__link_base
```

Double underscore separates the three parts, so a single-underscore link name is
unambiguous. Frame names are generated with the description; there is never a hand-written
frame string in code.

The facility root frame is `cite_world`, and it is tied to the **surveyed physical origin**
— see [L5](L5-twin-synchronization.md). This is the frame in which a measurement in the
model corresponds to a measurement in the building.

## Prefixes

Every robot instance is generated with `<asset_id>_` prefixing its joints, links, and
controllers:

```
arm_1_joint1 … arm_1_joint5
arm_1_joint_trajectory_controller
```

Two arms of the same type instantiate the same component definition with different
prefixes and never collide.

## The rules that matter

1. **Names are generated, never written twice.** Every name in this scheme derives from the
   L0 model. Writing a name by hand in a second place is a P1 violation, and it is how the
   sim/hardware guarantee breaks.
2. **Simulation and hardware use identical names.** Not similar. Identical. There is no
   `_sim` suffix, no separate namespace, no "simulation variant" of a controller name.
   The `tester` agent verifies this as a standing guarantee.
3. **Controller joint names must match the description exactly.** A mismatch fails at
   runtime with an error naming the spawner rather than the mismatch — one of the most
   time-consuming failures in ROS 2. `model-validator` checks it statically.
4. **`lower_snake_case` throughout.** No hyphens, no camel case, no leading digits.
5. **An asset ID is stable for the life of the asset.** Renaming invalidates every
   recording, every trend, and every historical comparison. Choose carefully once.
6. **Zones partition; they do not nest.** A flat zone list keeps names bounded. If nesting
   is ever genuinely needed, it needs an ADR, because it changes every name in the system.

## Why not per-robot root namespaces

An alternative is `/arm_1/...` with each robot at the root. Rejected for two reasons:
nothing distinguishes this system's topics from anything else on a shared lab network, and
there is nowhere to put facility-level or zone-level state. The `/cite/<zone>/` prefix
costs a few characters and buys both.

## Reserved names

| Name | Purpose |
|---|---|
| `/cite/facility/...` | Facility-scope state that belongs to no single asset |
| `/cite/twin/...` | L5 mode, divergence metrics, registration |
| `/cite/line/...` | L4 line state, throughput, work-piece tracking |
| `cite_world` | The facility root frame, tied to the survey origin |
