"""What a physical side's nodes are configured with, and the rules that keep it coherent.

ADR-0070 items 2-6, and the launch requirements of the safety re-audit (L-5,
L-6). The physical counterpart runs `cite_hardware`'s deadman, track adapter
and gripper relay beside its controller manager, and none of their parameters
has a default: every one is generated here from L0 into one per-side file.
These tests hold:

* least privilege on the vendor driver's services, and the switch that would
  turn every one of them on refused by name (S-06);
* the deadman's timing declared once, on the zone, with each relation between
  two declarations a validator rule;
* that every parameter each node declares is emitted, from the source of the
  node's own `SPECS` and not from a list restated here;
* that the kind of an environment value is declared, never inferred from an
  argument's name (R-NEW-2), and that a gripper the vendor does not integrate
  gets no vendor action (R-NEW-3).
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from conftest import REAL_MODEL

from cite_tools import generate as gen
from cite_tools.generate.adapters import PhysicalSideError
from cite_tools.model import ids
from cite_tools.model.loader import ModelError, load
from cite_tools.model.schema import VENDOR_SERVICES_THE_PHYSICAL_SIDE_CALLS
from cite_tools.validate import Severity, referential

ZONE = "cell_b"
ARM = "picker"
HARDWARE = REAL_MODEL.parent / "workspace/src/cite_hardware/cite_hardware"
ARM_TYPE = "assets/types/robots/xarm5.yaml"
TRACK_TYPE = "assets/types/axes/ufactory_linear_motor.yaml"
GRIPPER_TYPE = "assets/types/end_effectors/xarm_parallel_gripper.yaml"
ZONES = "facility/zones.yaml"


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def errors(path: Path) -> list:
    return [f for f in referential.check(load(path)) if f.severity is Severity.ERROR]


def rules(path: Path) -> set[str]:
    return {f.rule for f in errors(path)}


def adapters(path: Path) -> dict:
    text = artifacts(path)[gen.adapters_path(ZONE, ARM, ids.COUNTERPART_SIDE)]
    return yaml.safe_load(text)


def plan(path: Path) -> dict:
    return yaml.safe_load(artifacts(path)[f"bringup/{ZONE}_plan.yaml"])["plan"]


def spec_names(module: str) -> set[str]:
    """Every parameter name a `cite_hardware` node declares, read from its `SPECS`.

    Read from the source and not imported: `cite_hardware` is a ROS package and
    this suite runs without ROS. A parameter added to a node is one this test
    then demands the generator emit.
    """
    tree = ast.parse((HARDWARE / f"{module}.py").read_text())
    for node in tree.body:
        target = getattr(node, "target", None)
        if getattr(target, "id", None) == "SPECS":
            return {
                call.args[0].value
                for call in ast.walk(node.value)
                if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "Spec"
            }
    raise AssertionError(f"{module} declares no SPECS")


def _vendor_driver(document: dict) -> dict:
    return document["asset_type"]["hardware_backends"]["real"]["vendor_driver"]


def _physical_side(document: dict) -> dict:
    return document["zones"][0]["twin"]["physical_side"]


class TestVendorServicesAreLeastPrivilege:
    def test_the_allow_list_is_exactly_what_the_generated_nodes_call(self) -> None:
        """M-01: the schema's list and the generator's service maps are one statement."""
        from cite_tools.generate import adapters as adapter_generator

        called = {
            name
            for services in (
                adapter_generator._DEADMAN_SERVICES,
                adapter_generator._TRACK_SERVICES,
                adapter_generator._GRIPPER_SERVICES,
            )
            for name in services.values()
        }
        assert called == set(VENDOR_SERVICES_THE_PHYSICAL_SIDE_CALLS)

    def test_the_shipped_driver_switches_on_exactly_what_the_side_calls(self) -> None:
        driver = load(REAL_MODEL).asset_type("xarm5").hardware_backends["real"].vendor_driver
        assert sorted(driver.services) == sorted(VENDOR_SERVICES_THE_PHYSICAL_SIDE_CALLS)
        assert rules(REAL_MODEL) == set()

    @pytest.mark.parametrize("name", ["set_linear_motor_enable", "clean_error", "set_tcp_load"])
    def test_a_service_nothing_calls_is_refused(
        self, real_model: Path, edit_yaml: Callable, name: str
    ) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _vendor_driver(d)["services"].append(name))
        found = [f for f in errors(real_model) if f.rule == "vendor-service-not-allowed"]
        assert len(found) == 1 and name in found[0].message

    def test_the_switch_for_every_service_is_refused_by_name(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _vendor_driver(d)["services"].append("debug"))
        (found,) = (f for f in errors(real_model) if f.rule == "vendor-service-not-allowed")
        assert "EVERY" in found.message

    @pytest.mark.parametrize("name", VENDOR_SERVICES_THE_PHYSICAL_SIDE_CALLS)
    def test_a_service_the_side_calls_must_be_listed(
        self, real_model: Path, edit_yaml: Callable, name: str
    ) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _vendor_driver(d)["services"].remove(name))
        assert "vendor-service-missing" in rules(real_model)


class TestTheTimingIsDeclaredOnceAndCoherent:
    def test_a_pair_states_its_heartbeat(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(real_model / ZONES, lambda d: d["zones"][0]["twin"].pop("heartbeat_period_s"))
        with pytest.raises(ModelError, match="heartbeat_period_s"):
            load(real_model)

    def test_a_single_side_states_no_heartbeat(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            real_model / ZONES, lambda d: d["zones"][0]["twin"].__setitem__("sides", "single")
        )
        with pytest.raises(ModelError, match="belong to a pair"):
            load(real_model)

    def test_a_physical_counterpart_states_its_timing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / ZONES, lambda d: d["zones"][0]["twin"].pop("physical_side"))
        assert "physical-side-timing-unstated" in rules(real_model)

    @pytest.mark.parametrize(
        ("field", "value", "rule"),
        [
            ("deadman_timeout_s", 0.25, "deadman-timeout-below-three-heartbeats"),
            ("deadman_tick_period_s", 0.5, "deadman-tick-not-below-timeout"),
            ("state_max_age_s", 0.05, "state-max-age-not-above-tick"),
            ("call_deadline_s", 0.5, "call-deadline-not-below-timeout"),
        ],
    )
    def test_each_relation_is_a_rule(
        self, real_model: Path, edit_yaml: Callable, field: str, value: float, rule: str
    ) -> None:
        edit_yaml(real_model / ZONES, lambda d: _physical_side(d).__setitem__(field, value))
        assert rule in rules(real_model)

    def test_a_state_younger_than_a_poll_reads_as_stale(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Above the tick, below the adapters' read period.
        def edit(document: dict) -> None:
            _physical_side(document)["deadman_tick_period_s"] = 0.01
            _physical_side(document)["state_max_age_s"] = 0.08

        edit_yaml(real_model / ZONES, edit)
        assert rules(real_model) == {"state-max-age-not-above-a-poll-period"}

    @pytest.mark.parametrize(
        ("value", "rule"),
        [
            (0.1, "track-segment-not-above-poll"),
            (0.6, "track-segment-above-deadman-timeout"),
        ],
    )
    def test_the_track_segment_is_related_to_the_poll_and_the_deadman(
        self, real_model: Path, edit_yaml: Callable, value: float, rule: str
    ) -> None:
        """SA2c-S-02 d: re-sent before it ends, and no longer than the deadman's bound."""
        edit_yaml(
            real_model / TRACK_TYPE,
            lambda d: d["asset_type"]["hardware_backends"]["real"]["vendor_axis"].__setitem__(
                "segment_s", value
            ),
        )
        assert rules(real_model) == {rule}

    def test_a_track_position_younger_than_a_poll_reads_as_stale(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """M-03: the adapter's own read period against the age it trusts a read for."""
        edit_yaml(
            real_model / TRACK_TYPE,
            lambda d: d["asset_type"]["hardware_backends"]["real"]["vendor_axis"].__setitem__(
                "position_max_age_s", 0.1
            ),
        )
        assert rules(real_model) == {"track-position-age-not-above-poll"}

    def test_the_generated_values_honour_every_relation(self) -> None:
        nodes = adapters(REAL_MODEL)
        deadman = nodes[f"/cite/{ZONE}/{ARM}/{ids.DEADMAN_NODE}"]["ros__parameters"]
        heartbeat = plan(REAL_MODEL)["twin"]["heartbeat_period_s"]
        assert deadman["timeout_s"] >= 3 * heartbeat
        assert deadman["tick_period_s"] < deadman["timeout_s"]
        for name in (ids.TRACK_ADAPTER_NODE, ids.GRIPPER_RELAY_NODE):
            relay = nodes[f"/cite/{ZONE}/{ARM}/{name}"]["ros__parameters"]
            assert relay["deadman_state_max_age_s"] > deadman["tick_period_s"]
            assert relay["deadman_state_max_age_s"] > relay["poll_period_s"]


class TestEveryNodeParameterIsGenerated:
    @pytest.mark.parametrize(
        ("node", "module"),
        [
            (ids.DEADMAN_NODE, "deadman"),
            (ids.TRACK_ADAPTER_NODE, "track_adapter"),
            (ids.GRIPPER_RELAY_NODE, "gripper_relay"),
        ],
    )
    def test_the_file_carries_every_parameter_the_node_declares_and_no_other(
        self, node: str, module: str
    ) -> None:
        parameters = adapters(REAL_MODEL)[f"/cite/{ZONE}/{ARM}/{node}"]["ros__parameters"]
        assert set(parameters) == spec_names(module) | {"use_sim_time"}
        # L-7: the wall clock, on every node of a physical side.
        assert parameters["use_sim_time"] is False

    def test_the_plan_names_the_file_and_each_node(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        physical = manager["counterpart_physical"]
        assert physical["parameters"] == (
            f"package://cite_generated/{gen.adapters_path(ZONE, ARM, ids.COUNTERPART_SIDE)}"
        )
        assert set(adapters(REAL_MODEL)) == {
            physical["deadman"],
            physical["track_adapter"],
            physical["gripper_relay"],
        }
        assert physical["deadman_state_topic"] == f"/cite/{ZONE}/{ARM}/{ids.DEADMAN_STATE}"

    def test_the_deadman_cancels_the_arm_and_the_relay_actions(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        deadman = adapters(REAL_MODEL)[manager["counterpart_physical"]["deadman"]]
        cancel = deadman["ros__parameters"]["cancel_actions"]
        assert cancel == [manager["trajectory_action"], manager["gripper_action"]]
        relay = adapters(REAL_MODEL)[manager["counterpart_physical"]["gripper_relay"]]
        assert relay["ros__parameters"]["action_name"] == manager["gripper_action"]

    def test_every_vendor_name_is_one_the_plan_names(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        vendor = manager["counterpart_vendor"]
        named = set(vendor["services"].values()) | {vendor["gripper_action"]}
        for node in adapters(REAL_MODEL).values():
            for key, value in node["ros__parameters"].items():
                if key.endswith("_service") or key == "vendor_action_name":
                    assert value in named, key

    def test_the_track_travel_and_speed_are_the_axis_own(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        track = adapters(REAL_MODEL)[manager["counterpart_physical"]["track_adapter"]]
        parameters = track["ros__parameters"]
        assert parameters["position_min_m"] == 0.0
        assert parameters["position_max_m"] == manager["track"]["stroke_m"]
        assert parameters["max_speed_mps"] == manager["track"]["max_speed_mps"]
        assert parameters["command_topic"] == manager["track"]["command_topic"]
        assert parameters["auto_enable"] is False

    @pytest.mark.parametrize(("velocity_control", "mode"), [(False, 1), (True, 4)])
    def test_the_enable_mode_follows_velocity_control(
        self, real_model: Path, edit_yaml: Callable, velocity_control: bool, mode: int
    ) -> None:
        edit_yaml(
            real_model / ARM_TYPE,
            lambda d: d["asset_type"]["description"]["fixed_args"].__setitem__(
                "velocity_control", velocity_control
            ),
        )
        deadman = adapters(real_model)[f"/cite/{ZONE}/{ARM}/{ids.DEADMAN_NODE}"]
        assert deadman["ros__parameters"]["enable_mode"] == mode

    def test_the_readiness_joints_are_every_joint_the_side_publishes(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        joints = manager["counterpart_physical"]["joints"]
        arm = [f"{ARM}_joint{n}" for n in range(1, 6)]
        assert sorted(joints) == sorted([*arm, manager["track"]["joint"], f"{ARM}_drive_joint"])

    def test_no_plant_side_runs_an_adapter(self) -> None:
        generated = artifacts(REAL_MODEL)
        assert gen.adapters_path(ZONE, ARM, ids.COUNTERPART_SIDE) in generated
        assert not any(
            path.endswith("_adapters.yaml") and "/counterpart/" not in path for path in generated
        )


class TestWhatTheAdaptersTranslateWithIsDeclared:
    def test_a_plugin_less_physical_axis_states_its_vendor_units(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / TRACK_TYPE,
            lambda d: d["asset_type"]["hardware_backends"]["real"].pop("vendor_axis"),
        )
        assert "vendor-axis-unstated" in rules(real_model)

    def test_vendor_units_on_a_simulated_axis_are_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        def edit(document: dict) -> None:
            backends = document["asset_type"]["hardware_backends"]
            backends["sim"]["vendor_axis"] = backends["real"]["vendor_axis"]

        edit_yaml(real_model / TRACK_TYPE, edit)
        assert "vendor-axis-unstated" in rules(real_model)

    def test_a_vendor_served_gripper_states_its_vendor_units(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / GRIPPER_TYPE, lambda d: d["asset_type"]["grasp"].pop("vendor"))
        assert "vendor-gripper-units-unstated" in rules(real_model)

    def test_a_gripper_the_vendor_does_not_integrate_gets_no_vendor_action(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """R-NEW-3: no `gripper_action` is emitted unless the vendor integrates the gripper."""

        def edit(document: dict) -> None:
            document["assets"][0]["end_effector"]["vendor_integrated"] = False

        edit_yaml(real_model / "assets/instances/arms.yaml", edit)
        (manager,) = plan(real_model)["controller_managers"]
        assert "gripper_action" not in manager["counterpart_vendor"]
        assert "gripper_relay" not in manager["counterpart_physical"]


class TestControllersOnAPhysicalSideCanAllBeActive:
    def test_two_controllers_commanding_one_joint_are_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """L-5: the vendor plugin activates every listed controller at once on recovery."""

        def edit(document: dict) -> None:
            controllers = document["asset_type"]["controllers"]
            (trajectory,) = (c for c in controllers if c["suffix"] == "joint_trajectory_controller")
            controllers.append({**trajectory, "suffix": "second_trajectory_controller"})

        edit_yaml(real_model / ARM_TYPE, edit)
        with pytest.raises(PhysicalSideError, match="both command"):
            gen.generate(load(real_model))


class TestTheKindOfAnEnvironmentValueIsDeclared:
    def test_a_reference_without_a_kind_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"]["params"]["real"]["robot_ip"].pop("kind"),
        )
        with pytest.raises(ModelError, match="kind"):
            load(real_model)

    def test_a_kind_nobody_checks_is_refused(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"]["params"]["real"]["robot_ip"].__setitem__(
                "kind", "hostname"
            ),
        )
        with pytest.raises(ModelError, match="kind"):
            load(real_model)

    def test_the_plan_carries_the_kind_beside_the_variable(self) -> None:
        (manager,) = plan(REAL_MODEL)["controller_managers"]
        assert manager["counterpart_description_args"] == {
            "robot_ip": {"env": "CITE_XARM_IP", "kind": "ip_address"}
        }


class TestTheVendorGripperRangeIsDeclaredOnce:
    """M-02: `max_pos_pulses` is the one vendor value both relay ranges follow from."""

    def _relay(self, path: Path) -> dict:
        return adapters(path)[f"/cite/{ZONE}/{ARM}/{ids.GRIPPER_RELAY_NODE}"]["ros__parameters"]

    def test_both_ranges_follow_from_max_pos(self, real_model: Path, edit_yaml: Callable) -> None:
        shipped = self._relay(REAL_MODEL)
        assert shipped["vendor_closed_position"] == pytest.approx(0.85)
        assert shipped["vendor_state_open_position"] == pytest.approx(850.0)
        edit_yaml(
            real_model / GRIPPER_TYPE,
            lambda d: d["asset_type"]["grasp"]["vendor"].__setitem__("max_pos_pulses", 800.0),
        )
        edited = self._relay(real_model)
        assert edited["vendor_open_position"] == 0.0
        assert edited["vendor_closed_position"] == pytest.approx(0.8)
        assert edited["vendor_state_open_position"] == pytest.approx(800.0)
        assert edited["vendor_state_closed_position"] == 0.0
