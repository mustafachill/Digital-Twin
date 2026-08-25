"""Generate `ros2_control` configuration from L0.

This is where ADR-0005's guarantee stops being a promise and becomes structural:
the controller names, joint names and interfaces emitted here are the ones the
physical arm will use in Phase 2, because there is nowhere else for them to come
from. The only thing that changes between the two paths is the plugin string in
the description, which is itself a per-instance selection in the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.render import environment

#: Controller manager rate. The vendor ships 150 Hz for the xArm and there is no
#: reason to diverge; a controller loop that cannot hold its rate is a
#: performance finding, not a value to quietly lower.
UPDATE_RATE_HZ = 150

#: Controllers whose parameter is a single `joint`, not a `joints` list. Getting
#: this wrong produces a controller that loads and then claims no interfaces,
#: which presents as an arm that ignores commands.
SINGLE_JOINT_TYPES = frozenset({"position_controllers/GripperActionController"})


@dataclass(frozen=True)
class _ControllerView:
    name: str
    type: str
    stage: int
    joints: tuple[str, ...]
    command_interfaces: tuple[str, ...]
    state_interfaces: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    single_joint_key: bool


def _view(controller: object) -> _ControllerView:
    assert hasattr(controller, "name")
    return _ControllerView(
        name=controller.name,  # type: ignore[attr-defined]
        type=controller.type,  # type: ignore[attr-defined]
        stage=controller.stage,  # type: ignore[attr-defined]
        joints=controller.joints,  # type: ignore[attr-defined]
        command_interfaces=controller.command_interfaces,  # type: ignore[attr-defined]
        state_interfaces=controller.state_interfaces,  # type: ignore[attr-defined]
        parameters=tuple(
            (key, _yaml_scalar(value))
            for key, value in sorted(controller.parameters.items())  # type: ignore[attr-defined]
        ),
        single_joint_key=controller.type in SINGLE_JOINT_TYPES,  # type: ignore[attr-defined]
    )


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _controlled(cell: ResolvedCell) -> tuple[ResolvedAsset, ...]:
    return tuple(a for a in cell.assets if a.controllers)


def generate(cell: ResolvedCell) -> list[Artifact]:
    env = environment()
    template = env.get_template("control/controllers.yaml.j2")
    artifacts: list[Artifact] = []
    for asset in _controlled(cell):
        text = template.render(
            zone=cell.zone,
            arm=asset,
            namespace=asset.namespace,
            update_rate=UPDATE_RATE_HZ,
            use_sim_time="true" if asset.instance.hardware.backend == "sim" else "false",
            controllers=[_view(c) for c in asset.controllers],
        )
        artifacts.append(Artifact(f"control/{cell.zone}_{asset.id}_controllers.yaml", text))
    return artifacts
