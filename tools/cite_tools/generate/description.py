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

from cite_tools.generate import Artifact, arm_description_path, controllers_path
from cite_tools.model import ids
from cite_tools.model.geometry import Pose
from cite_tools.model.resolve import ResolvedAsset, ResolvedAxis, ResolvedCell
from cite_tools.model.schema import (
    PARAMS_BINDING_PREFIX,
    PLUGIN_BINDING,
    Body,
    EnvReference,
    Material,
    xacro_would_evaluate,
)
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
    #: The appearance this body wears, or ``None`` where L0 declares none.
    #: Resolved here so the template performs no lookup: a template that joined a
    #: name against a library would be a second place names are resolved, and the
    #: one that already exists is tested.
    material: Material | None = None


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
    #: The controller configuration this side's description names, relative to
    #: the generated package. Per side, because the configuration is.
    controllers_path: str = ""
    #: The linear track this arm rides, emitted between the mount and the arm's
    #: base (ADR-0067); `None` for an arm bolted in place.
    axis: _AxisView | None = None


@dataclass(frozen=True)
class _AxisView:
    """A track's joint and carriage, formatted for the arm's description."""

    joint: str
    carriage_link: str
    direction: str
    stroke_m: str
    max_speed_mps: str
    max_force_n: str
    mass_kg: str
    size_m: str
    half_height_m: str
    ixx: str
    iyy: str
    izz: str
    #: `None` on a side whose track backend declares no plugin: the joint is
    #: emitted and no `<ros2_control>` block claims it (ADR-0070 item 3).
    plugin: str | None


def _axis_view(axis: ResolvedAxis | None, side: str) -> _AxisView | None:
    """The carriage as a solid box, so the joint has a link with mass behind it."""
    if axis is None:
        return None
    x, y, z = axis.carriage_size_m
    m = axis.carriage_mass_kg
    return _AxisView(
        joint=axis.joint,
        carriage_link=axis.carriage_link,
        direction=fmt_triple(axis.direction),
        stroke_m=fmt(axis.stroke_m),
        max_speed_mps=fmt(axis.max_speed_mps),
        max_force_n=fmt(axis.max_force_n),
        mass_kg=fmt(m),
        size_m=fmt_triple(axis.carriage_size_m),
        half_height_m=fmt(-z / 2.0),
        ixx=fmt(round(m * (y * y + z * z) / 12.0, 9)),
        iyy=fmt(round(m * (x * x + z * z) / 12.0, 9)),
        izz=fmt(round(m * (x * x + y * y) / 12.0, 9)),
        plugin=axis.plugin_on(side),
    )


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


def _body_view(asset: ResolvedAsset, cell: ResolvedCell) -> _BodyView:
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
        material=None if body.material is None else cell.material(body.material),
    )


def env_argument(key: str) -> str:
    """The xacro argument a parameter read from the environment arrives under.

    The parameter's own name, so the plan's `description_args` and the
    `$(arg ...)` in the description are one statement read twice.
    """
    return key


