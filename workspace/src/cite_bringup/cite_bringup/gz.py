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

"""Start a process that speaks this side's Gazebo transport, or do not start it.

ADR-0042 decided that `GZ_PARTITION` is derived per side, emitted into the
generated plan, and never defaulted. Its cost section states the obligation this
module exists to discharge: **every path that starts or attaches to a Gazebo
process has to carry it** — the launch graph, `scripts/sim`, `scripts/scenario`,
and anything a developer runs by hand.

When ADR-0042 was promoted, only the first of those was covered. The launch graph
built the environment and refused without it; the scenario harness started its own
`ros_gz_sim create`, `gz model` and `gz service` processes with a bare inherited
environment and carried nothing. Those processes fell back to gz-transport's
default partition, discovered a world that was not there, and the harness hung at
its work-piece spawn — a silent failure of exactly the class the record exists to
prevent, in the one path nobody had updated.

So the answer to "what environment does a Gazebo-transport process need?" is
stated once, here, and both the launch graph and the harness ask this module
rather than each building it. A second construction of that environment is a
value in two places (P1), and the last time this value existed in one place and
was missing from another, the failure was silence.

This is bring-up mechanism and not test scaffolding: `cite_bringup` already owns
the plan, the variable name and the refusal, and the developer running
`gz topic -e` by hand against a running cell needs the same answer the harness
does — see this package's README.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
import subprocess

from cite_bringup.plan import (
    default_plan_path,
    GZ_PARTITION_ENV,
    load,
    Plan,
    require_gz_partition,
    Side,
)

#: Argument vectors, by their leading words, that speak the Gazebo transport and
#: therefore may not be started without a partition. Leading *words* rather than
#: a binary name, because `ros_gz_sim`'s spawner is reached through `ros2 run`
#: and its argv[0] says only `ros2`.
#:
#: This is the list the scenario guard scans source against
#: (`tests/scenarios/guards/test_gz_calls_carry_the_partition.py`). It is stated
#: here, next to the mechanism that makes such a call correct, so that adding a
#: new kind of Gazebo command extends the guard in the same edit.
GZ_TRANSPORT_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("gz",),
    ("ign",),
    ("ros2", "run", "ros_gz_sim"),
    ("ros2", "run", "ros_gz_bridge"),
    ("parameter_bridge",),
)

#: Plans read so far, keyed by zone. A plan is a generated artifact that does not
#: change while a process runs, and `continuous_line` asks for this environment
#: about twice a second for the length of a line run; re-reading and re-resolving
#: the YAML on every sample would make the instrument the expensive part. A stale
#: entry cannot outlive the process that cached it, and a stale *tree* is caught
#: by `./scripts/validate-model`, which is where that question belongs.
_PLANS: dict[str, Plan] = {}


def plan_for(zone: str) -> Plan:
    """Return the generated bring-up plan for ``zone``, read once per process."""
    cached = _PLANS.get(zone)
    if cached is None:
        cached = load(default_plan_path(zone))
        _PLANS[zone] = cached
    return cached


def gz_environment(plan: Plan) -> dict[str, str]:
    """Build the environment every Gazebo-transport process for this plan is given.

    One dictionary, applied to `gz sim`, to `parameter_bridge`, to every
    `ros_gz_sim create` and to every probe the harness runs — because all of them
    speak the Gazebo transport, and a partition that reaches only the server
    leaves the bridge, the spawners and the probes discovering a different one.
    gz_ros2_control needs nothing: its controller managers are created inside the
    server's own process.

    Which side this addresses is the PLANT, structurally: it is the side the
    untwinned model describes and the side every scenario and `./scripts/sim`
    already address (ADR-0041, Decision 3). Bringing a counterpart up is a
    separate launch and is not built yet; when it is, it takes the second entry
    of the same list rather than a second rule.
    """
    plant: Side = plan.sides[0]
    environment = {GZ_PARTITION_ENV: plant.gz_partition}
    # Checked on the dictionary just built, and that is the point: this is the
    # value the processes will actually be started with, so the check binds to
    # the path that starts them rather than to the shell that invoked it. A
    # future edit that builds this environment from somewhere else, or renames
    # the key, is refused here instead of producing two cells that quietly share
    # a transport.
    require_gz_partition(plant, environment)
    return environment


def process_environment(
    plan: Plan, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build a complete process environment: the caller's, with the partition set.

    `launch` merges `additional_env` into the inherited environment itself, so
    the launch graph wants `gz_environment` alone. A bare `subprocess` call does
    not: passing `env=` replaces the environment rather than extending it, and a
    `ros2 run` started with nothing but `GZ_PARTITION` loses `AMENT_PREFIX_PATH`
    and fails to find the executable at all. That asymmetry is the reason this
    function exists separately rather than callers remembering it.
    """
    merged = dict(os.environ if environ is None else environ)
    merged.update(gz_environment(plan))
    return merged


def run(
    argv: Sequence[str], *, zone: str, timeout: float, **kwargs: object
) -> subprocess.CompletedProcess:
    """Run a Gazebo-transport command in ``zone``'s partition and capture it.

    The single door every such call goes through. `capture_output` and `text`
    are fixed rather than offered: every caller reads what the command printed —
    a pose, an entity list, a creation result — and one that did not would be
    asking whether the process exited, which `gz` answers 0 to whether or not it
    reached a world.

    ``timeout`` is required. Without a partition these commands do not fail; they
    loop asking for a list of world names until something kills them, which is
    how this defect presented (`subprocess.TimeoutExpired` after 120 s), and a
    caller that forgot a timeout would hang the run instead of failing it.
    """
    return subprocess.run(
        list(argv),
        env=process_environment(plan_for(zone)),
        capture_output=True,
        text=True,
        timeout=timeout,
        **kwargs,
    )
