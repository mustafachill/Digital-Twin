"""The gripper's stall threshold, and the measured window that bounds it.

`stall_velocity_threshold` shipped at 0.001 rad/s, twenty-five times below the
floor of the physically achievable window. That is not a value that produces a
slightly worse answer; it produces no answer at all.
`GripperActionController::checkForSuccess` terminates a goal in exactly two ways
and in no others — `|error| < goal_tolerance`, or a velocity that stays at or
below this threshold for `stall_timeout`. A drive joint creeping against a part
at 0.003-0.024 rad/s is permanently above 0.001, so it is counted as moving and
`last_movement_time` is reset on every cycle; the part meanwhile holds the
position error above `goal_tolerance`. Neither branch can fire, and the action
never returns. The caller sees a timeout rather than a wrong answer, which is
what kept the search in the layer above.

What these tests pin is the WINDOW, not the number. The window is the measured
fact; the value in the model is a choice inside it, and any value strictly
inside satisfies the mechanism. So the guard fires for anything outside — the
old 0.001 below, and an over-correction above — and stays silent for every
defensible choice in between. `TestTheGuardRejectsBothEnds` exists because a
bound nobody has watched fail is a bound nobody should trust: it drives the same
predicate that guards the real model with the two values that must be rejected.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model.loader import load

#: The floor: the fastest contact creep observed while the drive joint pressed
#: against a part. The observed range was 0.003-0.024 rad/s, so 0.025 is the
#: rounded bound and 0.024 is the fastest value actually seen. A threshold at or
#: below this counts creep as motion, and the stall branch becomes unreachable.
WINDOW_FLOOR_RAD_S = 0.025
FASTEST_OBSERVED_CREEP_RAD_S = 0.024

#: The ceiling: in free air, and against a part narrower than commanded, the
#: drive joint is still travelling at 0.160 rad/s at the instant
#: `|error| < goal_tolerance`, and was never slower in the preceding 0.4 s. A
#: threshold above this arms the stall timer during an ordinary approach.
WINDOW_CEILING_RAD_S = 0.16

#: The span over which the ceiling observation holds. It is load-bearing rather
#: than decorative: the ceiling is only evidence of a FALSE STALL because 0.4 s
#: exceeds `stall_timeout`, so the timer has time to expire. Raise the timeout
#: past this and the observation no longer covers the case it was taken for.
CEILING_OBSERVATION_SPAN_S = 0.4

#: The value that shipped, and an over-correction past the other end. Both are
#: load-bearing: a guard demonstrated against only one end is a guard with one
#: end untested, and this project has already shipped a test that passed with
#: the thing it checked removed.
SHIPPED_DEFECTIVE_THRESHOLD_RAD_S = 0.001
OVER_CORRECTED_THRESHOLD_RAD_S = 0.2

PARAMETER = "stall_velocity_threshold"
GRIPPER_CONTROLLER_TYPE = "position_controllers/GripperActionController"


def inside_measured_window(value: float) -> bool:
    """The predicate the whole file turns on. Strict at both ends.

    Strict rather than inclusive because both bounds are values that were
    *observed*, not values that were shown to work: a threshold sitting exactly
    on the fastest observed creep counts that creep as stationary only by a
    rounding, which is not a margin.
    """
    return WINDOW_FLOOR_RAD_S < value < WINDOW_CEILING_RAD_S


def gripper_controller(path: Path):
    effector = load(path).asset_type("xarm_parallel_gripper")
    assert effector is not None
    controllers = [c for c in effector.controllers if c.type == GRIPPER_CONTROLLER_TYPE]
    assert len(controllers) == 1, f"expected one gripper controller, found {len(controllers)}"
    return controllers[0]


def declared_threshold(path: Path) -> float:
    parameters = gripper_controller(path).parameters
    assert PARAMETER in parameters, (
        f"{PARAMETER} is not declared on the gripper controller at all. Left to "
        "GripperActionController's own default it would be unmeasured and invisible."
    )
    return float(parameters[PARAMETER])


def generated(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def set_threshold(
    edit_yaml: Callable[[Path, Callable[[dict], None]], None], model: Path, value: float
) -> None:
    path = model / "assets/types/end_effectors/xarm_parallel_gripper.yaml"

    def mutate(document: dict) -> None:
        for controller in document["asset_type"]["controllers"]:
            if controller["type"] == GRIPPER_CONTROLLER_TYPE:
                controller["parameters"][PARAMETER] = value
                return
        raise AssertionError("no gripper controller in the end-effector type")

    edit_yaml(path, mutate)


class TestTheModelSitsInsideTheMeasuredWindow:
    def test_the_declared_threshold_is_inside_the_window(self, real_model: Path) -> None:
        value = declared_threshold(real_model)
        assert inside_measured_window(value), (
            f"{PARAMETER} is {value} rad/s, outside the measured window "
            f"({WINDOW_FLOOR_RAD_S}, {WINDOW_CEILING_RAD_S}) rad/s. Below the floor the "
            "action never returns; above the ceiling a normal approach is reported as a "
            "stall. Re-measure the window before moving the value outside it."
        )

    def test_the_window_is_a_window(self) -> None:
        # Cheap, and it is what makes every other assertion here meaningful: an
        # inverted or empty window would make `inside_measured_window` reject
        # everything, and three of these tests would still pass.
        assert WINDOW_FLOOR_RAD_S < WINDOW_CEILING_RAD_S

    def test_the_floor_is_above_the_fastest_creep_that_was_observed(self) -> None:
        """Ties the rounded bound to the observation it came from."""
        assert WINDOW_FLOOR_RAD_S >= FASTEST_OBSERVED_CREEP_RAD_S

    def test_the_ceiling_observation_still_covers_the_stall_timeout(self, real_model: Path) -> None:
        """The ceiling is evidence only while the timer can expire inside it.

        The 0.160 rad/s reading is evidence of a false stall because it was
        sustained for 0.4 s and `stall_timeout` is shorter than that. Raise the
        timeout past the span the measurement covers and the ceiling stops being
        supported by it — so this fails rather than letting the justification rot
        while the number it justifies stays put.
        """
        timeout = float(gripper_controller(real_model).parameters["stall_timeout"])
        assert timeout <= CEILING_OBSERVATION_SPAN_S


class TestTheGuardRejectsBothEnds:
    """Both ends, driven through the same predicate that guards the real model.

    These load a real model with one value changed, rather than asserting
    `0.001 < 0.025` against literals — a comparison of two constants would pass
    even if nothing ever read the model.
    """

    @pytest.mark.parametrize(
        "value",
        [SHIPPED_DEFECTIVE_THRESHOLD_RAD_S, OVER_CORRECTED_THRESHOLD_RAD_S],
        ids=["below-the-floor", "above-the-ceiling"],
    )
    def test_a_value_outside_the_window_is_rejected(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
        value: float,
    ) -> None:
        set_threshold(edit_yaml, real_model, value)
        assert not inside_measured_window(declared_threshold(real_model))

    def test_a_different_value_inside_the_window_is_accepted(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The guard pins the window, not the number.

        Without this the two tests above are equally satisfied by a check that
        rejects everything except the one value currently in the model, which
        would turn a derived bound back into a tuned constant.
        """
        set_threshold(edit_yaml, real_model, 0.1)
        assert inside_measured_window(declared_threshold(real_model))


