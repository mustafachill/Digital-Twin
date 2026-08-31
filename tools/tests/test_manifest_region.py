"""The derived-asset region of ``assets/manifest.yaml``.

The region is machine-written inside a hand-written file, which is a shape this
project is otherwise hostile to. What makes it acceptable is that the boundary is
exact: everything outside the markers survives untouched. These tests are that
guarantee, plus the two ways the boundary can be lost.

They are also what makes `manifest.py`'s own argument true rather than merely
stated. That module says *"a generated region that a check can falsify is stronger
discipline than a hand-written one that nothing verifies"*, and until 2026-08-31
three of the region's fields could be mutated into a well-formed lie with the whole
suite still passing — `source.version`, which `assets/README.md` calls out as the
thing a derived asset carries and an authored one does not; `bytes`; and
`installed_as`, the URI a consumer would actually use. `TestEveryRecordedFieldIsBound`
below is that half. It runs on the host, without the vendor tree, because the
inputs it compares against — `external/cite.repos`, the committed hulls and the L0
declaration — are all in git.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cite_tools import manifest
from cite_tools.cli import pinned_version
from cite_tools.model.loader import load

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "assets" / "manifest.yaml"


def declared_sets():
    """Every derived collision set the L0 model declares, with its type."""
    model = load(REPO_ROOT / "model")
    return [
        (asset_type, mesh_set)
        for asset_type in model.types
        if asset_type.description.collision is not None
        for mesh_set in asset_type.description.collision.sets
        if mesh_set.kind == "convex_hull"
    ]


SAMPLE = f"""# header comment
version: 1

assets: []

{manifest.BEGIN}
derived:
- id: old
{manifest.END}
# trailing comment
"""


class TestReplacement:
    def test_everything_outside_the_markers_survives(self) -> None:
        updated = manifest.replace(SAMPLE, [{"id": "new"}])
        assert updated.startswith("# header comment\nversion: 1\n\nassets: []\n")
        assert updated.endswith("# trailing comment\n")
        assert "id: new" in updated
        assert "id: old" not in updated

    def test_the_result_is_still_one_valid_document(self) -> None:
        updated = manifest.replace(SAMPLE, [{"id": "new", "sha256": "abc"}])
        document = yaml.safe_load(updated)
        assert document["assets"] == []
        assert document["derived"] == [{"id": "new", "sha256": "abc"}]

    def test_replacing_twice_is_idempotent(self) -> None:
        once = manifest.replace(SAMPLE, [{"id": "new"}])
        assert manifest.replace(once, [{"id": "new"}]) == once

    def test_an_empty_list_clears_the_region(self) -> None:
        updated = manifest.replace(SAMPLE, [])
        assert yaml.safe_load(updated)["derived"] == []


class TestTheMarkersAreRequired:
    @pytest.mark.parametrize(
        "text",
        [
            "version: 1\n",
            f"{manifest.BEGIN}\nderived: []\n",
            f"{manifest.END}\n{manifest.BEGIN}\n",
        ],
        ids=["absent", "no-end", "reversed"],
    )
    def test_a_missing_or_reversed_marker_is_an_error(self, text: str) -> None:
        with pytest.raises(manifest.ManifestError):
            manifest.split(text)


class TestTheRealManifest:
    """The shipped file, because the shape is only useful if it holds there."""

    def test_it_carries_the_markers(self) -> None:
        manifest.split(MANIFEST.read_text())

    def test_the_fetcher_still_sees_an_assets_key(self) -> None:
        """`scripts/fetch-assets` reads `assets`, and the region must not disturb it."""
        document = yaml.safe_load(MANIFEST.read_text()) or {}
        assert "assets" in document

    def test_every_derived_entry_names_its_source_pin(self) -> None:
        """Provenance without a version is not provenance (ADR-0012)."""
        for entry in manifest.read(MANIFEST):
            version = entry["source"]["version"]
            assert len(version) == 40, f"{entry['id']}: source is not pinned to a SHA"

    def test_every_derived_mesh_carries_both_digests(self) -> None:
        for entry in manifest.read(MANIFEST):
            for mesh in entry["meshes"]:
                assert len(mesh["sha256"]) == 64
                assert len(mesh["source_sha256"]) == 64


class TestEveryRecordedFieldIsBound:
    """Each of these was mutable into a well-formed lie until 2026-08-31.

    The shape of the hole is worth keeping in view: the region *had* checks, and
    every one of them checked a field's **form** rather than its **value**. A
    forty-character hexadecimal string that is not the pinned commit passes a
    length assertion, and a plausible byte count passes nothing at all. A check
    that cannot be falsified by a well-formed wrong answer is documentation.
    """

    def test_the_recorded_source_version_is_the_pin(self) -> None:
        """`source.version` against `external/cite.repos`, read the same way.

        This is the field `assets/README.md` names as what makes a derived asset
        different from an authored one — *"the file it came from, the commit that
        file is pinned at, and what both hash to"*. It is also the one a vendor
        bump moves: raising the pin without re-running `./scripts/hulls` leaves a
        hull of the arm the project used to have, carrying a commit it was never
        derived from, and ADR-0028 names that as a failure that presents as a
        planner bug.
        """
        for entry in manifest.read(MANIFEST):
            repo = Path(entry["source"]["repo"]).name
            assert entry["source"]["version"] == pinned_version(REPO_ROOT, repo), (
                f"{entry['id']}: the manifest records a commit that "
                f"external/cite.repos does not pin. Re-run ./scripts/hulls --write."
            )

    def test_every_recorded_byte_count_is_the_file_size(self) -> None:
        """`bytes` against the committed file, which is the only thing it can mean."""
        for entry in manifest.read(MANIFEST):
            root = REPO_ROOT / entry["dest"]
            for mesh in entry["meshes"]:
                path = root / mesh["path"]
                assert path.is_file(), f"{entry['id']}: {mesh['path']} is not committed"
                assert path.stat().st_size == mesh["bytes"], mesh["path"]

    def test_the_recorded_uri_is_the_one_the_model_binds(self) -> None:
        """`installed_as` against the L0 set it describes.

        A consumer reading provenance out of the manifest and a description
        emitted from L0 must name the same thing. Nothing compared them, so the
        manifest could have advertised a URI that resolved to nothing while every
        gate stayed green.
        """
        recorded = {entry["id"]: entry for entry in manifest.read(MANIFEST)}
        for asset_type, mesh_set in declared_sets():
            entry = recorded[f"{asset_type.id}_{mesh_set.id}"]
            assert entry["installed_as"] == f"package://{mesh_set.package}/{mesh_set.root}"
            assert entry["dest"] == f"assets/{mesh_set.root}"
            assert entry["source"]["package"] == mesh_set.source_package
            assert entry["source"]["root"] == mesh_set.source_root
