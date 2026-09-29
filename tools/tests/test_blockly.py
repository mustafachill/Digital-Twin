"""The Blockly reader: what it converts, and what it refuses (ADR-0067).

The real program is read from `model/programs/`, never restated here: these tests
check the reader against small programs written below, and the real program only
through what the reader makes of it.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools.generate import bringup, control, description
from cite_tools.model import blockly
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve
from cite_tools.validate import Severity, physical, referential

REPO = Path(__file__).resolve().parents[2]
REAL_PROGRAM = REPO / "model" / "programs" / "xarm5_real_demo.blockly.xml"
VENDOR_ARM = REPO / "workspace/src/external/xarm_ros2/xarm_description/urdf/xarm5/xarm5.urdf.xacro"


@pytest.fixture(scope="module")
def model():
    return load(REPO / "model")


@pytest.fixture(scope="module")
def linkage(model):
    return model.asset_type("xarm_parallel_gripper").grasp.linkage


def program(*blocks: str) -> str:
    """A workspace holding one chain of ``blocks``, in UFACTORY Studio's shape."""
    chain = ""
    for block in reversed(blocks):
        opening, closing = block.rsplit("</block>", 1)
        chain = f"{opening}{f'<next>{chain}</next>' if chain else ''}</block>{closing}"
    return f'<xml xmlns="https://developers.google.com/blockly/xml">{chain}</xml>'


BUTTONS = (
    '<value name="btn_move"><block type="btn_move" id="a"/></value>'
    '<value name="btn_edit"><block type="btn_edit" id="b"/></value>'
)
SPEED = '<block type="set_angle_speed" id="s"><field name="speed">20</field></block>'


def move(i, j, k, l, m, r="-1", wait="TRUE") -> str:  # noqa: E741 - Blockly's own names
    fields = "".join(
        f'<field name="{n}">{v}</field>' for n, v in zip("ijklm", (i, j, k, l, m), strict=True)
    )
    return (
        f'<block type="move_joints" id="mj">{fields}<field name="r">{r}</field>'
        f'<field name="wait">{wait}</field>{BUTTONS}</block>'
    )


def gripper(pos) -> str:
    return (
        f'<block type="gripper_set" id="g"><field name="pos">{pos}</field>'
        f'<field name="speed">5000</field><field name="wait">TRUE</field>{BUTTONS}</block>'
    )


def track(pos, speed=100) -> str:
    return (
        f'<block type="set_line_track" id="t"><field name="pos">{pos}</field>'
        f'<field name="speed">{speed}</field>{BUTTONS}</block>'
    )


def sleep(seconds) -> str:
    return (
        '<block type="sleep" id="z"><value name="sec"><shadow type="math_number" id="n">'
        f'<field name="NUM">{seconds}</field></shadow></value></block>'
    )


def parse(linkage, text: str) -> tuple[blockly.Step, ...]:
    return blockly.parse(text, dof=5, linkage=linkage, max_joint_velocity_rad_s=3.14)


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #


def test_joint_degrees_become_radians_and_a_named_pose(linkage) -> None:
    (step,) = parse(linkage, program(SPEED, move(-28, 31, -45, 14, -30)))
    assert isinstance(step, blockly.Move)
    assert step.pose == "blockly_01"
    assert step.joints_rad == pytest.approx(tuple(math.radians(d) for d in (-28, 31, -45, 14, -30)))


def test_the_angle_speed_is_a_fraction_of_the_velocity_limit(linkage) -> None:
    (step,) = parse(linkage, program(SPEED, move(0, 0, 0, 0, 0)))
    assert step.velocity_scaling == pytest.approx(math.radians(20) / 3.14)
    assert step.velocity_scaling == pytest.approx(0.1112, abs=1e-4)


def test_a_repeated_pose_keeps_its_first_name_and_reset_is_zero(linkage) -> None:
    steps = parse(
        linkage,
        program(
            SPEED,
            '<block type="reset" id="r"></block>',
            move(1, 2, 3, 4, 5),
            move(6, 7, 8, 9, 10),
            move(1, 2, 3, 4, 5),
        ),
    )
    assert [s.pose for s in steps] == ["zero", "blockly_01", "blockly_02", "blockly_01"]
    assert steps[0].joints_rad == (0.0,) * 5


