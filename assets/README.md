# assets/ — 3D assets and the scan pipeline

## Storage policy

Three tiers, because a 2 GB raw scan and a 400 KB collision mesh do not belong
in the same place.

| Tier | What | Where | In git |
|---|---|---|---|
| **Raw capture** | Photogrammetry and LiDAR output, unprocessed | Google Drive + lab local disks | No — recorded in `manifest.yaml` |
| **Working files** | Intermediate cleanup, registration, decimation | Local disk, `assets/scans/work/` | No — gitignored |
| **Simulator assets** | Decimated visual meshes, simplified collision geometry, materials | `assets/meshes/`, `assets/materials/` | **Yes** |

The rule that matters: **git holds what the simulator loads, and a record of
where everything else came from.** A fresh clone plus `./scripts/fetch-assets`
must be enough to reproduce a working scene.

### How a simulator asset is reached at runtime

The simulator and the planner load a mesh by URI, and a URI names a package.
[`cite_description`](../workspace/src/cite_description/README.md) installs
`assets/meshes` into `share/cite_description/meshes`, so a mesh here is reachable
as `package://cite_description/meshes/<path>` or
`file://$(find cite_description)/meshes/<path>`. It is the **only** package
permitted to install from this directory: two would make "where an asset lives"
and "how an asset is reached" two different answers.

## Derived assets

Some simulator assets are not captured or authored — they are **derived** from a
dependency this repository pins. The convex-hull collision meshes
([ADR-0028](../docs/adr/0028-convex-hull-collision-meshes.md)) are the first:
each one is the convex hull of a vendor mesh from the `xarm_ros2` commit
`external/cite.repos` names.

A derived asset is committed like any other simulator asset, and it carries one
thing an authored asset does not: **the file it came from, the commit that file
is pinned at, and what both hash to**. That lives in the `derived:` section of
`manifest.yaml`, which is written by

```bash
./scripts/enter dev python3 -m cite_tools.cli hulls --model model --write
```

and checked, without writing, by the same command without `--write`.

**Why the provenance is not optional here.** A derived asset can go stale in a
way an authored one cannot: a vendor bump changes the source, every gate passes,
and the tree still holds a hull of the arm the project used to have — a collision
shape that does not match the robot, which presents as a planner bug. The digests
are what make that state detectable. `tools/tests/test_hulls_match_the_vendor.py`
runs the comparison wherever the vendor source is imported.

**The `derived:` section is machine-written.** Everything above its markers in
`manifest.yaml` is hand-written and is preserved untouched; the region between
them is replaced whole. Sixty checksums maintained by hand is a discipline that
fails silently, which is the weakness ADR-0012 already names.

## Why a manifest instead of Git LFS

Raw scans are write-once and rarely re-fetched — the working set is the
processed meshes, which are small. Paying LFS bandwidth and quota to version
data nobody re-downloads buys little. The manifest keeps provenance and
integrity (source URL plus SHA-256) without putting gigabytes behind every
clone.

The cost is honest: **the manifest is only as good as its discipline.** An asset
used in a scene but absent from `manifest.yaml` is unreproducible, and nothing
outside review will catch it. Every raw capture gets an entry, at capture time,
with its checksum.

## Pipeline

```
capture  →  register  →  clean  →  decimate  →  split visual/collision  →  material  →  SDF
  Drive        work/      work/      work/            assets/meshes/                    model/
```

Two representations, always separate:

- **Visual** — may be dense; it only has to look right.
- **Collision** — primitives or convex hulls, never the visual mesh reused. A
  dense mesh used for collision is the most reliable way to destroy Gazebo's
  real-time factor and to produce contact behaviour nobody can explain. The
  `model-validator` agent rejects it.

  **The three arms do exactly this today, deliberately.** For the xArm variant
  this project models the vendor's own collision directory *is* its visual
  directory, so twelve links per arm collide against a rendering mesh. Hulls of
  all thirteen collision meshes are derived and committed below, and the L0 model
  can select them per robot type — but the shipped default is still the vendor's,
  because ADR-0028's promotion gate requires the friction-grasp campaign re-run
  against hull geometry first. This paragraph says what the tree does, not what
  the rule above wishes it did (P7).

## Registration

Scanned geometry is registered to the same coordinate frame as the engineered
assets, so a measurement taken in the model matches a measurement taken in the
building. Record the survey reference used for each capture in its manifest
entry — without it, a scan is decoration rather than a twin.
