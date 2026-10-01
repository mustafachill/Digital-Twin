"""The main tree names a snapshot's path only where it documents or runs the snapshot.

ADR-0068 decision 3 is one-way: the main tree never imports or builds from `projects/`,
and nothing is copied from there back into it. The first half has a mechanical shadow —
code that reaches into a snapshot has to name `projects/<name>/` — and this test catches
it: no tracked file outside `projects/` may name a snapshot's path, except the files whose
job is to describe or run the snapshots, listed below by exact path.

**The second half cannot be checked this way, and this test does not pretend to.** A value
or a function copied out of a snapshot carries no trace of where it came from, so copy-back
is caught by review and by the rule, not here. ADR-0068 says so too.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Files that describe, run or guard the snapshots, and so name their paths. Adding one
#: here is a statement, in review, that the file documents a snapshot rather than uses it.
ALLOWED = frozenset(
    {
        "CLAUDE.md",
        "README.md",
        "docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md",
        "docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md",
        "docs/operations/bring-up.md",
        "tools/snapshot_project.sh",
        "tools/tests/test_snapshots_are_left_out.py",
        "tools/tests/test_nothing_reaches_into_a_snapshot.py",
    }
)


def _tracked_outside_projects() -> list[str]:
    if shutil.which("git") is None:
        pytest.skip("the tracked-file list comes from git, which is not installed")
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        pytest.skip("the tracked-file list comes from git, and this is not a git checkout")
    names = [name for name in listed.stdout.decode().split("\0") if name]
    return [name for name in names if not name.startswith("projects/")]


def _snapshot_path_pattern() -> re.Pattern[str]:
    manifest = yaml.safe_load((REPO_ROOT / "projects" / "snapshots.yaml").read_text())
    names = "|".join(re.escape(entry["name"]) for entry in manifest["snapshots"])
    return re.compile(rf"projects/({names})\b")


def test_no_main_tree_file_names_a_snapshot_path_outside_the_allowlist() -> None:
    pattern = _snapshot_path_pattern()
    offenders = []
    for name in _tracked_outside_projects():
        if name in ALLOWED:
            continue
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(name)
    assert offenders == [], (
        "these files name a snapshot's path, and the main tree may not build from or import "
        f"a snapshot (ADR-0068 decision 3): {offenders}. If one only documents a snapshot, "
        "add it to ALLOWED in this test."
    )


def test_the_allowlist_names_only_files_that_exist() -> None:
    """A stale entry is a hole: a new file at that path would be exempt without review."""
    missing = sorted(name for name in ALLOWED if not (REPO_ROOT / name).is_file())
    assert missing == []


def test_every_allowlisted_file_names_a_snapshot_path() -> None:
    """An entry whose file names no snapshot is an exemption nobody needs, and a hole."""
    pattern = _snapshot_path_pattern()
    unused = sorted(
        name
        for name in ALLOWED
        if not pattern.search((REPO_ROOT / name).read_bytes().decode("utf-8", errors="ignore"))
    )
    assert unused == []


def test_the_pattern_catches_a_reach_into_a_snapshot() -> None:
    pattern = _snapshot_path_pattern()
    assert pattern.search("sys.path.insert(0, 'projects/02-fixed-program-pair/tools')")
    assert not pattern.search("projects/README.md")
    assert not pattern.search("projects/02-fixed-program-pairing")