def test_gripper_550_is_60_9_mm_and_a_close(linkage) -> None:
    opened, closed, reopened = parse(linkage, program(gripper(800), gripper(550), gripper(800)))
    assert blockly.gripper_drive_position(550) == pytest.approx(0.300)
    assert closed.width_m == pytest.approx(0.0609, abs=5e-5)
    assert opened.width_m == pytest.approx(0.0846, abs=5e-5)
    assert (opened.closing, closed.closing, reopened.closing) == (False, True, False)


def test_track_millimetres_become_metres(linkage) -> None:
    (step,) = parse(linkage, program(track(650, 100)))
    assert step == blockly.Track(position_m=0.65, speed_mps=0.1)


def test_sleep_is_seconds_and_a_remark_is_nothing(linkage) -> None:
    remark = (
        '<block type="tool_remark" id="c"><field name="msg">hello</field>'
        '<field name="colour">#ff8657</field></block>'
    )
    assert parse(linkage, program(remark, sleep(1.5))) == (blockly.Wait(1.5),)


def test_a_repeat_is_unrolled(linkage) -> None:
    body = sleep(1).replace("</block>", "</block>", 1)
    repeat = (
        '<block type="controls_repeat_ext" id="rp"><value name="TIMES">'
        '<shadow type="math_number" id="n"><field name="NUM">3</field></shadow></value>'
        f'<statement name="DO">{body}</statement></block>'
    )
    assert parse(linkage, program(repeat)) == (blockly.Wait(1.0),) * 3


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("blocks", "says"),
    [
        ((SPEED, '<block type="move_line" id="x"></block>'), "not modelled"),
        ((SPEED, move(0, 0, 0, 0, 0, r="5")), "blending"),
        ((SPEED, move(0, 0, 0, 0, 0, wait="FALSE")), "wait=FALSE"),
        ((move(0, 0, 0, 0, 0),), "set_angle_speed"),
        ((gripper(900),), "outside"),
        ((SPEED.replace('id="s"', 'id="s" disabled="true"'),), "disabled"),
    ],
)
def test_what_the_twin_does_not_model_is_refused(linkage, blocks, says) -> None:
    with pytest.raises(blockly.BlocklyError, match=says):
        parse(linkage, program(*blocks))


def test_two_top_level_chains_are_refused(linkage) -> None:
    text = program(SPEED).replace("</xml>", f"{sleep(1)}</xml>")
    with pytest.raises(blockly.BlocklyError, match="top-level"):
        parse(linkage, text)


# --------------------------------------------------------------------------- #
# The real program, as the model reads it
# --------------------------------------------------------------------------- #


def test_the_real_program_reads_as_the_robot_runs_it(model, linkage) -> None:
    steps = parse(linkage, REAL_PROGRAM.read_text())
    kinds = [type(s).__name__ for s in steps]
    assert kinds.count("Track") == 3
    assert [s.position_m for s in steps if isinstance(s, blockly.Track)] == [0.0, 0.65, 0.0]
    grips = [s for s in steps if isinstance(s, blockly.Grip)]
    assert [g.closing for g in grips] == [False, True, False]
    assert steps[0] == blockly.Move("zero", (0.0,) * 5, pytest.approx(0.1112, abs=1e-4))
    assert steps[-1].pose == "zero"


def test_the_plan_carries_the_program_poses_and_the_track(model) -> None:
    cell = resolve(model, "cell_b")
    (plan,) = bringup.generate(cell)
    document = yaml.safe_load(plan.content)["plan"]
    (manager,) = document["controller_managers"]
    poses = manager["moveit"]["poses_rad"]
    assert {"zero", "blockly_03", "blockly_06"} <= set(poses)
    assert manager["track"]["joint"] == "picker_track_joint"
    assert manager["track"]["command_topic"].endswith(
        "/picker_track_trajectory_controller/joint_trajectory"
    )
    assert {"name": "picker_track_trajectory_controller", "stage": 1} in manager["controllers"]
    (entry,) = document["programs"]
    assert entry["asset"] == "picker"
    tracks = [s for s in entry["steps"] if s["kind"] == "track"]
    assert [t["position_m"] for t in tracks] == [0, 0.65, 0]
    assert document["workpieces"]["models"][0]["size_m"] == [0.066, 0.066, 0.066]


