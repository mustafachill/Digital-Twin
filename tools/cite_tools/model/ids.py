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

#: Separates the three parts of a flattened TF frame name. Doubled so that a
#: link name containing a single underscore stays unambiguous.
FRAME_SEP = "__"

#: Namespaces reserved for state that belongs to no single asset.
#: `naming-and-namespaces.md`, "Reserved names".
RESERVED_SCOPES = ("facility", "twin", "line")

#: `lower_snake_case`: no hyphens, no camel case, no leading digit.
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


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
