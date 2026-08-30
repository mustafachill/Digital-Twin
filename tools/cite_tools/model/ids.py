"""Construction of every name the system uses.

This module is the *only* place in the repository that builds a topic, action,
service, frame, joint, or controller name. That is not a style preference. P2 —
that simulation and hardware are interchangeable — is made entirely of names, and
`naming-and-namespaces.md` states the consequence plainly: a single name written
by hand in a second place is how that guarantee breaks, invisibly, until someone
runs on hardware.

So: generators call these functions, nodes receive the results as generated
parameters, and nothing anywhere constructs a name by concatenating strings.

See `docs/architecture/naming-and-namespaces.md` for the scheme and
`docs/adr/0020-facility-model-conventions.md` for the conventions.
"""

from __future__ import annotations

import re

#: Fixed root of every name in the system. Isolates this system from anything
#: else on a shared lab network.
ROOT = "cite"

#: The facility root frame, tied to the surveyed physical origin (L5).
WORLD_FRAME = "cite_world"

#: The one backend id that cannot reach a physical machine. Every other value
#: names a `ros2_control` plugin that drives real hardware.
#:
#: Here rather than spelled at each call site because three separate rules turn
#: on it — a controller manager is hosted inside the Gazebo process for this
#: backend and runs its own node otherwise, `use_sim_time` is derived from it,
#: and a paired zone may not name anything else on its plant side — and a fourth
#: statement of the string would be the value-in-two-places P1 forbids.
#: `cite_bringup.plan.SIMULATION_BACKEND` is the one unavoidable second
#: statement: it is a different build unit that cannot import this one, and it
#: reads the value out of the generated plan rather than deciding it.
SIMULATION_BACKEND = "sim"

#: Separates the three parts of a flattened TF frame name. Doubled so that a
#: link name containing a single underscore stays unambiguous.
FRAME_SEP = "__"

#: Namespaces reserved for state that belongs to no single asset.
#: `naming-and-namespaces.md`, "Reserved names".
RESERVED_SCOPES = ("facility", "twin", "line")

#: `lower_snake_case`: no hyphens, no camel case, no leading digit.
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")

#: The side of a twin pair the untwinned model already describes — the one that
#: exists whether or not the twin does, and that every Phase 1 artifact, scenario
#: and script already addresses.
PLANT_SIDE = "plant"

#: The side that exists only where the zone declares ``twin.sides: pair``.
COUNTERPART_SIDE = "counterpart"

#: Both, in the order they are emitted. Defined structurally — by which side the
#: untwinned model describes — and NOT by which side is being commanded
#: (ADR-0041, Decision 3). That is what makes the partition below safe to derive:
#: a name that moved with `TwinMode` would change the transport partition when an
#: operator changed mode, which is the silent cross-talk ADR-0042 exists to
#: remove. It is also why the index is not `virtual`/`physical` — those are
#: backends, and a Phase 2.A pair has two simulated sides.
SIDES = (PLANT_SIDE, COUNTERPART_SIDE)


class InvalidIdentifierError(ValueError):
    """Raised when an identifier cannot legally take part in a name."""


def validate_identifier(value: str, *, kind: str) -> str:
    """Return ``value`` if it is a legal identifier, else raise.

    Rejecting early matters more than it looks. An identifier with a hyphen or a
    leading digit produces a name that is accepted by some ROS interfaces and
    rejected by others, so the failure surfaces far from its cause.
    """
    if not IDENTIFIER.match(value):
        raise InvalidIdentifierError(
            f"{kind} {value!r} is not lower_snake_case. "
            "Identifiers must start with a letter and contain only "
            "lowercase letters, digits and underscores "
            "(docs/architecture/naming-and-namespaces.md, rule 4)."
        )
    if value in RESERVED_SCOPES:
        raise InvalidIdentifierError(
            f"{kind} {value!r} is a reserved scope name "
            f"({', '.join(RESERVED_SCOPES)}) and cannot be used as a zone or asset id."
        )
    return value


def namespace(zone: str, asset_id: str) -> str:
    """`/cite/<zone>/<asset_id>` — the namespace an asset's interfaces live in."""
    validate_identifier(zone, kind="zone")
    validate_identifier(asset_id, kind="asset id")
    return f"/{ROOT}/{zone}/{asset_id}"


def interface(zone: str, asset_id: str, name: str) -> str:
    """`/cite/<zone>/<asset_id>/<interface>` — a topic, service, or action.

    ``name`` may contain slashes, because a controller's action is nested under
    the controller: ``joint_trajectory_controller/follow_joint_trajectory``.
    """
    for part in name.split("/"):
        validate_identifier(part, kind="interface name part")
    return f"{namespace(zone, asset_id)}/{name}"


def scope(reserved: str, name: str) -> str:
    """`/cite/<reserved>/<name>` — facility-, twin-, or line-scope state."""
    if reserved not in RESERVED_SCOPES:
        raise InvalidIdentifierError(
            f"{reserved!r} is not a reserved scope. Expected one of {RESERVED_SCOPES}."
        )
    for part in name.split("/"):
        validate_identifier(part, kind="interface name part")
    return f"/{ROOT}/{reserved}/{name}"


