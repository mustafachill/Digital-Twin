# Naming and namespaces

- **Status:** `PARTIAL` — the generator exists and forms every name, with one exception
  documented under "Frames" below.
  **Built:** `tools/cite_tools/model/ids.py` is the single place a name is formed, and
  `./scripts/scenario bringup` asserts the result — controller and joint names, the
  `/cite/facility/` scope, and station frames resolving against the world.
  **In use:** `/cite/facility/` (model version, frames) on every bring-up, and `/cite/twin/`
  (mode, divergence, one action endpoint per skill, the belt and track operator endpoints)
  whenever the pair supervisor starts the twin boundary; a `cite_twin` test asserts that no L5
  name collides with a name a side owns. `/cite/line/` is reserved and unused.
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
| `<zone>` | Facility zone from the L0 model. `lower_snake_case`. | `cell_b` |
| `<asset_id>` | Unique asset instance from the L0 model. | `picker` |
| `<interface>` | Topic, service, or action name. | `joint_states` |

```
/cite/cell_b/picker/joint_states
/cite/cell_b/picker/picker_joint_trajectory_controller/follow_joint_trajectory
/cite/cell_b/transfer_belt/state
/cite/cell_b/infeed_beam/detection
```

These are read from `workspace/src/cite_generated/bringup/cell_b_plan.yaml`, the plan of the
one zone L0 declares.
Note that the controller name carries the instance prefix too — see *Prefixes* below.

## Frames

There are **two** frame forms, and which one applies depends on where the frame comes from.
Both are formed in `tools/cite_tools/model/ids.py` and neither is ever written by hand.

**Frames the model declares** — a conveyor's infeed, a table's surface —
use the full identity, flattened because TF has no hierarchy:

```
<zone>__<asset_id>__<link>          ids.frame()
cell_b__transfer_belt__infeed
cell_b__infeed_table__surface
```

Double underscore separates the three parts, so a single-underscore link name is
unambiguous.

**Links inside a robot description** carry the instance prefix instead, because the link
names are the vendor's and the description is invoked rather than ingested (L1):

```
<asset_id>_<link>                   ids.link()
picker_link_base
picker_link_tcp
picker_mount
```

The distinction is not cosmetic and it is not optional: a URDF's link names are what
`robot_state_publisher` broadcasts, and rewriting them to the three-part form would mean
editing the vendor description, which P1 and L1 both forbid. A frame name in this system is
therefore either `<zone>__<asset_id>__<link>` or `<asset_id>_<link>`, and reading one form
where the other applies is a `frame does not exist` at runtime.

The facility root frame is `cite_world`, and it is tied to the **surveyed physical origin**
— see [L5](L5-twin-synchronization.md). This is the frame in which a measurement in the
model corresponds to a measurement in the building.

## Prefixes

Every robot instance is generated with `<asset_id>_` prefixing its joints, links, and
controllers:

```
picker_joint1 … picker_joint5
picker_joint_trajectory_controller
```

The track is prefixed the same way (`picker_track_trajectory_controller`). Two arms of the
same type instantiate the same component definition with different
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

An alternative is `/picker/...` with each robot at the root. Rejected for two reasons:
nothing distinguishes this system's topics from anything else on a shared lab network, and
there is nowhere to put facility-level or zone-level state. The `/cite/<zone>/` prefix
costs a few characters and buys both.

## Reserved names

| Name | Purpose |
|---|---|
| `/cite/facility/...` | Facility-scope state that belongs to no single asset |
| `/cite/twin/...` | L5 mode, divergence metrics, registration |
| `/cite/line/...` | Reserved for line-level state (charter §5's L4); **unused in the main tree** ([ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)) |
| `cite_world` | The facility root frame, tied to the survey origin |

**The first three are FACILITY-SINGULAR, and that is what bounds a deployment to one
zone.** They are deliberately not zone-scoped: there is one `/cite/facility/get_model_version`
and one `/cite/twin/mode`, whichever cell is running. Meanwhile `ROS_DOMAIN_ID` is derived per
checkout and per *side* and never per zone
([ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md)), so two zones started from
one checkout would share one ROS graph and one set of these names. L0 declares one zone, so
**exactly one zone is up at a time** holds trivially; a second zone would have to answer this
first, and zone-scoping these names changes every name in the system, which rule 6 already
says needs an ADR. What would collide: two servers on `/cite/facility/get_model_version`, two
`/robot_description` publishers describing **different robots**, and two `/clock` publishers
from two independent simulators — the mixed-time system CLAUDE.md §10 warns about.
`cite_facility/occupancy.py` refuses a second zone on one graph and documents what it cannot
see.
