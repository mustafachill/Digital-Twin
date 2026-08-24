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

## Registration

Scanned geometry is registered to the same coordinate frame as the engineered
assets, so a measurement taken in the model matches a measurement taken in the
building. Record the survey reference used for each capture in its manifest
entry — without it, a scan is decoration rather than a twin.
