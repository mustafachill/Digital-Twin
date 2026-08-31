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

"""Two ROS contexts in one process, and the names L5 is allowed to own.

ADR-0050 decision 1: **L5 is one process per zone holding one ROS context per
side, and nothing is republished across the boundary.** The mechanism is
`rclpy.init(context=..., domain_id=N)` per side, demonstrated in this repository
by the second-world campaign's Q5 rig, which carried 20,000 messages across two
domains publishing and subscribing on ONE topic string on both, and counted no
message arriving twice.

`domain_bridge` was refused for everything L5 does today, not on coverage but on
ADR-0044's criterion: **a bridge copies, and cannot refuse, transform, timestamp
or gate.** All four verbs are load-bearing here — `SetMode` must refuse, a
mirrored sample must be timestamped on arrival, and command routing must gate on
mode. A component that copies has already answered "yes" to every question L5
exists to ask.

WHAT L5 MAY PUBLISH ON A SIDE, and it is a short list:

* Its own products — mode and divergence — under `/cite/twin/...`, the scope
  `naming-and-namespaces.md` reserves for this layer, on the PLANT's domain,
  because that is the side the operator is on (ADR-0044 clause 5).
* Commands, in the one mode that has a command flow, as an action CLIENT of a
  side's own L3 server. A client is not a publisher of a name that side owns.

A message arriving on one side's context is consumed by L5. It is never
forwarded to a publisher on the other side's context, under its own name or any
other, in any mode. Both sides carry byte-identical names by rule (ADR-0044
clause 1), so a forwarded message would land on a topic the receiving side's own
broadcaster already owns and feed every consumer there a mixture of two cells —
and a remap to escape that is a second form of a name, inside the one component
whose job is to make the two sides interchangeable.

ONE TF BUFFER PER SIDE, if L5 ever grows one. Both sides broadcast identical
frame ids, so feeding both trees into one buffer produces a tree whose
transforms silently come from either cell (ADR-0050 clause 1c). No buffer exists
here yet; the rule is written down where the second context is, so that whoever
adds one meets it.

WHY THIS MODULE IS THE WHOLE OF THE CROSS-DOMAIN MECHANISM. ADR-0044 clause 3
makes L5 the only component with endpoints in both domains, and its cost is that
L5 concentrates the entire class of "which context is this call on?" defect in
one place. Concentrating it is the mitigation. Spreading `Context` objects
through the rest of the package would give that mitigation away.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
import threading

from cite_bringup.plan import ControllerManager, Plan, SkillActions, resolve_domain_id
from cite_interfaces.action import Grasp, MoveTo, Pick, Place, Transfer
from cite_interfaces.msg import DivergenceMetrics, TwinMode
from cite_interfaces.srv import SetMode
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

#: The fixed root of every name in this system.
#:
#: A second statement of `cite_tools.model.ids.ROOT`, in a build unit that
#: cannot import it, and it does not decide the value: :func:`operator_endpoint`
#: REFUSES a name that does not start with it rather than assuming one, so a
#: generated name that ever stopped starting with `/cite` fails here instead of
#: producing a plausible endpoint under a scope nobody reserved.
ROOT = "/cite"

#: The scope reserved for L5 — mode, divergence metrics, registration
#: (`naming-and-namespaces.md`, "Reserved names"). Nothing on either side owns a
#: name beneath it, which is what makes an L5 endpoint safe to advertise on a
#: side's own domain without colliding with that side's own graph.
TWIN_SCOPE = f"{ROOT}/twin"

#: The node name L5 runs under on each side. Identical on both, because names
#: are identical on both by rule and the side identity lives outside the graph
#: (ADR-0044 clause 1) — the two never meet, being on different domains.
NODE_NAME = "twin_boundary"

#: Every L3 skill the plan names for an arm, under the exact field name
#: `cite_bringup.plan.SkillActions` declares it, mapped to its action type.
#:
#: Keyed by that dataclass's own field names and checked against them at import,
#: so a sixth skill added to the plan reader is a failure here rather than a
#: skill L5 silently does not route. `Detect` is deliberately absent: it is
#: zone-level rather than per-asset, and it observes rather than commands, so it
#: is not a goal that crosses (ADR-0050 decision 2 is about commands).
SKILL_ACTION_TYPES: Mapping[str, type] = {
    "move_to": MoveTo,
    "pick": Pick,
    "place": Place,
    "grasp": Grasp,
    "transfer": Transfer,
}

_DECLARED = {field.name for field in fields(SkillActions)}
if set(SKILL_ACTION_TYPES) != _DECLARED:
    raise ImportError(
        "cite_twin routes the skills cite_bringup.plan.SkillActions declares, and the two "
        f"lists have drifted: the plan declares {sorted(_DECLARED)} and this module knows "
        f"{sorted(SKILL_ACTION_TYPES)}. A skill L5 does not know about is a skill an "
        "operator cannot reach through the twin boundary, silently."
    )


class BoundaryError(Exception):
    """L5 cannot span this deployment's boundary, and says why rather than guessing."""


