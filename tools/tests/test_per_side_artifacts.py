"""Per-side generated artifacts, and what a physical counterpart needs from L0 (ADR-0070).

ADR-0048 clause 2 fixed the shape and ADR-0070 builds it: a side whose backend
differs from the plant's gets a description and a controller configuration of
its own, under `<kind>/counterpart/`, generated from that side's own backend.
`test_generate.py` holds the diff between the two sides; this file holds the
pieces that make the diff possible and the ones that keep it honest:

* the robot's address is an environment REFERENCE, carried by the model, the
  description and the plan, and never a value;
* a backend may declare that no `ros2_control` component serves its joints, and
  where that would hand a vendor macro its own default plugin it is refused;
* the plugin each side's description carries is the plugin L0 declares for the
  backend that side loads (open-work #65, at the level of the generated text;
  `cite_description` repeats it on the expanded description).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.generate.description import BindingError
from cite_tools.model import ids
from cite_tools.model.loader import ModelError, load
from cite_tools.model.resolve import AXIS, END_EFFECTOR, resolve
from cite_tools.model.schema import EnvReference
from cite_tools.validate import Severity, referential

ZONE = "cell_b"
ARM = "picker"
TRACK = "picker_track"

#: RFC 5737 TEST-NET-3, reserved for documentation; it routes nowhere.
TEST_ADDRESS = "203.0.113.7"


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def errors(path: Path) -> set[str]:
    return {f.rule for f in referential.check(load(path)) if f.severity is Severity.ERROR}


class TestTheAddressIsAReference:
    def test_the_shipped_counterpart_reads_its_address_from_the_environment(
        self, real_model: Path
    ) -> None:
        picker = load(real_model).asset(ARM)
        assert picker is not None
        assert picker.hardware.params["real"]["robot_ip"] == EnvReference(env="CITE_XARM_IP")

    def test_a_reference_counts_as_supplied(self, real_model: Path) -> None:
        # Whether the variable is SET is a fact about the machine, decided at
        # launch; whether the model supplied the parameter is decided here.
        picker = load(real_model).asset(ARM)
        assert picker is not None
        assert "robot_ip" in picker.hardware.supplied_params("real")

    @pytest.mark.parametrize("name", ["1LEADING_DIGIT", "HAS SPACE", "", "DOLLAR$"])
    def test_a_reference_must_name_a_variable(
        self, real_model: Path, edit_yaml: Callable, name: str
    ) -> None:
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"]["params"]["real"].__setitem__(
                "robot_ip", {"env": name}
            ),
        )
        with pytest.raises(ModelError):
            load(real_model)

    def test_a_reference_takes_no_other_key(self, real_model: Path, edit_yaml: Callable) -> None:
        # A default here would be an address in the model by another route.
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"]["params"]["real"].__setitem__(
                "robot_ip", {"env": "CITE_XARM_IP", "default": TEST_ADDRESS}
            ),
        )
        with pytest.raises(ModelError):
            load(real_model)

    def test_the_description_carries_an_xacro_argument_and_never_a_value(
        self, real_model: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The generator does not read the environment, even when the variable is set.

        Set to a recognisable address in the generating process, the address
        reaches no artifact: what lands in the description is `$(arg robot_ip)`,
        and in the plan the variable's name.
        """
        monkeypatch.setenv("CITE_XARM_IP", TEST_ADDRESS)
        generated = artifacts(real_model)
        assert not [path for path, text in generated.items() if TEST_ADDRESS in text]
        description = generated[gen.arm_description_path(ZONE, ARM, ids.COUNTERPART_SIDE)]
        assert 'robot_ip="$(arg robot_ip)"' in description
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        (manager,) = (m for m in plan["controller_managers"] if m["asset"] == ARM)
        assert manager["counterpart_description_args"] == {"robot_ip": {"env": "CITE_XARM_IP"}}

    def test_the_plan_names_exactly_the_arguments_the_description_takes(
        self, real_model: Path
    ) -> None:
        """One statement read twice: the plan's keys are the description's `$(arg ...)`s.

        A launch hands xacro what the plan names. An argument the description
        takes and the plan does not name fails in xacro; one the plan names and
        the description does not take is a variable read for nothing.
        """
        generated = artifacts(real_model)
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        for manager in plan["controller_managers"]:
            for side, key, path_key in (
                (ids.PLANT_SIDE, "description_args", "description"),
                (ids.COUNTERPART_SIDE, "counterpart_description_args", "counterpart_description"),
            ):
                uri = manager.get(path_key)
                if uri is None:
                    continue
                text = generated[uri.removeprefix("package://cite_generated/")]
                taken = set(re.findall(r"\$\(arg ([A-Za-z_][A-Za-z0-9_]*)\)", text))
                assert taken == set(manager.get(key, {})), (side, taken)

    def test_a_literal_value_on_a_physical_backend_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """R-05: the reference is the only form a physical backend's parameter may take.

        This test used to assert the opposite - that a literal stayed legal and
        reached the description unchanged - which left one edit between the
        model and a committed robot address (ADR-0070 item 2).
        """
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"]["params"]["real"].__setitem__(
                "robot_ip", TEST_ADDRESS
            ),
        )
        assert "literal-param-on-physical-backend" in errors(real_model)

    def test_the_shipped_model_writes_no_literal_on_a_physical_backend(
        self, real_model: Path
    ) -> None:
        assert "literal-param-on-physical-backend" not in errors(real_model)


