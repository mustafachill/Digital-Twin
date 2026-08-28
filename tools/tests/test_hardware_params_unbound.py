"""`hardware.params` is legal in L0 and reaches no generated description.

ADR-0040 decision 2 argued that a test-only hardware plugin cannot be loaded by a
generated description because its parameters "have no home in L0". That is false
about the model and true about the generator, and the ADR's 2026-08-28 correction
says so: `HardwareSelection.params` is a free-form map, `HardwareBackend
.instance_params` is its per-backend allowlist, `validate.referential` already
enforces one against the other, and `xarm5.yaml` already declares
`instance_params: [robot_ip, report_type]` for the `real` backend against Phase 2.

What is actually true is one line of `generate/description.py`: it binds
`instance.hardware.ros2_control_plugin` and nothing else, and `hardware.params`
appears nowhere under `generate/`. That is the property this file pins, so that
the Phase 2 wiring fails here — in a host test, in a second — rather than silently
repealing an unreachability argument that a fixture's safety rests on.

WHY THIS IS NOT THE OBVIOUS XML TEST. "Assert the generated `<ros2_control>`
blocks carry no `<param>`" would pass today for the wrong reason: the generated
descriptions contain no literal `<ros2_control>` block at all. They invoke the
vendor's macro, which emits the block during xacro expansion — which needs ROS and
does not happen here. Such a test would find nothing, assert nothing and stay
green through exactly the change it was written to catch. Searching the generated
text for values the model DOES carry is strictly stronger: it catches a `<param>`,
a macro argument, a hardware parameter file, or any other route Phase 2 might
take.

The positive control is what makes the search trustworthy. The same mutation also
changes the backend's plugin string, and that string DOES reach the description —
so a test that finds the plugin and not the parameters has been shown to be
looking, rather than merely failing to find anything.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, referential

#: The arm the mutation is applied to, and the backend that declares the
#: parameters. Both come from the real model rather than from a toy, so a change
#: to either — a renamed instance, a withdrawn backend — fails here loudly instead
#: of quietly making the test vacuous.
MUTATED_ARM = "arm_1"
BACKEND_WITH_PARAMS = "real"

#: Values chosen to be unmistakable in a text search. The address is from
#: TEST-NET-3 (RFC 5737), which exists so that a routable address never ends up in
#: an example, and it appears nowhere else in this repository.
PARAMS = {"robot_ip": "203.0.113.7", "report_type": "normal"}

#: The one field of `hardware:` the description generator DOES bind. It is the
#: positive control: the search must find this in the same artifact in which it
#: fails to find the parameters above.
PLUGIN_OF_THE_REAL_BACKEND = "uf_robot_hardware/UFRobotSystemHardware"


def _select_backend(document: dict) -> None:
    for asset in document["assets"]:
        if asset["id"] == MUTATED_ARM:
            asset["hardware"] = {"backend": BACKEND_WITH_PARAMS, "params": dict(PARAMS)}
            return
    raise AssertionError(f"{MUTATED_ARM} is not in assets/instances/arms.yaml any more")


@pytest.fixture
def model_with_hardware_params(real_model: Path, edit_yaml: Callable) -> Path:
    """The real model, with `hardware.params` declared on one arm."""
    edit_yaml(real_model / "assets/instances/arms.yaml", _select_backend)
    return real_model


def _descriptions(model: Path) -> dict[str, str]:
    return {
        artifact.path: artifact.content
        for artifact in gen.generate(load(model))
        if artifact.path.startswith("description/")
    }


class TestTheParametersAreLegalAndUnbound:
    def test_the_mutation_is_valid_l0(self, model_with_hardware_params: Path) -> None:
        """The premise. An illegal model would make everything below vacuous.

        If `params` were rejected here, the ADR's original claim would be right
        and this file would be asserting against a model nobody can write.
        """
        findings = referential.check(load(model_with_hardware_params))
        assert [f.rule for f in findings if f.severity is Severity.ERROR] == []

    def test_no_generated_description_carries_the_parameters(
        self, model_with_hardware_params: Path
    ) -> None:
        """The pin. Phase 2 wiring `hardware.params` into a description fails here."""
        leaked = {
            path: [token for token in (*PARAMS, *PARAMS.values()) if token in content]
            for path, content in _descriptions(model_with_hardware_params).items()
        }
        assert not any(leaked.values()), (
            f"a generated description now carries hardware.params: "
            f"{ {p: t for p, t in leaked.items() if t} }. If this is the Phase 2 "
            f"backend wiring, it is working as intended — and ADR-0040 decision 2's "
            f"first unreachability argument has just become false, so the fixture in "
            f"cite_test_hardware is now expressible in L0. Re-read that decision and "
            f"its 2026-08-28 correction before deleting this assertion."
        )

    def test_the_search_finds_a_field_the_generator_does_bind(
        self, model_with_hardware_params: Path
    ) -> None:
        """The positive control, without which the test above proves nothing.

        Same `hardware:` block, same artifact, same substring search — and this one
        must be found. A test that cannot see the plugin string cannot be trusted
        to have looked for the parameters beside it.
        """
        descriptions = _descriptions(model_with_hardware_params)
        carrying = [
            path for path, content in descriptions.items() if PLUGIN_OF_THE_REAL_BACKEND in content
        ]
        assert carrying, (
            f"{PLUGIN_OF_THE_REAL_BACKEND} reached no generated description, so the "
            f"search above was blind and its silence means nothing. Either the "
            f"backend selection stopped being bound, or {MUTATED_ARM} stopped being "
            f"generated. Descriptions seen: {sorted(descriptions)}."
        )
