# ADR-0012: Store large assets by manifest, not Git LFS

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** `assets/README.md`, `assets/manifest.yaml`, charter §8 (Phase 3)

## Context

Phase 3 3D-scans the CITE facility. Raw photogrammetry and LiDAR output is gigabyte-scale
per capture. The simulator loads none of it directly — it loads decimated visual meshes and
simplified collision geometry derived from it, which are small.

The decision must be made before capture begins. Removing large binaries from git history
afterwards means rewriting history for everyone.

## Options considered

### Option A — Commit raw scans directly
Rejected without discussion. Every clone downloads every version of every scan, forever.

### Option B — Git LFS
Content stored separately, `git clone` works normally, versioning automatic, no extra
tooling for contributors. Rejected on cost-benefit: raw scans are write-once and rarely
re-fetched — the working set is the processed meshes. Paying LFS quota and bandwidth to
version data almost nobody re-downloads buys little, and GitHub LFS quotas become a
recurring administrative problem for an academic centre.

### Option C — External storage plus a manifest
Raw captures live in Google Drive and on lab local disks. The repository holds
`assets/manifest.yaml` — source URL, SHA-256, destination, capture date, survey reference
— plus the processed meshes the simulator actually loads. `./scripts/fetch-assets` pulls
what is missing and verifies checksums. Chosen.

## Decision

Three tiers:

| Tier | Where | In git |
|---|---|---|
| Raw capture | Google Drive + lab local disks | No — recorded in `manifest.yaml` |
| Working files | Local disk, `assets/scans/work/` | No — gitignored |
| Simulator assets | `assets/meshes/`, `assets/materials/` | **Yes** |

**Git holds what the simulator loads, and a record of where everything else came from.**
A fresh clone plus `./scripts/fetch-assets` must reproduce a working scene.

## Consequences

### What this gets us
- A small repository and fast clones.
- Provenance and integrity preserved: source, checksum, capture date, and the survey
  reference used for registration.
- No LFS quota, and no per-contributor LFS setup.

### What this costs us
- **The manifest is only as good as the discipline behind it.** An asset used in a scene
  but absent from the manifest is unreproducible, and nothing outside code review will
  catch it. This is a genuine weakness of this option compared to LFS, and it is stated
  plainly rather than minimised: every raw capture gets an entry, at capture time, with its
  checksum.
- Google Drive is not designed for programmatic fetching. Large files need confirmation
  handling, and links break when someone reorganises a shared folder.
- Raw captures are not versioned. Re-processing a scan replaces rather than revises, so
  the manifest entry must record enough to reproduce the processing.
- Access depends on Drive permissions, which is one more thing that can be wrong for a new
  contributor.

### What we will have to revisit
If raw scans start being edited iteratively rather than captured once, versioning becomes
worth paying for and Git LFS or DVC becomes the better answer. Revisit if the manifest is
found to be missing entries more than once — that is evidence the discipline is not
holding.
