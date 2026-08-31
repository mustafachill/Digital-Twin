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

"""Which sides a goal is dispatched to, per mode.

ADR-0050 decision 2's table, as data. The record's third column — *both sides
evaluate the same command?* — is the question this module answers, because it is
the same question: L5 dispatches a goal to the sides that evaluate it, and to no
others.

**What crosses is an L3 GOAL, at the action boundary, and nothing below L3 ever
crosses.** No trajectory, no joint command, no controller setpoint. The reason
that matters most is 2.B: the far side becomes hardware by one data change, and
hardware's entry point in this project is the same typed L3 action server on the
same name (P2, P9), so a design that streamed a trajectory would be a design 2.B
has to break. The other two are that a trajectory crossing the boundary would
make L5 a control path, which is L2's job and not L5's, and that at any
real-time factor below 1.0 a side's clock falls behind the wall clock without
bound (ADR-0049) — so a far side driven from the near side's MOTION would be
executing an arbitrarily old stream, and in 2.B that far side is an arm in a
room. A goal has no such property: it is evaluated when it arrives.

**THE HAZARD THIS CREATES, named here because it is a property of the design and
not a defect in it.** Both sides plan the goal independently, through their own
`move_group`. ADR-0027 establishes that an identical request returns a
byte-identical trajectory **from one `move_group`**, and records that *same
seed, same trajectory across runs* is **not** established. So an operator
watching the near side is not, on present evidence, watching the path the far
arm will take — only the endpoint it will reach. Fixing that needs planner
determinism, which is a separate decision; crossing the planned trajectory
instead was considered and refused by ADR-0050, because it bypasses the far
side's own collision gate against its own planning scene. Nothing in this module
may be read as saying the two paths agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cite_interfaces.msg import ResultCode, TwinMode

#: The side the operator is on, and the side L5 publishes its own products to
#: (ADR-0044 clause 5). Read out of the generated plan by
#: `cite_twin.boundary`; named here so the routing table can be written in side
#: identities rather than in positions.
PLANT_SIDE = "plant"

#: The other side. Derived from the mode table's *physical* side by a refusal
#: already in the L0 schema rather than chosen: ADR-0041 Decision 3 refuses
#: `hardware.backend: real` on a zone declaring `twin.sides: pair`, so on a
#: paired zone the plant is always `sim`, and a physical side — if one exists —
#: is always the counterpart.
#:
#: > The mode table's "physical" side is the `counterpart`; its "virtual" side
#: > is the `plant`.
#:
#: This is not reversible by anything short of reopening that refusal
#: (ADR-0050, Context).
COUNTERPART_SIDE = "counterpart"


@dataclass(frozen=True)
class Route:
    """Where one goal goes, or why it goes nowhere.

    `sides` empty means the goal is refused, and `code` and `detail` are what
    the caller is told. A refusal is never silent and never a timeout: a mode
    with no command flow through L5 says so in the goal response.
    """

    sides: tuple[str, ...]
    code: int
    detail: str

    @property
    def accepted(self) -> bool:
        return bool(self.sides)


#: Both sides evaluate the goal independently, which is what makes a divergence
#: sample definable at all (ADR-0050 decision 3, term 1). In plan order — the
#: plant first — because the operator's own side is the one whose refusal is
#: most informative and the one an operator is watching.
_BOTH_SIDES = (PLANT_SIDE, COUNTERPART_SIDE)

#: ADR-0050 decision 2's table, keyed by mode. The value is either the sides a
#: goal is dispatched to or the reason there are none.
#:
#: `SIM`, `REAL` and `SHADOW` carry no command across the boundary at all, so
#: L5's operator endpoint has no job in them — and it is deliberately NOT a
#: second front door to the plant's own skill server, which keeps its own
#: callers. `CLOSED_LOOP` is the one row the record leaves undecided, and an
#: undefined gate is not something to improvise inside a router.
_TABLE: Mapping[int, Route] = {
    TwinMode.MODE_SIM: Route(
        (),
        ResultCode.PRECONDITION_FAILED,
        "in SIM nothing crosses the boundary: the counterpart is idle, and the "
        "operator commands the plant's own L3 action server directly.",
    ),
    TwinMode.MODE_REAL: Route(
        (),
        ResultCode.PRECONDITION_FAILED,
        "in REAL nothing crosses the boundary: the plant is idle, and the "
        "physical side is commanded on its own side.",
    ),
    TwinMode.MODE_SHADOW: Route(
        (),
        ResultCode.PRECONDITION_FAILED,
        "SHADOW carries state from the physical side to the virtual one and no "
        "command in either direction; there is nothing here to dispatch.",
    ),
    TwinMode.MODE_VALIDATED: Route(
        _BOTH_SIDES,
        ResultCode.SUCCESS,
        "both sides evaluate the goal; the reverse state flow supplies the "
        "divergence metric's second operand.",
    ),
    TwinMode.MODE_CLOSED_LOOP: Route(
        (),
        ResultCode.NOT_IMPLEMENTED,
        "CLOSED_LOOP is VIRTUAL_LEAD's flow plus a validation gate, and what "
        "that gate checks is an open question filed for Phase 5 with its own "
        "ADR. A router may not improvise it (ADR-0050, decision 2).",
    ),
    TwinMode.MODE_VIRTUAL_LEAD: Route(
        _BOTH_SIDES,
        ResultCode.SUCCESS,
        "the goal crosses and the motion does not: both sides receive it at "
        "their own L3 action server and plan it independently. Nothing gates "
        "the far side on the near side's outcome - that gate is CLOSED_LOOP.",
    ),
}


def route(mode: int) -> Route:
    """Return the sides a goal entering L5 in ``mode`` is dispatched to.

    A mode this table does not know about is refused rather than defaulted. The
    project has already added a sixth mode, and a router that treated an
    unrecognised value as "dispatch to nobody" would answer a seventh silently
    while looking correct.
    """
    known = _TABLE.get(mode)
    if known is None:
        return Route(
            (),
            ResultCode.PRECONDITION_FAILED,
            f"mode {mode} is not one of TwinMode.MODE_*, so what crosses the "
            "boundary in it is undecided (ADR-0050, decision 2).",
        )
    return known


def reverse_state_flow(mode: int) -> tuple[str, ...]:
    """Return the sides whose STATE crosses into L5 in ``mode``, per the same table.

    Consumed by L5 and never republished (ADR-0050 decision 1b). It is the
    monitor's second operand, and its absence is why `VIRTUAL_LEAD` cannot
    produce a divergence number: the mode is DEFINED by there being no reverse
    flow (`TwinMode.msg`: "No reverse flow behind it - that is SHADOW"), so the
    number is uncomputable in it by the mode's own definition rather than
    undefined in principle.

    **L5 may not quietly open a reverse state flow to make it computable.**
    `VIRTUAL_LEAD` plus a reverse state flow is a mode the published set does
    not contain, and adding one is an argument in the mode set — never a
    decision taken inside a monitor.

    The action result and feedback an L5 client receives are NOT this flow. A
    client receives them by construction; that is the forward call returning,
    not a mirror. They carry no joint state and cannot supply the metric's
    second operand.
    """
    if mode in (TwinMode.MODE_SHADOW, TwinMode.MODE_VALIDATED, TwinMode.MODE_CLOSED_LOOP):
        return (COUNTERPART_SIDE,)
    return ()
