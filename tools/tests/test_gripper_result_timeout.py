"""The gripper result deadline: where it lives, and the floor it may not go under.

ADR-0045. The deadline used to be `constexpr std::chrono::seconds{20}` in
`cite_skills`, compared against `steady_clock` — the host's wall clock — while
everything it supervised ran in simulation time. On a loaded CI runner it expired
while the gripper was still moving, three times, and each time `Pick` reported an
empty gripper it had never observed.

The remedy has two halves and this file guards the model half: the value is
declared on the L0 end-effector type and travels to L3 through the generated
bring-up plan, so no number for it exists in C++ at all. The other half — that the
deadline is counted in the node's own clock and that its expiry cancels the goal —
is a behaviour of the running node and is held by
`cite_bringup/test/test_gripper_deadline_launch.py`.

WHAT IS PINNED HERE IS THE FLOOR AND NOT THE VALUE, and that asymmetry is the
decision rather than an omission. Above the floor the number carries no claim,
because the quantity anyone would want to bound — how long
`GripperActionController` takes to declare a stall under contact chatter — has no
upper bound at all: the controller restarts its stall search on every control
cycle above `stall_velocity_threshold`. Below the floor the deadline cuts short
grasps that were about to succeed, and that IS derivable.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, physical

#: The rule this file is about.
RULE = "gripper-result-timeout-cuts-the-stall-search-short"

#: The key as L0 spells it, and as the generated plan and the skill server spell
#: it. Written once here so that a rename that broke the chain fails a test rather
#: than silently delivering nothing — which is exactly how seven linkage
#: dimensions once travelled nowhere while the node ran on compiled defaults.
MODEL_KEY = "result_timeout_s"
PLAN_KEY = "gripper_result_timeout_s"

EFFECTOR = "assets/types/end_effectors/xarm_parallel_gripper.yaml"


def physical_rules(path: Path, severity: Severity) -> set[str]:
    return {f.rule for f in physical.check(load(path)) if f.severity is severity}


def generated(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


@pytest.fixture
def grasp(real_model: Path):
    effector = load(real_model).asset_type("xarm_parallel_gripper")
    assert effector is not None and effector.grasp is not None
    return effector.grasp


@pytest.fixture
def stall_timeout_s(real_model: Path) -> float:
    effector = load(real_model).asset_type("xarm_parallel_gripper")
    assert effector is not None
    for controller in effector.controllers:
        value = controller.parameters.get("stall_timeout")
        if value is not None:
            return float(value)
    raise AssertionError(
        "the gripper controller declares no stall_timeout, so the floor below is "
        "derived from nothing"
    )


class TestTheFloorArithmetic:
    """The derivation a future reader has to be able to recompute."""

    def test_the_floor_is_the_stroke_plus_the_stall_timeout(
        self, grasp, stall_timeout_s: float
    ) -> None:
        """`GripperActionController` ends a goal in exactly two ways.

        Either the joint arrives, or it stops moving for `stall_timeout`. So a full
        stroke at the MAXIMUM rate the joint may travel, plus that timeout, is the
        SHORTEST time in which either branch can fire on a full-stroke close.
        Anything below it gives up on grasps that were about to succeed.

        WHICH MAKES THE FLOOR NECESSARY AND NOT SUFFICIENT, and this docstring used
        to say the opposite — "the longest a legitimate close can take". It is a
        lower bound, because it is computed from a maximum rate: a plant driving at
        half its declared limit takes twice as long, and a value that clears this
        floor can still expire mid-stroke. What the assertion below pins is that
        the declared value is not BELOW the least it could possibly need.
        """
        stroke_s = abs(grasp.closed_position - grasp.open_position) / grasp.max_drive_rate_rad_s
        floor_s = stroke_s + stall_timeout_s
        assert grasp.result_timeout_s > floor_s, (
            f"the declared {grasp.result_timeout_s} s does not clear the {floor_s:.3f} s "
            f"floor, so an ordinary contact stall can be cut short"
        )

    def test_the_declared_value_clears_the_floor_by_an_order_of_magnitude(
        self, grasp, stall_timeout_s: float
    ) -> None:
        """Not a requirement — a statement of where the shipped value sits.

        The floor is the constraint and this is the margin above it, asserted
        loosely so that it records the shape of the choice without pretending the
        exact number was measured. It was not: ADR-0045 decision 3 says in as many
        words that above the floor its size carries no claim.
        """
        stroke_s = abs(grasp.closed_position - grasp.open_position) / grasp.max_drive_rate_rad_s
        assert grasp.result_timeout_s > 10.0 * (stroke_s + stall_timeout_s)


class TestTheValidatorRejectsTheDefect:
    def test_the_real_model_is_clean(self, real_model: Path) -> None:
        assert RULE not in physical_rules(real_model, Severity.ERROR)

    def test_a_deadline_inside_the_stall_search_is_an_error(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """A tenth of a second: shorter than the stroke, let alone the stall wait."""
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__(MODEL_KEY, 0.1),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)

    def test_a_deadline_exactly_at_the_floor_is_an_error(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The boundary is exclusive, and it is exclusive on purpose.

        A deadline equal to the floor expires at the same instant the controller
        becomes able to answer — a race whose two outcomes are "the grasp worked"
        and "the gripper never replied". A bound that has to win a race is not a
        bound.
        """
        model = load(real_model)
        effector = model.asset_type("xarm_parallel_gripper")
        grasp = effector.grasp
        stall = float(
            next(
                c.parameters["stall_timeout"]
                for c in effector.controllers
                if "stall_timeout" in c.parameters
            )
        )
        floor = (
            abs(grasp.closed_position - grasp.open_position) / grasp.max_drive_rate_rad_s
        ) + stall
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__(MODEL_KEY, floor),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)

    def test_a_slower_gripper_moves_the_floor_with_it(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The floor is derived, not written down, and this is what proves it.

        A deadline that is comfortable at 1 rad/s is not comfortable on a gripper
        whose stroke takes fifty times longer. Nothing in the rule mentions a
        number, so this passes only if the arithmetic is really being done.
        """
        edit_yaml(
            real_model / EFFECTOR,
            lambda d: (
                d["asset_type"]["grasp"].__setitem__("max_drive_rate_rad_s", 0.02),
                d["asset_type"]["grasp"].__setitem__("follower_max_rate_rad_s", 2.0),
            ),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)


class TestTheValueTravelsToL3:
    """P1: one declaration, delivered — not a second copy that happens to agree."""

    def test_the_generated_plan_carries_it_for_every_arm(self, real_model: Path) -> None:
        effector = load(real_model).asset_type("xarm_parallel_gripper")
        declared = effector.grasp.result_timeout_s

        plans = [
            content
            for path, content in generated(real_model).items()
            if path.endswith("_plan.yaml")
        ]
        assert plans, "the generator emitted no bring-up plan at all"

        carried = 0
        for plan in plans:
            document = yaml.safe_load(plan)
            for manager in document["plan"]["controller_managers"]:
                if not manager.get("gripper_action"):
                    continue
                assert PLAN_KEY in manager, (
                    f"{manager['asset']} has a gripper and the plan does not tell its skill "
                    f"server how long to wait for it. An undelivered parameter is accepted "
                    f"by launch, dropped by rclcpp and reported by neither"
                )
                assert manager[PLAN_KEY] == pytest.approx(declared)
                carried += 1
        assert carried >= 1, "no arm in the generated plan has a gripper at all"

    def test_no_deadline_is_compiled_into_the_skill_server(self) -> None:
        """ADR-0045 decision 2, read from the source it is about.

        `kGripperResultWait` is deleted rather than moved, and the parameter's
        compiled default is zero — a sentinel meaning "not supplied", against
        which the node refuses to configure. A default equal to the L0 value would
        be the second copy the decision exists to remove: it would work, and it
        would work only for as long as the two copies agreed.

        THIS TEST IS COUPLED TO A LITERAL COMMENT FRAGMENT AND THAT IS A KNOWN
        WEAKNESS. The `replace` below exempts one comment line — the one in
        `skill_server.cpp` that says what the deleted constant used to be — by
        matching its exact text. Reword that comment and this test fails for a
        reason that has nothing to do with the constant; delete the comment and the
        exemption stops covering anything and the test passes for the wrong reason.
        What it is actually asking is "does the identifier appear outside prose",
        which wants a comment-stripping parse rather than a string match. Left as it
        is deliberately: the fix is a small parser and it is not this change's.
        """
        source = (
            Path(__file__).resolve().parents[2] / "workspace/src/cite_skills/src/skill_server.cpp"
        ).read_text()
        assert "kGripperResultWait" not in source.replace(
            "//: `kGripperResultWait{20}` bounded", ""
        ), "the compiled constant is still there under its own name"
        assert f'declare_parameter("{PLAN_KEY}", 0.0)' in source, (
            "the deadline parameter is either undeclared — in which case a delivered value "
            "is dropped silently — or declared with a compiled duration, which is a second "
            "home for an L0 value"
        )
