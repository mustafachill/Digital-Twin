"""Internal link checker for the repository's Markdown.

Documentation rots by renaming. A file moves, six documents point at where it used to be,
and nobody notices until a reader follows a dead link months later. This makes that a lint
failure instead.

Checks relative links and anchors within the repository. External URLs are not fetched —
that would make linting depend on the network and on other people's uptime.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# [text](target) — skips images, which are ![text](target)
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")
# "## Some Heading" -> "some-heading"
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)

#: Directories whose Markdown is not ours to report on.
#:
#: `.claude` is here for a reason worth stating: CLAUDE.md §11 makes it local
#: tooling that is deliberately **not committed**, and it holds agent worktrees —
#: whole copies of the repository. Walking it reports the same document many
#: times over, and reports dead links in those copies that no commit can repair,
#: because the target they reach for is itself uncommitted. A gate that fails on
#: files no change of ours can fix is a gate people learn to ignore, which is the
#: failure `./scripts/lint` documents at length elsewhere.
SKIP_DIRS = {
    ".claude",
    ".git",
    ".venv",
    "build",
    "install",
    "legacy",
    "log",
    "node_modules",
}


def slugify(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor conversion."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~]", "", text)
    text = text.strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9\-_]", "", text)


def anchors_of(path: Path) -> set[str]:
    try:
        return {slugify(h) for h in HEADING.findall(path.read_text(encoding="utf-8"))}
    except OSError:
        return set()


def markdown_files(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
    ]


def check(root: Path) -> list[str]:
    problems: list[str] = []

    for source in markdown_files(root):
        try:
            body = source.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - unreadable file
            problems.append(f"{source}: cannot read ({exc})")
            continue

        for target in LINK.findall(body):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue  # external, or a same-file anchor we do not resolve

            file_part, _, anchor = target.partition("#")
            if not file_part:
                continue

            resolved = (source.parent / file_part).resolve()
            if not resolved.exists():
                rel = source.relative_to(root)
                problems.append(f"{rel}: dead link -> {target}")
                continue

            if anchor and resolved.suffix == ".md" and anchor not in anchors_of(resolved):
                rel = source.relative_to(root)
                problems.append(f"{rel}: missing anchor -> {target}")

    return problems


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    problems = check(root)

    if problems:
        for problem in problems:
            print(f"  {problem}")
        print(f"\n  {len(problems)} broken link(s)")
        return 1

    count = len(markdown_files(root))
    print(f"  {count} markdown files, all internal links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
