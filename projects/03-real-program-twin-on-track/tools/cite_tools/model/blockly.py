"""Read a UFACTORY Studio Blockly program into the twin's step vocabulary (ADR-0067).

The real xArm 5 is programmed in UFACTORY Studio, whose programs are Blockly
workspaces saved as XML. The twin runs THE SAME program: this module reads that
XML and nothing else says what the cell does, so no angle, width or speed is
copied out of it by hand (P1).

STRICT ON PURPOSE. It accepts exactly the blocks the shipped program uses and
refuses everything else — an unknown block, a blended move (`r != -1`), a move
or grip that does not wait (`wait != TRUE`), a disabled block, a second
top-level chain. A reader that skipped what it did not understand would run a
different program from the robot's and report nothing; refusing makes a program
edited on the robot fail `./scripts/validate-model` until the twin models the
new block.

WHAT IT CONVERTS, and from what:

* `move_joints` fields `i`..`m` are joint angles in DEGREES, joint1 first. They
  become radians and a named pose (`blockly_01`, ...), one per distinct value,
  in the order the program first uses them. `reset` is every joint at zero and
  becomes the pose `zero`.
* `set_angle_speed` is a joint speed in degrees per second, in force for every
  later move. It becomes a MoveIt velocity scaling: that speed over the
  description's own joint velocity limit.
* `gripper_set` `pos` is the UFACTORY gripper's own position unit. The vendor
  driver maps it onto the drive joint as `q = (850 - pos) / 1000` rad
  (`xarm_ros2`, `xarm_api/src/xarm_driver.cpp`, lines 510-513, at the pinned
  commit), and the end effector's L0 linkage maps `q` onto the width between the
  pads. A grip narrower than the one before it is a CLOSE, and a close expects a
  part between the pads.
* `set_line_track` `pos` and `speed` are millimetres and millimetres per second
  along the linear track. They become metres.
* `sleep` is seconds, and stays seconds.
* `controls_repeat_ext` is unrolled: its body appears that many times.
* `tool_remark` is a comment on the robot's pendant and produces nothing.

WHAT IT DOES NOT CONVERT. `gripper_set`'s `speed` is recorded by the robot in
motor r/min and is not used: the twin's gripper runs at the rate its L0 end
effector declares, the same on both sides. `set_line_track` carries no `wait`
field; UFACTORY Studio's track block waits for the move, and the twin's track
step does the same.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from dataclasses import dataclass

from cite_tools.model.schema import GripperLinkage

#: The Blockly namespace UFACTORY Studio writes every element in.
NAMESPACE = "https://developers.google.com/blockly/xml"

#: The vendor driver's gripper map, `q = (OPEN_POS - pos) / POS_PER_RAD`
#: (`xarm_api/src/xarm_driver.cpp:510-513`). A fact about the program's units,
#: which is why it lives with the reader of those units.
GRIPPER_OPEN_POS = 850.0
GRIPPER_POS_PER_RAD = 1000.0

#: The joint fields of `move_joints`, joint1 first. UFACTORY Studio names them
#: by letter; a five-axis arm uses the first five.
JOINT_FIELDS = ("i", "j", "k", "l", "m", "n", "o")

#: The one pose name `reset` produces.
ZERO_POSE = "zero"

#: The prefix of every pose a `move_joints` produces.
POSE_PREFIX = "blockly_"

#: `value` inputs that are buttons on the Studio editor and carry no program.
_EDITOR_BUTTONS = ("btn_move", "btn_edit")


class BlocklyError(ValueError):
    """The program uses something this reader does not model. The message says what."""


@dataclass(frozen=True)
class Move:
    """Move the arm to a named joint pose, at a fraction of its velocity limit."""

    pose: str
    joints_rad: tuple[float, ...]
    velocity_scaling: float


@dataclass(frozen=True)
class Grip:
    """Open or close the gripper to a width between the pads."""

    width_m: float
    closing: bool


@dataclass(frozen=True)
class Wait:
    """Dwell, in the cell's own clock."""

    seconds: float


@dataclass(frozen=True)
class Track:
    """Move the linear track's carriage to a position, at a speed."""

    position_m: float
    speed_mps: float


Step = Move | Grip | Wait | Track


def gripper_drive_position(pos: float) -> float:
    """The drive-joint angle, in radians, the vendor driver commands for `pos`."""
    return (GRIPPER_OPEN_POS - pos) / GRIPPER_POS_PER_RAD


