"""`hardware.params` reaches a description when the loaded backend declares it.

**This file used to pin the opposite**, and its name is kept so that ADR-0053's
references to it resolve. Until 2026-09-08 the generator bound
`instance.hardware.ros2_control_plugin` and nothing else, so a `backend: real`
arm generated a description naming the physical plugin and carrying no address —
and the vendor's own component answers an empty `robot_ip` with `RCLCPP_ERROR`,
`rclcpp::shutdown()` and `exit(1)` from inside `on_init`. That failure was loud
and it was in the wrong place: the value was in L0 and the generator dropped it,
so it landed at bring-up beside the arm instead of at `./scripts/validate-model`
on a laptop. ADR-0053 closed that, and the reach itself is asserted in
`test_hardware_param_bindings.py` against the macro argument list.

**What this file pins now is the silence that survived**, which is the one the
record names as a permanent cost. `params` is indexed by backend id, and a block
for a backend nobody on this asset selects is legal, valid and inert. That is
deliberate — it is what makes flipping an arm to hardware a one-field edit — and
its price is that a stale address in an unexercised block is indistinguishable
from a deliberate pre-declaration. Nothing in this repository can tell those
apart, and this file is where that is written down as a tested property rather
than as a paragraph.

WHY THIS IS NOT THE OBVIOUS XML TEST, unchanged from the original and still
true. "Assert the generated `<ros2_control>` blocks carry no `<param>`" would
pass for the wrong reason: the generated descriptions contain no literal
`<ros2_control>` block at all. They invoke the vendor's macro, which emits the
block during xacro expansion — which needs ROS and does not happen here. Such a
test would find nothing, assert nothing and stay green through exactly the change
it was written to catch. Searching the generated text for values the model DOES
carry is strictly stronger.

The positive control is what makes the search trustworthy, and it is why this
file survives its own subject changing. Each search below is paired with a string
that MUST be found in the same artifact by the same means — the plugin the arm's
selected backend loads. A test that cannot see the plugin string cannot be
trusted to have looked for the parameters beside it, and its silence would mean
nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, referential

#: The arm the mutation is applied to, and the backend whose block is written.
#: Both come from the real model rather than from a toy, so a change to either —
#: a renamed instance, a withdrawn backend — fails here loudly instead of quietly
#: making the test vacuous.
MUTATED_ARM = "arm_1"
BACKEND_WITH_PARAMS = "real"

#: Values chosen to be unmistakable in a text search. The address is from
#: TEST-NET-3 (RFC 5737), which exists so that a routable address never ends up
#: in an example, and it appears nowhere else in this repository outside the
#: tests that use it deliberately.
PARAMS = {"robot_ip": "203.0.113.7"}

#: The two plugin class strings, each of which is the positive control for the
#: class that selects its backend.
PLUGIN_OF_THE_REAL_BACKEND = "uf_robot_hardware/UFRobotSystemHardware"
PLUGIN_OF_THE_SIM_BACKEND = "gz_ros2_control/GazeboSimSystem"


def _hardware(model: Path, edit_yaml: Callable, block: dict) -> Path:
    def mutate(document: dict) -> None:
        for asset in document["assets"]:
            if asset["id"] == MUTATED_ARM:
                asset["hardware"] = block
                return
        raise AssertionError(f"{MUTATED_ARM} is not in assets/instances/arms.yaml any more")

    edit_yaml(model / "assets/instances/arms.yaml", mutate)
    return model


@pytest.fixture
def selecting_the_backend(real_model: Path, edit_yaml: Callable) -> Path:
    """The real model, with `arm_1` loading the backend whose block it writes."""
    return _hardware(
        real_model,
        edit_yaml,
        {"backend": BACKEND_WITH_PARAMS, "params": {BACKEND_WITH_PARAMS: dict(PARAMS)}},
    )


@pytest.fixture
def not_selecting_the_backend(real_model: Path, edit_yaml: Callable) -> Path:
    """The same block, on an arm that stays simulated."""
    return _hardware(
        real_model, edit_yaml, {"backend": "sim", "params": {BACKEND_WITH_PARAMS: dict(PARAMS)}}
    )


def _descriptions(model: Path) -> dict[str, str]:
    return {
        artifact.path: artifact.content
        for artifact in gen.generate(load(model))
        if artifact.path.startswith("description/")
    }


def _carrying(model: Path, token: str) -> list[str]:
    return [path for path, content in _descriptions(model).items() if token in content]


class TestTheSelectedBackendsBlockIsBound:
    def test_the_mutation_is_valid_l0(self, selecting_the_backend: Path) -> None:
        """The premise. An illegal model would make everything below vacuous."""
        findings = referential.check(load(selecting_the_backend))
        assert [f.rule for f in findings if f.severity is Severity.ERROR] == []

    def test_the_value_reaches_a_description(self, selecting_the_backend: Path) -> None:
        """The reach, by the same coarse search this file has always used.

        The precise form of it — that the value is a macro ARGUMENT and not a
        word in a comment — is `test_hardware_param_bindings.py`'s job. What this
        assertion adds is that the coarse instrument below is capable of seeing a
        value that is present, which is what makes the silence in the next class
        a measured one.
        """
        assert _carrying(selecting_the_backend, PARAMS["robot_ip"])

    def test_the_search_finds_the_plugin_of_the_selected_backend(
        self, selecting_the_backend: Path
    ) -> None:
        """The positive control. Same `hardware:` block, same artifact, same search."""
        assert _carrying(selecting_the_backend, PLUGIN_OF_THE_REAL_BACKEND), (
            f"{PLUGIN_OF_THE_REAL_BACKEND} reached no generated description, so every "
            f"search in this file is blind and its results mean nothing. Either the "
            f"backend selection stopped being bound, or {MUTATED_ARM} stopped being "
            f"generated."
        )


class TestAnUnselectedBackendsBlockIsInertAndUndetectable:
    def test_the_mutation_is_valid_l0(self, not_selecting_the_backend: Path) -> None:
        """A block for a declared backend nobody selects is legal (ADR-0053,
        decision 1). If this ever starts failing, the one-field flip to hardware
        has stopped being one field."""
        findings = referential.check(load(not_selecting_the_backend))
        assert [f.rule for f in findings if f.severity is Severity.ERROR] == []

    def test_nothing_of_it_reaches_a_generated_description(
        self, not_selecting_the_backend: Path
    ) -> None:
        """The pin. Neither the parameter's name nor its value reaches anything.

        THIS IS ALSO THE STATEMENT OF THE COST, and it is why the assertion is
        worth having rather than merely true. A wrong address written here for an
        arm nobody has switched over yet is invisible to this repository — no
        validator rule, no generator raise and no test can distinguish it from a
        deliberate pre-declaration, and it will be found by the arm failing to
        connect. A typo in the BACKEND ID is caught, by
        `unknown-hardware-param-backend`; a typo in a value is not, and never
        could be.
        """
        leaked = {
            path: [token for token in (*PARAMS, *PARAMS.values()) if token in content]
            for path, content in _descriptions(not_selecting_the_backend).items()
        }
        assert not any(leaked.values()), (
            f"a generated description now carries an UNSELECTED backend's parameters: "
            f"{ {p: t for p, t in leaked.items() if t} }. The selected backend is `sim`, "
            f"whose `instance_params` is empty, so ADR-0053 decision 2b's filter should "
            f"have dropped the binding. Check that the filter is still the union — "
            f"declared by some backend and not by the selected one — and re-read that "
            f"decision before changing this assertion."
        )

    def test_the_search_finds_the_plugin_of_the_selected_backend(
        self, not_selecting_the_backend: Path
    ) -> None:
        """The positive control for the silence above, without which it proves nothing."""
        assert _carrying(not_selecting_the_backend, PLUGIN_OF_THE_SIM_BACKEND), (
            f"{PLUGIN_OF_THE_SIM_BACKEND} reached no generated description, so the "
            f"search above was blind. Either the backend selection stopped being bound, "
            f"or {MUTATED_ARM} stopped being generated."
        )
