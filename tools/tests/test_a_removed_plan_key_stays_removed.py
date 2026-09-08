"""ADR-0048 clause 3's removed plan key, held out of the tree.

`hosted_by` stated whether an asset's controller manager is created inside the
Gazebo process or runs its own `ros2_control_node`. It was a total function of
the backend the plan already states per side, it was read by nothing, and no
production path starts a `ros2_control_node` — so the plan stopped stating it and
`cite_bringup` derives what it needs from `ControllerManager.backend_on`.

**Why a test rather than a deletion.** The argument for removing it was written
as *"a field nobody reads is at its cheapest to delete before something starts
reading it"*, and that argument expires the moment a reader appears. A grep run
once by the change that deleted it says nothing about the change after. Phase
2.B's per-side generator work is where the question *"what hosts this side's
controller manager"* comes back, and the answer there is the side's own backend
rather than a reinstated field — ADR-0048's own revisit section says so.

**Scope: source, not records.** Every document under `docs/` legitimately carries
the name — a decision record states what it decided, and open-work names what
closed. What may not carry it is code, whose comments are read as current
instruction. That is the same split
`test_superseded_real_time_requirement.py` draws, for the same reason.

**Two exemptions, and each is a file whose whole subject is the removal:** this
one, and `cite_bringup`'s `test_a_removed_plan_key_is_ignored.py`, which pins
that a document still carrying the key loads rather than being refused. A guard
with a list of exemptions cannot say a field is gone; a guard with two can.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The key itself.
REMOVED_KEY = "hosted_by"

#: Where a source file is read as instruction. `docs/` is deliberately absent.
GUARDED_TREES = ("workspace", "tools", "tests", "scripts")

#: Files whose subject IS the removed key, named relative to the repository root.
#: Both are tests about the removal; neither reads the key out of a plan.
EXEMPT = (
    "tools/tests/test_a_removed_plan_key_stays_removed.py",
    "workspace/src/cite_bringup/test/test_a_removed_plan_key_is_ignored.py",
)


def guarded_files() -> list[Path]:
    """Every tracked file under the four trees code lives in.

    `git ls-files` rather than a walk, for the reason
    `test_superseded_real_time_requirement.py` gives: the question is what the
    repository carries, and a walk answers about whatever is on disk — including
    build trees carrying a plan generated before the removal, which is exactly
    the document `test_a_removed_plan_key_is_ignored.py` says must still load.

    Every suffix, not a chosen set: the key lived in a Jinja template, a YAML
    artifact and a CMake comment as well as in Python, and a suffix list is how
    one of those is missed.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", *GUARDED_TREES],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / name for name in out if name not in EXEMPT]


def test_the_guard_reaches_the_files_it_is_about() -> None:
    """A guard over an empty set passes for the wrong reason."""
    files = guarded_files()
    assert len(files) > 100, f"only {len(files)} tracked files found under {GUARDED_TREES}"
    assert any(
        path.name == "plan.py" and path.parent.name == "cite_bringup" for path in files
    ), "the bring-up plan reader is not in the walk, so this guard checks the wrong tree"


def test_both_exemptions_exist_and_are_about_the_removal() -> None:
    """An exemption naming a file that is gone is an exemption nobody notices."""
    for name in EXEMPT:
        path = REPO_ROOT / name
        assert path.is_file(), f"{name} is exempted and does not exist"
        assert REMOVED_KEY in path.read_text(encoding="utf-8"), (
            f"{name} is exempted from this guard and no longer mentions "
            f"{REMOVED_KEY!r}. Delete the exemption rather than leaving a hole "
            "where nobody is looking"
        )


@pytest.mark.parametrize("path", guarded_files(), ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_no_source_file_states_the_removed_plan_key(path: Path) -> None:
    """The name itself, barred from every tree code is read out of."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    assert REMOVED_KEY not in text, (
        f"{path.relative_to(REPO_ROOT)} states {REMOVED_KEY!r}, which ADR-0048 "
        "clause 3 removed from the bring-up plan. Nothing read it, and it was "
        "deleted before anything could start to; what needs to know how a side's "
        "controller manager is hosted asks `ControllerManager.backend_on` for "
        "that side's backend. If the plan genuinely has to state it again, that "
        "is an amendment to ADR-0048 and not an edit here"
    )
