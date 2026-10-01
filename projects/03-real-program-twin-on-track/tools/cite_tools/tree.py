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

#: Directory *suffixes*, matched at any depth. Packaging metadata, whose directory name is
#: the distribution's — `cite_tools.egg-info` — so it cannot be listed by exact name without
#: writing that name in a second place.
#:
#: This is here for the same reason `SKIP_PATHS` records for the vendor tree: an editable
#: install writes five files under `tools/cite_tools.egg-info/`, so the walk answered 653 in
#: a bootstrapped checkout against 648 tracked files on 2026-08-27 — the count moving with
#: local build state, which is precisely the instability this module was extracted to end.
SKIP_DIR_SUFFIXES = (".egg-info",)

#: Names skipped at any depth **whether they are a file or a directory**. This set holds
#: exactly one entry, and the distinction from `SKIP_DIRS` is the reason it exists rather
#: than being folded into it.
#:
#: In an ordinary clone `.git` is a directory and `SKIP_DIRS` would cover it. In a `git
#: worktree` checkout — which is how this project runs its agents, as the module docstring
#: records — `.git` is a **file** holding `gitdir: <absolute path>`. It is git's plumbing in
#: both shapes: never ours to edit, machine-local in the second, and repairable by no commit.
#: Matching it by name keeps it out of the walk either way.
SKIP_NAMES = {
    ".git",
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
#: `.env` is the per-machine environment file `./scripts/bootstrap` copies from
#: `.env.example`. It is git-ignored, it differs on every machine, and it is the one file in
#: the walk where a finding could be repaired by no commit and silenced by no shared
#: exemption — the escape hatch takes an exact path in a *tracked* configuration file, which
#: cannot describe a file that only exists on one laptop. Its tracked template
#: `.env.example` is checked, and that is the copy a commit can act on.
SKIP_PATHS = {
    Path("workspace/src/external"),
    Path(".env"),
}


def _under_skipped_path(relative: Path) -> bool:
    """True if `relative` is one of the anchored `SKIP_PATHS`, or lies inside one."""
    return any(relative.is_relative_to(prefix) for prefix in SKIP_PATHS)


def _is_skipped_directory_name(name: str) -> bool:
    """True if a single path component names a directory outside every checker's remit."""
    return name in SKIP_DIRS or name.endswith(SKIP_DIR_SUFFIXES)


def is_skipped(relative: Path) -> bool:
    """True if a repository-relative **file** path lies outside every checker's remit.

    `SKIP_DIRS` is matched against the path's *directories* — `relative.parts[:-1]` — and
    deliberately not against its basename. `Path.parts` includes the basename, and testing
    every part therefore drops any file whose own name happens to spell a directory we
    skip. That is not hypothetical: it silently removed `scripts/build`, one of the
    documented `./scripts/*` entry points, from the English-only gate, which reported
    `652 files checked, no non-English content` and exited 0 over a file containing a
    deliberate lapse. `SKIP_DIRS` says where content is not ours; a file is not a directory
    because it shares a directory's spelling.

    `doclinks.py` was unaffected in practice — it only ever passes `*.md` paths, and no
    `SKIP_DIRS` entry ends in `.md` — so its output is unchanged by this distinction.
    """
    return (
        any(_is_skipped_directory_name(part) for part in relative.parts[:-1])
        or any(part in SKIP_NAMES for part in relative.parts)
        or _under_skipped_path(relative)
    )


def is_skipped_directory(relative: Path) -> bool:
    """True if a repository-relative **directory** path lies outside every checker's remit.

    The counterpart to `is_skipped`: here the basename *is* a directory name, so it must be
    matched. This is what prunes `build/`, `.venv/`, `.claude/` and the rest at the moment
    the walk reaches them, which is where the pruning cost recorded on `our_files` is saved.
    """
    return any(
        _is_skipped_directory_name(part) or part in SKIP_NAMES for part in relative.parts
    ) or _under_skipped_path(relative)


def our_files(root: Path) -> list[Path]:
    """Every file under `root` that is ours to check, sorted for a stable report order.

    Prunes as it descends rather than filtering afterwards. `rglob("*")` walks the whole of
    `.git` and `.venv` before discarding them, which measured at 0.78 s against 0.28 s for
    the same answer here — and the gap grows with the size of the virtualenv, which is not
    something a lint gate's runtime should depend on.

    The two filters ask different questions and must use the different predicates. Pruning
    tests a directory, so `SKIP_DIRS` applies to its basename; the post-walk filter tests a
    *file*, where it must not — see `is_skipped`. Pruning has already excluded everything
    beneath a skipped directory by the time the second filter runs, so what remains for it
    is the anchored `SKIP_PATHS` case: a plain file at exactly one of those locations.
    """
    found: list[Path] = []
    for parent, directories, names in os.walk(root):
        here = Path(parent)
        directories[:] = [
            name
            for name in directories
            if not is_skipped_directory((here / name).relative_to(root))
        ]
        found.extend(here / name for name in names)
    return sorted(path for path in found if not is_skipped(path.relative_to(root)))
