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
from cite_tools.model.schema import PARAMS_BINDING_PREFIX, PLUGIN_BINDING, Body
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
    #: Where the mass sits, in the link's own frame. See `_body_view`.
    inertial_origin_m: tuple[float, float, float]
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
    # room writes it down. The anchor joint therefore places `<asset>_base_link`
    # at the foot, and the visual and collision origins sit half a height up.
    half_height = body.collision.size_m[2] / 2.0 if body.collision.kind == "box" else 0.0

    # ONE convention, applied everywhere in this module. `base_link` is at the
    # foot, so a type frame declared at z = 0.600 attaches at z = 0.600 and no
    # half-height is subtracted. Subtracting one here — which this generator used
    # to do — would only have been right if the link origin were the box centre,
    # and it published `pedestal_1_top` 0.3 m below `cell_a__pedestal_1__top`:
    # the same L0 frame, twice, 0.3 m apart, in two live representations (P1).
    #
    # A frame that names a `link` is skipped. That frame belongs to a description
    # `robot_state_publisher` already publishes, and emitting a second copy of it
    # is the same duplication in the other direction — see `generate.frames`,
    # which applies the identical rule to the static transform table.
    frames = tuple(
        _Frame(
            name=ids.link(asset.id, f.id),
            xyz_m=f.xyz_m,
            rpy_rad=f.rpy_rad,
        )
        for f in sorted(asset.asset_type.frames, key=lambda f: f.id)
        if f.link is None
    )

    # The tensor in the model is centroidal and `com_m` is measured from the box
    # CENTRE (see `schema.Inertial.com_m`), so the inertial origin has to carry
    # the same half height the geometry does. Emitting `com_m` raw declared the
    # mass at the foot, which stated a centroidal tensor about a point up to
    # 0.3 m away from the mass and made 315 kg of furniture sit flat on the
    # floor — more stable than reality, and hiding tipping rather than showing
    # it.
    com = body.inertial.com_m
    inertial_origin_m = (com[0], com[1], com[2] + half_height)

    return _BodyView(
        id=asset.id,
        asset_type=asset.asset_type,
        prefix=asset.prefix,
        body=body,
        world_pose=asset.world_pose,
        half_height=half_height,
        inertial_origin_m=inertial_origin_m,
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
        PLUGIN_BINDING: asset.ros2_control_plugin,
        "instance.end_effector.vendor_integrated": str(
            bool(asset.instance.end_effector and asset.instance.end_effector.vendor_integrated)
        ).lower(),
    }

    # The one open family, for the SELECTED backend — the same quantity
    # `_collision_args` resolves the collision URI scheme against, and the
    # plant's, because there is one artifact set per asset until ADR-0048 clause 2
    # is built. Until it is, ADR-0048 clause 1 refuses any asset whose two sides
    # differ, so both sides load the same backend and the question of which side
    # this is cannot arise.
    #
    # KEYED ON WHAT THE BACKEND DECLARES, AND ONLY VALUED FROM THE BLOCK. The
    # names come from `instance_params`, the field `_dropped_on_this_backend`
    # reads, so the resolver and the filter agree about which names exist. Built
    # from the supplied block instead, a misspelt binding was satisfied by the
    # same misspelling in `params` and reached the description under the
    # binding's argument name, never reaching the unknown-binding raise below.
    #
    # "Supplied" is `HardwareSelection.supplied_params`, the predicate the
    # validator's `missing-hardware-param` reads too, so an empty string is not a
    # value here either and falls through to the backstop.
    #
    # Bools are lowercased for the same reason `fixed_args` lowercases them: xacro
    # reads `true`, not Python's `True`.
    selected = asset.instance.hardware.backend
    selected_backend = asset.asset_type.hardware_backends.get(selected)
    declared = selected_backend.instance_params if selected_backend is not None else ()
    supplied = asset.instance.hardware.supplied_params(selected)
    for key in sorted(declared):
        if key in supplied:
            value = supplied[key]
            values[f"{PARAMS_BINDING_PREFIX}{key}"] = (
                str(value).lower() if isinstance(value, bool) else str(value)
            )

    # How fast the fitted end effector's drive joint may travel. Resolved from the
    # END-EFFECTOR TYPE rather than from the instance, because the rate is a fact
    # about the hardware rather than about this arm's use of it — the instance
    # only names which type is fitted.
    #
    # Absence raises rather than defaulting, for the reason in this function's
    # docstring: handing the vendor macro its own default here would produce a
    # description that loads, runs, and bounds the gripper at a number nobody
    # chose. `vendor_integrated` above may legitimately resolve to "false" for an
    # arm with no end effector, because that IS the answer; a drive rate has no
    # such answer.
    rate = _end_effector_drive_rate(asset, cell)
    if rate is not None:
        values["instance.end_effector.max_drive_rate_rad_s"] = fmt(rate)
    elif binding == "instance.end_effector.max_drive_rate_rad_s":
        raise BindingError(
            f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, but "
            f"asset {asset.id!r} fits no end effector whose type declares a grasp "
            f"specification. Fit one, or remove the binding from the type."
        )

    # A key the selected backend DECLARES and the instance does not supply a value
    # for — absent, or a string that is empty after stripping. The
    # validator answers this first and in the findings report (ADR-0053 decision
    # 2a); this is the backstop for a caller that came into `generate` by another
    # door, and it raises for the same reason `_end_effector_drive_rate` does —
    # handing the vendor macro its own `robot_ip:=''` produces a description that
    # loads and takes an arm's `ros2_control_node` down at `on_init`.
    if binding not in values and binding.startswith(PARAMS_BINDING_PREFIX):
        key = binding[len(PARAMS_BINDING_PREFIX) :]
        backend = asset.asset_type.hardware_backends.get(asset.instance.hardware.backend)
        if backend is not None and key in backend.instance_params:
            raise BindingError(
                f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, "
                f"and asset {asset.id!r} loads backend "
                f"{asset.instance.hardware.backend!r}, which declares parameter "
                f"{key!r} — but the asset supplies no value for it. Add it under "
                f"`hardware.params.{asset.instance.hardware.backend}`."
            )

    if binding not in values:
        raise BindingError(
            f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, "
            f"which this generator does not provide. Known bindings: "
            f"{', '.join(sorted(values))}."
        )
    return values[binding]


