"""The real robot's program is read, never edited, and this is what holds it so.

`model/programs/xarm5_real_demo.blockly.xml` is the UFACTORY Studio program that
drives the real xArm 5, copied byte for byte out of the robot's own export
(ADR-0067, `model/programs/README.md`). The twin takes its poses, its gripper
widths, its speeds and its track moves from that file, so an edit to it would
change what the twin does while the real robot kept doing the old thing. Pinning
the digest makes an edit a failing test rather than a silent divergence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROGRAM = REPO_ROOT / "model" / "programs" / "xarm5_real_demo.blockly.xml"

#: The sha256 of `./app.xml` in `blockly-xArm5-RealDemo.tar.gz`, as recorded in
#: `model/programs/README.md` when it was copied.
PINNED_SHA256 = "998e3d2eec6d32f56e08e86ce1f28ea4c5261632c9bfe2c9070c9c2860e79887"


def test_the_real_program_is_byte_identical_to_the_robots_export() -> None:
    digest = hashlib.sha256(PROGRAM.read_bytes()).hexdigest()
    assert digest == PINNED_SHA256, (
        f"{PROGRAM.relative_to(REPO_ROOT)} has changed (sha256 {digest}). It is the real "
        "robot's program and is read-only here: change it on the robot, export it, copy "
        "the new app.xml byte for byte, and update the digest in this test and in "
        "model/programs/README.md together."
    )


def test_the_provenance_note_states_the_same_digest() -> None:
    note = (PROGRAM.parent / "README.md").read_text()
    assert PINNED_SHA256 in note
