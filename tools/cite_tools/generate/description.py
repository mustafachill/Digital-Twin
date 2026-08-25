"""Generate the cell description (URDF/Xacro) from L0.

The rule this module implements, and which L1 left open: **a vendor description
is invoked, never ingested.** Nothing here opens a file belonging to
``xarm_description``, copies one, or patches one. The generator's entire
knowledge of that package is the argument names in the component library entry,
which are model data — so a vendor upgrade that renames a macro parameter is a
two-line diff in a YAML file rather than a change to code.

Assets we author ourselves — pedestals, tables, conveyors, sensor housings — are
emitted as links directly, because their geometry is ours and belongs in the
model rather than in a vendor package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.geometry import Pose
from cite_tools.model.resolve import ResolvedAsset, ResolvedCell
from cite_tools.model.schema import Body
from cite_tools.model.units import fmt, fmt_triple
from cite_tools.render import environment


class BindingError(Exception):
    """A component library entry named a generator binding that does not exist."""


@dataclass(frozen=True)
class _Frame:
    name: str
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]


@dataclass(frozen=True)
class _BodyView:
    id: str
    asset_type: Any
    prefix: str
    body: Body
    world_pose: Pose
    half_height: float
    visual_xml: str
    collision_xml: str
    named_frames: tuple[_Frame, ...]


@dataclass(frozen=True)
class _ArmView:
    id: str
    asset_type: Any
    package: str
    file: str
    macro: str
    namespace: str
    mount_link: str
    args: tuple[tuple[str, str], ...]


def _geometry_xml(geometry: Any) -> str:
    if geometry.kind == "box":
        return f"<box size={_attr(fmt_triple(geometry.size_m))}/>"
    if geometry.kind == "cylinder":
        return (
            f"<cylinder radius={_attr(fmt(geometry.radius_m))} "
            f"length={_attr(fmt(geometry.length_m))}/>"
        )
    scale = fmt_triple(geometry.scale)
    return f"<mesh filename={_attr(geometry.uri)} scale={_attr(scale)}/>"


def _attr(value: str) -> str:
    return f'"{value}"'


def _body_view(asset: ResolvedAsset) -> _BodyView:
    body = asset.asset_type.description.body
    assert body is not None  # callers filter on provider == "body"

    # An authored body's pose names the point it stands on — a pedestal's pose is
    # where its foot is, not its centre — because that is how someone measuring a
    # room writes it down. The link origin therefore sits half a height up.
    half_height = body.collision.size_m[2] / 2.0 if body.collision.kind == "box" else 0.0

    frames = tuple(
        _Frame(
            name=ids.link(asset.id, f.id),
            xyz_m=(f.xyz_m[0], f.xyz_m[1], f.xyz_m[2] - half_height),
            rpy_rad=f.rpy_rad,
        )
        for f in sorted(asset.asset_type.frames, key=lambda f: f.id)
    )

    return _BodyView(
        id=asset.id,
        asset_type=asset.asset_type,
        prefix=asset.prefix,
        body=body,
        world_pose=asset.world_pose,
        half_height=half_height,
        visual_xml=_geometry_xml(body.visual),
        collision_xml=_geometry_xml(body.collision),
        named_frames=frames,
    )


def _binding_value(asset: ResolvedAsset, binding: str, cell: ResolvedCell) -> str:
    """Resolve one `bound_args` binding name to its value.

    Every binding is enumerated. An unknown one raises rather than defaulting,
    so a typo in the component library fails loudly here instead of silently
    handing the vendor macro its own default — which would produce a description
    that loads and is wrong.
    """
    # An arm is its own Gazebo model, so it attaches to its own root link rather
    # than to a link in the scene. Where that root sits in the world is stated
    # once, by the generated static transform table and the spawn pose — not
    # inside this description.
    values: dict[str, str] = {
        "instance.id": asset.id,
        "instance.prefix": asset.prefix,
        "instance.zone": asset.zone,
        "instance.namespace": asset.namespace,
        "instance.parent_link": _mount_link(asset),
        # Zero: the arm's root link IS its mount, and the model is placed in the
        # world at spawn time. Writing the pose here as well would state the same
        # fact twice.
        "instance.parent_xyz_m": fmt_triple((0.0, 0.0, 0.0)),
        "instance.parent_rpy_rad": fmt_triple((0.0, 0.0, 0.0)),
        "instance.hardware.ros2_control_plugin": asset.ros2_control_plugin,
        "instance.end_effector.vendor_integrated": str(
            bool(asset.instance.end_effector and asset.instance.end_effector.vendor_integrated)
        ).lower(),
    }
    if binding not in values:
        raise BindingError(
            f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, "
            f"which this generator does not provide. Known bindings: "
            f"{', '.join(sorted(values))}."
        )
    return values[binding]


def _arm_view(asset: ResolvedAsset, cell: ResolvedCell) -> _ArmView:
    spec = asset.asset_type.description
    if not (spec.package and spec.file and spec.macro):
        raise BindingError(
            f"type {asset.asset_type.id!r} uses the xacro_macro provider but does not "
            "name a package, file and macro"
        )

    args: list[tuple[str, str]] = [
        (name, str(value).lower() if isinstance(value, bool) else str(value))
        for name, value in sorted(spec.fixed_args.items())
    ]
    args += [
        (name, _binding_value(asset, binding, cell))
        for name, binding in sorted(spec.bound_args.items())
    ]

    return _ArmView(
        id=asset.id,
        asset_type=asset.asset_type,
        package=spec.package,
        file=spec.file,
        macro=spec.macro,
        namespace=asset.namespace,
        mount_link=_mount_link(asset),
        args=tuple(sorted(args)),
    )


def _mount_link(asset: ResolvedAsset) -> str:
    """The root link of an arm's own model, which the vendor macro attaches to."""
    return ids.link(asset.id, "mount")


def generate(cell: ResolvedCell) -> list[Artifact]:
    bodies = tuple(
        _body_view(a)
        for a in cell.assets
        if a.asset_type.description.provider == "body" and a.asset_type.description.body
    )
    arms = tuple(
        _arm_view(a, cell)
        for a in cell.assets
        if a.asset_type.description.provider == "xacro_macro" and a.asset_type.category == "robot"
    )

    env = environment()
    artifacts = [
        Artifact(
            f"description/{cell.zone}_scene.urdf.xacro",
            env.get_template("description/scene.urdf.xacro.j2").render(
                cell=cell, world_frame=ids.WORLD_FRAME, bodies=bodies
            ),
        )
    ]
    artifacts += [
        Artifact(
            f"description/{cell.zone}_{arm.id}.urdf.xacro",
            env.get_template("description/arm.urdf.xacro.j2").render(zone=cell.zone, arm=arm),
        )
        for arm in arms
    ]
    return artifacts
