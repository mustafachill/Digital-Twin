"""A backend's instance parameters reach the generated description (ADR-0053).

Every test here runs the real model with one thing changed, and asserts against
the **macro argument list** rather than against the text of the generated file.
That distinction is the point of the file. The vendor's `<param>` block is
emitted during xacro expansion, which needs ROS and does not happen in a host
test, so the only thing a host test can see is the argument this generator hands
the vendor macro. A substring search over the file would also pass on a value
that landed in a comment, and the banner at the top of every generated artifact
is a comment.

WHAT THE VALUE LOOKS LIKE ON THE FAR SIDE, so that nobody "fixes" the assertions
below. `xarm5.ros2_control.xacro` emits `<param name="robot_ip">R${robot_ip}</param>`
— a literal `R` prefix — and `uf_robot_system_hardware.cpp` takes `substr(1)` to
remove it again. The generator emits the plain address; pre-stripping a character
here would turn 192.168.1.203 into 92.168.1.203 and nothing would find out until
an arm existed.

The addresses are from TEST-NET-3 (RFC 5737), which exists so that a routable
address never ends up in an example.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools import generate as gen
from cite_tools.generate.description import BindingError
from cite_tools.model.loader import load

ARM = "arm_1"
ADDRESS = "203.0.113.7"
SECOND_ADDRESS = "203.0.113.8"

#: One line per macro argument, which is what makes an argument-level assertion
#: possible at all — `arm.urdf.xacro.j2` emits `{{ name }}="{{ value }}"`.
_ARGUMENT = re.compile(r'^\s*([a-z_][a-z0-9_]*)="(.*)"\s*$')


def macro_arguments(description: str) -> dict[str, str]:
    """The macro invocation's arguments, by name.

    Parsed from the invocation block rather than from the whole file, so a name
    appearing in the generated banner or in a comment cannot be mistaken for an
    argument.
    """
    lines = description.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("  <xacro:xarm_device"))
    end = next(i for i, line in enumerate(lines[start:], start) if line.strip() == "/>")
    arguments = {}
    for line in lines[start + 1 : end]:
        match = _ARGUMENT.match(line)
        assert match, f"unparsed line inside the macro invocation: {line!r}"
        arguments[match.group(1)] = match.group(2)
    return arguments


def description_of(model: Path, asset: str) -> str:
    for artifact in gen.generate(load(model)):
        if artifact.path == f"description/cell_a_{asset}.urdf.xacro":
            return artifact.content
    raise AssertionError(f"no description was generated for {asset!r}")


def select_real(document: dict, params: dict | None = None) -> None:
    """Put `arm_1` on the `real` backend, supplying the address it must state."""
    for asset in document["assets"]:
        if asset["id"] == ARM:
            asset["hardware"] = {
                "backend": "real",
                "params": {"real": {"robot_ip": ADDRESS}} if params is None else params,
            }
            return
    raise AssertionError(f"{ARM} is not in assets/instances/arms.yaml any more")


class TestTheValueReachesASelectingArm:
    """Promotion clause 1."""

    def test_the_address_is_a_macro_argument(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(real_model / "assets/instances/arms.yaml", select_real)
        arguments = macro_arguments(description_of(real_model, ARM))
        assert arguments["robot_ip"] == ADDRESS

    def test_the_family_takes_more_than_one_name(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The same clause on a type declaring two, because one proves a binding
        and not a family.

        An implementation that hard-codes `robot_ip` passes the test above and
        fails this one. The second name is bound to a second macro argument the
        vendor macro genuinely takes, so nothing here depends on a parameter this
        project invented.
        """
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: (
                d["asset_type"]["hardware_backends"]["real"].__setitem__(
                    "instance_params", ["robot_ip", "report_type"]
                ),
                d["asset_type"]["description"]["bound_args"].__setitem__(
                    "report_type", "instance.hardware.params.report_type"
                ),
            ),
        )
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: select_real(d, {"real": {"robot_ip": ADDRESS, "report_type": "dev"}}),
        )
        arguments = macro_arguments(description_of(real_model, ARM))
        assert arguments["robot_ip"] == ADDRESS
        assert arguments["report_type"] == "dev"

    def test_two_instances_of_one_backend_carry_different_values(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """`params` is per instance and the backend id is an index inside it.

        The failure this catches is hoisting the block onto `HardwareBackend`,
        where the type would declare one address and three arms would share it.
        """

        def two_real_arms(document: dict) -> None:
            for asset in document["assets"]:
                if asset["id"] in ("arm_1", "arm_2"):
                    address = ADDRESS if asset["id"] == "arm_1" else SECOND_ADDRESS
                    asset["hardware"] = {
                        "backend": "real",
                        "params": {"real": {"robot_ip": address}},
                    }

        edit_yaml(real_model / "assets/instances/arms.yaml", two_real_arms)
        assert macro_arguments(description_of(real_model, "arm_1"))["robot_ip"] == ADDRESS
        assert macro_arguments(description_of(real_model, "arm_2"))["robot_ip"] == SECOND_ADDRESS


class TestItDoesNotReachASimulatedArm:
    """Promotion clause 2. Absence of the argument, not an empty value."""

    def test_the_argument_name_is_absent_from_a_sim_arm(self, real_model: Path) -> None:
        # The shipped model is all-`sim`, so this is the shipped path.
        assert "robot_ip" not in macro_arguments(description_of(real_model, ARM))

    def test_an_unselected_backends_block_reaches_nothing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """A block for a backend nobody selects is legal and inert (decision 1).

        This is the property that makes flipping an arm to hardware a one-field
        edit, and its cost is that a stale address here is undetectable.
        """
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: [
                asset.__setitem__(
                    "hardware", {"backend": "sim", "params": {"real": {"robot_ip": ADDRESS}}}
                )
                for asset in d["assets"]
                if asset["id"] == ARM
            ],
        )
        assert "robot_ip" not in macro_arguments(description_of(real_model, ARM))


