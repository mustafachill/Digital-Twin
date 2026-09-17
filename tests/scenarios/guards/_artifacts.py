"""Where a zone's generated artifacts are, for the ROS-free guards.

The guards read the generated tree directly as YAML rather than through
`cite_bringup.plan`: this suite must run on a host with no ROS and no built
workspace, and every file here is produced from the L0 model (ADR-0021), so
reading it duplicates no value (P1).

WHY THIS FILE EXISTS. Both guards used to name `cell_a`'s topology, transform
table and world as module constants, and went on naming them after the scenarios
they guard were pointed at `cell_b`. Nothing failed: a guard reading one cell's
artifacts to check another cell's scenario is green about a file nobody drives.
Breaking `cell_b`'s transform table and declaring a second carried work-piece in
its world left both guards reporting 21 passed.

So the guards do not name a zone at all any more. They parametrise over EVERY
zone the generated tree declares, which is a superset of whatever zone the
scenarios are pointed at and cannot come apart from it. `cell_a` keeps this much
coverage after losing its scenarios, which is the cheapest half of what ADR-0056
records as lost.

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

    @property
    def conveyor_assets(self) -> tuple[str, ...]:
        """The belts this zone runs, named by the plan rather than by spelling.

        The guard used to find a belt with `child.endswith("__conveyor_1__surface")`,
        which is a test of how an asset id happens to be spelled: rename the
        asset and the guard silently measures nothing, or picks up whichever
        other frame ends that way.
        """
        return tuple(conveyor["asset"] for conveyor in self.plan.get("conveyors") or ())

    def belt_surface_frame(self, asset: str) -> str:
        """Where the scenario looks a belt's surface up.

        The same composition `continuous_line` makes when it resolves a belt
        through TF — `f"{ZONE}__{link}__surface"` — with the asset coming from
        the plan rather than from a guess about its name.
        """
        return f"{self.zone}__{asset}__surface"

    def frame_height(self, frame: str) -> float:
        for entry in self.static_transforms:
            if entry.get("child") == frame:
                return float(entry["xyz_m"][2])
        raise AssertionError(
            f"{frame} is not in the generated transform table for {self.zone}; the "
            "scenario resolves it through TF and would hang waiting for it"
        )


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
