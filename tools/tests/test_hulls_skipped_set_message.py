"""A skipped hull set must not produce a message naming a destructive remedy.

ADR-0028 recorded this as residual **R-09** for one cause and it has two. When a
declared `convex_hull` set is skipped, it contributes no entry, so
`manifest.replace(text, entries)` derives the manifest's machine-written region
**with that set deleted from it**, which cannot equal the committed file. The
check form then emitted a second error saying the derived region did not match
and to run `--write` — and `--write` is what would have erased the region that
message named.

**Nothing was ever lost**, because the `problems` guard precedes the write. What
was wrong is that the message told a reader to do the destructive thing, and it
fired on the ordinary state of a checkout nobody has bootstrapped, which is the
first state a new contributor is in.

**R-09 was recorded as the missing-vendor-tree case and is broader than that.**
It was reproduced on a stale checkout where the vendor tree was present and
`scipy` was absent: the set was skipped inside `_hull_set` instead of before it,
and the same wrong second message appeared from a different cause. So the guard
is on *a set produced no entry*, for any reason, and both routes into that state
are exercised below.

The last test is the anti-vacuous half, and it is the one that matters most: a
guard that suppresses a comparison is indistinguishable from a guard that deleted
it, unless something still shows the comparison firing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import typer

from cite_tools import cli, manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR = REPO_ROOT / "workspace" / "src" / "external" / "xarm_ros2"

#: The message the fix removes from every skipped-set run, and its remedy. Matched
#: as substrings of the flattened output rather than by equality, because Rich
#: wraps to the terminal width and a literal here would be checking the wrap.
REGION_COMPLAINT = "derived region does not match the meshes on disk"
DESTRUCTIVE_REMEDY = "hulls --write"

needs_vendor = pytest.mark.skipif(
    not VENDOR.is_dir(),
    reason="the vendor source is not imported here — run ./scripts/bootstrap",
)


def _flat(text: str) -> str:
    """Rich wraps at the terminal width; the assertions are about words."""
    return " ".join(text.split())


def _repo(tmp_path: Path) -> Path:
    """A repository root carrying everything the hull command reads but the vendor.

    `model/` and `assets/` are copied rather than pointed at, so a `--write` that
    got through would damage a copy and the real manifest stays available as the
    thing to compare against.
    """
    shutil.copytree(REPO_ROOT / "model", tmp_path / "model")
    shutil.copytree(REPO_ROOT / "assets", tmp_path / "assets")
    (tmp_path / "external").mkdir()
    shutil.copy(REPO_ROOT / "external" / "cite.repos", tmp_path / "external" / "cite.repos")
    return tmp_path


def _run(repo: Path, capsys, *, write: bool = False) -> tuple[int, str]:
    """The command, its exit code, and its two streams flattened together."""
    code = 0
    try:
        cli.hulls(model=repo / "model", write=write)
    except typer.Exit as exit_:
        code = exit_.exit_code
    captured = capsys.readouterr()
    return code, _flat(captured.out + " " + captured.err)


class TestASkippedSetSaysNothingAboutTheManifest:
    """Both routes into a skip, and the same requirement of each."""

    def test_a_missing_vendor_tree_produces_one_message_and_not_two(
        self, tmp_path: Path, capsys
    ) -> None:
        """R-09 as recorded: the ordinary state of a checkout nobody bootstrapped."""
        code, output = _run(_repo(tmp_path), capsys)

        assert code == 1
        assert "the vendor meshes are not in this checkout" in output
        assert "Run ./scripts/bootstrap" in output
        assert REGION_COMPLAINT not in output
        assert "region was not checked" in output

    def test_a_set_that_fails_mid_derivation_is_also_a_skip(self, tmp_path: Path, capsys) -> None:
        """R-09 as reproduced: the vendor tree is there and the set still fails.

        The declared meshes are absent from a directory that exists, which is the
        route `_hull_set` raises through — the same route `scipy` missing takes.
        """
        repo = _repo(tmp_path)
        model = cli.load(repo / "model")
        mesh_set = next(
            mesh_set
            for asset_type in model.types
            if asset_type.description.collision is not None
            for mesh_set in asset_type.description.collision.sets
            if mesh_set.kind == "convex_hull"
        )
        assert mesh_set.source_package and mesh_set.source_root
        source_root = (
            repo / "workspace" / "src" / "external" / "xarm_ros2" / mesh_set.source_package
        ) / mesh_set.source_root
        source_root.mkdir(parents=True)

        code, output = _run(repo, capsys)

        assert code == 1
        assert "declared collision mesh is missing" in output
        assert "the vendor meshes are not in this checkout" not in output
        assert REGION_COMPLAINT not in output
        assert "region was not checked" in output

    def test_the_note_does_not_send_the_reader_to_write(self, tmp_path: Path, capsys) -> None:
        """The whole point of R-09: no remedy that would erase what it names."""
        _, output = _run(_repo(tmp_path), capsys)

        assert f"run `./scripts/{DESTRUCTIVE_REMEDY}`" not in output
        assert f"run `cite-model {DESTRUCTIVE_REMEDY}`" not in output
        assert "do not run --write to make it agree" in output

    def test_write_refuses_and_leaves_the_manifest_byte_identical(
        self, tmp_path: Path, capsys
    ) -> None:
        """The destructive path, refused on the skip itself rather than by luck."""
        repo = _repo(tmp_path)
        before = (repo / "assets" / "manifest.yaml").read_bytes()

        code, output = _run(repo, capsys, write=True)

        assert code == 1
        assert (repo / "assets" / "manifest.yaml").read_bytes() == before
        assert "wrote" not in output


@needs_vendor
class TestTheComparisonStillFiresWhenNothingIsSkipped:
    """Anti-vacuous. A suppressed comparison and a deleted one look alike."""

    def test_a_corrupted_region_is_still_caught_and_names_the_script(
        self, tmp_path: Path, capsys
    ) -> None:
        repo = _repo(tmp_path)
        external = repo / "workspace" / "src" / "external"
        external.mkdir(parents=True)
        (external / "xarm_ros2").symlink_to(VENDOR, target_is_directory=True)

        manifest_path = repo / "assets" / "manifest.yaml"
        entries = manifest.read(manifest_path)
        entries[0]["meshes"][0]["triangles"] += 1
        manifest_path.write_text(manifest.replace(manifest_path.read_text(), entries))

        code, output = _run(repo, capsys)

        assert code == 1
        assert REGION_COMPLAINT in output
        assert "run `./scripts/hulls --write`" in output
        assert "region was not checked" not in output