class TestTheThresholdReachesTheGeneratedConfiguration:
    """A threshold the controller never receives is not a threshold.

    `GripperActionController` reads this from its own parameters, so unlike the
    close rate it needs no description argument and no patch — but it still has
    to be emitted, and it has to be emitted from the model rather than from the
    generator.
    """

    def gripper_controllers(self, path: Path) -> dict[str, dict]:
        blocks: dict[str, dict] = {}
        for name, text in generated(path).items():
            if not name.startswith("control/"):
                continue
            for key, block in yaml.safe_load(text).items():
                parameters = block.get("ros__parameters", {})
                if PARAMETER in parameters:
                    blocks[f"{name}:{key}"] = parameters
        return blocks

    def test_every_generated_gripper_controller_carries_the_declared_value(
        self, real_model: Path
    ) -> None:
        blocks = self.gripper_controllers(real_model)
        assert blocks, f"no generated controller configuration declares {PARAMETER} at all"
        expected = declared_threshold(real_model)
        for name, parameters in blocks.items():
            assert parameters[PARAMETER] == pytest.approx(expected), name

    def test_the_value_follows_the_model_rather_than_the_generator(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """P1 and P5: one home for the value, and code that only carries it."""
        set_threshold(edit_yaml, real_model, 0.075)
        blocks = self.gripper_controllers(real_model)
        assert blocks
        for name, parameters in blocks.items():
            assert parameters[PARAMETER] == pytest.approx(0.075), name
