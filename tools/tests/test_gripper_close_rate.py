"""The gripper's close rate, and the headroom that is the reason for it.

This exists because the defect it guards was invisible three separate ways. The
gripper looked correct in its URDF, the controller reported every goal reached,
and the two earlier explanations offered for it — that the leader joint stepped,
and that the runaway follower was structurally `left_finger_joint` — were both
disproved by traces. What was actually wrong was a quantity nothing computed:
the leader and its mimic followers carried the same 2 rad/s velocity limit, so a
follower keeping up with the leader was already at its own limit and had nothing
left to correct with.

The tests below pin the arithmetic of that quantity, pin the model against it,
and pin the two halves of the remedy — a bound and something that enforces it —
which were measured to be worthless individually and sufficient together.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, physical

#: Vendor fact: `xarm_gripper.urdf.xacro` gives all six gripper joints
#: `<limit lower="0" upper="0.85" effort="50" velocity="2"/>`. The model restates
#: it as `follower_max_rate_rad_s`, and this is the independent copy that catches
#: the restatement drifting away from the vendor.
VENDOR_JOINT_VELOCITY_LIMIT_RAD_S = 2.0

#: The leader rate measured sufficient in 3 of 3 runs, and the one measured to
#: fail in 3 of 3. Both are load-bearing: the second is what makes the first
#: evidence rather than a preference.
MEASURED_SUFFICIENT_RATE_RAD_S = 1.5
MEASURED_FAILING_RATE_RAD_S = 2.0


@pytest.fixture
def grasp(real_model: Path):
    effector = load(real_model).asset_type("xarm_parallel_gripper")
    assert effector is not None and effector.grasp is not None
    return effector.grasp


def physical_rules(path: Path, severity: Severity) -> set[str]:
    return {f.rule for f in physical.check(load(path)) if f.severity is severity}


def generated(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


class TestTheHeadroomArithmetic:
    """The derivation a future reader has to be able to recompute."""

    def test_headroom_is_what_is_left_below_the_follower_limit(self, grasp) -> None:
        expected = 1.0 - (grasp.max_drive_rate_rad_s / grasp.follower_max_rate_rad_s)
        assert grasp.follower_headroom_fraction == pytest.approx(expected)

    def test_equal_limits_leave_exactly_nothing(self, grasp) -> None:
        """The measured defect, expressed as the number that describes it.

        With the leader and the followers both at 2 rad/s the followers were at
        100% of their authority for the whole stroke — the standing error the
        servo needs to command 2 rad/s is 2/150 = 0.0133 rad and the measured lag
        was 0.0124.
        """
        equal = grasp.model_copy(update={"max_drive_rate_rad_s": grasp.follower_max_rate_rad_s})
        assert equal.follower_headroom_fraction == 0.0

    def test_the_declared_rate_leaves_at_least_what_was_measured(self, grasp) -> None:
        assert grasp.follower_headroom_fraction >= physical.MIN_MEASURED_FOLLOWER_HEADROOM

    def test_the_measured_threshold_is_the_headroom_1_point_5_gives(self) -> None:
        # Ties the constant to the run it came from, so moving one without the
        # other fails rather than silently loosening the bound.
        measured = 1.0 - MEASURED_SUFFICIENT_RATE_RAD_S / VENDOR_JOINT_VELOCITY_LIMIT_RAD_S
        assert measured == pytest.approx(physical.MIN_MEASURED_FOLLOWER_HEADROOM)


class TestTheModelMatchesTheVendorDescription:
    def test_the_follower_limit_is_the_one_the_vendor_declares(self, grasp) -> None:
        """`follower_max_rate_rad_s` is a restatement, and restatements rot.

        L1 forbids ingesting a vendor description, so this number is written in
        the model rather than parsed out of `xarm_gripper.urdf.xacro`. That is a
        deliberate trade: the cost is that a vendor bump can invalidate it
        silently, and this test is what converts that into a failure.
        """
        assert grasp.follower_max_rate_rad_s == VENDOR_JOINT_VELOCITY_LIMIT_RAD_S

    def test_the_close_rate_is_below_the_follower_limit(self, grasp) -> None:
        assert grasp.max_drive_rate_rad_s < grasp.follower_max_rate_rad_s

    def test_the_stroke_still_completes_within_the_joint_travel(self, grasp) -> None:
        # A rate is only meaningful against a stroke: 0.85 rad at 1.0 rad/s is
        # 0.85 s of travel, which is the cost the declaration is buying margin at.
        stroke = grasp.closed_position - grasp.open_position
        assert stroke / grasp.max_drive_rate_rad_s < 1.0


class TestTheValidatorRejectsTheDefect:
    def test_the_real_model_is_clean(self, real_model: Path) -> None:
        assert "gripper-followers-have-no-headroom" not in physical_rules(
            real_model, Severity.ERROR
        )
        assert "gripper-follower-headroom-is-unmeasured" not in physical_rules(
            real_model, Severity.WARNING
        )

    def test_restoring_the_vendor_rate_is_an_error(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """The exact configuration that produced the measured failure."""
        path = real_model / "assets/types/end_effectors/xarm_parallel_gripper.yaml"
        edit_yaml(
            path,
            lambda d: d["asset_type"]["grasp"].__setitem__(
                "max_drive_rate_rad_s", MEASURED_FAILING_RATE_RAD_S
            ),
        )
        assert "gripper-followers-have-no-headroom" in physical_rules(real_model, Severity.ERROR)

    def test_a_rate_below_the_measured_threshold_only_warns(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """Unmeasured is not the same as broken, and the severities say so."""
        path = real_model / "assets/types/end_effectors/xarm_parallel_gripper.yaml"
        edit_yaml(
            path,
            lambda d: d["asset_type"]["grasp"].__setitem__("max_drive_rate_rad_s", 1.9),
        )
        assert "gripper-follower-headroom-is-unmeasured" in physical_rules(
            real_model, Severity.WARNING
        )
        assert "gripper-followers-have-no-headroom" not in physical_rules(
            real_model, Severity.ERROR
        )


class TestEnforcementReachesTheGeneratedConfiguration:
    """The other half of the remedy. A bound nothing enforces changes nothing."""

    def controller_managers(self, path: Path) -> dict[str, dict]:
        managers: dict[str, dict] = {}
        for name, text in generated(path).items():
            if not name.startswith("control/"):
                continue
            for key, block in yaml.safe_load(text).items():
                if key.endswith("/controller_manager"):
                    managers[key] = block["ros__parameters"]
        return managers

    def test_every_controller_manager_enforces_limits(self, real_model: Path) -> None:
        managers = self.controller_managers(real_model)
        assert managers, "no controller manager was generated at all"
        for name, params in managers.items():
            assert params["enforce_command_limits"] is True, name

    def test_the_flag_follows_the_model_rather_than_the_generator(
        self,
        real_model: Path,
        edit_yaml: Callable[[Path, Callable[[dict], None]], None],
    ) -> None:
        """P5: the generator encodes how to emit the flag, never which value."""
        path = real_model / "assets/types/robots/xarm5.yaml"
        edit_yaml(
            path,
            lambda d: d["asset_type"]["control"].__setitem__("enforce_command_limits", False),
        )
        for name, params in self.controller_managers(real_model).items():
            assert params["enforce_command_limits"] is False, name

    def test_no_limit_value_is_stated_in_the_controller_configuration(
        self, real_model: Path
    ) -> None:
        """P1, and a mechanism check at the same time.

        The controller manager constructs its limiters with
        `init(..., nullptr, nullptr)`, so it reads no `joint_limits.<joint>.*`
        parameter at all. A limit written here would be both a second statement
        of a value and a silently inert one — the worst combination, because it
        would read as enforcement while enforcing nothing.
        """
        for name, params in self.controller_managers(real_model).items():
            assert "joint_limits" not in params, name
            assert "max_velocity" not in params, name


class TestTheRateReachesTheSkillLayer:
    def test_the_bring_up_plan_carries_it(self, real_model: Path, grasp) -> None:
        """The established L0 -> L3 channel, the same one `goal_tolerance` uses.

        It matters on the hardware path too, and for a blunter reason than L3
        convenience: the physical gripper is not a `ros2_control` joint, so no
        command limiter will ever bound it. This value is what Phase 2 has to
        convert into the vendor SDK's gripper speed. If it did not travel, the
        two paths would be free to disagree about how fast the gripper is.
        """
        plan = yaml.safe_load(generated(real_model)["bringup/cell_a_plan.yaml"])
        managers = [
            m for m in plan["plan"]["controller_managers"] if m.get("gripper_action") is not None
        ]
        assert managers, "no arm with a gripper appeared in the plan"
        for manager in managers:
            assert manager["gripper_max_drive_rate_rad_s"] == pytest.approx(
                grasp.max_drive_rate_rad_s
            )