def partition(zone: str, side: str) -> str:
    """`cite/<zone>/<side>` — the Gazebo transport partition one side runs in.

    Not a ROS name, and deliberately built here anyway. `ROS_DOMAIN_ID` does not
    isolate Gazebo transport at all: two `gz sim` servers in one container on
    separate ROS domains were measured with two publishers on one world's stats
    topic and two subscribers on one belt's command topic, so a single conveyor
    setpoint would have started both cells' belts with nothing logged
    (ADR-0042). What kept the measured pairs apart was the container hostname,
    which gz-transport derives its default partition from — an accident of one
    deployment, with two terms either of which can silently stop differing.

    So the partition is stated explicitly, and it is stated once. A hand-typed
    partition is a value in two places and is one typo away from re-creating that
    defect with the same silence, which is why this is a name like every other
    name in this system rather than a string in a launch file.

    No leading slash, and only lowercase letters, digits, underscores and
    slashes: a partition is prefixed to every Gazebo topic name, and
    gz-transport validates it as a namespace.
    """
    validate_identifier(zone, kind="zone")
    if side not in SIDES:
        raise InvalidIdentifierError(
            f"{side!r} is not a side of a twin pair. Expected one of {SIDES}."
        )
    return f"{ROOT}/{zone}/{side}"


def domain_offset(side: str) -> int:
    """How far this side's ROS domain sits from the checkout's base — 0 or 1.

    The second of the two isolations a side needs, formed here beside
    :func:`partition` and from the same ``SIDES`` tuple, so that one side
    identity produces both and a third isolation added later has an obvious home.
    They are independent and neither substitutes for the other: `GZ_PARTITION`
    is a gz-transport namespace that `move_group`, the controller managers and
    the skill servers have never heard of, and `ROS_DOMAIN_ID` was measured not
    to isolate Gazebo transport at all (ADR-0042, ADR-0044 clause 2).

    An OFFSET rather than a domain, and that is the whole reason this function
    returns a small integer instead of a number anyone could use directly. A
    domain id is not a name: it is a host-scoped resource allocation, closer to a
    TCP port, and emitting an absolute one into the committed generated tree
    fails in both of the only two ways it could be derived (ADR-0044, clause 4).
    Derived from the deployment, it differs in every clone, so
    `./scripts/validate-model` — which regenerates and requires the output to be
    byte-identical — would fail in every checkout but the one that wrote it.
    Derived from the model instead, it is the same number everywhere, so two
    checkouts of one commit resolve the same domain and discover each other,
    which is the defect the per-checkout derivation exists to prevent.

    What IS a fact about the modelled system is which side this is, and the
    offset is a function of nothing else. The base travels separately, in
    `CITE_DOMAIN_BASE`, and the absolute value is base plus offset resolved once
    in `cite_bringup`.

    The plant is 0 deliberately: an untwinned zone then resolves to exactly the
    domain it uses today, so nothing in Phase 1 moves and `./scripts/enter` from
    a checkout still lands on the side every existing script addresses.
    """
    if side not in SIDES:
        raise InvalidIdentifierError(
            f"{side!r} is not a side of a twin pair. Expected one of {SIDES}."
        )
    return SIDES.index(side)


def frame(zone: str, asset_id: str, link: str) -> str:
    """`<zone>__<asset_id>__<link>` — a TF frame.

    Flattened because TF has no hierarchy. Note there is no leading slash: TF
    frame ids are not topic names, and prefixing one with a slash is a
    long-standing source of frames that silently never connect.
    """
    validate_identifier(zone, kind="zone")
    validate_identifier(asset_id, kind="asset id")
    validate_identifier(link, kind="link name")
    return f"{zone}{FRAME_SEP}{asset_id}{FRAME_SEP}{link}"


def prefix(asset_id: str) -> str:
    """`<asset_id>_` — prefixes the joints, links and controllers of one instance.

    Two instances of the same component type differ only by this, which is what
    lets the component library be instantiated many times without collision.
    """
    validate_identifier(asset_id, kind="asset id")
    return f"{asset_id}_"


def joint(asset_id: str, suffix: str) -> str:
    """`<asset_id>_<suffix>` — e.g. ``arm_1_joint1``.

    The suffix is the vendor's own joint name. It is deliberately not
    reformatted: it must match the description exactly, because a controller
    whose joint names differ from the description fails at runtime with an error
    naming the spawner rather than the mismatch.
    """
    validate_identifier(suffix, kind="joint suffix")
    return f"{prefix(asset_id)}{suffix}"


def controller(asset_id: str, suffix: str) -> str:
    """`<asset_id>_<suffix>` — e.g. ``arm_1_joint_trajectory_controller``."""
    validate_identifier(suffix, kind="controller suffix")
    return f"{prefix(asset_id)}{suffix}"


def link(asset_id: str, suffix: str) -> str:
    """`<asset_id>_<suffix>` — e.g. ``arm_1_link_base``."""
    validate_identifier(suffix, kind="link suffix")
    return f"{prefix(asset_id)}{suffix}"


def controller_action(zone: str, asset_id: str, controller_suffix: str, action: str) -> str:
    """The full action name a controller exposes.

    ``/cite/cell_a/arm_1/joint_trajectory_controller/follow_joint_trajectory``

    Note that the controller appears twice in different forms: prefixed
    (``arm_1_joint_trajectory_controller``) as the controller manager knows it,
    and unprefixed inside the asset's namespace as consumers address it. Both
    derive from the same suffix here, so they cannot drift apart.
    """
    validate_identifier(controller_suffix, kind="controller suffix")
    validate_identifier(action, kind="action name")
    return interface(zone, asset_id, f"{controller_suffix}/{action}")