def _binding_value(asset: ResolvedAsset, binding: str, cell: ResolvedCell, side: str) -> str:
    """Resolve one `bound_args` binding name to its value on ``side``.

    Every binding is enumerated. An unknown one raises rather than defaulting,
    so a typo in the component library fails loudly here instead of silently
    handing the vendor macro its own default — which would produce a description
    that loads and is wrong.

    Every backend term is the SIDE's: the plugin, and the parameter block it is
    valued from (ADR-0048 clause 2, open-work #38).
    """
    plugin = asset.ros2_control_plugin_on(side)
    if binding == PLUGIN_BINDING and plugin is None:
        # The backstop for `plugin-less-backend-on-a-bound-description`. Binding
        # nothing here hands the vendor macro its OWN default, which for
        # `xarm_description` is the physical component.
        raise BindingError(
            f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, and "
            f"asset {asset.id!r} loads backend {asset.backend_on(side)!r} on the {side} "
            "side, which declares no `ros2_control_plugin`. The vendor macro would load "
            "its own default plugin. Declare one, or do not bind it."
        )
    # An arm is its own Gazebo model, so it attaches to its own root link rather
    # than to a link in the scene. Where that root sits in the world is stated
    # once, by the generated static transform table and the spawn pose — not
    # inside this description.
    values: dict[str, str] = {
        "instance.id": asset.id,
        "instance.prefix": asset.prefix,
        "instance.zone": asset.zone,
        "instance.namespace": asset.namespace,
        # The carriage when the arm rides a track: the vendor base then sits on
        # the moving link, and the track's joint is between it and the mount.
        "instance.parent_link": (
            asset.axis.carriage_link if asset.axis is not None else _mount_link(asset)
        ),
        # Zero: the arm's root link IS its mount, and the model is placed in the
        # world at spawn time. Writing the pose here as well would state the same
        # fact twice.
        "instance.parent_xyz_m": fmt_triple((0.0, 0.0, 0.0)),
        "instance.parent_rpy_rad": fmt_triple((0.0, 0.0, 0.0)),
        PLUGIN_BINDING: str(plugin),
        "instance.end_effector.vendor_integrated": str(
            bool(asset.instance.end_effector and asset.instance.end_effector.vendor_integrated)
        ).lower(),
    }

    # The one open family, for the backend SELECTED ON THIS SIDE — the same
    # quantity `_collision_args` resolves the collision URI scheme against. A side
    # whose backend differs from the plant's gets a description of its own
    # (ADR-0048 clause 2, built by ADR-0070), so each side's parameters come from
    # the block of the backend that side loads.
    #
    # A value read FROM THE ENVIRONMENT (`EnvReference`) is emitted as the xacro
    # argument `$(arg <key>)` and never resolved here: the value is not the
    # model's, and the generated tree is committed. The plan names the variable,
    # `cite_bringup.plan.resolve_description_args` reads it at launch and hands it
    # to xacro, and a description expanded without it fails in xacro rather than
    # reaching the vendor component with an empty address (ADR-0070 item 2).
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
    selected = asset.backend_on(side)
    selected_backend = asset.asset_type.hardware_backends.get(selected)
    declared = selected_backend.instance_params if selected_backend is not None else ()
    supplied = asset.instance.hardware.supplied_params(selected)
    for key in sorted(declared):
        if key in supplied:
            value = supplied[key]
            if isinstance(value, EnvReference):
                values[f"{PARAMS_BINDING_PREFIX}{key}"] = f"$(arg {env_argument(key)})"
                continue
            # Refused rather than escaped: xacro evaluates `${...}` and `$(...)`
            # after XML has unescaped the attribute, and the template cannot
            # escape `$` for every argument because a collision root relies on
            # `$(find ...)`. The validator reports it first as
            # `hardware-param-contains-dollar`, reading the same predicate; this
            # raises only for the binding actually being resolved.
            if binding == f"{PARAMS_BINDING_PREFIX}{key}" and xacro_would_evaluate(value):
                raise BindingError(
                    f"asset {asset.id!r} supplies {value!r} for parameter {key!r} of "
                    f"backend {selected!r}, which {binding!r} binds into the description, "
                    f"and it contains `$`, which xacro would evaluate. Remove it."
                )
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
        backend = asset.asset_type.hardware_backends.get(selected)
        if backend is not None and key in backend.instance_params:
            raise BindingError(
                f"type {asset.asset_type.id!r} binds a macro argument to {binding!r}, "
                f"and asset {asset.id!r} loads backend {selected!r} on the {side} side, "
                f"which declares parameter {key!r} — but the asset supplies no value "
                f"for it. Add it under `hardware.params.{selected}`."
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


def _dropped_on_this_backend(asset: ResolvedAsset, binding: str, side: str) -> bool:
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
    returns `[]` in the same file for the same reason: a simulated side's
    description must stay byte-identical whatever parameters other backends
    declare, or `./scripts/validate-model` stops being able to tell "the default
    is unchanged" from "the default moved".

    Asked per SIDE: a binding dropped on the simulated plant is emitted on a
    physical counterpart, whose description is its own (ADR-0070).
    """
    if not binding.startswith(PARAMS_BINDING_PREFIX):
        return False
    key = binding[len(PARAMS_BINDING_PREFIX) :]
    backends = asset.asset_type.hardware_backends
    declared_somewhere = any(key in backend.instance_params for backend in backends.values())
    selected = backends.get(asset.backend_on(side))
    declared_here = selected is not None and key in selected.instance_params
    return declared_somewhere and not declared_here


def environment_arguments(asset: ResolvedAsset, side: str) -> tuple[tuple[str, str], ...]:
    """The xacro arguments ``side``'s description takes from the environment.

    `(argument, variable)` pairs, sorted: one for every parameter the backend
    selected on that side declares and the asset supplies as an `EnvReference`.
    The bring-up plan carries exactly these, so a launch knows which variables
    to resolve and which arguments to hand xacro (ADR-0070 item 2). Empty for a
    side that reads nothing from the environment, which is every simulated side.
    """
    selected = asset.asset_type.hardware_backends.get(asset.backend_on(side))
    if selected is None:
        return ()
    supplied = asset.instance.hardware.supplied_params(asset.backend_on(side))
    return tuple(
        (env_argument(key), value.env)
        for key in sorted(selected.instance_params)
        if isinstance(value := supplied.get(key), EnvReference)
    )


def _arm_view(asset: ResolvedAsset, cell: ResolvedCell, side: str) -> _ArmView:
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
            f"{asset.backend_on(side)!r} declares. Bind it."
        )

    args: list[tuple[str, str]] = [
        (name, str(value).lower() if isinstance(value, bool) else str(value))
        for name, value in sorted(spec.fixed_args.items())
    ]
    args += [
        (name, _binding_value(asset, binding, cell, side))
        for name, binding in sorted(spec.bound_args.items())
        if not _dropped_on_this_backend(asset, binding, side)
    ]
    args += _collision_args(spec, asset, side)

    return _ArmView(
        id=asset.id,
        asset_type=asset.asset_type,
        package=spec.package,
        file=spec.file,
        macro=spec.macro,
        namespace=asset.namespace,
        mount_link=_mount_link(asset),
        args=tuple(sorted(args)),
        controllers_path=controllers_path(cell.zone, asset.id, side),
        axis=_axis_view(asset.axis, side),
    )


#: How a collision-mesh root is spelled in each scheme. The vendor's two spellings
#: of its own root, and nothing else may introduce a third — a scheme this map does
#: not know is a model error rather than a string built inline.
_ROOT_URI = {
    "file": "file://$(find {package})/{root}",
    "package": "package://{package}/{root}",
}


def _collision_args(spec: Any, asset: ResolvedAsset, side: str) -> list[tuple[str, str]]:
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
    backend = asset.backend_on(side)
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
        _body_view(a, cell)
        for a in cell.assets
        if a.asset_type.description.provider == "body" and a.asset_type.description.body
    )


def scene_materials(bodies: tuple[_BodyView, ...]) -> tuple[Material, ...]:
    """The appearances this cell's bodies wear, each once, in a stable order.

    THE ONES WORN, NOT THE WHOLE LIBRARY. A material no body in this zone wears
    would be a definition in a document that never references it — noise in a
    diff, and a reader's first question about a scene should not be why it
    declares a colour nothing is painted with. The library itself is emitted
    whole, once, by `generate.materials`, which is where a consumer outside the
    generated tree reads it.

    DE-DUPLICATED BECAUSE URDF REQUIRES IT: urdfdom keeps the first definition of
    a repeated material name and warns, so two tables wearing `table_top` must
    produce one definition and two references, not two of each.
    """
    seen: dict[str, Material] = {}
    for body in bodies:
        if body.material is not None:
            seen[body.material.id] = body.material
    return tuple(seen[name] for name in sorted(seen))


def described_sides(cell: ResolvedCell, asset: ResolvedAsset) -> tuple[str, ...]:
    """The sides that get an artifact of their own for ``asset``.

    The plant always; the counterpart only on a paired zone and only where it
    loads a backend other than the plant's (ADR-0048 clause 2). Read by the
    description, control and bring-up generators alike, so the file a plan names
    and the file that exists are decided once.
    """
    return tuple(
        side
        for side in (s.name for s in cell.sides)
        if side == ids.PLANT_SIDE or asset.differs_on(side)
    )


def generate(cell: ResolvedCell) -> list[Artifact]:
    bodies = body_views(cell)
    arms = tuple(
        (side, _arm_view(a, cell, side))
        for a in cell.assets
        if a.asset_type.emits_vendor_description
        for side in described_sides(cell, a)
    )

    env = environment()
    artifacts = [
        Artifact(
            f"description/{cell.zone}_scene.urdf.xacro",
            env.get_template("description/scene.urdf.xacro.j2").render(
                cell=cell,
                world_frame=ids.WORLD_FRAME,
                bodies=bodies,
                materials=scene_materials(bodies),
            ),
        )
    ]
    artifacts += [
        Artifact(
            arm_description_path(cell.zone, arm.id, side),
            env.get_template("description/arm.urdf.xacro.j2").render(zone=cell.zone, arm=arm),
        )
        for side, arm in arms
    ]
    return artifacts
