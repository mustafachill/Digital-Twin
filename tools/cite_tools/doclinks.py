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

from cite_tools.tree import is_skipped

# [text](target) — skips images, which are ![text](target)
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")
# "## Some Heading" -> "some-heading"
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)

#: Whose files this checker walks lives in `tree.py`, because `english.py` asks the same
#: question and P1 forbids a second copy of the answer. The rationale and the measurements
#: that produced these rules moved there with them.
#: ---------------------------------------------------------------------------------------


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
    return [p for p in root.rglob("*.md") if not is_skipped(p.relative_to(root))]


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
