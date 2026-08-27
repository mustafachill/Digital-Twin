"""Which files in this repository are ours to check.

Every repository-wide checker needs the same answer to the same question, and the answer is
not obvious: a checkout contains a vendored ROS tree we pin rather than edit, build output
that is regenerated rather than written, a virtualenv, and — because `CLAUDE.md` §11 makes
`.claude/` local tooling that is deliberately not committed — agent worktrees that are whole
copies of this repository. A checker that walks those reports findings no commit of ours can
act on, and a gate that fails on something nobody can fix is a gate people learn to ignore.

This module exists so that answer is written once (P1). `doclinks.py` established the rules
and the measurements behind them; `english.py` needs exactly the same remit, and a second
copy of the list would be the duplication this project's first principle forbids.

**Not `git ls-files`**, which was tried first and rejected on evidence. It is attractive —
it makes the file set a property of the commit and excludes all of the above for free — but
this repository's own development workflow runs agents in `git worktree` checkouts, whose
`.git` is a *file* pointing at an absolute path inside the parent clone. That path does not
exist inside the container, so `git ls-files` fails outright there:
`fatal: not a git repository`. The container is where `./scripts/lint` runs its full gate.
A discovery mechanism that works in a fresh clone and fails in the setup the project
actually uses is not a discovery mechanism. Walking the tree also catches a lapse in a file
that has been written but not yet staged, which for a lint gate is the more useful moment.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Directory *names*, matched at any depth. Build and tool output, which is regenerated
#: rather than edited, plus one deliberate exception.
#:
#: `.claude` is here for a reason worth stating: CLAUDE.md §11 makes it local tooling that is
#: deliberately **not committed**, and it holds agent worktrees — whole copies of the
#: repository. Walking it reports the same file many times over, and reports problems in
#: those copies that no commit can repair, because the tree they belong to is itself
#: uncommitted.
#:
#: The cache entries were added when `english.py` started using this list. `doclinks.py`
#: never needed them because it globs `*.md` and a cache holds none — but a checker that
#: walks *every* file finds 1205 files under `.mypy_cache` alone in a tree that has run the
#: lint gate once, which is both slow and a report about files nobody wrote.
SKIP_DIRS = {
    ".claude",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "install",
    "log",
    "node_modules",
}

#: Paths relative to the repository root, skipped at **exactly** that location.
#:
#: `workspace/src/external` is the vendor tree `./scripts/bootstrap` imports from
#: `external/cite.repos`. Its content belongs to `xarm_ros2`, and ADR-0008 pins and patches
#: that source rather than hand-correcting it — so any finding raised inside it is one no
#: commit of ours may act on.
#:
#: The measured cost of not skipping it, taken when `doclinks.py` was written: walking it
#: made the answer depend on whether `vcs import` had run. **100** Markdown files with the
#: vendor tree imported, **88** without it — same commit, same command, twelve vendor files.
#: None of those twelve had a dead link that day, so what is repaired here is the unstable
#: count. The unactionable failure is the standing risk of gating on a tree we do not
#: control, not a defect observed on the day.
#:
#: It is anchored rather than added to `SKIP_DIRS` because that set matches path *parts*. A
#: bare `"external"` would also skip the top-level `external/`, which is ours:
#: `external/patches/README.md` links to ADR-0008 and to the v1 lessons, and keeping links
#: like those alive is the whole point of the link checker. Skipping a directory we own to
#: avoid naming a directory we do not would be a checker quietly reducing its own coverage.
SKIP_PATHS = {
    Path("workspace/src/external"),
}


def is_skipped(relative: Path) -> bool:
    """True if a repository-relative path lies outside every checker's remit."""
    if any(part in SKIP_DIRS for part in relative.parts):
        return True
    return any(relative.is_relative_to(prefix) for prefix in SKIP_PATHS)


def our_files(root: Path) -> list[Path]:
    """Every file under `root` that is ours to check, sorted for a stable report order.

    Prunes as it descends rather than filtering afterwards. `rglob("*")` walks the whole of
    `.git` and `.venv` before discarding them, which measured at 0.78 s against 0.28 s for
    the same answer here — and the gap grows with the size of the virtualenv, which is not
    something a lint gate's runtime should depend on.
    """
    found: list[Path] = []
    for parent, directories, names in os.walk(root):
        here = Path(parent)
        directories[:] = [
            name for name in directories if not is_skipped((here / name).relative_to(root))
        ]
        found.extend(here / name for name in names)
    return sorted(path for path in found if not is_skipped(path.relative_to(root)))
