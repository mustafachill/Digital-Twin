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

from cite_interfaces.msg import ResultCode, TwinMode

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

#: The modes whose ENTRY places physical actuation under an authority that was
#: not previously commanding it, whatever the far side turns out to be.
#:
#: `cross-cutting-safety.md` owns this list and the criterion behind it; this is
#: a mapping of two of its three rows onto constants, not a second list. Both
#: mean physical actuation whoever asks, which is why neither needs the far
#: side's backend to be resolved before it is judged
#: (`L5-twin-synchronization.md`, open questions).
#:
#: A fourth candidate is judged against the criterion in that document. It is
#: not added here by resemblance to these two.
COMMANDS_HARDWARE_ON_ENTRY = frozenset({TwinMode.MODE_REAL, TwinMode.MODE_CLOSED_LOOP})

#: The third row, which is the one that is NOT self-identifying from the
#: requested value. Entering it is dangerous exactly where the far side actuates
#: hardware, which is a per-(asset, side) fact and has to be resolved per asset
#: before the transition is decided.
COMMANDS_HARDWARE_AGAINST_A_REAL_FAR_SIDE = TwinMode.MODE_VIRTUAL_LEAD

#: The one far-side backend that cannot reach a physical machine.
#:
#: A third statement of the string `cite_tools.model.ids.SIMULATION_BACKEND`
#: owns and `cite_bringup.plan.SIMULATION_BACKEND` restates, for the same reason
#: that one exists: this is a different build unit that cannot import either.
#: As there, it does not DECIDE the value — every use below reads a backend out
#: of the generated plan and compares, so a plan naming something else is
#: treated as hardware rather than silently permitted. An allowlist and never a
#: denylist: a backend nobody anticipated is refused, because
#: `cross-cutting-safety.md` requires that a hardware path is never reachable by
#: omission.
SIMULATION_BACKEND = "sim"


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

    `far_side_backends` is keyed by asset id, and a value of `None` means the
    zone declares no far side for that asset at all. It comes from the plan's
    `counterpart_backend`, which a paired zone states for every asset — so
    `None` means "there is no such side" and never "the model left the key out"
    (ADR-0041 Decision 3).

    **What the plan does not carry, and what is therefore NOT refused here.**
    ADR-0050 decision 4 leaves open whether a `SHADOW`-only deployment ships a
    physics-free following side, and names the requirement that L5 be able to
    read the far side's shape without choosing the spelling. The generated plan
    carries a backend and nothing about a side's physics, so a mode that needs
    the far side to simulate dynamics cannot be refused on that ground today. It
    is a residual and not a check that was decided against.
    """

    far_side_backends: Mapping[str, str | None]

    def assets_in_scope(self, asset_id: str) -> tuple[str, ...]:
        """The assets a request naming ``asset_id`` decides for.

        Empty `asset_id` is facility-wide (`TwinMode.msg`), and a facility-wide
        request is emphatically **not** the per-asset question asked once:
        charter §8 puts one physical arm beside two simulated ones, so a mixed
        cell is the planned state, and two assets answering "simulated" is not
        an answer for the third (`cross-cutting-safety.md`).
        """
        if asset_id == "":
            return tuple(sorted(self.far_side_backends))
        if asset_id not in self.far_side_backends:
            raise ModeError(
                ResultCode.PRECONDITION_FAILED,
                f"no asset {asset_id!r} in this zone; it has "
                f"{', '.join(repr(name) for name in sorted(self.far_side_backends))}.",
            )
        return (asset_id,)

    def has_a_far_side(self, asset_id: str) -> bool:
        """Whether every asset the request decides for has a far side at all."""
        assets = self.assets_in_scope(asset_id)
        return bool(assets) and all(
            self.far_side_backends[asset] is not None for asset in assets
        )

    def physical_far_sides(self, asset_id: str) -> tuple[str, ...]:
        """The assets in scope whose far side actuates hardware, sorted.

        An allowlist: anything that is not :data:`SIMULATION_BACKEND` is
        hardware. A far side that does not exist is not hardware.
        """
        return tuple(
            asset
            for asset in self.assets_in_scope(asset_id)
            if (backend := self.far_side_backends[asset]) is not None
            and backend != SIMULATION_BACKEND
        )


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
        assets = self._deployment.assets_in_scope(asset_id)

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
                    asset
                    for asset in assets
                    if self._deployment.far_side_backends[asset] is None
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

        Evaluated for the mode being ENTERED, so a request for the mode already
        in force is not a transition and the caller above answers it before this
        value is used.
        """
        if mode == self._mode:
            return False
        if mode in COMMANDS_HARDWARE_ON_ENTRY:
            return True
        if mode == COMMANDS_HARDWARE_AGAINST_A_REAL_FAR_SIDE:
            return bool(self._deployment.physical_far_sides(asset_id))
        return False

    def _require_hardware_opt_in(self, mode: int, asset_id: str) -> None:
        try:
            self._hardware_opt_in()
        # Broad on purpose: the injected check owns its own refusal and its own
        # message, and a narrower clause here would be a second statement of
        # which exception type that check raises.
        except Exception as refusal:
            physical = self._deployment.physical_far_sides(asset_id)
            named = ", ".join(physical) if physical else "this zone"
            raise ModeError(
                ResultCode.SAFETY_BLOCKED,
                f"entering {MODE_NAMES[mode]} would place physical actuation under an "
                f"authority that was not commanding it ({named}), and the hardware "
                f"opt-in was not given: {refusal}",
            ) from refusal
