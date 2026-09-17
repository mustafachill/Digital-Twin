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

"""Exactly one zone runs on a ROS graph, and this is what says otherwise.

ADR-0056 decision 3 states the invariant — a zone is addressed by name and
exactly one is up at a time — and, until this module, NOTHING ENFORCED IT. The
three facility scopes `/cite/facility`, `/cite/line` and `/cite/twin` are
deliberately singular, and `ROS_DOMAIN_ID` is derived per checkout and side and
never per zone, so two zones started from one checkout share one graph. Exactly
one of the collisions was loud, and only with `line:=true`. The rest were silent:
two `model_info` servers on one fixed service, two `/robot_description`
publishers describing DIFFERENT ROBOTS — so one cell's furniture can be spawned
into the other cell's world — and two `/clock` publishers from two independent
simulators, which is CLAUDE.md §10's "a mixed-time system produces plausible,
wrong results".

The realistic trigger is the use ADR-0056 keeps `cell_a` for: somebody
demonstrates the showcase in a second terminal while a `cell_b` run is up.

WHAT THE DETECTOR IS. A zone's bring-up puts that zone's name into the ROS graph
— `/cite/<zone>/<asset>/<interface>` for every asset it runs — and the set of
zone names this facility can produce is the set of generated bring-up plans. So
"another zone is here" is a synchronous question about the graph's own name list,
asked and answered without a single wait.

WHAT IT IS NOT, and this is load-bearing:

  * **It is not complete.** DDS discovery is asynchronous, so a zone started at
    the same instant may not be in this node's graph cache yet and will not be
    seen. The refusal is sound rather than exhaustive: it never fires on a cell
    that is alone, and it fires on one that is not IF the other has been
    discovered. Making it complete would mean waiting for an absence, and a
    bring-up that waits a guessed interval to decide it is alone is exactly the
    timing guess CLAUDE.md P4 forbids.
  * **It does not catch the same zone twice.** Two `cell_b` bring-ups collide
    identically, and this says nothing about them: `cell_b`'s names are not
    foreign to `cell_b`. That case is deliberately out of scope — CI brings the
    same zone up twice in a row per run, and a detector that could confuse a
    teardown that has not finished with a second cell would turn a lingering
    process into a hard bring-up failure.
  * **It is not a protective measure.** It refuses a bring-up. It cannot stop a
    cell that is already running, and it moves no robot.

The residual — the discovery race above, and the same-zone case — is recorded in
ADR-0056 and in `docs/open-work.md`.
"""

from __future__ import annotations

from collections.abc import Iterable

#: How a zone's names are spelled, once. `/cite/<zone>/<asset>/<interface>`
#: (`docs/architecture/naming-and-namespaces.md`), generated from the L0 model
#: and identical in simulation and on hardware.
_PREFIX = "/cite/{zone}/"


def zones_already_on_the_graph(
    graph_names: Iterable[str], ours: Iterable[str], declared: Iterable[str]
) -> list[str]:
    """Which OTHER declared zones have names on this ROS graph.

    `declared` is the set of zones the generated tree can produce, read from the
    bring-up plans rather than listed here: that is what keeps this from having
    to know the three reserved facility scopes, and what keeps it from firing on
    any other `/cite/...` name a test fixture might invent. A scope that is not a
    zone of this facility is not this function's business.
    """
    mine = set(ours)
    others = [zone for zone in sorted(set(declared)) if zone not in mine]
    if not others:
        return []
    names = list(graph_names)
    return [zone for zone in others if _present(names, zone)]


def _present(names: list[str], zone: str) -> bool:
    prefix = _PREFIX.format(zone=zone)
    return any(name.startswith(prefix) for name in names)


def refusal(intruders: list[str], ours: list[str], domain: str) -> str:
    """What a person reads when the refusal fires.

    Names the zone that is already there, because "another zone is running" sends
    the reader to look for it and this sends them to stop it.
    """
    return (
        f"zone(s) {intruders} are already on ROS_DOMAIN_ID={domain}, and this bring-up "
        f"is {ours}. Exactly one zone runs at a time (ADR-0056 decision 3): the "
        "`/cite/facility`, `/cite/line` and `/cite/twin` scopes are facility-singular "
        "by design and the domain is derived per checkout, not per zone, so two zones "
        "here would share one `/cite/facility/get_model_version`, one `/clock` fed by "
        "two independent simulators, and two `/robot_description` publishers "
        "describing different robots. Stop the other cell, or bring this one up from "
        "another checkout, which gets its own domain."
    )
