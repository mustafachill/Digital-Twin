# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Which zone a command drives when none is named (ADR-0069 decision 5).

THE RULE. When the generated plans declare exactly one zone, that zone is the
default; when they declare more than one, there is no default and the caller
has to name one. So ADR-0056's "--zone is required" returns by itself the day a
second zone is declared, and nothing has to remember to put it back.

THIS IS THE ONE PLACE THE DEFAULT IS DERIVED. `./scripts/sim`,
`./scripts/scenario` (through `tests/scenarios/_cell.py`) and `./scripts/program`
all ask this module; none of them states a zone name of its own. Read from the
generated bring-up plans rather than from L0 directly, because a plan is the
artifact a zone is addressed through — `<zone>_plan.yaml` is the composition
`cite_bringup.plan.default_plan_path` makes — and the plans are generated from L0
(ADR-0021), so this duplicates no value (P1).

IT ALSO SAYS WHETHER A NAMED ZONE EXISTS (`--check`). A zone the model does
not declare used to reach `simulation.launch.py`, inside a freshly started
container, where the plan lookup failed — and `./scripts/sim` exited 0. The
shell entry points now ask this file first, on the host, and refuse naming the
zones there are.

STANDARD LIBRARY ONLY, AND RUNNABLE AS A FILE. The shell scripts ask it on the
host, before the container is entered, so that a refusal stays cheap; and the
scenario guards import `_cell.py` on a host with no ROS overlay. Neither can
import an installed workspace package, so both run this file by its path in the
source tree. Nothing here may import ROS, `yaml` or a sibling module.

THE SOURCE TREE ONLY, AND IT REFUSES ANYWHERE ELSE. The plans it reads are
found from this file's own (resolved) place in `workspace/src`. This module
ships in the `cite_bringup` package, so an install prefix carries it too.
`./scripts/build` installs with `--symlink-install`, whose entry resolves back
to this file and answers correctly; a build without that flag puts a COPY there,
which has no plans beside it, and answering from there would mean answering "no
zones" about a facility that has one. So importing or running it from anywhere
its source-tree plans are not refuses, saying where to run it instead. A node
that is already running knows its zone: it is handed one
(`cite_bringup.plan.default_plan_path` takes it as a required argument), and it
has no business asking for a default.

THE SAME SET IS COMPUTED TWICE MORE, ON PURPOSE.
`cite_facility.artifacts.declared_zones` reads it from the INSTALLED
`cite_generated` share directory through the ament index, because it runs inside
a node, where this file is refused; and `tests/scenarios/guards/_artifacts.py`'s
`zone_ids` reads it from the source tree with no ROS, because the guards run on a
host and `cite_facility` is a workspace package they cannot import. This module
cannot call the first, which needs the ament index and therefore ROS, and the
first cannot call this one, which refuses inside an install prefix. That is a
layering necessity rather than a copy made for convenience. The rule all three
apply is one line —
every `<zone>_plan.yaml` under `cite_generated/bringup`, sorted — and it is the
plan file name `cite_bringup.plan.default_plan_path` composes, which is what
keeps them from drifting.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

#: What every generated bring-up plan's file name ends with.
PLAN_SUFFIX = "_plan.yaml"

#: The generated plans in the source tree this file sits in. Committed, never
#: hand-edited (ADR-0021), and byte-identical to what the build installs.
SOURCE_PLANS = Path(__file__).resolve().parents[2] / "cite_generated" / "bringup"

if not SOURCE_PLANS.is_dir():
    raise ImportError(
        f"cite_bringup/zones.py answers from the source tree's generated plans, and "
        f"this copy at {Path(__file__).resolve()} has none beside it — it is the copy "
        "an install prefix carries. Run the source-tree file by its path, as "
        "scripts/_lib.sh's `default_zone` does; a running node is handed its zone "
        "and never asks for a default."
    )


class NoDefaultZone(Exception):
    """The generated plans do not name exactly one zone, so none is the default."""


class UndeclaredZone(Exception):
    """A zone was named that no generated bring-up plan declares."""


def zones(plans: Path) -> list[str]:
    """Every zone with a generated bring-up plan in ``plans``, sorted."""
    return sorted(
        path.name[: -len(PLAN_SUFFIX)] for path in Path(plans).glob(f"*{PLAN_SUFFIX}")
    )


def default_zone(plans: Path = SOURCE_PLANS) -> str:
    """Return the only zone the plans in ``plans`` declare, or refuse.

    Raises `NoDefaultZone` naming every zone found, so that a caller who has to
    pick one is told what there is to pick from.
    """
    found = zones(plans)
    if len(found) == 1:
        return found[0]
    if not found:
        raise NoDefaultZone(
            f"no generated bring-up plan under {plans}, so there is no zone to default "
            "to. Run ./scripts/validate-model --write, or name one with --zone."
        )
    raise NoDefaultZone(
        f"--zone is required: the model declares {len(found)} zones "
        f"({', '.join(found)}) and none of them is the default. Name one with --zone."
    )


def check(zone: str, plans: Path = SOURCE_PLANS) -> str:
    """Return ``zone`` if the plans in ``plans`` declare it, or refuse naming them.

    Raises `UndeclaredZone` naming every zone found, so a caller who mistyped
    one is told what there is.
    """
    found = zones(plans)
    if zone in found:
        return zone
    declared = ", ".join(found) if found else f"none — there is no plan under {plans}"
    raise UndeclaredZone(
        f"the model declares no zone {zone!r}. Declared: {declared}."
    )


def main(argv: list[str] | None = None) -> int:
    """Print the default zone, or the checked one; say why not and exit 2."""
    parser = argparse.ArgumentParser(
        prog="zones.py",
        description="Print the zone a command drives when none is named, or check a named one.",
    )
    parser.add_argument(
        "--plans", type=Path, default=SOURCE_PLANS,
        help="The directory of generated bring-up plans to read.",
    )
    parser.add_argument(
        "--check", metavar="ZONE",
        help="Print ZONE if the plans declare it, and refuse naming them if not.",
    )
    args = parser.parse_args(argv)
    try:
        print(default_zone(args.plans) if args.check is None else check(args.check, args.plans))
    except (NoDefaultZone, UndeclaredZone) as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
