#!/usr/bin/env python3
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

"""Block until this side is genuinely serving, then exit.

ADR-0047 clause 3's readiness witness. It is the same shape as `ros_gz_sim
create` and the controller-manager spawner — a process that blocks on a condition
and exits — so its exit is consumed by the launch graph's existing `_gate` and a
witness that cannot satisfy its condition fails the launch with a diagnosis, like
every other link.

**Why the chain needed one at all.** The last gate in `simulation.launch.py` was
labelled `"the skill servers"` and fired when they were *started*, not when they
were serving. Nothing in this project has ever announced that a cell finished
coming up — not a pair, and not the single cell every scenario runs today. That
is what this closes, and it improves the solo bring-up as much as the paired one.

**What it observes: one side, its own.** It runs in the process environment the
launch gave it, so its `ROS_DOMAIN_ID` and `GZ_PARTITION` are this side's, and
every name it addresses is byte-identical to the other side's by rule (ADR-0044
clause 1). It therefore cannot observe the counterpart even in principle, which
is what keeps the supervisor above it from being a cross-domain observer.

**What it may not observe, and this is a rule rather than a limitation.**

- **The other side.** Not "does not", *cannot*: it holds one context on one
  domain, and it is given no side's identity but its own.
- **Real-time factor.** ADR-0043's second half — both sides sustaining 1.0
  concurrently — is explicitly **not** a bring-up condition, so a side can be up,
  slow, and indistinguishable from a healthy one here. Making readiness depend on
  a performance figure would turn a slow host into a bring-up failure, which is
  the opposite of what a ceiling on a failure means.

**Its deadline is measured on the wall clock, deliberately.** Every other node in
this launch honours `use_sim_time` and this one is declared `False`, because one
of the failures it exists to catch is a cell whose simulated clock never starts:
a deadline measured in a clock that is not running cannot expire, and the witness
would hang forever exactly where it is supposed to produce a diagnosis. It reads
no clock for anything else — it publishes nothing, subscribes to nothing, and
sends no goal.
"""

from __future__ import annotations

import argparse
import sys
import time

from cite_bringup.plan import default_plan_path, load, Plan, PlanError
from cite_interfaces.action import Detect, Grasp, MoveTo, Pick, Place, Transfer
from cite_runtime import runtime
import rclpy
from rclpy.action import ActionClient
from rclpy.parameter import Parameter

#: A ceiling on a failure, never a schedule. Nothing proceeds when it expires:
#: the witness exits non-zero, `_gate` stops the launch, and the supervisor above
#: reports which side never announced. Generous enough that a loaded host reaches
#: the end of its own gate chain, and short enough that a skill server which is
#: never going to serve is reported rather than waited on forever.
#:
#: It sits above the chain it follows rather than beside it: by the time this
#: process starts, every controller has been spawned and the planning scene has
#: been applied, so what remains is one MoveGroupInterface construction per arm.
DEADLINE_S = 300.0

#: How long a single `wait_for_server` call blocks before the loop re-checks the
#: overall deadline.
#:
#: **This is a poll, and calling it anything else would be false.** An earlier
#: version of this comment said the call was "a blocking wait on a graph event"
#: that "returns the instant the server appears". It is neither. Read on
#: 2026-08-30 in the installed package,
#: `/opt/ros/jazzy/lib/python3.12/site-packages/rclpy/action/client.py`:
#: `ActionClient.wait_for_server` loops on `self.server_is_ready()` with a
#: `sleep_time = 0.25` between attempts, decrementing `timeout_sec` itself, and
#: the two lines directly above that loop are
#: `# TODO(jacobperron): Remove arbitrary sleep time and return as soon as server
#: is ready` and a link to ros2/rclpy#58. So the server can be up for a quarter of
#: a second before this process learns of it, and that latency is upstream's to
#: remove rather than this file's.
#:
#: **What makes it permitted is the ceiling, not the interval.** P4 forbids
#: sleeping for a guessed duration in place of an event; this waits under
#: :data:`DEADLINE_S`, whose expiry is a failure that names the endpoints that
#: never answered. Nothing here proceeds because a timer elapsed. This bound is
#: only how often the deadline gets a chance to be enforced, and shortening or
#: lengthening it changes no outcome.
_SLICE_S = 1.0

#: Every action a skill server advertises, paired with the plan field naming it.
#: Read from the plan rather than composed here, because an action name assembled
#: in this file would be a second place a name is made (CLAUDE.md §8).
_SKILL_ACTIONS = (
    ("move_to", MoveTo),
    ("pick", Pick),
    ("place", Place),
    ("grasp", Grasp),
    ("transfer", Transfer),
)


