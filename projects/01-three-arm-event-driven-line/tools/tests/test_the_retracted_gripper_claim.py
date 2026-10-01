"""The gripper claims ADR-0028 retracted, held out of the tree. Two of them now.

ADR-0028 said in four places that a convex hull *"fills the space between the
fingers"*. It does not, and the reason it mattered is not style: that sentence was
the hypothesis clause 2 of the promotion gate would have been tested against, and
a friction-grasp re-run designed to look for a filled inter-finger gap would have
found no difference and read as a clean pass.

**Its replacement was wrong in the same way, and that is why this file grew.**
The 2026-08-31 correction replaced it with *"both shoulders lie inside the part's
envelope"* and a prediction of inclined wedges pressing on the part — derived
from the same static audit, at a *commanded* aperture the gripper never occupies
while holding this cell's 50 mm part. It became a promotion condition before
anyone checked it, and the campaign of 2026-09-01 measured it not to occur. The
change that retracted it corrected four files and extended no guard, which is
precisely the omission this file exists to close, so both spellings are in
``RETRACTED`` now. **The pattern to carry is not either sentence: it is that an
audit taken at a commanded value must state whether the machine ever reaches that
value.**

Two things are checked here, and they are different in kind.

* **The structural fact the retraction rests on** — the fingers are hulled
  independently, so the space between them is between two collision bodies. This
  is checkable from L0 and from what is committed, on any machine, and it is what
  makes the retracted sentence false rather than merely unproven.
* **The sentence does not come back.** A claim retracted in prose is retracted by
  nothing, which is how this one survived four restatements and two reviews. Every
  surviving occurrence is a *quotation inside its own retraction*, and this test
  fails if one appears anywhere else.

Deliberately not checked here: anything about grasp behaviour. That belongs to the
campaign ADR-0028's gate names, and an opinion formed here would poison it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cite_tools import manifest
from cite_tools.model.loader import load

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "assets" / "manifest.yaml"

#: Every spelling of a retracted gripper-geometry claim.
#:
#: The first three are the 2026-08-31 retraction: a hull *fills the space between
#: the fingers*. The last two are the **second** mechanism, retracted 2026-09-01
#: and derived exactly the same way — from a static audit taken at a *commanded*
#: aperture the gripper never occupies while holding this cell's part. Both were
#: stated as fact, both were falsified by measurement, and the second one had
#: become a promotion condition before anyone checked it.
#:
#: **The second one is here because a claim retracted in prose is retracted by
#: nothing.** The change that retracted it corrected four files and extended no
#: guard, which is the same omission that let the first survive four restatements
#: and two reviews.
RETRACTED = (
    "fills the space between the fingers",
    "fills the space between the gripper fingers",
    "fills the gap between the pads",
    "both shoulders lie inside the part's envelope",
    "wedges inside the part's envelope",
)

#: Why each claim was retracted, so the failure message names the right
#: measurement instead of the first one this file was written for.
_FILLED_GAP = (
    "ADR-0028's correction of 2026-08-31 retracted it: each link is hulled "
    "separately, so that space lies between two collision bodies."
)
_SHOULDERS = (
    "ADR-0028's correction of 2026-09-01 retracted it: the audit it came from was "
    "taken at a commanded aperture the gripper never occupies while holding this "
    "cell's part, and the wedges sit 0.41 mm of aperture behind the pad plane on "
    "the same rigid link. Measured in docs/measurements/2026-09-01-hull-grasp/."
)
WHY_RETRACTED = {
    "fills the space between the fingers": _FILLED_GAP,
    "fills the space between the gripper fingers": _FILLED_GAP,
    "fills the gap between the pads": _FILLED_GAP,
    "both shoulders lie inside the part's envelope": _SHOULDERS,
    "wedges inside the part's envelope": _SHOULDERS,
}

#: A retraction says so beside the quotation. An assertion does not.
#:
#: The last two entries were added on 2026-09-01 with the second claim, and each
#: is here because a real retraction in this repository is worded that way and
#: would otherwise have been reported as a re-assertion:
#:
#: * ``What was wrong`` — ADR-0028's correction of 2026-09-01 opens the paragraph
#:   that retracts the shoulder inference with exactly that heading, and then
#:   argues rather than negating, so no "does not" falls inside the window;
#: * ``was not observed`` — the frozen campaign
#:   ``docs/measurements/2026-09-01-hull-grasp/`` refutes the wedge prediction in
#:   those words. A published campaign is not edited to satisfy a guard, so the
#:   guard learns the wording instead.
#:
#: **This widens the vocabulary and it does not weaken the question**, which is
#: still "does a negation stand beside this sentence". Every marker here is
#: language a re-assertion has no reason to carry.
RETRACTION_MARKERS = (
    "Corrected",
    "corrected",
    "It does not",
    "it does not",
    "does not",
    "What was wrong",
    "was not observed",
)

#: How much text around an occurrence is read looking for a marker. Wide enough to
#: span the sentence that retracts it, narrow enough that a marker elsewhere in the
#: document cannot vouch for an unrelated re-assertion.
WINDOW = 400


def tracked_text_files() -> list[Path]:
    """Every tracked file, filtered to the ones a claim can be written in.

    `git ls-files` rather than a walk: the question is what the repository
    carries, and a walk answers about whatever is on disk, including build trees
    and other checkouts' artefacts.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    suffixes = {".md", ".py", ".yaml", ".yml", ".xacro", ".hpp", ".cpp", ".json", ".patch"}
    return [REPO_ROOT / name for name in out if Path(name).suffix in suffixes]


