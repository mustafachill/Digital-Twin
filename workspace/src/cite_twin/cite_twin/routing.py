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


#: **Which sides are under command in each mode, whoever is commanding them.**
#:
#: This is not :data:`_TABLE`. `_TABLE` answers *where does L5 send a goal*;
#: this answers *which side is being driven at all*, including by callers L5
#: never sees. The two differ in exactly the modes where a side is commanded on
#: its own side: `REAL` and `SHADOW` carry no command across the boundary, and
#: the physical side is being driven in both.
#:
#: Read out of `TwinMode.msg`, mode by mode, and out of nothing else — that
#: file's per-mode comment is the one statement of what a mode means (P1):
#:
#: * `SIM` — "physical idle, virtual commanded" -> the plant.
#: * `REAL` — "physical commanded, virtual idle" -> the counterpart.
#: * `SHADOW` — "physical commanded, virtual follows its state" -> the
#:   counterpart. The plant follows; a follower is not commanded.
#: * `VALIDATED` — "both commanded" -> both.
#: * `CLOSED_LOOP` — "physical commanded only after the virtual validates it"
#:   -> both. The gate decides WHEN, never WHETHER.
#: * `VIRTUAL_LEAD` — "virtual commanded; the far side follows and actuates"
#:   -> both. The far side actuates, which is what separates this row from
#:   `SHADOW`'s follower.
#:
#: **This table is what the hardware gate is computed from** (`cite_twin.mode`),
#: which is why it is here beside the routing table rather than in the mode
#: server: a mode that dispatches a goal to a side it does not list as commanded
#: would be a contradiction between two tables, and the check below refuses to
#: import in that state rather than letting one of them be believed.
_COMMANDED: Mapping[int, tuple[str, ...]] = {
    TwinMode.MODE_SIM: (PLANT_SIDE,),
    TwinMode.MODE_REAL: (COUNTERPART_SIDE,),
    TwinMode.MODE_SHADOW: (COUNTERPART_SIDE,),
    TwinMode.MODE_VALIDATED: _BOTH_SIDES,
    TwinMode.MODE_CLOSED_LOOP: _BOTH_SIDES,
    TwinMode.MODE_VIRTUAL_LEAD: _BOTH_SIDES,
}


def _declared_modes() -> tuple[int, ...]:
    """Every `TwinMode.MODE_*` constant the message declares.

    `dir()` rather than `vars()`: rosidl exposes a message's constants as
    properties on its METACLASS, so the class's own `__dict__` does not hold
    them and a `vars()` scan would silently find nothing.
    """
    return tuple(
        getattr(TwinMode, name) for name in dir(TwinMode) if name.startswith("MODE_")
    )


def _refuse_to_import_a_mode_no_table_knows_about() -> None:
    """Fail the import when a mode exists that either table has not been told about.

    The alternative was discovered rather than chosen: a mode absent from
    `_COMMANDED` would be judged as commanding nothing, so a seventh mode would
    arrive **ungated** while every test that names modes by hand kept passing.
    This is the same guard `cite_twin.boundary` puts on `SKILL_ACTION_TYPES`,
    for the same reason and with the same cost — the package refuses to load
    until whoever added the mode has said what it does.
    """
    declared = set(_declared_modes())
    for name, table in (("_TABLE", _TABLE), ("_COMMANDED", _COMMANDED)):
        missing = declared - set(table)
        if missing:
            raise ImportError(
                f"TwinMode declares mode(s) {sorted(missing)} that cite_twin.routing's "
                f"{name} does not know about. What crosses the boundary in a mode, and "
                "which sides that mode commands, are decided in the mode set and read "
                "here - never defaulted, because a defaulted mode is an ungated one."
            )
    for mode, chosen in _TABLE.items():
        undeclared = set(chosen.sides) - set(_COMMANDED.get(mode, ()))
        if undeclared:
            raise ImportError(
                f"mode {mode} dispatches a goal to {sorted(undeclared)}, which "
                "_COMMANDED does not list as commanded in it. The two tables answer "
                "different questions and the second must contain the first: a side "
                "L5 sends a goal to is a side under command by definition."
            )


_refuse_to_import_a_mode_no_table_knows_about()


def commanded_sides(mode: int) -> tuple[str, ...]:
    """Return every side under command in ``mode``, whoever commands it.

    The superset of :func:`route`'s sides, and the one the hardware gate is
    computed from: *placing physical actuation under an authority that was not
    previously commanding it* (`cross-cutting-safety.md`) is a question about
    which sides the mode drives, not about which of them L5 happens to be the
    caller for. `REAL` is the case that separates the two — L5 dispatches
    nothing in it and the physical side is being driven.

    A mode no table knows about commands **both** sides. That is the
    conservative answer and it is unreachable in a loaded package — the import
    check above refuses a declared mode that is missing here — so it only ever
    answers for an integer that is not a mode at all, which `cite_twin.mode`
    has already refused by name before it asks.
    """
    return _COMMANDED.get(mode, _BOTH_SIDES)


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
