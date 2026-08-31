"""Every document that states how many interfaces exist must state the truth.

Both `docs/interfaces/README.md` and `workspace/src/cite_interfaces/README.md`
open by counting the package: "23 definitions - 14 `.msg`, 3 `.srv`, 6
`.action`". Nothing checked the arithmetic, and on 2026-08-27 one of them said
**22** with the same breakdown beside it - the `.srv` count had been updated when
`ResetStation.srv` landed and the total had not.

That is P7's failure mode in miniature. A number in prose is a claim about the
system, it rots the moment the system changes, and a reader has no way to know
which of the two documents is the stale one. ADR-0027's first correction states
the general rule this test enforces the exception to: *"do not state the
cardinality of a generated collection in prose."* These two collections are not
generated - they are a directory of hand-written `.msg`, `.srv` and `.action`
files - and both documents open with the count because it is the first thing a
reader wants. So the count stays, and this counts the directory instead.

**The two-document list was the hole, and a third document fell through it.**
`docs/architecture/cross-cutting-testing.md`'s status line said *"22 interface
definitions"* where the package held 23 - the same defect, the same week, in a
document `DOCUMENTS` did not reach, because that list held the two READMEs that
*open* by counting the package and nothing else. A guard that names its subjects
one at a time is a guard over the documents someone remembered.

So there are now two checks of different kinds. `DOCUMENTS` still holds the two
canonical homes and checks the full breakdown in them, because only those two
state one. `test_no_document_states_a_wrong_interface_count` reads **every**
tracked Markdown file and checks any total it finds, so a fourth document is
caught by existing, not by being added here.

**Where a count may live, since the scan permits one anywhere.** The convention
this repository keeps is CLAUDE.md §2's: a count in prose names the command that
reproduces it. A document that is not the count's canonical home has neither, and
the remedy is to delete the number and cite the home rather than to correct it
again - which is what `cross-cutting-testing.md` and the root `README.md` did on
2026-08-31. This scan is the backstop for the ones that stay.

A HOST TEST, deliberately. It reads files and needs no ROS, so it runs under
`./scripts/bootstrap --host-only` and under `./scripts/test`'s first half. A
check that only ran inside the container would not run on the machine most of
this documentation is edited from.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "workspace" / "src" / "cite_interfaces"

#: The three interface kinds, under the directory name and the extension each
#: uses. Read from the tree rather than listed, so a fourth kind would be a
#: change here and not a silent omission.
KINDS = (("msg", ".msg"), ("srv", ".srv"), ("action", ".action"))

#: The two documents that open by counting the package, and the only two that
#: state the full breakdown. Both are checked, because the defect was exactly one
#: of them disagreeing with the other. This tuple is NOT the set of documents that
#: may state a count - see `test_no_document_states_a_wrong_interface_count`,
#: which reaches every tracked Markdown file and exists because this tuple missed
#: a third document that stated one.
DOCUMENTS = (
    REPO_ROOT / "docs" / "interfaces" / "README.md",
    PACKAGE / "README.md",
)

#: A total stated in prose: `23 definitions`, `23 interface definitions`, however
#: it is emphasised. The lookbehind excludes `ROS 2 interface definition`, which is
#: a name and not a count and appears in ADR-0010's decision; without it the scan
#: reads that sentence as claiming the package holds two.
STATED_TOTAL = re.compile(r"(?<!ROS )(?<!ROS\n)(\d+)[*`]*\s+(?:interface\s+)?definitions?\b")

#: `23 definitions - 14 .msg, 3 .srv, 6 .action`, however it is emphasised.
#: Markdown bold and backticks are stripped by the character class rather than
#: parsed, because what is under test is the arithmetic and not the formatting.
COUNT_SENTENCE = re.compile(
    r"[*`]*(\d+)[*`]*\s+definitions?\s*[^\d]*?"
    r"[*`]*(\d+)[*`]*\s*[`]*\.msg[`]*[^\d]*?"
    r"[*`]*(\d+)[*`]*\s*[`]*\.srv[`]*[^\d]*?"
    r"[*`]*(\d+)[*`]*\s*[`]*\.action[`]*"
)


def tracked_markdown() -> list[Path]:
    """Every tracked Markdown file.

    `git ls-files` rather than a walk: the question is what the repository
    carries, and a walk answers about whatever is on disk - including build trees
    and, in a worktree, another checkout's artefacts.
    """
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / name for name in listed]


def _on_disk() -> dict[str, int]:
    return {kind: len(sorted((PACKAGE / kind).glob(f"*{extension}"))) for kind, extension in KINDS}


def test_the_package_still_has_the_three_interface_directories() -> None:
    for kind, _ in KINDS:
        assert (PACKAGE / kind).is_dir(), f"{PACKAGE / kind} is not a directory"


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.name)
def test_the_stated_counts_match_the_directory(document: Path) -> None:
    """Every count in the opening sentence, against the files that are there."""
    assert document.is_file(), f"{document} does not exist"
    match = COUNT_SENTENCE.search(document.read_text(encoding="utf-8"))
    assert match is not None, (
        f"{document} no longer states a count in the shape "
        '"N definitions - N .msg, N .srv, N .action". Either restore it or delete '
        "this test with the sentence it guards."
    )

    total, stated_msg, stated_srv, stated_action = (int(group) for group in match.groups())
    on_disk = _on_disk()

    assert stated_msg == on_disk["msg"], f"{document} states {stated_msg} .msg files"
    assert stated_srv == on_disk["srv"], f"{document} states {stated_srv} .srv files"
    assert stated_action == on_disk["action"], f"{document} states {stated_action} .action files"
    assert total == sum(on_disk.values()), (
        f"{document} states {total} definitions and the three kinds it lists sum to "
        f"{sum(on_disk.values())} - this is the arithmetic that was wrong"
    )


@pytest.mark.parametrize(
    "document", tracked_markdown(), ids=lambda path: str(path.relative_to(REPO_ROOT))
)
def test_no_document_states_a_wrong_interface_count(document: Path) -> None:
    """Any total, in any tracked document, against the files that are there.

    The check `DOCUMENTS` above did not make: it named its subjects, so a third
    document stating a count was outside it by construction and drifted for as
    long as nobody re-ran the arithmetic by hand.
    """
    if not document.is_file():
        return
    total = sum(_on_disk().values())
    for match in STATED_TOTAL.finditer(document.read_text(encoding="utf-8")):
        stated = int(match.group(1))
        line = document.read_text(encoding="utf-8")[: match.start()].count("\n") + 1
        assert stated == total, (
            f"{document.relative_to(REPO_ROOT)}:{line} states {stated} interface "
            f"definitions and {PACKAGE.name} holds {total}. If this document is not the "
            "count's canonical home, delete the number and cite "
            "docs/interfaces/README.md rather than correcting it a second time - a count "
            "in prose that names no command reproducing it is the shape that goes stale "
            "unnoticed (CLAUDE.md section 2)"
        )


def test_every_definition_on_disk_is_listed_in_the_cmakelists() -> None:
    """The count is only worth anything if the files are actually built.

    A `.srv` in the directory and absent from `rosidl_generate_interfaces` is
    generated for nobody: `ros2 interface show` cannot find it, which by P3 means
    the interface does not exist. It would still be counted by the test above.
    """
    cmakelists = (PACKAGE / "CMakeLists.txt").read_text(encoding="utf-8")
    missing = [
        f"{kind}/{path.name}"
        for kind, extension in KINDS
        for path in sorted((PACKAGE / kind).glob(f"*{extension}"))
        if f"{kind}/{path.name}" not in cmakelists
    ]
    assert not missing, (
        f"{missing} are in the package and in no `rosidl_generate_interfaces` list, so "
        "nothing is generated for them and `ros2 interface show` cannot find them"
    )