def operator_endpoint(name: str) -> str:
    """The `/cite/twin/...` name L5 advertises for a side-owned interface.

    `/cite/cell_a/arm_1/move_to` becomes `/cite/twin/cell_a/arm_1/move_to`.

    **The operator's command enters L5 and not the plant's skill server**, and
    it cannot enter the plant's skill server and be observed there: both sides
    carry identical names, so L5 cannot serve `/cite/cell_a/arm_1/move_to`
    beside the plant's own server, and reading another server's goals is not
    something the action protocol offers (ADR-0050 decision 2).

    Derived from the side's own generated name rather than composed from a zone
    and an asset, so no asset name is written here at all (CLAUDE.md §8). The
    one thing this function adds is the reserved scope, which is the one part
    that is L5's to own.
    """
    if not name.startswith(f"{ROOT}/"):
        raise BoundaryError(
            f"{name!r} does not start with {ROOT}/, so it is not a name this system "
            "formed and there is no way to say what its twin-scope form would be. "
            "Every name comes from the generated plan (CLAUDE.md §8)."
        )
    return f"{TWIN_SCOPE}{name[len(ROOT):]}"


def asset_namespace(manager: ControllerManager) -> str:
    """The `/cite/<zone>/<asset>` namespace an asset's interfaces live under.

    Read off a name the plan already carries rather than composed, for the same
    reason :func:`operator_endpoint` is: the zone and the asset are stated once,
    in the model, and reach here inside every generated name.

    `node` is the controller manager's fully qualified node name, so its parent
    is the asset's namespace. A test asserts that the result is a prefix of
    every other name the plan states for the same asset, which is what makes
    this a derivation rather than an assumption.
    """
    namespace, _, leaf = manager.node.rpartition("/")
    if not namespace or not leaf:
        raise BoundaryError(
            f"asset {manager.asset!r} names its controller manager {manager.node!r}, "
            "which has no namespace to take. Every generated node name is "
            "/cite/<zone>/<asset>/<node> (CLAUDE.md §8)."
        )
    return namespace


#: The interface an arm's joint state arrives on, under the asset's namespace.
#:
#: **A leaf written by hand, and the one name in this package that the plan does
#: not carry.** It is `joint_state_broadcaster`'s own topic, formed upstream, and
#: the generated plan states the broadcaster's controller name without stating
#: what it publishes. So this is a second statement of a name in the sense P1
#: cares about, mitigated only by the namespace above being read rather than
#: composed. What closes it is the plan carrying the topic, which is generator
#: work and is deliberately not done here.
JOINT_STATE_INTERFACE = "joint_states"


@dataclass(frozen=True)
class SideAddress:
    """Which side, and which ROS domain it is on.

    Resolved through `cite_bringup.plan.resolve_domain_id` and nowhere else:
    that is ADR-0044 clause 4's single resolver, and L5 recomputes `base +
    offset` in no place at all. Addressed by side IDENTITY and never by list
    position — reading `sides[1]` gives a caller who meant the counterpart
    whatever happens to be second.
    """

    name: str
    domain_id: int