class TestABackendWithNoPlugin:
    def test_the_physical_track_declares_no_plugin_and_commands_hardware(
        self, real_model: Path
    ) -> None:
        track_type = load(real_model).asset_type("ufactory_linear_motor")
        assert track_type is not None
        real = track_type.hardware_backends["real"]
        assert real.ros2_control_plugin is None
        assert real.commands_physical_hardware is True
        assert real.instance_params == []

    def test_the_plugin_must_be_written_even_when_it_is_null(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Required with no default: a backend becomes plugin-less only by someone
        # writing `null`, never by leaving the key out.
        edit_yaml(
            real_model / "assets/types/axes/ufactory_linear_motor.yaml",
            lambda d: d["asset_type"]["hardware_backends"]["real"].pop("ros2_control_plugin"),
        )
        with pytest.raises(ModelError, match="ros2_control_plugin"):
            load(real_model)

    def test_a_plugin_less_backend_on_a_vendor_description_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The vendor macro would load its own default — the physical component."""
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["hardware_backends"]["real"].__setitem__(
                "ros2_control_plugin", None
            ),
        )
        assert "plugin-less-backend-on-a-bound-description" in errors(real_model)
        with pytest.raises(BindingError, match="declares no `ros2_control_plugin`"):
            gen.generate(load(real_model))

    def test_the_shipped_model_declares_no_plugin_less_backend_on_a_bound_type(
        self, real_model: Path
    ) -> None:
        assert "plugin-less-backend-on-a-bound-description" not in errors(real_model)

    def test_controllers_are_dropped_by_where_they_came_from(self, real_model: Path) -> None:
        """Only the two unserved controllers leave the physical side, for their two reasons."""
        (picker,) = (a for a in resolve(load(real_model), ZONE).assets if a.id == ARM)
        plant = {c.name: c.origin for c in picker.controllers_on(ids.PLANT_SIDE)}
        counterpart = {c.name: c.origin for c in picker.controllers_on(ids.COUNTERPART_SIDE)}
        assert set(plant) - set(counterpart) == {
            f"{ARM}_gripper_controller",
            f"{TRACK}_trajectory_controller",
        }
        assert plant[f"{ARM}_gripper_controller"] == END_EFFECTOR
        assert plant[f"{TRACK}_trajectory_controller"] == AXIS
        assert set(counterpart) <= set(plant)


class TestEachSideSpawnsWhatItsOwnFileDefines:
    """ADR-0070 item 1: the plan's controller list is per side, not the plant's alone."""

    @staticmethod
    def _defined(text: str) -> set[str]:
        document = yaml.safe_load(text)
        (manager,) = (
            block["ros__parameters"]
            for node, block in document.items()
            if node.endswith("/controller_manager")
        )
        return {name for name, value in manager.items() if isinstance(value, dict) and "type" in value}

    def test_the_plan_lists_each_sides_controllers(self, real_model: Path) -> None:
        generated = artifacts(real_model)
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        (manager,) = (m for m in plan["controller_managers"] if m["asset"] == ARM)
        for side, list_key, file_key in (
            (ids.PLANT_SIDE, "controllers", "parameters"),
            (ids.COUNTERPART_SIDE, "counterpart_controllers", "counterpart_parameters"),
        ):
            listed = {c["name"] for c in manager[list_key]}
            text = generated[manager[file_key].removeprefix("package://cite_generated/")]
            assert listed == self._defined(text), side
        assert {c["name"] for c in manager["counterpart_controllers"]} < {
            c["name"] for c in manager["controllers"]
        }


class TestTheDeclaredPluginIsTheLoadedOne:
    """open-work #65, on the generated text: each side carries its own backend's plugin.

    #65 asks whether the plugin L0 declares is the plugin the description loads.
    The strong form needs the vendor macro expanded and lives in
    `cite_description`; this is the half that runs anywhere, and it is the half
    that catches a generator site reading the wrong side's backend — the defect
    open-work #38 named.
    """

    @staticmethod
    def _declared(model_path: Path, asset_id: str, side: str) -> str | None:
        model = load(model_path)
        asset = model.asset(asset_id)
        assert asset is not None
        asset_type = model.asset_type(asset.type)
        assert asset_type is not None
        backend = (
            asset.hardware.backend
            if side == ids.PLANT_SIDE
            else asset.hardware.effective_counterpart_backend
        )
        return asset_type.hardware_backends[backend].ros2_control_plugin

    @pytest.mark.parametrize("side", ids.SIDES)
    def test_each_sides_description_carries_its_own_backends_plugins(
        self, real_model: Path, side: str
    ) -> None:
        text = artifacts(real_model)[gen.arm_description_path(ZONE, ARM, side)]
        arm_plugins = re.findall(r'^\s*ros2_control_plugin="([^"]*)"\s*$', text, re.MULTILINE)
        assert arm_plugins == [self._declared(real_model, ARM, side)]

        track_plugins = re.findall(r"<plugin>([^<]*)</plugin>", text)
        declared = self._declared(real_model, TRACK, side)
        assert track_plugins == ([] if declared is None else [declared])


#: The pinned vendor source, where `./scripts/bootstrap` imported it. The vendor
#: checks below read it when it is there and are skipped where it is not; the
#: rule each one restates is cited by file and line either way.
VENDOR = Path(__file__).resolve().parents[2] / "workspace/src/external/xarm_ros2"


def _vendor_source(relative: str) -> str:
    path = VENDOR / relative
    if not path.is_file():
        pytest.skip(f"vendor source not imported: {relative}")
    return path.read_text()


def _description_arg(text: str, name: str) -> str:
    (value,) = re.findall(rf'^\s*{name}="([^"]*)"\s*$', text, re.MULTILINE)
    return value


class TestVendorNames:
    """ADR-0070: every vendor name the real side needs, as the vendor would create it.

    The expected names are computed HERE from the generated description and the
    vendor's own rules, not through `ids.vendor_interface`, so a generator that
    formed them wrongly cannot agree with itself:

    * the driver node is ``ufactory_driver``, unprefixed, in the process's
      namespace (`xarm_controller/src/hardware/uf_robot_system_hardware.cpp:53`);
    * its services live on a sub-node named by the hardware parameter `hw_ns`
      (`xarm_api/src/xarm_driver.cpp:157-159`), which the vendor macro sets to
      ``${prefix}${hw_ns}`` (`xarm_description/urdf/xarm5/xarm5.ros2_control.xacro:17`),
      and each is created relative to it
      (`xarm_api/src/xarm_driver_service.cpp:20`);
    * the gripper action is ``prefix + "xarm_gripper/gripper_action"`` on the
      driver node (`xarm_api/src/xarm_driver.cpp:486`).

    The process's namespace is the controller manager's, which the real side
    runs in as the plant does (`/cite/<zone>/<asset>/controller_manager`).
    """

    @staticmethod
    def _expected(generated: dict[str, str], manager: dict) -> dict:
        text = generated[manager["counterpart_description"].removeprefix("package://cite_generated/")]
        prefix = _description_arg(text, "prefix")
        hw_ns = _description_arg(text, "hw_ns")
        namespace = manager["node"].rsplit("/", 1)[0]
        service_namespace = f"{namespace}/{prefix}{hw_ns}"
        return {
            "driver_node": f"{namespace}/ufactory_driver",
            "service_namespace": service_namespace,
            "services": {
                name: f"{service_namespace}/{name}"
                for name in (
                    "get_linear_motor_is_enabled",
                    "get_linear_motor_pos",
                    "set_linear_motor_enable",
                    "set_linear_motor_pos",
                    "set_linear_motor_speed",
                    "set_linear_motor_stop",
                    "set_state",
                )
            },
            "gripper_action": f"{namespace}/{prefix}xarm_gripper/gripper_action",
        }

    def test_the_plan_names_what_the_vendor_creates(self, real_model: Path) -> None:
        generated = artifacts(real_model)
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        (manager,) = (m for m in plan["controller_managers"] if m["asset"] == ARM)
        assert manager["counterpart_vendor"] == self._expected(generated, manager)
        # The shipped expansion, stated once so a reader sees what it is: `hw_ns`
        # is bound to the instance id and the vendor prepends the prefix.
        assert manager["counterpart_vendor"]["service_namespace"] == (
            "/cite/cell_b/picker/picker_picker"
        )

    def test_the_vendor_rules_restated_above_are_the_pinned_sources(self) -> None:
        macro = _vendor_source("xarm_description/urdf/xarm5/xarm5.ros2_control.xacro")
        assert '<param name="hw_ns">${prefix}${hw_ns}</param>' in macro
        driver = _vendor_source("xarm_api/src/xarm_driver.cpp")
        assert 'node_->get_parameter_or("hw_ns", hw_ns, std::string("xarm"));' in driver
        assert "hw_node_ = node_->create_sub_node(hw_ns);" in driver
        assert 'node_, prefix + "xarm_gripper/gripper_action",' in driver
        hardware = _vendor_source("xarm_controller/src/hardware/uf_robot_system_hardware.cpp")
        assert 'rclcpp::Node::make_shared("ufactory_driver", node_options);' in hardware

    def test_only_a_side_embedding_a_driver_names_one(self, real_model: Path) -> None:
        generated = artifacts(real_model)
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        for manager in plan["controller_managers"]:
            assert "vendor" not in manager
            if "counterpart_description" not in manager:
                assert "counterpart_vendor" not in manager, manager["asset"]


class TestVendorServicesAreSwitchedOn:
    """ADR-0070: each service the real side calls is created, and no other is.

    The driver creates a service only where `services.<name>` is true, default
    false (`xarm_api/src/xarm_driver_service.cpp:19`), reading its parameters as
    the node `ufactory_driver` (`uf_robot_system_hardware.cpp:51-53`, undeclared
    parameters allowed and declared from overrides). The vendor's parameter file
    is not loaded on our side, so its own `true` for `set_state` does not apply.
    """

    @staticmethod
    def _driver_parameters(text: str, node: str) -> dict | None:
        block = yaml.safe_load(text).get(node)
        return None if block is None else block["ros__parameters"]

    def test_the_counterpart_configuration_switches_on_exactly_the_named_services(
        self, real_model: Path
    ) -> None:
        generated = artifacts(real_model)
        plan = yaml.safe_load(generated[f"bringup/{ZONE}_plan.yaml"])["plan"]
        (manager,) = (m for m in plan["controller_managers"] if m["asset"] == ARM)
        vendor = manager["counterpart_vendor"]
        text = generated[manager["counterpart_parameters"].removeprefix("package://cite_generated/")]
        parameters = self._driver_parameters(text, vendor["driver_node"])
        assert parameters == {"services": dict.fromkeys(vendor["services"], True)}

    def test_the_plants_configuration_carries_no_driver(self, real_model: Path) -> None:
        text = artifacts(real_model)[gen.controllers_path(ZONE, ARM, ids.PLANT_SIDE)]
        assert "ufactory_driver" not in text

    def test_every_named_service_is_one_the_vendor_creates_off_by_default(
        self, real_model: Path
    ) -> None:
        service_source = _vendor_source("xarm_api/src/xarm_driver_service.cpp")
        assert 'node_->get_parameter_or("services." + service_name, enable, false);' in (
            service_source
        )
        arm_type = load(real_model).asset_type("xarm5")
        assert arm_type is not None
        driver = arm_type.hardware_backends["real"].vendor_driver
        assert driver is not None
        for name in driver.services:
            assert re.search(rf'_create_service<[^>]+>\("{name}",', service_source), name
