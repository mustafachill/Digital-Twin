"""The link checker's remit: whose Markdown it walks, and whose it must not.

`workspace/src/external/` is the vendor tree `./scripts/bootstrap` imports from
`external/cite.repos`. Walking it made the checker's answer depend on whether
`vcs import` had run: 100 Markdown files with the tree imported against 88
without it, same commit, same command, twelve vendor files between them. A gate
whose result is a property of the machine rather than of the commit is not a
gate.

The second reason is a risk rather than a measurement, and is recorded as such.
ADR-0008 pins and patches vendor source and never hand-corrects it, so a dead
link inside `xarm_ros2` would fail our lint for a file no commit of ours may
repair — and a gate that fails on something nobody can fix is one people learn
to ignore. On the day this was written none of the twelve had a dead link.

The fix has a trap in it, which is why these tests exist rather than an assertion
on a constant. `SKIP_DIRS` matches path *parts*, so a bare `"external"` entry also
silences the top-level `external/` — and that directory is ours.
`external/patches/README.md` links to ADR-0008 and to the v1 lessons, and those are
exactly the links this checker exists to keep alive. So the tests below pin the
behaviour from both sides: the vendor tree is not walked, and our own `external/`
still is.
"""

from __future__ import annotations

from pathlib import Path

from cite_tools.doclinks import check, markdown_files

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Where `./scripts/bootstrap` puts the vendored ROS source.
VENDOR_TREE = "workspace/src/external"

#: A relative link with no target. Any walked file containing it is reported.
DEAD_LINK = "# Title\n\nSee [the manual](nowhere.md).\n"


def _write(root: Path, relative: str, body: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_vendor_markdown_is_not_walked(tmp_path: Path) -> None:
    vendor_readme = _write(tmp_path, f"{VENDOR_TREE}/xarm_ros2/ReadMe.md", DEAD_LINK)
    _write(tmp_path, "docs/ours.md", "# Ours\n")

    assert vendor_readme not in markdown_files(tmp_path)
    assert check(tmp_path) == []


def test_vendor_presence_does_not_change_the_file_count(tmp_path: Path) -> None:
    """The count must be a property of the commit, not of whether bootstrap ran."""
    _write(tmp_path, "docs/ours.md", "# Ours\n")
    before = len(markdown_files(tmp_path))

    _write(tmp_path, f"{VENDOR_TREE}/xarm_ros2/ReadMe.md", "# Vendor\n")
    _write(tmp_path, f"{VENDOR_TREE}/xarm_ros2/xarm_api/README.md", "# Vendor\n")

    assert len(markdown_files(tmp_path)) == before


def test_our_own_external_directory_is_still_walked(tmp_path: Path) -> None:
    """The skip is anchored to the vendor path, not to the name `external`."""
    ours = _write(tmp_path, "external/patches/README.md", DEAD_LINK)

    assert ours in markdown_files(tmp_path)
    assert check(tmp_path) == ["external/patches/README.md: dead link -> nowhere.md"]


def test_repository_patches_readme_is_within_the_checkers_remit() -> None:
    """Guards the real file the anchoring decision was made for."""
    assert REPO_ROOT / "external" / "patches" / "README.md" in markdown_files(REPO_ROOT)


def test_a_link_into_the_vendor_tree_is_still_resolved(tmp_path: Path) -> None:
    """Not walking the vendor tree must not stop us checking links that point at it."""
    _write(tmp_path, f"{VENDOR_TREE}/xarm_ros2/ReadMe.md", "# Vendor\n")
    _write(
        tmp_path,
        "docs/ours.md",
        f"# Ours\n\n"
        f"[present](../{VENDOR_TREE}/xarm_ros2/ReadMe.md)\n"
        f"[absent](../{VENDOR_TREE}/xarm_ros2/Missing.md)\n",
    )

    assert check(tmp_path) == [f"docs/ours.md: dead link -> ../{VENDOR_TREE}/xarm_ros2/Missing.md"]
