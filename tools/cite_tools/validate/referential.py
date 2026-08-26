"""Referential integrity: does everything the model points at actually exist?

These are the checks a JSON Schema structurally cannot make. A schema can say
``type`` is a lower_snake_case string; only this can say that the string names a
type in the component library.

Each failure here corresponds to a real runtime symptom, and the messages say
which — a duplicate asset id is a namespace collision where two robots publish
the same topic, and finding that at validation time instead of at bring-up time
is the entire point of having this level.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from cite_tools.model.ids import WORLD_FRAME
from cite_tools.model.loader import FacilityModel
from cite_tools.model.schema import FlowEdge
from cite_tools.validate import Finding, error

#: Which configuration kind each category expects. `None` means the category
#: carries no configuration at all, so any configuration on it is a mistake.
_CATEGORY_CONFIG_KIND: dict[str, str | None] = {
    "robot": "robot",
    "conveyor": "conveyor",
    "sensor": "sensor",
    "fixture": None,
    "end_effector": None,
    "workpiece": None,
}


def check(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    findings += _duplicate_ids(model)
    findings += _asset_types_exist(model)
    findings += _zones_exist(model)
    findings += _pose_frames_resolve(model)
    findings += _no_pose_cycles(model)
    findings += _hardware_backends_exist(model)
    findings += _configuration_matches_category(model)
    findings += _stations_reference_real_things(model)
    findings += _workpiece_models_exist(model)
    findings += _flow_is_consistent(model)
    return findings


def _duplicate_ids(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    for label, ids in (
        ("asset", [a.id for a in model.assets]),
        ("asset type", [t.id for t in model.types]),
        ("zone", [z.id for z in model.zones]),
        ("station", [s.id for s in model.stations]),
    ):
        for value, count in sorted(Counter(ids).items()):
            if count > 1:
                findings.append(
                    error(
                        "duplicate-id",
                        f"{label}.{value}",
                        f"{count} {label}s share the id {value!r}",
                        "Ids must be unique across the whole model: every topic, frame and "
                        "controller name derives from them, so a duplicate means two things "
                        "publishing to the same name and neither of them working.",
                    )
                )
    return findings


def _asset_types_exist(model: FacilityModel) -> list[Finding]:
    known = {t.id for t in model.types}
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.type not in known:
            findings.append(
                error(
                    "unknown-type",
                    f"assets.{asset.id}.type",
                    f"no component library entry named {asset.type!r}",
                    f"Known types: {', '.join(sorted(known)) or '(none)'}.",
                )
            )
        if asset.end_effector and asset.end_effector.type not in known:
            findings.append(
                error(
                    "unknown-type",
                    f"assets.{asset.id}.end_effector.type",
                    f"no component library entry named {asset.end_effector.type!r}",
                )
            )
    return findings


def _zones_exist(model: FacilityModel) -> list[Finding]:
    known = {z.id for z in model.zones}
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.zone not in known:
            findings.append(
                error(
                    "unknown-zone",
                    f"assets.{asset.id}.zone",
                    f"no zone named {asset.zone!r}",
                    f"Known zones: {', '.join(sorted(known)) or '(none)'}.",
                )
            )
    for station in model.stations:
        if station.zone not in known:
            findings.append(
                error(
                    "unknown-zone", f"stations.{station.id}.zone", f"no zone named {station.zone!r}"
                )
            )
    for flow in model.flows:
        if flow.zone not in known:
            findings.append(
                error("unknown-zone", f"flow.{flow.id}.zone", f"no zone named {flow.zone!r}")
            )
    return findings


def _frames_of(model: FacilityModel, asset_id: str) -> set[str]:
    asset = model.asset(asset_id)
    if asset is None:
        return set()
    asset_type = model.asset_type(asset.type)
    if asset_type is None:
        return set()
    return {f.id for f in asset_type.frames}


def _pose_frames_resolve(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_assets = {a.id for a in model.assets}
    for asset in model.assets:
        ref = asset.pose.frame
        if ref == WORLD_FRAME:
            continue
        if "/" not in ref:
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"{ref!r} is neither {WORLD_FRAME!r} nor an <asset_id>/<frame_id> reference",
                )
            )
            continue
        target, frame_id = ref.split("/", 1)
        if target not in known_assets:
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"references asset {target!r}, which does not exist",
                )
            )
        elif frame_id not in _frames_of(model, target):
            available = sorted(_frames_of(model, target))
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"asset {target!r} has no frame named {frame_id!r}",
                    f"Frames on that asset's type: {', '.join(available) or '(none)'}. "
                    "Frames are declared on the type, so the coordinate is written once.",
                )
            )
    return findings


def _no_pose_cycles(model: FacilityModel) -> list[Finding]:
    """An asset placed relative to an asset placed relative to the first.

    Without this the resolver recurses until the stack runs out, and the
    traceback names the recursion rather than the two assets involved.
    """
    parent: dict[str, str] = {}
    for asset in model.assets:
        if asset.pose.frame != WORLD_FRAME and "/" in asset.pose.frame:
            parent[asset.id] = asset.pose.frame.split("/", 1)[0]

    findings: list[Finding] = []
    for start in sorted(parent):
        seen = [start]
        current = start
        while current in parent:
            current = parent[current]
            if current in seen:
                chain = " -> ".join([*seen[seen.index(current) :], current])
                findings.append(
                    error(
                        "pose-cycle",
                        f"assets.{start}.pose.frame",
                        f"placement cycle: {chain}",
                        "Every asset must ultimately be placed relative to cite_world.",
                    )
                )
                break
            seen.append(current)
    # One cycle produces a finding per member; keep only the first by chain text.
    return _unique_by_message(findings)


def _unique_by_message(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for f in findings:
        if f.message not in seen:
            seen.add(f.message)
            out.append(f)
    return out


def _hardware_backends_exist(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    for asset in model.assets:
        asset_type = model.asset_type(asset.type)
        if asset_type is None:
            continue
        backends = asset_type.hardware_backends
        if not backends:
            continue
        chosen = asset.hardware.backend
        if chosen not in backends:
            findings.append(
                error(
                    "unknown-backend",
                    f"assets.{asset.id}.hardware.backend",
                    f"type {asset_type.id!r} declares no backend named {chosen!r}",
                    f"Declared backends: {', '.join(sorted(backends))}.",
                )
            )
            continue
        allowed = set(backends[chosen].instance_params)
        for key in sorted(set(asset.hardware.params) - allowed):
            findings.append(
                error(
                    "unexpected-hardware-param",
                    f"assets.{asset.id}.hardware.params.{key}",
                    f"backend {chosen!r} of type {asset_type.id!r} declares no parameter {key!r}",
                    f"Declared parameters: {', '.join(sorted(allowed)) or '(none)'}.",
                )
            )
    return findings


def _configuration_matches_category(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    for asset in model.assets:
        asset_type = model.asset_type(asset.type)
        if asset_type is None or asset.configuration is None:
            continue
        expected = _CATEGORY_CONFIG_KIND.get(asset_type.category)
        actual = asset.configuration.kind
        if expected is None:
            findings.append(
                error(
                    "configuration-mismatch",
                    f"assets.{asset.id}.configuration",
                    f"type {asset_type.id!r} is a {asset_type.category}, which takes no "
                    "configuration",
                )
            )
        elif actual != expected:
            findings.append(
                error(
                    "configuration-mismatch",
                    f"assets.{asset.id}.configuration.kind",
                    f"is {actual!r} but type {asset_type.id!r} is a {asset_type.category}",
                    f"Expected kind {expected!r}.",
                )
            )
    return findings


def _stations_reference_real_things(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_assets = {a.id for a in model.assets}
    for station in model.stations:
        for asset_id in station.assets:
            if asset_id not in known_assets:
                findings.append(
                    error(
                        "unknown-asset",
                        f"stations.{station.id}.assets",
                        f"no asset named {asset_id!r}",
                    )
                )
        if station.actor is not None and station.actor not in known_assets:
            findings.append(
                error(
                    "unknown-asset",
                    f"stations.{station.id}.actor",
                    f"no asset named {station.actor!r}",
                )
            )
        for label, point in (("pick_from", station.pick_from), ("place_to", station.place_to)):
            if point is None:
                continue
            if point.asset not in known_assets:
                findings.append(
                    error(
                        "unknown-asset",
                        f"stations.{station.id}.{label}.asset",
                        f"no asset named {point.asset!r}",
                    )
                )
            elif point.frame not in _frames_of(model, point.asset):
                available = sorted(_frames_of(model, point.asset))
                findings.append(
                    error(
                        "unresolved-frame",
                        f"stations.{station.id}.{label}.frame",
                        f"asset {point.asset!r} has no frame named {point.frame!r}",
                        f"Frames on that asset's type: {', '.join(available) or '(none)'}.",
                    )
                )
        if station.trigger is not None and station.trigger.sensor not in known_assets:
            findings.append(
                error(
                    "unknown-asset",
                    f"stations.{station.id}.trigger.sensor",
                    f"no asset named {station.trigger.sensor!r}",
                )
            )
        if station.type == "transfer_station" and station.actor is None:
            findings.append(
                error(
                    "station-without-actor",
                    f"stations.{station.id}.actor",
                    "a transfer station must name the asset that does the work",
                )
            )
    return findings


def _workpiece_models_exist(model: FacilityModel) -> list[Finding]:
    """A work-piece the facility handles, with no type behind it.

    The name alone is not harmless. It reaches the generated world as the belt's
    ``<carry>`` list and the beam's ``<watch>`` list, so a misspelling produces a
    belt that carries nothing and a sensor that sees nothing, with no error
    anywhere — and it is now also the datum two validation rules size themselves
    from, which silently lose their bound when it does not resolve.
    """
    findings: list[Finding] = []
    by_id = {t.id: t for t in model.types}
    for name in model.facility.workpiece_models:
        asset_type = by_id.get(name)
        if asset_type is None:
            available = sorted(t.id for t in model.types if t.category == "workpiece")
            findings.append(
                error(
                    "unknown-type",
                    f"facility.workpiece_models.{name}",
                    f"no component library entry named {name!r}",
                    f"Declared work-piece types: {', '.join(available) or '(none)'}. "
                    "The name reaches the simulator as a Gazebo model name, so an "
                    "unresolved one gives a belt that carries nothing and a beam that "
                    "watches nothing, without an error.",
                )
            )
        elif asset_type.category != "workpiece":
            findings.append(
                error(
                    "workpiece-is-not-a-workpiece",
                    f"facility.workpiece_models.{name}",
                    f"names type {name!r}, which is a {asset_type.category}",
                    "Only a type of category 'workpiece' may be listed here. Listing a "
                    "fixture would tell the belt to carry the table.",
                )
            )
    return findings


def _flow_is_consistent(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_stations = {s.id for s in model.stations}
    known_assets = {a.id for a in model.assets}
    for flow in model.flows:
        for index, edge in enumerate(flow.edges):
            where = f"flow.{flow.id}.edges[{index}]"
            for label, station_id in (("from", edge.from_station), ("to", edge.to_station)):
                if station_id not in known_stations:
                    findings.append(
                        error(
                            "unknown-station",
                            f"{where}.{label}",
                            f"no station named {station_id!r}",
                        )
                    )
            if edge.via is not None and edge.via not in known_assets:
                findings.append(
                    error("unknown-asset", f"{where}.via", f"no asset named {edge.via!r}")
                )
            if edge.from_station == edge.to_station:
                findings.append(
                    error("self-edge", where, f"station {edge.from_station!r} flows to itself")
                )

        reachable = _reachable_stations(flow.edges)
        orphans = sorted(
            s.id for s in model.stations if s.zone == flow.zone and s.id not in reachable
        )
        for station_id in orphans:
            findings.append(
                error(
                    "unreachable-station",
                    f"stations.{station_id}",
                    f"is in zone {flow.zone!r} but appears in no edge of flow {flow.id!r}",
                    "A station nothing flows into or out of can never receive work. "
                    "Either connect it or remove it.",
                )
            )
    return findings


def _reachable_stations(edges: Iterable[FlowEdge]) -> set[str]:
    reachable: set[str] = set()
    for edge in edges:
        reachable.add(edge.from_station)
        reachable.add(edge.to_station)
    return reachable