class TestADeclaredKeyWithNoValueIsRefused:
    """Promotion clause 3, the generator half. The validator half is in
    `test_validate_referential.py`."""

    def test_the_generator_raises_naming_the_asset_and_the_binding(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / "assets/instances/arms.yaml", lambda d: select_real(d, {}))
        with pytest.raises(BindingError) as raised:
            description_of(real_model, ARM)
        assert ARM in str(raised.value)
        assert "instance.hardware.params.robot_ip" in str(raised.value)

    def test_the_same_model_with_the_value_supplied_does_not_raise(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Without this the test above proves only that something raised."""
        edit_yaml(real_model / "assets/instances/arms.yaml", select_real)
        assert macro_arguments(description_of(real_model, ARM))["robot_ip"] == ADDRESS


class TestTheFilterIsKeyedOnTheDeclaration:
    """Promotion clause 4 — the clause that separates decision 2b's union filter
    from a silent swallow.

    A `bound_args` entry naming a key NO backend declares must raise on both
    backends. Under a single-term predicate — "not declared by the selected
    backend" — it is dropped on both instead, and the description silently
    carries the vendor's own default. Mutating
    `description._dropped_on_this_backend` to that single term is what this class
    is here to fail.
    """

    @staticmethod
    def _misspell_the_binding(document: dict) -> None:
        document["asset_type"]["description"]["bound_args"]["robot_ip"] = (
            "instance.hardware.params.robot_ipp"
        )

    def test_a_key_no_backend_declares_raises_on_a_sim_arm(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / "assets/types/robots/xarm5.yaml", self._misspell_the_binding)
        with pytest.raises(BindingError, match="robot_ipp"):
            description_of(real_model, ARM)

    def test_a_key_no_backend_declares_raises_on_a_real_arm(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / "assets/types/robots/xarm5.yaml", self._misspell_the_binding)
        edit_yaml(real_model / "assets/instances/arms.yaml", select_real)
        with pytest.raises(BindingError, match="robot_ipp"):
            description_of(real_model, ARM)

    def test_a_key_the_unselected_backend_declares_is_dropped_and_does_not_raise(
        self, real_model: Path
    ) -> None:
        """The other half of the union, on the shipped model.

        `robot_ip` is declared by `real` and not by `sim`, `arm_1` is `sim`, and
        the shipped type binds it — so the first term holds, the second does not,
        and the binding is dropped rather than raising.
        """
        assert "robot_ip" not in macro_arguments(description_of(real_model, ARM))