class TestTheFingersAreHulledIndependently:
    """Why the retracted sentence is false, checked rather than asserted."""

    def _finger_meshes(self) -> tuple[str, ...]:
        model = load(REPO_ROOT / "model")
        for asset_type in model.types:
            spec = asset_type.description.collision
            if spec is None:
                continue
            for mesh_set in spec.sets:
                if mesh_set.kind != "convex_hull":
                    continue
                return tuple(m for m in mesh_set.meshes if m.endswith("_finger.stl"))
        return ()

    def test_each_finger_is_its_own_declared_mesh(self) -> None:
        """One hull per mesh file, and the two fingers are two files."""
        fingers = self._finger_meshes()
        assert len(fingers) == 2, f"expected a left and a right finger mesh, got {fingers}"
        assert len(set(fingers)) == 2

    def test_each_finger_has_its_own_committed_hull(self) -> None:
        recorded = {
            mesh["path"]: (Path(entry["dest"]), mesh)
            for entry in manifest.read(MANIFEST)
            for mesh in entry["meshes"]
        }
        for finger in self._finger_meshes():
            assert finger in recorded, f"{finger} is declared and not recorded"
            dest, mesh = recorded[finger]
            path = REPO_ROOT / dest / finger
            assert path.is_file(), f"{finger} has no committed hull"
            assert path.stat().st_size == mesh["bytes"]

    def test_the_two_fingers_are_two_distinct_bodies(self) -> None:
        """Distinct files with distinct digests: no hull spans both.

        A hull over the assembly is the only shape that could fill the space
        between them, and this pipeline computes one hull per declared mesh —
        never one over a group.
        """
        digests = {
            mesh["path"]: mesh["sha256"]
            for entry in manifest.read(MANIFEST)
            for mesh in entry["meshes"]
        }
        left, right = sorted(self._finger_meshes())
        assert digests[left] != digests[right]


class TestTheClaimDoesNotComeBack:
    def test_every_retracted_claim_carries_its_reason(self) -> None:
        """Otherwise the guard fires and then dies of a `KeyError` in its message.

        A guard that crashes where it means to report is a guard nobody reads,
        and the message is the whole value here: the next person meets a sentence
        they believe and has to be told which measurement retracted it.
        """
        assert set(RETRACTED) == set(WHY_RETRACTED)

    @pytest.mark.parametrize("claim", RETRACTED)
    def test_every_occurrence_is_inside_its_own_retraction(self, claim: str) -> None:
        offenders: list[str] = []
        for path in tracked_text_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            start = text.find(claim)
            while start >= 0:
                window = text[max(0, start - WINDOW) : start + len(claim) + WINDOW]
                if not any(marker in window for marker in RETRACTION_MARKERS):
                    line = text.count("\n", 0, start) + 1
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}")
                start = text.find(claim, start + 1)
        assert not offenders, (
            f"{claim!r} is stated as fact at: {', '.join(offenders)}. "
            f"{WHY_RETRACTED[claim]} Quote it only inside its own retraction, with a "
            "negation beside it."
        )
