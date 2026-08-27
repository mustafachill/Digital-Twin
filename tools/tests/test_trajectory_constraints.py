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


class TestTheVelocityCheckIsDeadOnThisCell:
    """`stopped_velocity_tolerance` cannot fire here, and the record must say so.

    ADR-0036's first version claimed the opposite in four places: that this was
    the one goal-side check already armed, and that setting `goal_time` armed it.
    Both are false for a controller that commands position alone.
    `check_state_tolerance_per_joint` compares the tolerance against
    `state_error_.velocities[i]`, and `compute_error_for_joint` writes that entry
    only under `has_velocity_state_interface_ && (has_velocity_command_interface_
    || has_effort_command_interface_)` — so with `command_interfaces: [position]`
    it stays at the zero it was sized to and no tolerance can be exceeded.

    The claim was prose, so nothing could catch it. These tests make the fact the
    prose rests on a generated one instead.
    """

    def test_no_arm_commands_velocity_or_effort(self, real_model: Path) -> None:
        # THE FACT THE WHOLE CORRECTION RESTS ON. If this fails, somebody has
        # given an arm a velocity or effort command interface — a reasonable
        # change, and also the single change that arms
        # `stopped_velocity_tolerance` for the first time. UFACTORY's own
        # xarm5_controllers.yaml commands [position, velocity], so this is a
        # plausible direction rather than a hypothetical one. Whoever makes it
        # owns deciding that tolerance: the upstream default is 0.01, not zero.
        for arm in ARMS:
            block = controller_block(real_model, arm)
            assert set(block["command_interfaces"]) == {"position"}, arm
            assert block["constraints"]["stopped_velocity_tolerance"] == 0.0, arm

    def test_the_generated_comment_says_the_check_cannot_fire(self, real_model: Path) -> None:
        text = artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        assert "THIS CHECK CANNOT FIRE on this controller" in text
        assert "THIS CHECK IS LIVE" not in text

    def test_a_velocity_command_interface_flips_the_comment(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The direction that matters, and the one no fixed comment could get
        # right: the generated file has to change its account of this tolerance
        # when the model changes the interfaces the account depends on. Before
        # the 2026-08-27 correction the template emitted one paragraph claiming
        # the check was armed — wrong for the cell as it stands, and it would
        # have stayed wrong in the other direction here.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c.__setitem__("command_interfaces", ["position", "velocity"]),
        )
        text = artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        assert "THIS CHECK IS LIVE on this controller" in text
        assert "THIS CHECK CANNOT FIRE" not in text

    def test_an_effort_command_interface_also_flips_it(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # `has_effort_command_interface_` is the second disjunct upstream, and
        # reading only the first is how this class of mistake happens.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c.__setitem__("command_interfaces", ["position", "effort"]),
        )
        assert (
            "THIS CHECK IS LIVE on this controller"
            in artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        )

    def test_a_velocity_state_interface_alone_does_not_arm_it(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The conjunction, not the disjunction. A velocity STATE interface is
        # what this cell already has, and on its own it arms nothing. Mistaking
        # the two is exactly the reading that produced the false claim.
        edit_constraints(
            edit_yaml,
            real_model,
            lambda c: c.__setitem__("state_interfaces", ["position", "velocity"]),
        )
        assert (
            "THIS CHECK CANNOT FIRE on this controller"
            in artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        )


class TestEveryControllerTypeIsClassified:
    """A new controller type cannot slip the tolerance guard in silence.

    `TRAJECTORY_CONTROLLER_TYPES` is an exact-match set, deliberately — a
    substring test on a plugin name is the kind of rule that matches the wrong
    thing quietly. But an exact-match set has its own silent failure: a type
    declaring a trajectory controller under some other plugin name is not in the
    set, is therefore never required to carry tolerances, and ships with them
    disabled. That is the original ADR-0036 defect, reintroduced with no signal.

    This is the signal. It does not guess which kind a new type is; it refuses to
    let one exist without somebody saying.
    """

    def test_every_declared_controller_type_is_in_exactly_one_set(self, real_model: Path) -> None:
        assert not (
            gen.control.TRAJECTORY_CONTROLLER_TYPES & gen.control.NON_TRAJECTORY_CONTROLLER_TYPES
        )
        known = (
            gen.control.TRAJECTORY_CONTROLLER_TYPES | gen.control.NON_TRAJECTORY_CONTROLLER_TYPES
        )
        # The TYPE is where the guard reads from — `_constraints_view` tests
        # `controller.type` against the set — so the type is where an
        # unclassified controller has to be caught, whether or not any instance
        # of it is placed yet.
        declared = {
            controller.type
            for asset_type in load(real_model).types
            for controller in asset_type.controllers
        }
        unclassified = declared - known
        assert not unclassified, (
            f"controller type(s) {sorted(unclassified)} appear in model/ and in neither "
            "TRAJECTORY_CONTROLLER_TYPES nor NON_TRAJECTORY_CONTROLLER_TYPES in "
            "cite_tools/generate/control.py. Decide which: a type that executes whole "
            "trajectories belongs in the first and must then declare a `constraints:` "
            "block, or the generator ships it with every tolerance at the 0.0 that "
            "disables the check (ADR-0036). Anything else belongs in the second."
        )