def parse(
    xml_text: str,
    *,
    dof: int,
    linkage: GripperLinkage,
    max_joint_velocity_rad_s: float,
) -> tuple[Step, ...]:
    """Read a Blockly program into steps, or raise `BlocklyError` naming why not.

    ``dof`` is the arm's joint count, ``linkage`` its gripper's opening map and
    ``max_joint_velocity_rad_s`` the velocity limit its description declares —
    the three facts the program's units are converted against.
    """
    if not 1 <= dof <= len(JOINT_FIELDS):
        raise BlocklyError(f"an arm with {dof} joints has no Blockly field names")
    if max_joint_velocity_rad_s <= 0.0:
        raise BlocklyError("the joint velocity limit must be positive")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise BlocklyError(f"not well-formed XML: {exc}") from exc
    if root.tag != _q("xml"):
        raise BlocklyError(f"the root element is {root.tag!r}, not a Blockly workspace")
    tops = [child for child in root if child.tag == _q("block")]
    others = [child.tag for child in root if child.tag != _q("block")]
    if others:
        raise BlocklyError(f"the workspace holds {others}; only blocks are read")
    if len(tops) != 1:
        raise BlocklyError(
            f"the workspace holds {len(tops)} top-level chains; the robot runs one, so "
            "this reader refuses to choose"
        )
    reader = _Reader(dof, linkage, max_joint_velocity_rad_s)
    return tuple(reader.chain(tops[0]))


def poses(steps: tuple[Step, ...]) -> dict[str, tuple[float, ...]]:
    """Every named pose the program moves through, in the order it first uses them."""
    named: dict[str, tuple[float, ...]] = {}
    for step in steps:
        if isinstance(step, Move):
            named.setdefault(step.pose, step.joints_rad)
    return named


def _q(tag: str) -> str:
    return f"{{{NAMESPACE}}}{tag}"