def test_the_track_joint_is_under_the_arm_and_has_a_controller(model) -> None:
    cell = resolve(model, "cell_b")
    urdf = next(a for a in description.generate(cell) if a.path.endswith("_picker.urdf.xacro"))
    assert '<joint name="picker_track_joint" type="prismatic">' in urdf.content
    assert 'attach_to="picker_track_carriage"' in urdf.content
    controllers = next(a for a in control.generate(cell) if "picker" in a.path).content
    assert "/cite/cell_b/picker/picker_track_trajectory_controller:" in controllers
    assert "      - picker_track_joint" in controllers


def test_an_arm_without_a_track_is_unchanged(model) -> None:
    cell = resolve(model, "cell_a")
    assert all(a.axis is None and not a.program for a in cell.assets)


# --------------------------------------------------------------------------- #
# The validator
# --------------------------------------------------------------------------- #


def _rules(path: Path, level) -> set[str]:
    return {f.rule for f in level.check(load(path)) if f.severity is Severity.ERROR}


def test_a_program_the_reader_refuses_is_a_finding(real_model: Path) -> None:
    source = real_model / "programs" / "xarm5_real_demo.blockly.xml"
    source.write_text(source.read_text().replace('"move_joints"', '"move_line"', 1))
    assert "program-refused" in _rules(real_model, referential)


def test_a_pose_past_the_vendor_limit_is_a_finding(real_model: Path) -> None:
    source = real_model / "programs" / "xarm5_real_demo.blockly.xml"
    text = source.read_text().replace('<field name="k">-45</field>', '<field name="k">15</field>')
    source.write_text(text)
    assert "program-pose-outside-joint-limits" in _rules(real_model, referential)


def test_a_track_move_past_the_stroke_is_a_finding(real_model: Path) -> None:
    source = real_model / "programs" / "xarm5_real_demo.blockly.xml"
    source.write_text(source.read_text().replace('"pos">650<', '"pos">750<'))
    assert "program-track-beyond-stroke" in _rules(real_model, referential)


def test_a_part_the_program_cannot_stall_on_is_a_finding(
    real_model: Path, edit_yaml: Callable
) -> None:
    edit_yaml(
        real_model / "assets/types/workpieces/workpiece.yaml",
        lambda d: d["asset_type"]["description"]["body"]["collision"].__setitem__(
            "size_m", [0.065, 0.065, 0.065]
        ),
    )
    assert "program-grip-never-evidences-a-grasp" in _rules(real_model, physical)


def test_an_arm_and_its_track_on_different_backends_is_a_finding(
    real_model: Path, edit_yaml: Callable
) -> None:
    def to_real(document: dict) -> None:
        picker = next(a for a in document["assets"] if a["id"] == "picker")
        picker["hardware"] = {"backend": "real", "params": {"real": {"robot_ip": "10.0.0.2"}}}

    edit_yaml(real_model / "assets/instances/arms.yaml", to_real)
    assert "track-backend-differs-from-its-arm" in _rules(real_model, referential)


@pytest.mark.skipif(not VENDOR_ARM.is_file(), reason="the vendor source is not imported")
def test_the_declared_limits_are_the_vendors(model) -> None:
    """L0 copies the vendor's joint limits; a pin bump that moves them fails here."""
    source = VENDOR_ARM.read_text()
    kinematics = model.asset_type("xarm5").kinematics
    for (low, high), text in zip(
        kinematics.joint_limits_rad,
        ("${-2.0*pi}", "${-2.059}", "${-3.927}", "${-1.69297}", "${-2.0*pi}"),
        strict=True,
    ):
        assert text in source
        assert low < high
    assert kinematics.joint_limits_rad[1] == (-2.059, 2.0944)
    assert kinematics.joint_limits_rad[2] == (-3.927, 0.19198)
    assert source.count(f'velocity="{kinematics.max_joint_velocity_rad_s}"') == 5