def endpoints(plan: Plan) -> list[tuple[str, type]]:
    """Every action server this side must be answering before it is ready.

    The tail of the bring-up chain and only the tail. Everything before it is
    already gated on a real completion event — a spawner exiting, a lifecycle
    transition, the planning-scene loader finishing — so re-checking it here
    would be a second statement of a fact the launch already holds. What the
    chain did *not* hold is that the servers it started last are serving.

    The L4 line coordinator is **not** in this list, and that is a stated
    limitation rather than an oversight: it starts only under `line:=true`, it
    takes exclusive hold of the very skills below, and a pair is brought up idle.
    A witness that waited on it would fail every bring-up that does not run it.
    **So readiness under `line:=true` does not cover L4**: the token means this
    side's skills and detection are serving, and says nothing about whether the
    coordinator that was started alongside them ever reached its own first tick.

    **An empty list is not "nothing to wait on", it is a plan this witness cannot
    read**, and :func:`main` refuses it rather than exiting 0. See the refusal
    there for what that would otherwise announce.
    """
    wanted: list[tuple[str, type]] = []
    for manager in plan.controller_managers:
        if manager.skills is None:
            continue
        for field, action_type in _SKILL_ACTIONS:
            wanted.append((getattr(manager.skills, field), action_type))
    if plan.detection is not None:
        wanted.append((plan.detection.detect_action, Detect))
    return wanted


def main(argv: list[str] | None = None) -> int:
    """Wait for this side's endpoints, then exit 0 — or name what never appeared."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", required=True)
    parser.add_argument(
        "--side",
        required=True,
        help="The side this process belongs to. Reported in the diagnosis only; "
             "this witness observes one domain and it is the one it was started "
             "in, so the name cannot select what it looks at.",
    )
    parser.add_argument("--deadline", type=float, default=DEADLINE_S)
    args, ros_args = parser.parse_known_args(argv)

    try:
        plan = load(default_plan_path(args.zone))
    except PlanError as exc:
        print(f"READINESS WITNESS FAILED: {exc}", file=sys.stderr)
        return 2

    outstanding = endpoints(plan)
    if not outstanding:
        # Refused before a context is created, because there is nothing this
        # process could go on to observe. `plan.load` accepts a plan whose
        # controller managers declare no `skills:` block, so an edit or a
        # generator change that dropped it would leave this witness with an empty
        # condition - which it would satisfy instantly, exit 0 on, and the launch
        # would announce the side ready and the supervisor would report the pair
        # up. "Nothing to wait on" is the one answer a readiness witness may
        # never give.
        print(
            f"READINESS WITNESS FAILED: the plan for zone {plan.zone!r} names no "
            f"action server for side {args.side!r} to wait on, over "
            f"{len(plan.controller_managers)} controller manager(s). A side with "
            "no endpoints cannot be observed to be serving, and exiting 0 here "
            "would announce a readiness nothing checked.",
            file=sys.stderr,
        )
        return 2

    # `cite_runtime.init` rather than `rclpy.init`, for the reason ADR-0034
    # records: this process can still be alive when the launch tears the side
    # down, and the raw pair loses the context shutdown to a signal-handler race.
    runtime.init(args=ros_args)
    node = rclpy.create_node(
        "readiness_witness",
        # Declared rather than defaulted, and False rather than True: see this
        # module's docstring. A deadline in a clock that may never start cannot
        # expire, and expiry is the whole point of this process.
        parameter_overrides=[Parameter("use_sim_time", value=False)],
    )
    node.get_logger().info(
        f"waiting for {len(outstanding)} action server(s) on side {args.side!r}"
    )

    deadline = time.monotonic() + args.deadline
    pending = list(outstanding)
    try:
        while pending:
            name, action_type = pending[0]
            client = ActionClient(node, action_type, name)
            try:
                while not client.wait_for_server(timeout_sec=_SLICE_S):
                    if time.monotonic() >= deadline:
                        missing = ", ".join(entry[0] for entry in pending)
                        print(
                            f"READINESS WITNESS FAILED: side {args.side!r} did not "
                            f"finish coming up within {args.deadline:g} s. Still "
                            f"unanswered: {missing}. Every step before this one "
                            "reported success, so the servers were started and are "
                            "not serving.",
                            file=sys.stderr,
                        )
                        return 1
            finally:
                client.destroy()
            node.get_logger().info(f"serving: {name}")
            pending.pop(0)
    finally:
        runtime.shutdown(node)
    return 0


if __name__ == "__main__":
    sys.exit(main())