def _end_effector_drive_rate(asset: ResolvedAsset, cell: ResolvedCell) -> float | None:
    """The fitted end effector's declared drive rate in rad/s, or None if unfitted.

    None for an arm with no end effector, and for one whose end-effector type
    declares no grasp specification — a real state rather than an error, and the
    same shape `generate.bringup._grasp` uses for the same reason. The caller
    decides whether the absence matters.
    """
    if asset.instance.end_effector is None:
        return None
    effector = cell.end_effector_type(asset.instance.end_effector.type)
    if effector is None or effector.grasp is None:
        return None
    return float(effector.grasp.max_drive_rate_rad_s)


def _dropped_on_this_backend(asset: ResolvedAsset, binding: str) -> bool:
    """Whether an `instance.hardware.params.*` binding is left unemitted here.

    THE PREDICATE IS A UNION AND BOTH TERMS ARE LOAD-BEARING (ADR-0053, decision
    2b). Drop the binding **iff** the key is declared in `instance_params` by
    SOME backend of the type **and not** by the SELECTED one.

    The first term is what makes a drop DELIBERATE: it fires only on a key L0 has
    stated somewhere, so the generator is honouring a declaration rather than
    concealing a failure. The second is what makes it CONDITIONAL on which
    backend is loaded, which is the whole point — `sim` declares no instance
    parameters, so on a simulated arm the argument is not emitted at all and the
    vendor's own default stands. That is correct rather than merely tolerable:
    `xarm5.ros2_control.xacro` emits no `<param>` block whatsoever unless the
    plugin is the UFACTORY one, so a value passed to a simulated arm would be
    inert anyway — and emitting nothing is the same output for a stronger reason,
    one that lives in this repository instead of in a vendor file a pin bump can
    change.

    WHY A SINGLE TERM IS THE SILENT SWALLOW. `instance.hardware.params.robot_ipp`
    is in neither `sim`'s `[]` nor `real`'s `[robot_ip]`. Under "not declared by
    the selected backend" alone it would be dropped on BOTH backends and would
    never reach `_binding_value`'s unknown-binding raise, so a typo in a
    component library entry would silently produce a description with a vendor
    default in it. Under the union it fails the first term everywhere, is never a
    candidate for the filter, and raises. Filtering on "could not resolve"
    instead fails in the same direction.

    This union is NOT the one ADR-0053 rejects as Option B. That one takes the
    union of every backend's `instance_params` as the VALIDATOR's allowlist over a
    FLAT map, which is what loses the ability to say which backend a shared name
    belongs to. Here the map is indexed by backend, the validator still checks
    each block against the backend that block names, and the union appears only
    here, where its job is to separate "a backend deliberately declares no such
    parameter" from "nobody declares it, so this is a typo".

    The precedent for emitting no argument at all is `_collision_args`, which
    returns `[]` in the same file for the same reason: the shipped model is
    all-`sim`, so this filter must leave every committed description byte-identical
    or `./scripts/validate-model` stops being able to tell "the default is
    unchanged" from "the default moved".
    """
    if not binding.startswith(PARAMS_BINDING_PREFIX):
        return False
    key = binding[len(PARAMS_BINDING_PREFIX) :]
    backends = asset.asset_type.hardware_backends
    declared_somewhere = any(key in backend.instance_params for backend in backends.values())
    selected = backends.get(asset.instance.hardware.backend)
    declared_here = selected is not None and key in selected.instance_params
    return declared_somewhere and not declared_here


