"""ADR-0043 half 2's wording, kept out of the source it used to be quoted in.

ADR-0043's half 2 required *"both sides sustain a real-time factor of 1.0
concurrently"*. Its status line now says not to cite that wording, and the reason
is structural rather than editorial: half 1 puts `real_time_factor` `1.0` into the
generated world, SDFormat's factor is a *ceiling*, and a rate measured under a
ceiling is capped at it by construction. So half 2 as worded is a test no machine
passes, and an adequate machine and an over-provisioned one answer it alike.

[ADR-0049](../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md) keeps the
1.0 floor and moves it onto two quantities — **capacity**, sampled with the throttle
lifted, and the accumulated **clock deficit** in seconds, sampled with it in force —
with neither threshold set and nothing in the tree measuring either.

**Why a test rather than an edit.** Four source files carried half 2 as the
requirement, and none of them was *false*: each said the requirement is on the
machine and unmeasured, which is still true. They were wrong only in pointing a
reader at wording a record has since retired, which is exactly the failure a prose
correction does not prevent — the same shape as
`test_the_retracted_gripper_claim.py`, which exists because a sentence retracted in
one document survived four restatements elsewhere.

**Scope: source, not records.** Every document under `docs/adr/`, the charter and
`CLAUDE.md` legitimately carry half 2's wording — a record states what it decided
and a correction quotes what it corrects. What may not carry it is code, whose
comments are read as current instruction and not as history.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Files whose comments are read as instruction. Markdown is deliberately absent:
#: the records are where the superseded wording belongs.
SOURCE_SUFFIXES = {".py", ".cpp", ".hpp", ".sh", ".yaml", ".yml", ".xacro"}

#: How a file refers to the half whose wording is superseded. Matched only inside a
#: file that names ADR-0043 at all, so an unrelated "other half" cannot trip it.
HALF_TWO = re.compile(r"\b(second half|other half|half 2|half two)\b", re.IGNORECASE)

#: The retired wording itself, in the spellings it was written in. These are barred
#: from source outright, whether or not ADR-0049 is cited beside them.
RETIRED = (
    "sustain 1.0 concurrently",
    "sustaining 1.0 concurrently",
    "both sides sustain",
    "both sides sustaining",
)


def tracked_source_files() -> list[Path]:
    """Every tracked source file.

    `git ls-files` rather than a walk, for the reason
    `test_the_retracted_gripper_claim.py` gives: the question is what the
    repository carries, and a walk answers about whatever is on disk — including
    build trees and, in a worktree, another checkout's artefacts.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / name for name in out if Path(name).suffix in SOURCE_SUFFIXES]


def _mentions_0043() -> list[Path]:
    return [
        path
        for path in tracked_source_files()
        if path.is_file() and "ADR-0043" in path.read_text(encoding="utf-8", errors="ignore")
    ]


def test_some_source_file_still_names_the_record() -> None:
    """A guard over an empty set passes for the wrong reason."""
    assert _mentions_0043(), (
        "no tracked source file names ADR-0043 any more. Either the throttle left "
        "the generator, or this test has stopped reaching the files it guards - "
        "check which before deleting it"
    )


@pytest.mark.parametrize(
    "path", _mentions_0043(), ids=lambda path: str(path.relative_to(REPO_ROOT))
)
def test_a_source_file_citing_half_two_also_cites_its_restatement(path: Path) -> None:
    """Half 2 may be referred to from code only alongside ADR-0049."""
    text = path.read_text(encoding="utf-8")
    if not HALF_TWO.search(text):
        return
    assert "ADR-0049" in text, (
        f"{path.relative_to(REPO_ROOT)} refers to ADR-0043's half 2 and does not name "
        "ADR-0049, which restates it. ADR-0043's status line says not to cite half 2's "
        "wording as the requirement: point at ADR-0049's two quantities instead - "
        "capacity with the world's throttle lifted, and the accumulated clock deficit "
        "in seconds with it in force"
    )


@pytest.mark.parametrize(
    "path", tracked_source_files(), ids=lambda path: str(path.relative_to(REPO_ROOT))
)
def test_the_retired_wording_is_not_in_any_source_file(path: Path) -> None:
    """The sentence itself, barred from code in every spelling it was written in."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.resolve() == Path(__file__).resolve():
        return
    found = [phrase for phrase in RETIRED if phrase in text]
    assert not found, (
        f"{path.relative_to(REPO_ROOT)} states ADR-0043 half 2's retired wording {found}. "
        "It is capped at the declared factor by construction and is a test no machine "
        "passes; ADR-0049 carries the requirement now"
    )
