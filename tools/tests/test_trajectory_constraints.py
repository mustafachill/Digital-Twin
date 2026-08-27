"""ADR-0036: the execution-side mistracking detector, generated from L0.

The gap these tests guard is a *silence*, which makes the negative assertions the
load-bearing half. Before this block existed, `joint_trajectory_controller`
defaulted every tolerance to 0.0, 0.0 disables the check, and a trajectory that
clipped a fixture ran to the end and reported SUCCEEDED. Nothing failed. So a
test that merely renders the model and finds numbers in the output would have
passed just as happily against a generator that emitted them for one joint, or
for one arm, or with the zero that means "off" — and each of those is the
original defect wearing the new block's name.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model.loader import ModelError, load

#: Every arm in the real cell. The detector is worth nothing on two arms out of
#: three, and an expansion bug is per-instance rather than per-type.
ARMS = ("arm_1", "arm_2", "arm_3")

ARM_TYPE = "assets/types/robots/xarm5.yaml"


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def controller_block(path: Path, arm: str) -> dict:
    """The parsed `ros__parameters` of one arm's trajectory controller."""
    document = yaml.safe_load(artifacts(path)[f"control/cell_a_{arm}_controllers.yaml"])
    return document[f"/cite/cell_a/{arm}/{arm}_joint_trajectory_controller"]["ros__parameters"]


def edit_constraints(edit_yaml: Callable, model: Path, mutate: Callable[[dict], None]) -> None:
    """Mutate the trajectory controller's `constraints:` block in the arm type.

    The controller is found by TYPE rather than by list index, so that reordering
    the type's controllers does not silently point these tests at the gripper.
    """

    def _apply(document: dict) -> None:
        controllers = document["asset_type"]["controllers"]
        trajectory = next(
            c
            for c in controllers
            if c["type"] == "joint_trajectory_controller/JointTrajectoryController"
        )
        mutate(trajectory)

    edit_yaml(model / ARM_TYPE, _apply)


class TestTheDetectorReachesEveryJoint:
    """The block is generated, complete, and per-instance."""

    def test_every_arm_declares_a_constraints_block(self, real_model: Path) -> None:
        for arm in ARMS:
            assert "constraints" in controller_block(real_model, arm), arm

    def test_every_joint_the_controller_owns_has_a_tolerance(self, real_model: Path) -> None:
        # The per-joint expansion is keyed by joint NAME, and a name that is not
        # in the controller's own `joints:` list is a parameter the controller
        # never reads — it does not error, it is simply ignored, which is the
        # silent-miss shape this whole block exists to remove.
        for arm in ARMS:
            block = controller_block(real_model, arm)
            constraints = block["constraints"]
            per_joint = {k: v for k, v in constraints.items() if isinstance(v, dict)}
            assert set(per_joint) == set(block["joints"]), arm
            assert len(per_joint) == 5, arm
            for joint, tolerances in per_joint.items():
                assert tolerances["goal"] > 0.0, joint
                assert tolerances["trajectory"] > 0.0, joint

    def test_the_joint_names_are_the_instances_own(self, real_model: Path) -> None:
        # arm_2's tolerances must name arm_2's joints. A type-level expansion
        # would emit the vendor's bare `joint1`, which every controller ignores.
        block = controller_block(real_model, "arm_2")
        assert "arm_2_joint1" in block["constraints"]
        assert "joint1" not in block["constraints"]
        assert "arm_1_joint1" not in block["constraints"]

    def test_a_non_trajectory_controller_gets_no_constraints(self, real_model: Path) -> None:
        # The gripper ends a goal by stalling, deliberately (ADR-0022). A path
        # tolerance there would abort exactly the grasp it is supposed to report.
        document = yaml.safe_load(artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"])
        gripper = document["/cite/cell_a/arm_1/arm_1_gripper_controller"]["ros__parameters"]
        assert "constraints" not in gripper


class TestTheValuesAreTheTypesOwn:
    """P5: the model states the tolerance, the generator expands it."""

    def test_the_tolerances_follow_the_model(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c["constraints"].update(
                {
                    "goal_time_s": 1.25,
                    "goal_tolerance_rad": 0.02,
                    "trajectory_tolerance_rad": 0.75,
                    "stopped_velocity_tolerance_rad_s": 0.03,
                }
            ),
        )
        constraints = controller_block(real_model, "arm_1")["constraints"]
        assert constraints["goal_time"] == 1.25
        assert constraints["stopped_velocity_tolerance"] == 0.03
        assert constraints["arm_1_joint3"] == {"trajectory": 0.75, "goal": 0.02}

        # The negative half. A generator holding its own constants would still
        # have passed everything above if it also emitted them somewhere.
        text = artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        assert "goal_time: 0.5" not in body
        assert "trajectory: 1.0" not in body

    def test_zero_survives_as_a_float(self, real_model: Path) -> None:
        # `stopped_velocity_tolerance` is 0.0 on purpose, and 0.0 is exactly the
        # value that YAML would hand back as an INTEGER if the generator wrote a
        # bare `0`. The node declares a double and rejects an integer with
        # "invalid type: expected [double] got [integer]" — an error that names
        # the type and not the missing decimal point, at controller load.
        text = artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        assert "stopped_velocity_tolerance: 0.0" in text
        assert "stopped_velocity_tolerance: 0\n" not in text
        value = controller_block(real_model, "arm_1")["constraints"]["stopped_velocity_tolerance"]
        assert isinstance(value, float)

    def test_the_block_is_identical_on_both_backends(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # P2. A tolerance that differed between simulation and hardware would
        # mean the two cells fail at different times on the same trajectory, and
        # every claim built on the twin's execution path would be unfounded.
        sim = controller_block(real_model, "arm_1")["constraints"]
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0].__setitem__(
                "hardware", {"backend": "real", "params": {"robot_ip": "192.168.1.100"}}
            ),
        )
        assert controller_block(real_model, "arm_1")["constraints"] == sim


