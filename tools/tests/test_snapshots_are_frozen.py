"""The frozen snapshots under `projects/` are frozen by a check, not only by a rule.

ADR-0068 calls each snapshot a record: it changes only by a patch its `PROVENANCE.md`
lists. Until this test, nothing noticed an edit that was not listed — the main tree's
checks skip `projects/` on purpose, and a snapshot's own checks are outside its contract.
`projects/snapshots.yaml` now pins each folder's committed git tree hash, and this test
fails when the committed tree differs, so a change to a record needs a hash bump in the
same commit and is visible in review. How to bump it is in the manifest's header.

It also holds the manifest to the folders on disk and to the one fact of each snapshot
that the main tree acts on, its image tag, so the workflow matrix read from it cannot
name a snapshot that is not there or build under a tag the snapshot does not use.

The hash is read from `HEAD`, so it judges what is committed: an uncommitted edit is not
a change to the record yet. It needs a git checkout, and says so rather than passing
silently where there is none.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS = REPO_ROOT / "projects"
MANIFEST = PROJECTS / "snapshots.yaml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "projects.yml"


def _snapshots() -> list[dict]:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["snapshots"]


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


def _committed_tree(name: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", f"HEAD:projects/{name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"projects/{name} is not in HEAD: {result.stderr.strip()}"
    return result.stdout.strip()


def test_the_manifest_lists_exactly_the_snapshot_folders() -> None:
    listed = sorted(entry["name"] for entry in _snapshots())
    on_disk = sorted(path.name for path in PROJECTS.iterdir() if path.is_dir())
    assert listed == on_disk


@pytest.mark.skipif(
    not _in_a_git_checkout(),
    reason="a snapshot's tree hash is read from git, and this is not a git checkout",
)
@pytest.mark.parametrize("entry", _snapshots(), ids=lambda entry: entry["name"])
def test_a_snapshot_is_byte_identical_to_its_pinned_tree(entry: dict) -> None:
    actual = _committed_tree(entry["name"])
    assert actual == entry["tree"], (
        f"projects/{entry['name']} has changed: its committed tree is {actual}, and "
        f"projects/snapshots.yaml pins {entry['tree']}. A snapshot is a record (ADR-0068). "
        "If the change is a patch listed in its PROVENANCE.md, or a row in its verification "
        "log, bump `tree` in the manifest to the value above in the same commit; otherwise "
        "revert the change."
    )


@pytest.mark.parametrize("entry", _snapshots(), ids=lambda entry: entry["name"])
def test_the_manifest_names_the_image_the_snapshot_builds(entry: dict) -> None:
    compose = PROJECTS / entry["name"] / "infra" / "docker" / "docker-compose.yml"
    text = compose.read_text(encoding="utf-8")
    assert f"image: {entry['image']}\n" in text


def test_the_workflow_takes_its_matrix_from_the_manifest() -> None:
    """A second list of the snapshots in the workflow is the one that would drift."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "projects/snapshots.yaml" in workflow
    assert "fromJSON(needs.matrix.outputs.snapshots)" in workflow
    for entry in _snapshots():
        assert entry["name"] not in workflow, f"{entry['name']} is restated in {WORKFLOW.name}"