def _arm_view(asset: ResolvedAsset, cell: ResolvedCell) -> _ArmView:
    spec = asset.asset_type.description
    if not (spec.package and spec.file and spec.macro):
        raise BindingError(
            f"type {asset.asset_type.id!r} uses the xacro_macro provider but does not "
            "name a package, file and macro"
        )

    # Before any argument is resolved, and for every backend. The validator
    # reports the same condition as `unrouted-hardware-params` and gates
    # generation on it; this is the backstop for a caller that reached `generate`
    # by another door. The predicate is the model's one definition, so the two
    # halves cannot disagree about a type.
    unrouted = spec.unrouted_param_arguments()
    if unrouted:
        raise BindingError(
            f"type {asset.asset_type.id!r} binds macro argument(s) "
            f"{', '.join(unrouted)} to an instance parameter, but no `bound_args` entry "
            f"carries {PLUGIN_BINDING!r}, so the description of asset {asset.id!r} would "
            f"load the vendor macro's default plugin rather than the one backend "
            f"{asset.instance.hardware.backend!r} declares. Bind it."
        )

    args: list[tuple[str, str]] = [
        (name, str(value).lower() if isinstance(value, bool) else str(value))
        for name, value in sorted(spec.fixed_args.items())
    ]
    args += [
        (name, _binding_value(asset, binding, cell))
        for name, binding in sorted(spec.bound_args.items())
        if not _dropped_on_this_backend(asset, binding)
    ]
    args += _collision_args(spec, asset)

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


#: How a collision-mesh root is spelled in each scheme. The vendor's two spellings
#: of its own root, and nothing else may introduce a third — a scheme this map does
#: not know is a model error rather than a string built inline.
_ROOT_URI = {
    "file": "file://$(find {package})/{root}",
    "package": "package://{package}/{root}",
}


def _collision_args(spec: Any, asset: ResolvedAsset) -> list[tuple[str, str]]:
    """The collision-mesh root, if the type binds one (ADR-0028).

    Empty whenever the selected set is the vendor's own meshes, and that emptiness
    is load-bearing: selecting `vendor_meshes` emits exactly the bytes this
    generator emitted before the field existed. A binding that changed the output
    when nothing was selected would have made the byte-identity check unable to
    tell "the default is unchanged" from "the default moved".

    **The shipped model no longer selects `vendor_meshes`.** It selected it until
    2026-09-01; ADR-0028 is `Accepted` against the clause ADR-0051 restates and
    `select` is `convex_hull`, so the emptiness above describes the *fallback*
    rather than the shipped path. This paragraph said the opposite until
    2026-09-01, and worse: it asserted a byte-identity property — "this generator
    emits exactly the bytes it emitted before the field existed" — as a statement
    about the shipped output, which stopped being true the moment the field moved.
    A reader relying on it would have expected three unchanged descriptions.
    `tools/tests/test_collision_binding.py` holds both halves.

    The scheme comes from the model, per backend, because the root this replaces
    branches on the backend and this one has to branch with it.
    `xarm_device_macro.xacro` sets `mesh_path` to `file://$(find ...)` for a Gazebo
    plugin and `package://` for anything else; this function emitted `file://`
    unconditionally, so `backend: real` produced a description whose visuals
    resolved through the package path and whose collisions were absolute paths into
    the generating machine's install prefix. That is unportable, and it is the half
    a planner uses.

    Deriving it here instead would mean writing the vendor's three Gazebo plugin
    class strings into the generator, which is the knowledge `DescriptionSpec`'s
    docstring says this generator does not have: its entire knowledge of the vendor
    package is model data. `$(find ...)` is expanded by xacro rather than here, so
    the generated artifact carries no absolute path and is identical in every
    checkout.
    """
    selected = spec.collision.selected if spec.collision else None
    if selected is None or selected.kind == "vendor_meshes":
        return []
    backend = asset.instance.hardware.backend
    try:
        scheme = spec.collision.scheme_for(backend)
    except KeyError as exc:
        raise BindingError(
            f"type {asset.asset_type.id!r} binds a collision root, and asset "
            f"{asset.id!r} loads backend {backend!r}: {exc}"
        ) from exc
    root = _ROOT_URI[scheme].format(package=selected.package, root=selected.root)
    return [(spec.collision.root_arg, root)]


def _mount_link(asset: ResolvedAsset) -> str:
    """The root link of an arm's own model, which the vendor macro attaches to."""
    return ids.link(asset.id, "mount")


def body_views(cell: ResolvedCell) -> tuple[_BodyView, ...]:
    """Every authored body in the cell, resolved.

    Public because `generate.planning_scene` builds the planner's view of the
    cell from exactly these objects. Two generators reading one function is what
    stops the planner's idea of where a table is from drifting away from the
    simulator's.
    """
    return tuple(
        _body_view(a)
        for a in cell.assets
        if a.asset_type.description.provider == "body" and a.asset_type.description.body
    )


def generate(cell: ResolvedCell) -> list[Artifact]:
    bodies = body_views(cell)
    arms = tuple(_arm_view(a, cell) for a in cell.assets if a.asset_type.emits_vendor_description)

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