class TestThePathToleranceCanBeDeclined:
    """`null` is a supported answer, and it is not the same as zero."""

    def test_null_omits_the_trajectory_key_and_keeps_the_goal_key(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The path tolerance is the one that can cry wolf, and a flake here lands
        # on a blocking CI gate. Declining it must stay cheaper than widening it
        # to a value that never fires — otherwise the pressure runs the wrong way.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c["constraints"].__setitem__("trajectory_tolerance_rad", None),
        )
        constraints = controller_block(real_model, "arm_1")["constraints"]
        for arm_joint in (f"arm_1_joint{n}" for n in range(1, 6)):
            assert constraints[arm_joint] == {"goal": 0.01}, arm_joint
        # The goal-side pair is untouched: declining the path check must not
        # quietly disable the detector that fires after the trajectory ends.
        assert constraints["goal_time"] == 0.5


class TestTheDisabledCombinationsCannotBeWritten:
    """The schema refuses the values that turn a detector into a defect."""

    def test_a_missing_block_on_a_trajectory_controller_is_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # THIS IS THE REGRESSION GUARD, and it is the test that fails on the
        # tree as it stood before ADR-0036. Defaulting instead of raising would
        # reproduce the original defect exactly: every tolerance 0.0, every
        # check disabled, every mistracked trajectory reported SUCCEEDED.
        from cite_tools.generate.control import MissingTrajectoryConstraintsError

        edit_constraints(edit_yaml, real_model, lambda c: c.pop("constraints"))
        with pytest.raises(MissingTrajectoryConstraintsError, match="SUCCEEDED"):
            artifacts(real_model)

    @pytest.mark.parametrize("field", ["goal_time_s", "goal_tolerance_rad"])
    def test_zero_is_refused_for_the_goal_side_pair(
        self, real_model: Path, edit_yaml: Callable, field: str
    ) -> None:
        # These two are useless apart and dangerous apart, so neither may be
        # zeroed to "switch off half".
        #
        #   goal_tolerance_rad = 0.0  -> the position check is skipped, the
        #       success branch is taken at once, and goal_time is dead config.
        #   goal_time_s = 0.0         -> `within_goal_time` is only ever set
        #       false inside `if (goal_time_tolerance != 0.0)`, so a joint
        #       outside tolerance can neither succeed nor fail and the
        #       controller runs another cycle forever. Upstream: "If set to
        #       zero, the controller will wait a potentially infinite amount of
        #       time." That is a HANG, which is strictly worse than the false
        #       success this block replaces — the caller sees a timeout in the
        #       layer above rather than an answer.
        edit_constraints(edit_yaml, real_model, lambda c: c["constraints"].__setitem__(field, 0.0))
        with pytest.raises(ModelError, match=field):
            artifacts(real_model)

    def test_a_negative_stopped_velocity_tolerance_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Zero is legal here and means "do not check velocity at the goal".
        # Negative is not a looser zero; it is a value nothing reads.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c["constraints"].__setitem__("stopped_velocity_tolerance_rad_s", -1.0),
        )
        with pytest.raises(ModelError, match="stopped_velocity_tolerance_rad_s"):
            artifacts(real_model)

    def test_an_unknown_constraint_key_is_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # `extra="forbid"`, asserted here because a mistyped tolerance is the
        # failure that looks most like success: the block renders, the file
        # loads, and the tolerance the author meant to set is simply absent.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c["constraints"].__setitem__("goal_tolerance_radians", 0.02),
        )
        with pytest.raises(ModelError):
            artifacts(real_model)
