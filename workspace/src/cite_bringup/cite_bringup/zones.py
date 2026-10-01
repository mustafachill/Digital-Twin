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

STANDARD LIBRARY ONLY, AND RUNNABLE AS A FILE. The shell scripts ask it on the
host, before the container is entered, so that a refusal stays cheap; and the
scenario guards import `_cell.py` on a host with no ROS overlay. Neither can
import an installed workspace package, so both run this file by its path in the
source tree. Nothing here may import ROS, `yaml` or a sibling module.
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


class NoDefaultZone(Exception):
    """The generated plans do not name exactly one zone, so none is the default."""


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


def main(argv: list[str] | None = None) -> int:
    """Print the default zone, or say why there is none and exit 2."""
    parser = argparse.ArgumentParser(
        prog="zones.py",
        description="Print the zone a command drives when none is named.",
    )
    parser.add_argument(
        "--plans", type=Path, default=SOURCE_PLANS,
        help="The directory of generated bring-up plans to read.",
    )
    args = parser.parse_args(argv)
    try:
        print(default_zone(args.plans))
    except NoDefaultZone as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
