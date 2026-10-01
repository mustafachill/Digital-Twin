"""The committed hulls are still hulls of the vendor meshes they name (ADR-0028).

A derived asset that is committed can go stale, and ADR-0028 names exactly what
that costs: *"a stale hull is a collision shape that does not match the arm — a
failure that looks like a planner bug."* Nothing else in this repository would
notice. A vendor bump changes `external/cite.repos`, `./scripts/bootstrap`
re-imports, every gate passes, and the arm collides against the shape of the arm
it used to be.

So this is the check, and it is written as a test rather than as a step in
``./scripts/lint`` for one reason: it needs the **vendor** tree, which exists only
after ``vcs import``. It skips where that tree is absent, so a laptop that could
never build the simulator still runs the rest of the suite — the property
``./scripts/validate-model`` exists to have — and it runs for real in the
container and in CI.

Skipping is a real weakness and is stated rather than hidden: on a machine
without the import this file proves nothing. What stops that being silent is that
the skip names its reason, and that the same comparison is one command away
(``cite-model hulls``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cite_tools import manifest, meshes
from cite_tools.model.loader import load

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "assets" / "manifest.yaml"
VENDOR = REPO_ROOT / "workspace" / "src" / "external" / "xarm_ros2"


def _declared_sets():
    model = load(REPO_ROOT / "model")
    return [
        (asset_type, mesh_set)
        for asset_type in model.types
        if asset_type.description.collision is not None
        for mesh_set in asset_type.description.collision.sets
        if mesh_set.kind == "convex_hull"
    ]


needs_vendor = pytest.mark.skipif(
    not VENDOR.is_dir(),
    reason="the vendor source is not imported here — run ./scripts/bootstrap",
)


class TestTheDeclarationAndTheTreeAgree:
    """Checkable anywhere: what L0 declares against what is committed."""

    def test_the_model_declares_a_derived_set(self) -> None:
        assert _declared_sets(), "no type declares a convex_hull collision set"

    def test_every_declared_mesh_is_committed(self) -> None:
        for asset_type, mesh_set in _declared_sets():
            root = REPO_ROOT / "assets" / mesh_set.root
            for name in mesh_set.meshes:
                assert (root / name).is_file(), f"{asset_type.id}/{mesh_set.id}: {name}"

    def test_the_manifest_records_exactly_the_declared_meshes(self) -> None:
        """A hull with no manifest entry is the failure ADR-0012 names by name."""
        recorded = {
            entry["id"]: {m["path"] for m in entry["meshes"]} for entry in manifest.read(MANIFEST)
        }
        for asset_type, mesh_set in _declared_sets():
            assert recorded[f"{asset_type.id}_{mesh_set.id}"] == set(mesh_set.meshes)

    def test_no_committed_mesh_is_undeclared(self) -> None:
        """The other direction: an asset in the tree that the model never asked for."""
        for _asset_type, mesh_set in _declared_sets():
            root = REPO_ROOT / "assets" / mesh_set.root
            present = {str(p.relative_to(root)) for p in root.rglob("*.stl")}
            assert present == set(mesh_set.meshes)

    def test_every_committed_hull_matches_its_recorded_digest(self) -> None:
        for entry in manifest.read(MANIFEST):
            root = REPO_ROOT / entry["dest"]
            for mesh in entry["meshes"]:
                assert meshes.sha256_of(root / mesh["path"]) == mesh["sha256"], mesh["path"]


@needs_vendor
class TestTheHullsStillMatchTheVendor:
    """The check a vendor bump has to pass. Needs the imported source."""

    def test_the_vendor_file_still_hashes_to_what_was_recorded(self) -> None:
        for entry in manifest.read(MANIFEST):
            source_root = VENDOR / entry["source"]["package"] / entry["source"]["root"]
            for mesh in entry["meshes"]:
                path = source_root / mesh["path"]
                assert path.is_file(), f"vendor mesh has moved or gone: {mesh['path']}"
                assert meshes.sha256_of(path) == mesh["source_sha256"], (
                    f"{mesh['path']}: the vendor mesh changed. Re-derive with "
                    "`./scripts/hulls --write` and review the diff."
                )

    def test_re_deriving_reproduces_the_committed_bytes(self) -> None:
        """Byte-identical, not merely equivalent. ADR-0028 decision 1."""
        for entry in manifest.read(MANIFEST):
            source_root = VENDOR / entry["source"]["package"] / entry["source"]["root"]
            for mesh in entry["meshes"]:
                payload, source_triangles, triangles = meshes.hull_bytes(source_root / mesh["path"])
                assert hashlib.sha256(payload).hexdigest() == mesh["sha256"], mesh["path"]
                assert source_triangles == mesh["source_triangles"]
                assert triangles == mesh["triangles"]

    def test_a_hull_is_smaller_than_what_it_replaces(self) -> None:
        """The claim the whole exercise rests on, checked rather than asserted.

        Not a performance measurement — that needs a running cell — but the
        arithmetic that has to hold before one is worth taking. One entry is
        deliberately allowed to fail it: `end_tool` is the vendor's own collision
        proxy rather than a rendering mesh, so it is already small.
        """
        for entry in manifest.read(MANIFEST):
            rendering = [m for m in entry["meshes"] if not m["path"].startswith("end_tool/")]
            assert rendering, "nothing in this set replaces a rendering mesh"
            for mesh in rendering:
                assert mesh["triangles"] < mesh["source_triangles"], mesh["path"]
