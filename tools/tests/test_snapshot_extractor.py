"""`tools/snapshot_project.sh` extracts a commit minus exactly the paths it names.

ADR-0068 decision 1: a snapshot is `git archive <commit>` of the whole tree, minus a
fixed list of paths. Every snapshot's `PROVENANCE.md` names that script as the command
that produced it, so a reviewer can re-run it and diff. These tests extract `HEAD` into a
temporary directory and check the list from both sides — every excluded path is absent, a
path beside each exclusion is present — and that the script refuses to extract over
something already there, which is what keeps a snapshot from being the union of two
commits.

`HEAD` rather than a milestone's source commit, because a CI checkout may be shallow and
carry no other commit; `HEAD` carries every excluded path this list needs, `projects/` and
`.github/` included.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "snapshot_project.sh"


def _in_a_git_checkout() -> bool:
    if shutil.which("git") is None:
        return False
    probe = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "--quiet", "HEAD^{commit}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _in_a_git_checkout(),
    reason="the extractor reads git's object database, and this is not a git checkout",
)

#: Excluded at the top level. Each is tracked at HEAD, so its absence is the script's doing.
EXCLUDED = (
    "docs/measurements",
    "CLAUDE.md",
    "AGENTS.md",
    "what-we-are-doing.md",
    "projects",
    ".github",
)

#: Beside each exclusion, and must survive it.
KEPT = (
    "docs/adr",
    "docs/README.md",
    "README.md",
    "scripts/_lib.sh",
    "model",
    "tools/snapshot_project.sh",
    "workspace/src",
)


def _extract(dest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), "HEAD", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )


def _tracked(path: str) -> bool:
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "--name-only", "HEAD", "--", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(listed.stdout.strip())


@pytest.fixture(scope="module")
def extract(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("snapshot") / "out"
    result = _extract(dest)
    assert result.returncode == 0, result.stderr
    return dest


@pytest.mark.parametrize("path", EXCLUDED)
def test_an_excluded_path_is_absent(extract: Path, path: str) -> None:
    assert _tracked(path), f"{path} is not tracked at HEAD, so this case proves nothing"
    assert not (extract / path).exists(), f"{path} was extracted and should not have been"


@pytest.mark.parametrize("path", KEPT)
def test_a_path_beside_the_exclusions_is_extracted(extract: Path, path: str) -> None:
    assert (extract / path).exists(), f"{path} was left out and should not have been"


def test_the_workspace_log_exclusion_is_anchored(extract: Path) -> None:
    """Only `workspace/log` is runtime output; a `log` directory elsewhere is source."""
    assert not (extract / "workspace" / "log").exists()


def test_a_non_empty_destination_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "taken"
    dest.mkdir()
    (dest / "already-here").write_text("x\n")
    result = _extract(dest)
    assert result.returncode != 0
    assert "not empty" in result.stderr
    assert sorted(p.name for p in dest.iterdir()) == ["already-here"]


def test_an_existing_file_is_refused_as_not_a_directory(tmp_path: Path) -> None:
    dest = tmp_path / "a-file"
    dest.write_text("")
    result = _extract(dest)
    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_an_empty_directory_is_accepted(tmp_path: Path) -> None:
    dest = tmp_path / "empty"
    dest.mkdir()
    result = _extract(dest)
    assert result.returncode == 0, result.stderr
    assert (dest / "scripts" / "_lib.sh").is_file()