class _Reader:
    """Walks one chain of blocks, carrying the program's running state."""

    def __init__(self, dof: int, linkage: GripperLinkage, velocity_limit: float) -> None:
        self._dof = dof
        self._linkage = linkage
        self._velocity_limit = velocity_limit
        self._scaling: float | None = None
        self._last_width: float | None = None
        self._names: dict[tuple[float, ...], str] = {}

    # ------------------------------------------------------------ structure

    def chain(self, block: ElementTree.Element | None) -> Iterator[Step]:
        while block is not None:
            yield from self._block(block)
            block = self._next(block)

    def _next(self, block: ElementTree.Element) -> ElementTree.Element | None:
        following = block.find(_q("next"))
        if following is None:
            return None
        inner = following.find(_q("block"))
        if inner is None:
            raise BlocklyError(f"{self._where(block)}: an empty `next`")
        return inner

    def _block(self, block: ElementTree.Element) -> Iterator[Step]:
        kind = block.get("type", "")
        if block.get("disabled") is not None:
            raise BlocklyError(
                f"{self._where(block)} is disabled on the robot; this reader does not "
                "decide whether a disabled block runs"
            )
        handler = _HANDLERS.get(kind)
        if handler is None:
            raise BlocklyError(
                f"{self._where(block)}: block type {kind!r} is not modelled by the twin. "
                f"Modelled: {', '.join(sorted(_HANDLERS))}. Model it in "
                "cite_tools.model.blockly, or take it out of the program on the robot."
            )
        yield from handler(self, block)

    # ------------------------------------------------------------ blocks

    def _remark(self, block: ElementTree.Element) -> Iterator[Step]:
        self._fields(block, {"msg", "colour"})
        self._values(block, set())
        return iter(())

    def _angle_speed(self, block: ElementTree.Element) -> Iterator[Step]:
        fields = self._fields(block, {"speed"})
        self._values(block, set())
        speed = math.radians(self._number(block, fields["speed"], "speed"))
        if speed <= 0.0:
            raise BlocklyError(f"{self._where(block)}: a joint speed must be positive")
        self._scaling = speed / self._velocity_limit
        return iter(())

    def _reset(self, block: ElementTree.Element) -> Iterator[Step]:
        self._fields(block, set())
        self._values(block, set())
        yield Move(ZERO_POSE, (0.0,) * self._dof, self._require_scaling(block))

    def _move_joints(self, block: ElementTree.Element) -> Iterator[Step]:
        joints = JOINT_FIELDS[: self._dof]
        fields = self._fields(block, {*joints, "r", "wait"})
        self._values(block, set(_EDITOR_BUTTONS))
        if self._number(block, fields["r"], "r") != -1.0:
            raise BlocklyError(
                f"{self._where(block)}: r={fields['r']} blends this move into the next; the "
                "twin moves pose to pose and does not model blending (only r=-1 is read)"
            )
        self._require_wait(block, fields["wait"])
        value = tuple(math.radians(self._number(block, fields[f], f)) for f in joints)
        name = self._names.setdefault(value, f"{POSE_PREFIX}{len(self._names) + 1:02d}")
        yield Move(name, value, self._require_scaling(block))

    def _sleep(self, block: ElementTree.Element) -> Iterator[Step]:
        self._fields(block, set())
        seconds = self._number_input(block, "sec")
        if seconds < 0.0:
            raise BlocklyError(f"{self._where(block)}: a negative sleep")
        yield Wait(seconds)

    def _gripper(self, block: ElementTree.Element) -> Iterator[Step]:
        fields = self._fields(block, {"pos", "speed", "wait"})
        self._values(block, set(_EDITOR_BUTTONS))
        self._require_wait(block, fields["wait"])
        pos = self._number(block, fields["pos"], "pos")
        if not 0.0 <= pos <= GRIPPER_OPEN_POS:
            raise BlocklyError(
                f"{self._where(block)}: gripper pos {pos:g} is outside the vendor's "
                f"0..{GRIPPER_OPEN_POS:g}"
            )
        width = self._linkage.opening_m(gripper_drive_position(pos))
        closing = self._last_width is not None and width < self._last_width
        self._last_width = width
        yield Grip(width, closing)

    def _line_track(self, block: ElementTree.Element) -> Iterator[Step]:
        fields = self._fields(block, {"pos", "speed"})
        self._values(block, set(_EDITOR_BUTTONS))
        position = self._number(block, fields["pos"], "pos") / 1000.0
        speed = self._number(block, fields["speed"], "speed") / 1000.0
        if speed <= 0.0:
            raise BlocklyError(f"{self._where(block)}: a track speed must be positive")
        yield Track(position, speed)

    def _repeat(self, block: ElementTree.Element) -> Iterator[Step]:
        self._fields(block, set())
        times = self._number_input(block, "TIMES", allowed_statements={"DO"})
        if times < 0.0 or times != int(times):
            raise BlocklyError(f"{self._where(block)}: repeat {times:g} times")
        statement = block.find(_q("statement"))
        body = None if statement is None else statement.find(_q("block"))
        for _ in range(int(times)):
            yield from self.chain(body)

    # ------------------------------------------------------------ fields

    def _fields(self, block: ElementTree.Element, expected: set[str]) -> dict[str, str]:
        found = {f.get("name", ""): (f.text or "") for f in block.findall(_q("field"))}
        if set(found) != expected:
            raise BlocklyError(
                f"{self._where(block)}: fields {sorted(found)}, expected {sorted(expected)}"
            )
        return found

    def _values(self, block: ElementTree.Element, allowed: set[str]) -> None:
        for value in block.findall(_q("value")):
            name = value.get("name", "")
            if name not in allowed:
                raise BlocklyError(f"{self._where(block)}: an input {name!r} is not read")
            inner = value.find(_q("block"))
            if inner is None or inner.get("type") != name or len(inner):
                raise BlocklyError(
                    f"{self._where(block)}: input {name!r} is not the editor's own button"
                )
        if block.find(_q("statement")) is not None:
            raise BlocklyError(f"{self._where(block)}: a nested statement is not read")

    def _number_input(
        self,
        block: ElementTree.Element,
        name: str,
        allowed_statements: set[str] | None = None,
    ) -> float:
        values = block.findall(_q("value"))
        if [v.get("name") for v in values] != [name]:
            raise BlocklyError(f"{self._where(block)}: expected exactly one input {name!r}")
        statements = {s.get("name", "") for s in block.findall(_q("statement"))}
        if statements - (allowed_statements or set()):
            raise BlocklyError(f"{self._where(block)}: statements {sorted(statements)}")
        literal = next(iter(values[0]), None)
        if (
            literal is None
            or literal.tag not in (_q("shadow"), _q("block"))
            or literal.get("type") != "math_number"
            or len(values[0]) != 1
        ):
            raise BlocklyError(
                f"{self._where(block)}: input {name!r} is not a number literal; a computed "
                "value is not read"
            )
        field = self._fields(literal, {"NUM"})
        return self._number(block, field["NUM"], name)

    def _number(self, block: ElementTree.Element, text: str, name: str) -> float:
        try:
            value = float(text)
        except ValueError as exc:
            raise BlocklyError(f"{self._where(block)}: {name}={text!r} is not a number") from exc
        if not math.isfinite(value):
            raise BlocklyError(f"{self._where(block)}: {name}={text!r} is not finite")
        return value

    def _require_wait(self, block: ElementTree.Element, wait: str) -> None:
        if wait != "TRUE":
            raise BlocklyError(
                f"{self._where(block)}: wait={wait} lets the program run on before this "
                "motion ends; the twin runs one step at a time (only wait=TRUE is read)"
            )

    def _require_scaling(self, block: ElementTree.Element) -> float:
        if self._scaling is None:
            raise BlocklyError(
                f"{self._where(block)}: the program moves before any `set_angle_speed`; the "
                "robot's own default speed is not modelled, so the program must state one"
            )
        return self._scaling

    @staticmethod
    def _where(block: ElementTree.Element) -> str:
        return f"block {block.get('type', '?')!r} (id {block.get('id', '?')!r})"


_HANDLERS = {
    "tool_remark": _Reader._remark,
    "set_angle_speed": _Reader._angle_speed,
    "reset": _Reader._reset,
    "move_joints": _Reader._move_joints,
    "sleep": _Reader._sleep,
    "gripper_set": _Reader._gripper,
    "set_line_track": _Reader._line_track,
    "controls_repeat_ext": _Reader._repeat,
}
