"""Generate the process topology L4 consumes.

The model stores flow as an edge list, because writing both ends of a link states
the same fact twice. L4 wants each station's neighbours, so the derivation
happens here — once, in the generator — rather than in the coordinator, where it
would be logic nobody tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from cite_tools.generate import Artifact
from cite_tools.model import ids
from cite_tools.model.loader import FacilityModel
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment


@dataclass(frozen=True)
class _StationView:
    id: str
    type: str
    actor: str | None
    capacity: int
    pick_frame: str | None
    place_frame: str | None
    trigger_topic: str | None
    trigger_state: str | None
    upstream: tuple[str, ...]
    downstream: tuple[str, ...]


def generate(model: FacilityModel, cell: ResolvedCell) -> list[Artifact]:
    flow = next((f for f in model.flows if f.zone == cell.zone), None)
    if flow is None:
        return []

    upstream: dict[str, list[str]] = {}
    downstream: dict[str, list[str]] = {}
    for edge in flow.edges:
        downstream.setdefault(edge.from_station, []).append(edge.to_station)
        upstream.setdefault(edge.to_station, []).append(edge.from_station)

    stations = [
        _StationView(
            id=s.id,
            type=s.type,
            actor=s.actor,
            capacity=s.capacity,
            pick_frame=ids.frame(cell.zone, *s.pick_from) if s.pick_from else None,
            place_frame=ids.frame(cell.zone, *s.place_to) if s.place_to else None,
            trigger_topic=(
                ids.interface(cell.zone, s.trigger_sensor, "detection")
                if s.trigger_sensor
                else None
            ),
            trigger_state=s.trigger_state,
            upstream=tuple(sorted(upstream.get(s.id, []))),
            downstream=tuple(sorted(downstream.get(s.id, []))),
        )
        for s in sorted(cell.stations, key=lambda s: s.id)
    ]

    text = (
        environment()
        .get_template("topology/flow.yaml.j2")
        .render(
            cell=cell,
            flow_id=flow.id,
            stations=stations,
            edges=flow.edges,
        )
    )
    return [Artifact(f"topology/{cell.zone}_flow.yaml", text)]
