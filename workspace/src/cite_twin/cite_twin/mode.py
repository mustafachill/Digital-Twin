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

"""Who may change the twin's mode, and what a refusal says.

Kept apart from the node for the reason `cite_bringup.plan` is kept apart from
the launch file: a decision function that takes a request and returns a verdict
is testable without a ROS runtime, and every rule worth arguing about is in
here rather than in a callback.

WHAT THIS IS NOT. It is one refusal in one server. `cross-cutting-safety.md`'s
safety layer does not exist, and a transition this module permits is not thereby
supervised — what it buys is that a transition which places physical actuation
under a new authority cannot be taken without the deliberate opt-in, at the
moment it is taken rather than only at bring-up (P7).

THE TRANSITION IS ATOMIC, and that is a consequence of ADR-0050 decision 4
rather than a simplification. A mode never instantiates anything: it does not
start or stop a simulator, and L5 may not start processes at all (ADR-0047
clause 2). So there is nothing to wait for, nothing to poll and no duration to
guess (P4) — `TwinMode.transition_in_progress` is false in every message this
layer publishes, and `requested_mode` always equals `mode`. If a future mode
does need a staged transition, that field is where it goes, and the thing being
waited on has to be an event rather than a sleep.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cite_interfaces.msg import ResultCode, TwinMode
from cite_twin.routing import commanded_sides, COUNTERPART_SIDE, PLANT_SIDE

if TYPE_CHECKING:  # pragma: no cover - typing only
    from cite_bringup.plan import Plan

#: Every mode, under the name every document writes it by. Mapped rather than
#: formatted, for the reason `cite_facility.topology_server.STATION_TYPES` is: a
#: mode the message grows and this table does not know about is refused by name
#: at the boundary, rather than being reported as a number no reader can act on.
#:
#: The set is `TwinMode.msg`'s and is re-typed here only as a display name. What
#: each mode MEANS is that file's and `L5-twin-synchronization.md`'s.
MODE_NAMES: Mapping[int, str] = {
    TwinMode.MODE_SIM: "SIM",
    TwinMode.MODE_REAL: "REAL",
    TwinMode.MODE_SHADOW: "SHADOW",
    TwinMode.MODE_VALIDATED: "VALIDATED",
    TwinMode.MODE_CLOSED_LOOP: "CLOSED_LOOP",
    TwinMode.MODE_VIRTUAL_LEAD: "VIRTUAL_LEAD",
}

#: The mode a deployment is in before anyone asks for anything.
#:
#: `SIM` and never a parameter, an environment variable or a launch-argument
#: default. `TwinMode.msg` and `cross-cutting-safety.md` both say the same thing
#: in the same words: a system that can enter `REAL` because someone forgot an
#: argument is a system that will. It is also the only mode a deployment with no
#: far side can support, so the default is the one value that is always
#: supportable.
INITIAL_MODE = TwinMode.MODE_SIM

#: **THERE IS NO LIST OF GATED MODES IN THIS MODULE, AND THAT IS THE POINT.**
#:
#: There was one until 2026-08-31: `{REAL, CLOSED_LOOP}`, plus `VIRTUAL_LEAD`
#: against a non-simulated far side, which is `cross-cutting-safety.md`'s three
#: rows transcribed. **`VALIDATED` was not in it**, and `VALIDATED` dispatches
#: the operator's goal to both sides by byte-identical code to `VIRTUAL_LEAD`'s
#: — so on a 2.B plan `SetMode(VIRTUAL_LEAD)` was refused `SAFETY_BLOCKED`,
#: `SetMode(VALIDATED)` was accepted with no gate and no `force`, and a goal
#: then reached the physical arm. A transcribed list cannot notice that, and a
#: seventh mode would rediscover it. Adding `VALIDATED` to the list would be
#: exactly the resemblance reasoning the criterion was written to replace.
#:
#: What replaces it is the criterion itself, computed:
#:
#: > a transition belongs here when it **places physical actuation under an
#: > authority that was not previously commanding it**
#: > (`cross-cutting-safety.md`)
#:
#: read as two questions, both answered by data: *which sides does this mode
#: command* — `cite_twin.routing.commanded_sides`, the superset of the sides it
#: dispatches a goal to — and *is any of those sides, for any asset in scope,
#: something other than a simulation*, which the generated plan states. Nothing
#: about which modes are dangerous is written in this module, so `mode.py` and
#: `routing.py` cannot drift apart: a mode added to one is refused by the other
#: at import.
#:
#: **What that changes, stated so it is reviewed rather than discovered.**
#: Against a non-simulated far side the gate now also covers `VALIDATED` — the
#: hole — and `SHADOW`, which is the criterion applied where the list never
#: asked: `TwinMode.msg` says the physical side is commanded in `SHADOW`, so
#: entering it makes a physical machine the commanded side of this twin.
#: Against a wholly simulated deployment, `REAL` and `CLOSED_LOOP` are no longer
#: *reported* as commanding hardware — there is no hardware in such a deployment
#: for them to command, and the injected check is plan-scoped, so it never
#: refused them there in any case. **No refusal that used to happen stops
#: happening; two modes gain one.**

# A third restatement of the backend id `sim` used to live here, and
# `physical_sides_commanded` compared far-side backends against it. ADR-0054
# removed it: the id is a NAME, and that record's Context measures this gate
# reporting NO PHYSICAL SIDE COMMANDED, for every mode, on a zone whose every
# side loads the vendor's physical `ros2_control` component under that id. That
# is `cross-cutting-safety.md:124-146`'s own lesson reached by a different
# route - the shape was right and the datum was wrong, because a criterion
# applied to a name is still a name.
#
# What this module reads instead is the fact L0 declares per backend and the
# generated plan carries per (asset, side). The allowlist property the old
# comment claimed is what the boolean delivers structurally: the dangerous
# branch is the positive one, so nothing is permitted by having a name nobody
# anticipated.


class ModeError(Exception):
    """A mode transition was refused. Carries the code the caller gets back."""

    def __init__(self, code: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Deployment:
    """What L5 read about the far side at start-up, and nothing it read later.

    ADR-0050 decision 4 requires the far side's shape to be a fact L5 can read
    at start-up, so that `SetMode` can refuse a mode the running deployment
    cannot support rather than accepting it and producing an invalid metric
    forever. This is that fact, as much of it as the generated plan carries.

    `sides` is keyed by asset id and then by SIDE NAME, and its value is
    **three-valued on purpose**: `True` and `False` are what that side's backend
    declares about reaching a physical machine, and `None` means the zone
    declares no such side for that asset at all. It comes from the plan's
    `commands_physical_hardware` and `counterpart_commands_physical_hardware`,
    which a paired zone states for every asset — so `None` means "there is no
    such side" and never "the model left the key out" (ADR-0041 Decision 3).

    **COLLAPSING IT TO A BARE `bool` IS A SILENT SAFETY REGRESSION**, and it is
    the failure ADR-0054 decision 2 names by hand. `assets_without_a_far_side`
    tests `is None`, and that is what drives the `PRECONDITION_FAILED` refusal of
    a two-sided mode on a one-sided deployment. With a bare `bool`, every
    unpaired asset looks like it *has* a far side that is merely simulated, and
    that refusal stops firing — on the shipped single-sided model, which is every
    deployment this repository can generate today.

    **IT HOLDS THE DECLARED FACT AND NOT THE BACKEND ID** (ADR-0054). It used to
    hold the id and compare against the literal `sim`, which reports no physical
    side commanded on a zone whose every side loads the vendor's physical
    component under that name. The id is not carried alongside, because carrying
    the value the record just removed from the safety path is how a later reader
    concludes it still decides something.

    **Both sides and not only the far one.** `require_hardware_opt_in` reads
    both, for the reason its own docstring gives — a backend is selected per
    (asset, side) — and a gate that claims to apply the same check has to ask
    the same question of the same data. That the plant is always `sim` on a
    paired zone is a refusal in the L0 validator (ADR-0041 Decision 3) and not a
    fact this module may assume: assuming it is what a list does, and reading it
    costs one key.

    **What the plan does not carry, and what is therefore NOT refused here.**
    ADR-0050 decision 4 leaves open whether a `SHADOW`-only deployment ships a
    physics-free following side, and names the requirement that L5 be able to
    read the far side's shape without choosing the spelling. The generated plan
    carries a backend and nothing about a side's physics, so a mode that needs
    the far side to simulate dynamics cannot be refused on that ground today. It
    is a residual and not a check that was decided against.
    """

    sides: Mapping[str, Mapping[str, bool | None]]

    @staticmethod
    def paired(far_side_physical: Mapping[str, bool | None]) -> Deployment:
        """Build a zone whose plant is simulated, from what each far side declares.

        The shape of every paired zone this repository can generate — the L0
        validator refuses a paired zone whose plant commands physical hardware —
        and the one a test states most readably. A constructor and not the
        representation: nothing downstream stops asking per side.
        """
        return Deployment(
            {
                asset: {PLANT_SIDE: False, COUNTERPART_SIDE: physical}
                for asset, physical in far_side_physical.items()
            }
        )

    def declares_physical_hardware(self, asset: str, side: str) -> bool | None:
        """Return what ``side`` declares for ``asset``, or `None` for no such side.

        Total, and three-valued for the reason the class docstring gives. A
        caller deciding a safety question must ask for `is True` or `is None`
        explicitly and never by truthiness, because `None` and `False` are
        different answers to different questions.
        """
        return self.sides[asset].get(side)

    def assets_in_scope(self, asset_id: str) -> tuple[str, ...]:
        """Return the assets a request naming ``asset_id`` decides for.

        Empty `asset_id` is facility-wide (`TwinMode.msg`), and a facility-wide
        request is emphatically **not** the per-asset question asked once:
        charter §8 puts one physical arm beside two simulated ones, so a mixed
        cell is the planned state, and two assets answering "simulated" is not
        an answer for the third (`cross-cutting-safety.md`).
        """
        if asset_id == "":
            return tuple(sorted(self.sides))
        if asset_id not in self.sides:
            raise ModeError(
                ResultCode.PRECONDITION_FAILED,
                f"no asset {asset_id!r} in this zone; it has "
                f"{', '.join(repr(name) for name in sorted(self.sides))}.",
            )
        return (asset_id,)

    def has_a_far_side(self, asset_id: str) -> bool:
        """Whether every asset the request decides for has a far side at all."""
        assets = self.assets_in_scope(asset_id)
        return bool(assets) and all(
            self.declares_physical_hardware(asset, COUNTERPART_SIDE) is not None
            for asset in assets
        )

    def assets_without_a_far_side(self, asset_id: str) -> tuple[str, ...]:
        """Return the assets in scope for which this zone declares no counterpart."""
        return tuple(
            asset
            for asset in self.assets_in_scope(asset_id)
            if self.declares_physical_hardware(asset, COUNTERPART_SIDE) is None
        )

    def physical_sides_commanded(self, mode: int, asset_id: str) -> tuple[str, ...]:
        """Name every (asset, side) ``mode`` commands that is not a simulation.

        **The gate, as data.** Which sides a mode commands is
        `cite_twin.routing`'s; what each side loads is the generated plan's;
        this function does the intersection and knows nothing about which modes
        are dangerous.

        **The datum is the fact L0 declares, not the backend's name** (ADR-0054).
        It was the name, compared against the literal `sim`, and that returns the
        empty tuple for every mode on a cell whose every side loads the vendor's
        physical component under that id. An allowlist and never a denylist, and
        now structurally so: the dangerous branch is the positive one, so a side
        is hardware exactly when someone wrote `commands_physical_hardware: true`
        in L0 — there is no unanticipated name left to fall through. A side that
        does not exist commands nothing, which is `is True` and not truthiness.

        Named `(asset, side)` and not by asset alone, because that is the
        granularity at which a backend is selected, and because a refusal that
        cannot say *which side* of which asset is the physical one sends its
        reader to look at the wrong half of the cell.

        **THE BACKEND ID IS DELIBERATELY GONE FROM THIS STRING**, and it is named
        rather than allowed to disappear quietly. This returned
        `f"{asset} ({side} {backend!r})"` and that string is the `SAFETY_BLOCKED`
        diagnostic. Once the decision is made on the declaration, printing the id
        would be printing the value ADR-0054 removed from the safety path, and a
        reader would take it for the reason. The load-bearing half — which
        (asset, side) was refused for — is kept.
        """
        return tuple(
            f"{asset} ({side})"
            for asset in self.assets_in_scope(asset_id)
            for side in commanded_sides(mode)
            if self.declares_physical_hardware(asset, side) is True
        )


def deployment_from_plan(plan: Plan) -> Deployment:
    """Read what L5 knows about both sides out of the generated bring-up plan.

    **A free function, and its being one is a requirement rather than a style
    choice** (ADR-0054, clause 8). This map used to be built inline in
    `TwinBoundary.__init__`, which means the failure it can produce is an
    exception raised *during* construction — and no test that needs a working
    `__init__` can reach that. Built here, the whole of it is assertable on the
    shipped single-sided plan without a node, a graph or a cell.

    **It asks the plan's TOTAL accessor and never the refusing one.** The shipped
    zone declares `twin: {sides: single}`, so no controller manager states a
    counterpart, and `commands_physical_hardware_on` refuses an undeclared side
    with `SideNotDeclaredError`. Calling that here would raise on the model this
    repository actually ships. `commands_physical_hardware_on_or_none` returns
    the `None` `Deployment` needs, with the same meaning `Deployment` gives it,
    so the distinction survives the crossing instead of being rebuilt from an
    exception at this end.
    """
    return Deployment(
        {
            manager.asset: {
                side: manager.commands_physical_hardware_on_or_none(side)
                for side in (PLANT_SIDE, COUNTERPART_SIDE)
            }
            for manager in plan.controller_managers
        }
    )


def far_side_is_physical(declared: bool | None) -> bool:
    """Whether the far side is a physical machine, for ADR-0050's validity terms.

    One line, and a named one, for two reasons. It is the last place in this
    package that turns the three-valued declaration into the two-valued answer a
    condition wants, so the direction of that collapse is written down once
    instead of being spelled at a call site inside a publisher callback — and
    `divergence.assess` reads it, which is a P8 concern rather than a motion
    path. And it is what makes the derivation assertable at all: it was a local
    inside `TwinBoundary._sample`, so migrating `Deployment` fully while leaving
    `_sample` deciding on a backend's name would have passed every other
    assertion (ADR-0054, clause 8).

    **`None` is not physical**, because `None` means there is no far side, and a
    side that does not exist is not a machine. Written `is True` rather than as a
    truth test so that the two false answers stay one answer here and nowhere
    else.
    """
    return declared is True


@dataclass(frozen=True)
class Verdict:
    """What one `SetMode` call did, in the fields the response carries."""

    accepted: bool
    mode: int
    code: int
    detail: str
    #: True when this transition placed physical actuation under an authority
    #: that was not previously commanding it — computed BEFORE `force` is looked
    #: at anywhere, which is how `force` is structurally unable to skip the
    #: check the flag's own comment forbids it from skipping.
    commands_hardware: bool


class ModeAuthority:
    """The mode in force, and the only thing permitted to change it.

    The hardware check arrives as a callable rather than being written here.
    `SetMode.srv`'s header commits this server to applying **the same** check
    bring-up applies, and the same check means the same function —
    `cite_bringup.plan.require_hardware_opt_in`, which raises. Injecting it
    keeps this module free of a dependency on the bring-up plan, and it lets the
    tests drive both answers without touching the process environment.
    """

    def __init__(
        self,
        deployment: Deployment,
        hardware_opt_in: Callable[[], None],
        initial_mode: int = INITIAL_MODE,
    ) -> None:
        self._deployment = deployment
        self._hardware_opt_in = hardware_opt_in
        self._mode = initial_mode
        self._reason = "the mode a deployment starts in; never reached by a default"

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def reason(self) -> str:
        """Why the current mode was entered, for the record."""
        return self._reason

    def request(self, mode: int, asset_id: str, reason: str, force: bool) -> Verdict:
        """Decide one `SetMode` call and, if it is accepted, take the mode.

        The order of the checks is the decision. The hardware gate is evaluated
        after the cheap refusals so that a malformed request is answered as a
        malformed request, and before anything `force` can reach.
        """
        try:
            return self._decide(mode, asset_id, reason, force)
        except ModeError as refusal:
            return Verdict(
                accepted=False,
                mode=self._mode,
                code=refusal.code,
                detail=refusal.detail,
                commands_hardware=False,
            )

    def _decide(self, mode: int, asset_id: str, reason: str, force: bool) -> Verdict:
        if mode not in MODE_NAMES:
            raise ModeError(
                ResultCode.PRECONDITION_FAILED,
                f"{mode} is not one of TwinMode.MODE_* "
                f"({', '.join(f'{name}={value}' for value, name in sorted(MODE_NAMES.items()))}).",
            )
        if reason.strip() == "":
            raise ModeError(
                ResultCode.PRECONDITION_FAILED,
                "SetMode.reason is required, so that every transition has a why on the "
                "record. A transition nobody has to justify is one nobody reviews.",
            )

        # Asked before anything else looks at the scope, so that an unknown
        # asset is reported as an unknown asset rather than as a mode refusal.
        # The result is discarded: what is wanted is the refusal it raises.
        self._deployment.assets_in_scope(asset_id)

        commands_hardware = self._commands_hardware(mode, asset_id)

        if mode == self._mode:
            # Not a transition: nothing enters an authority it was not already
            # under, so there is nothing for the gate above to guard. The reason
            # is still recorded, because a re-assertion is a decision too.
            self._reason = reason
            return Verdict(
                accepted=True,
                mode=self._mode,
                code=ResultCode.SUCCESS,
                detail=f"already in {MODE_NAMES[mode]}",
                commands_hardware=False,
            )

        if mode != TwinMode.MODE_SIM and not self._deployment.has_a_far_side(asset_id):
            # A non-safety precondition, so `force` may skip it: every mode but
            # SIM is a statement about two sides, and a deployment with one side
            # cannot support one. Skippable because "what this deployment is"
            # is a judgement about the running system rather than a safety
            # property — and because a forced mode against a missing far side
            # produces invalid divergence samples, which is exactly what the
            # monitor is built to report rather than hide.
            if not force:
                without = ", ".join(
                    self._deployment.assets_without_a_far_side(asset_id)
                )
                raise ModeError(
                    ResultCode.PRECONDITION_FAILED,
                    f"{MODE_NAMES[mode]} is a statement about two sides and this "
                    f"deployment declares no far side for {without}. Whether a zone "
                    "runs as a pair is an L0 fact - set `twin: {sides: pair}` on the "
                    "zone and regenerate (ADR-0041).",
                )

        if commands_hardware:
            # NEVER behind `force`. SetMode.srv: "Never skips a safety check - no
            # value of this field can do that."
            self._require_hardware_opt_in(mode, asset_id)

        previous = self._mode
        self._mode = mode
        self._reason = reason
        return Verdict(
            accepted=True,
            mode=mode,
            code=ResultCode.SUCCESS,
            detail=f"{MODE_NAMES[previous]} -> {MODE_NAMES[mode]}",
            commands_hardware=commands_hardware,
        )

    def _commands_hardware(self, mode: int, asset_id: str) -> bool:
        """Whether entering ``mode`` places physical actuation under a new authority.

        The criterion, computed — see the block comment where the list used to
        be. Evaluated for the mode being ENTERED, so a request for the mode
        already in force is not a transition and the caller above answers it
        before this value is used.
        """
        if mode == self._mode:
            return False
        return bool(self._deployment.physical_sides_commanded(mode, asset_id))

    def _require_hardware_opt_in(self, mode: int, asset_id: str) -> None:
        try:
            self._hardware_opt_in()
        # Broad on purpose: the injected check owns its own refusal and its own
        # message, and a narrower clause here would be a second statement of
        # which exception type that check raises.
        except Exception as refusal:
            named = ", ".join(
                self._deployment.physical_sides_commanded(mode, asset_id)
            )
            raise ModeError(
                ResultCode.SAFETY_BLOCKED,
                f"entering {MODE_NAMES[mode]} would place physical actuation under an "
                f"authority that was not commanding it ({named}), and the hardware "
                f"opt-in was not given: {refusal}",
            ) from refusal