def address(plan: Plan, side: str, base: int) -> SideAddress:
    """Where one side of ``plan`` is, by name."""
    return SideAddress(name=side, domain_id=resolve_domain_id(plan, side, base))


class SideContext:
    """One side's ROS context, its node, and the thread that spins it.

    The unit of "which side am I talking to". Every publisher, subscription,
    service and action client L5 creates is created on one of these, so the
    question the compiler will not answer — *which context is this call on?* —
    is answered by which object the call went through.

    **The executor is multi-threaded and the reason is deliberate.** L5's
    operator endpoint dispatches a goal and then waits for two far-side goals to
    finish. That wait is inside a callback, which CLAUDE.md §10 forbids doing on
    a single-threaded executor with a default callback group, and would deadlock
    on the plant's own side: the responses being waited for need the same
    executor that is blocked. A multi-threaded executor with reentrant groups is
    the shape that makes the wait safe, and it is chosen here rather than
    discovered later.
    """

    def __init__(self, side: SideAddress, node_name: str = NODE_NAME) -> None:
        self.side = side
        self.context = rclpy.context.Context()
        # Signal handling is installed once, by the first context to ask for it.
        # rclpy's handler shuts down every context it knows about, so the second
        # side does not need its own and installing two would be two handlers
        # racing for one signal.
        options = (
            SignalHandlerOptions.ALL
            if not _signal_handlers_installed()
            else SignalHandlerOptions.NO
        )
        rclpy.init(
            context=self.context, domain_id=side.domain_id, signal_handler_options=options
        )
        _mark_signal_handlers_installed()
        self.node = Node(node_name, context=self.context)
        self.executor = MultiThreadedExecutor(context=self.context)
        self.executor.add_node(self.node)
        self._thread: threading.Thread | None = None

    def spin_in_a_thread(self) -> None:
        """Spin this side's executor off the calling thread."""
        if self._thread is not None:
            raise BoundaryError(f"side {self.side.name!r} is already spinning")
        self._thread = threading.Thread(
            target=self._spin, name=f"twin-{self.side.name}", daemon=True
        )
        self._thread.start()

    def _spin(self) -> None:
        try:
            self.executor.spin()
        except Exception:  # the context went away underneath us; stop() reports it
            return

    def stop(self) -> None:
        """Release this side, executor first, then node, then context.

        In that order, and not idempotent-by-flag: a second call would reach
        `destroy_node` on a destroyed node. The context is read off the node
        before it is destroyed so the two halves cannot disagree about which
        context is being released.
        """
        self.executor.shutdown()
        context = self.node.context
        self.node.destroy_node()
        if rclpy.ok(context=context):
            rclpy.shutdown(context=context)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None


#: Whether any context in this process has installed rclpy's signal handlers.
#:
#: Module state rather than a parameter, because the question is about the
#: PROCESS and not about a side: whichever side is constructed first takes the
#: handlers, and which one that is must not change what either side does.
_INSTALLED = threading.Lock()
_INSTALLED_FLAG = [False]


def _signal_handlers_installed() -> bool:
    with _INSTALLED:
        return _INSTALLED_FLAG[0]


def _mark_signal_handlers_installed() -> None:
    with _INSTALLED:
        _INSTALLED_FLAG[0] = True


def twin_endpoints() -> tuple[str, ...]:
    """Every name L5 owns that is fixed rather than derived from an asset.

    Read off the contracts rather than written here: the topic names are
    constants on their messages and the service name is a constant on its
    service, which is the one place each is written (ADR-0050 decision 5d). A
    test requires every one of them to be under :data:`TWIN_SCOPE`, which is
    what makes "L5 publishes nothing onto a name a side already owns" checkable
    rather than asserted.
    """
    # `SetMode.Request.SERVICE` and not `SetMode.SERVICE`: rosidl puts a
    # service's constants on the section they were declared in, which is how
    # C++ reaches it too (`ResetStation::Request::SERVICE`).
    return (TwinMode.TOPIC, DivergenceMetrics.TOPIC, SetMode.Request.SERVICE)
