# cite_description

**Status:** `PARTIAL` — it installs one asset set, the convex-hull collision
meshes for `xarm5` (ADR-0028). Nothing selects them by default.

L1. The project's own description assets, installed so a simulator or a planner
can reach them by URI. No code, no node, no launch file.

## What is in it

Nothing, on disk. The files live in [`assets/`](../../../assets/README.md) at the
repository root, which is where ADR-0012's storage policy puts simulator assets
and where their provenance is recorded; this package installs `assets/meshes`
into `share/cite_description/meshes` so that

```
file://$(find cite_description)/meshes/collision/xarm5/convex_hull
package://cite_description/meshes/collision/xarm5/convex_hull
```

both resolve. It is the only package permitted to install from `assets/`.

## What belongs here

The admission test is in `package.xml` and is not repeated here. In short:
geometry or material, ours or derived here from a pinned dependency, and **not**
generated from the L0 model — everything that is generated lives in
`cite_generated`, whole (ADR-0021).

## How the hulls get there

They are derived from the vendor meshes `external/cite.repos` pins, by

```bash
./scripts/hulls --write
```

and checked, without writing, by the same command with no `--write`. The check
re-derives every mesh and compares byte for byte, so a hull that no longer
matches the vendor file it names is a failure rather than a silence. It runs from
the host and from `./scripts/enter dev` alike. See
[ADR-0028](../../../docs/adr/0028-convex-hull-collision-meshes.md).

## How it fails

- **A mesh is declared in L0 and absent from `assets/`.** The collision reference
  resolves to nothing once the root is substituted, and Gazebo warns and
  simulates a body with no collision geometry. `test/` catches this at build
  time; `cite-model hulls` catches it against the vendor tree.
- **`assets/meshes` is missing entirely.** Configure-time `FATAL_ERROR`, rather
  than an install that silently contains nothing.
- **A hull is stale against a vendor bump.** Two things notice, and this entry
  named neither of them until 2026-08-31. `tools/tests/test_hulls_match_the_vendor.py`
  is the one that has always run — it re-derives every declared mesh from the
  imported vendor tree and compares, and it skips, naming its reason, where that
  tree is absent. `./scripts/hulls` is the same comparison plus the manifest
  region, and it is a step in `./scripts/lint` under the same condition. This
  entry credited `cite-model hulls` and said "nothing else notices"; the test was
  what noticed, and the command was in no gate at all.
