"""Where a zone's generated artifacts are, for the ROS-free guards.

The guards read the generated tree directly as YAML rather than through
`cite_bringup.plan`: this suite must run on a host with no ROS and no built
workspace, and every file here is produced from the L0 model (ADR-0021), so
reading it duplicates no value (P1).

WHY THIS FILE EXISTS. The guards used to name one zone's topology, transform
table and world as module constants, and went on naming them after the scenarios
they guard were pointed at another zone. Nothing failed: a guard reading one
cell's artifacts to check another cell's scenario is green about a file nobody
drives.

So the guards do not name a zone at all. They parametrise over EVERY zone the
generated tree declares, which is a superset of whatever zone the scenarios are
pointed at and cannot come apart from it.

ONE SPELLING IS DERIVED FROM A ZONE NAME and the rest come out of the plan:
`<zone>_plan.yaml` is the same composition `cite_bringup.plan.default_plan_path`
makes, and it is the one door into the set. Every other path below is a
`package://` URI read out of the plan the generator wrote.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

#: The scenario directory, so that `_cell` — the scenarios' own shared
#: derivations — imports here as it does there. Added rather than assumed:
#: pytest puts this guard's directory on `sys.path`, never its parent.
SCENARIOS = Path(__file__).resolve().parents[1]
if str(SCENARIOS) not in sys.path:
    sys.path.insert(0, str(SCENARIOS))

GENERATED = Path(__file__).resolve().parents[3] / "workspace" / "src" / "cite_generated"

_URI_PREFIX = "package://cite_generated/"


def resolve(uri: str) -> Path:
    """A generated `package://` URI as a path in this checkout."""
    assert uri.startswith(_URI_PREFIX), (
        f"{uri!r} is not a cite_generated package URI; the plan names every artifact "
        "that way and a guard that resolved something else would be reading a file the "
        "cell never loads"
    )
    return GENERATED / uri[len(_URI_PREFIX) :]


def zone_ids() -> list[str]:
    """Every zone the generated tree declares, sorted.

    Collected from the bring-up plans because a plan is the artifact a zone is
    addressed through: `./scripts/sim --zone X` and every scenario reach the cell
    by loading `X`'s plan, so a zone with no plan is a zone nothing can start.
    """
    return sorted(path.name[: -len("_plan.yaml")] for path in GENERATED.glob("bringup/*_plan.yaml"))


@dataclass(frozen=True)
class Artifacts:
    """One zone's generated artifacts, read as data."""

    zone: str
    plan: dict
    topology: dict
    static_transforms: list[dict]
    world: Path

    @property
    def published_frames(self) -> set[str]:
        return {entry["child"] for entry in self.static_transforms}


def load(zone: str) -> Artifacts:
    """Read `zone`'s plan and everything the plan points at."""
    plan_path = GENERATED / "bringup" / f"{zone}_plan.yaml"
    assert plan_path.is_file(), (
        f"{plan_path} is missing; it is generated from the L0 model and is how a zone "
        "is addressed"
    )
    plan = dict(yaml.safe_load(plan_path.read_text())["plan"])
    assert plan["zone"] == zone, (
        f"{plan_path.name} declares zone {plan['zone']!r}; the file name and the plan "
        "disagree, so the zone a caller names and the cell it gets are two things"
    )
    topology_path = resolve(plan["topology"])
    tf_path = resolve(plan["static_frames"])
    return Artifacts(
        zone=zone,
        plan=plan,
        topology=dict(yaml.safe_load(topology_path.read_text())["topology"]),
        static_transforms=list(yaml.safe_load(tf_path.read_text())["static_transforms"]),
        world=resolve(plan["world"]),
    )
