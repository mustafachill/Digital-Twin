"""The frozen snapshots are left out of the main tree's checks, and nothing else is.

ADR-0068 decision 4 narrows the main tree's coverage on purpose: `projects/<name>/` holds
whole trees extracted from past commits, each a record rather than a source, whose own lint
is outside its contract (it builds, its scenario passes, its `./run` runs). That narrowing is
the kind a later edit widens without anyone noticing — a prefix match instead of a component
match, an exception that grows, a skip that moves from the top level to any depth — and a
widened skip reports "clean" over files it never read. These tests pin the boundary from
both sides: what must be skipped, and everything adjacent to it that must not be.

The `git ls-files` walkers (`test_interface_counts.py`,
`test_superseded_real_time_requirement.py`, `test_the_retracted_gripper_claim.py`) use
`in_a_snapshot` rather than stating the prefix again, so pinning that one predicate here pins
them too; the last test below checks that they still do.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from cite_tools import tree
from cite_tools.doclinks import markdown_files
from cite_tools.tree import in_a_snapshot, is_skipped, is_skipped_directory, our_files

TOOLS_TESTS = Path(__file__).resolve().parent

#: Paths that are inside a snapshot and must be left out.
INSIDE = (
    "projects/01-three-arm-event-driven-line/README.md",
    "projects/01-three-arm-event-driven-line/scripts/_lib.sh",
    "projects/02-fixed-program-pair/docs/adr/0066-run-the-cell-from-a-fixed-program.md",
    "projects/notes.md",
    "projects/03-real-program-twin-on-track/projects/README.md",
)

#: Paths next to the boundary that must still be checked. Each is a way the skip could widen.
OUTSIDE = (
    "projects/README.md",  # the main tree's own index of the snapshots
    "projects/snapshots.yaml",  # the main tree's own manifest of them
    "projectsX/foo.md",  # a prefix, not the directory
    "projects.md",
    "tools/projects/foo",  # the name at depth, not at the top level
    "docs/projects/README.md",
    "workspace/src/projects/package.xml",
)


@pytest.mark.parametrize("path", INSIDE)
def test_a_file_inside_a_snapshot_is_skipped(path: str) -> None:
    assert in_a_snapshot(Path(path))
    assert is_skipped(Path(path))


@pytest.mark.parametrize("path", OUTSIDE)
def test_a_file_beside_the_snapshots_is_not_skipped(path: str) -> None:
    assert not in_a_snapshot(Path(path))
    assert not is_skipped(Path(path))


def test_the_snapshot_directories_are_pruned_and_their_parent_is_not() -> None:
    """`projects/` itself must survive pruning, or the walk never reaches its README."""
    assert not is_skipped_directory(Path("projects"))
    assert is_skipped_directory(Path("projects/01-three-arm-event-driven-line"))
    assert is_skipped_directory(Path("projects/01-three-arm-event-driven-line/docs"))
    assert not is_skipped_directory(Path("tools/projects"))
    assert not is_skipped_directory(Path("projectsX"))


def test_exactly_two_files_are_walked_inside_the_snapshots() -> None:
    """The exception is two exact paths, so it cannot quietly grow into a second skip hole."""
    walked = tree.WALKED_INSIDE_SKIP_PATHS
    assert walked == frozenset({Path("projects/README.md"), Path("projects/snapshots.yaml")})


def _tree(root: Path) -> None:
    for relative in (
        "projects/README.md",
        "projects/01-demo/README.md",
        "projects/01-demo/scripts/run.sh",
        "projectsX/foo.md",
        "tools/projects/foo.md",
        "docs/index.md",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("text\n")


def test_the_walk_reaches_the_index_and_nothing_else_under_projects(tmp_path: Path) -> None:
    _tree(tmp_path)
    walked = {path.relative_to(tmp_path).as_posix() for path in our_files(tmp_path)}
    assert walked == {
        "projects/README.md",
        "projectsX/foo.md",
        "tools/projects/foo.md",
        "docs/index.md",
    }


def test_the_link_checker_sees_the_same_boundary(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = {path.relative_to(tmp_path).as_posix() for path in markdown_files(tmp_path)}
    assert "projects/README.md" in found
    assert "projects/01-demo/README.md" not in found
    assert "projectsX/foo.md" in found


@pytest.mark.parametrize(
    "walker",
    [
        "test_interface_counts.py",
        "test_superseded_real_time_requirement.py",
        "test_the_retracted_gripper_claim.py",
    ],
)
def test_every_ls_files_walker_takes_the_boundary_from_the_one_predicate(walker: str) -> None:
    """A walker that spelled `projects/` itself would be a second statement that can drift."""
    source = (TOOLS_TESTS / walker).read_text(encoding="utf-8")
    assert "from cite_tools.tree import in_a_snapshot" in source
    assert "not in_a_snapshot(Path(name))" in source
    assert '"projects' not in source and "'projects" not in source


REPO_ROOT = TOOLS_TESTS.parents[1]


def _lines_naming_projects(lines: list[str]) -> list[str]:
    return [
        line.strip() for line in lines if "projects" in line and not line.strip().startswith("#")
    ]


def test_yamllint_ignores_exactly_the_root_projects_directory() -> None:
    """`.yamllint`'s `ignore` is gitignore syntax: a leading `/` anchors it at the root.

    The one negation re-admits the main tree's own manifest, which is not a snapshot.

    Without the slash, `projects/` would also match `tools/projects/` or any deeper
    directory of that name — the widening this file exists to catch.
    """
    config = yaml.safe_load((REPO_ROOT / ".yamllint").read_text(encoding="utf-8"))
    ignore = config["ignore"].splitlines()
    assert _lines_naming_projects(ignore) == ["/projects/", "!/projects/snapshots.yaml"]


def test_dockerignore_excludes_exactly_the_root_projects_directory() -> None:
    """`.dockerignore` patterns are matched from the context root, so `projects/` is anchored.

    Docker has no unanchored form; depth comes only from a `**` prefix, which is what this
    refuses, along with any second pattern naming the directory.
    """
    lines = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert _lines_naming_projects(lines) == ["projects/"]


def test_the_fixture_walker_skips_exactly_the_root_projects_directory() -> None:
    """`cite_test_hardware`'s repository walk cannot import `in_a_snapshot` (it runs under
    ctest, without `cite_tools`), so it states `projects` itself. Its matcher is anchored at
    the root (`relative == skip or relative.startswith(skip + '/')`); this pins the entry.
    """
    source = (REPO_ROOT / "workspace/src/cite_test_hardware/test/test_unreachable.py").read_text(
        encoding="utf-8"
    )
    skipped = next(
        node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SKIPPED" for t in node.targets)
    )
    entries = ast.literal_eval(skipped)
    assert [e for e in entries if "projects" in e] == ["projects"]
    assert "relative == skip or relative.startswith(skip + '/')" in source
