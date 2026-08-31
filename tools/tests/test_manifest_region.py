"""The derived-asset region of ``assets/manifest.yaml``.

The region is machine-written inside a hand-written file, which is a shape this
project is otherwise hostile to. What makes it acceptable is that the boundary is
exact: everything outside the markers survives untouched. These tests are that
guarantee, plus the two ways the boundary can be lost.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cite_tools import manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "assets" / "manifest.yaml"

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
