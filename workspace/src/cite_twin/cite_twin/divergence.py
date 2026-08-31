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

"""The divergence arithmetic, and the conjunction that decides whether to read it.

ADR-0050 decision 3, as code. The rule it turns on, in the record's words:

    A divergence sample is defined only when the two states being compared were
    produced by INDEPENDENT EVALUATION OF THE SAME COMMAND over the same
    interval. If either side's state was derived from the other side's state,
    the comparison measures the derivation.

**`valid` cannot be true today, and that is the intended behaviour rather than a
defect to work around.** Term 3 is each side's accumulated clock deficit over
the window, which ADR-0049 decision 1 requires be measured and bounded — and
nothing in this tree measures it, and that record deliberately leaves the bound
unset. A term with no instrument makes the conjunction false, so the gate is
arithmetic rather than a warning in prose. A monitor built to this and run today
publishes samples that are all invalid, each carrying the term that failed.

**NO NUMBER PRODUCED HERE IS A FIDELITY NUMBER.** `valid` does not mean "true of
reality"; it means the arithmetic was defined and its terms were measured in
this window. Whether a defined number is a fidelity number is a separate
predicate, answered by `far_side_physical` — and where both sides run the same
L0 model, the same generated description, the same controllers and the same
solver, what is being compared is a thing with itself. Such a plot is a test of
the instrument and must be labelled as one (P8, ADR-0041).

**Do not make `valid` true by weakening a term.** If the conjunction is
unsatisfiable in a way ADR-0050 did not anticipate, that is a finding to report,
not a threshold to adjust.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from cite_interfaces.msg import TwinMode

#: How far apart two operands' arrival instants may be and still be one sample,
#: in seconds of the WALL clock.
#:
#: The pairing key is wall clock and not either side's simulated clock, because
#: the two simulated clocks are independent and separate without bound
#: (ADR-0043, ADR-0049), and because in 2.B the far side's clock IS the wall
#: clock. It is stated here rather than derived, and that is a weakness: nothing
#: measured it, it is not a threshold any campaign registered, and the honest
#: reading is that it is a window wide enough that pairing is not the term that
#: fails. Term 3 is what fails, by construction, and it will keep failing after
#: this number is replaced by a measured one.
PAIRING_WINDOW_S = 0.100

#: How much accumulated clock deficit a side may carry over the window and still
#: support a readable comparison, in seconds.
#:
#: **`None`, and deliberately not a number.** ADR-0049 decision 2 refuses to set
#: it: the bound is a statement about what a divergence measurement can
#: tolerate, which is L5's question and unanswered, and naming a figure now
#: would be deciding what a campaign will find. `None` is therefore not a
#: missing value to be filled in by whoever needs a green sample — it is the
#: decision, and it makes term 3 false for every sample by construction.
DEFICIT_BOUND_S: float | None = None

#: The modes in which the rule above defines the comparison at all.
#:
#: `VALIDATED` and nothing else, which is ADR-0050 decision 3 applied mode by
#: mode and is deliberately not the list `DivergenceMetrics.msg` used to carry:
#:
#: * `SIM`, `REAL` — one side is idle, so there is no second evaluation.
#: * `SHADOW` — the virtual side's state is DERIVED from the physical side's, so
#:   the comparison measures the mirror and the follower's own tracking law,
#:   entangled, and not the model. ADR-0011's level table says the same thing:
#:   Shadow is L1 and "divergence measured" appears one row down at L2
#:   Validated, as the refinement that distinguishes them.
#: * `VIRTUAL_LEAD` — both sides do evaluate the same goal, so the RULE is
#:   satisfied, and the second operand does not exist: the mode is defined by
#:   there being no reverse flow. Uncomputable by the mode's own definition
#:   rather than undefined in principle.
#: * `CLOSED_LOOP` — not decided; the default rule governs.
MODES_THAT_DEFINE_THE_COMPARISON = frozenset({TwinMode.MODE_VALIDATED})

#: What a sample age or a clock deficit carries when the quantity was not
#: measured at all.
#:
#: Negative, because both quantities are non-negative by construction — an age
#: is now minus an arrival instant and a deficit is wall time minus simulated
#: time — so no measured value can collide with it. A zero would be a
#: measurement of zero, which is the strongest possible claim, reported for the
#: case where nothing was measured at all.
UNMEASURED = -1.0


@dataclass(frozen=True)
class Operand:
    """One side's state at the comparison instant, as it reached L5.

    `received_wall_s` is when this sample arrived AT L5, by L5's own host clock.
    That is deliberately not a transport latency: measuring one needs a clock
    the two sides share, and ADR-0043 refused to give them one. The difference
    between the two sides' ages is the pair's wall-clock skew, which is the
    quantity that separates L5's "mirroring lag treated as divergence" failure
    row from a model error.
    """

    positions: Mapping[str, float]
    received_wall_s: float
    model_version: str
    #: Wall time minus simulated time over the window, or `None` where nothing
    #: measured it — which is every side today (ADR-0049 decision 5's instrument
    #: does not exist).
    clock_deficit_s: float | None = None


@dataclass(frozen=True)
class Comparison:
    """The part of the sample that is arithmetic over two operands.

    Joint space only. The other four fields on `DivergenceMetrics` are not
    computed by this module and the node sets them to zero:

    * `tcp_position_error_m` and `tcp_orientation_error_rad` need a tool pose
      per side, which needs one TF buffer per side (ADR-0050 clause 1c —
      feeding both trees into one buffer produces a tree whose transforms
      silently come from either cell) and forward kinematics for each. Neither
      exists here.
    * `cycle_time_deviation_s` and `event_timing_deviation_s` need L4 line state
      from both sides, which L5 does not subscribe to yet.

    **Their zero is not distinguishable from the zeroing rule's zero today**,
    because `valid` is false for every sample and the rule zeroes all six
    anyway. That stops being true the moment term 3 gains an instrument, and it
    is named here so the gap is found then rather than discovered as a wrong
    number.
    """

    joint_error_rms_rad: float
    joint_error_max_rad: float
    #: The joints both operands reported, sorted. Empty means the two operands
    #: had no joint in common, which is a real state — a side that has not
    #: published yet, or two sides describing different robots — and is why the
    #: errors above are zero rather than an exception.
    joints: tuple[str, ...]

    @staticmethod
    def zeroed() -> Comparison:
        return Comparison(0.0, 0.0, ())


@dataclass(frozen=True)
class Conditions:
    """The five terms of ADR-0050 decision 3's conjunction, each named.

    Named rather than reduced to a boolean because the terms are how a reader
    learns WHICH conjunct failed, and because a term that is false for a reason
    nobody can see is a term somebody will delete.
    """

    #: Term 1. The mode in force defines the comparison at all.
    mode_defines_the_comparison: bool
    #: Term 2. Both operands were present and paired within the stated window,
    #: on the wall clock.
    operands_paired_in_window: bool
    #: Term 3. Both sides' clock deficit over the window was MEASURED and is
    #: within ADR-0049's bound. False whenever either was not measured or the
    #: bound is unset — which is always, today.
    clock_deficit_within_bound: bool
    #: Term 4. Both sides report the same `model_version`.
    model_versions_agree: bool
    #: Term 5. The two frames correspond.
    frames_correspond: bool

    @property
    def valid(self) -> bool:
        """Report the conjunction. All five terms, never four."""
        return (
            self.mode_defines_the_comparison
            and self.operands_paired_in_window
            and self.clock_deficit_within_bound
            and self.model_versions_agree
            and self.frames_correspond
        )

    def failed_terms(self) -> tuple[str, ...]:
        """Which conjuncts are false, in the record's order, for the log."""
        failures = {
            "mode_defines_the_comparison": self.mode_defines_the_comparison,
            "operands_paired_in_window": self.operands_paired_in_window,
            "clock_deficit_within_bound": self.clock_deficit_within_bound,
            "model_versions_agree": self.model_versions_agree,
            "frames_correspond": self.frames_correspond,
        }
        return tuple(name for name, held in failures.items() if not held)


def assess(
    mode: int,
    plant: Operand | None,
    counterpart: Operand | None,
    far_side_physical: bool,
    pairing_window_s: float = PAIRING_WINDOW_S,
    deficit_bound_s: float | None = DEFICIT_BOUND_S,
) -> Conditions:
    """Evaluate the five terms for one candidate sample.

    ``far_side_physical`` decides term 5 and nothing else here. In 2.A both
    sides are generated from one L0 model, so the frame correspondence is
    identity and the term is trivially met — and it stops being trivial in 2.B,
    where it is the registration transform, which does not exist and whose
    survey charter §8 puts in Phase 3. Every asset instance in L0 carries a
    `registration` block reading `unregistered` today.
    """
    paired = (
        plant is not None
        and counterpart is not None
        and abs(plant.received_wall_s - counterpart.received_wall_s) <= pairing_window_s
    )
    return Conditions(
        mode_defines_the_comparison=mode in MODES_THAT_DEFINE_THE_COMPARISON,
        operands_paired_in_window=paired,
        clock_deficit_within_bound=_deficit_within_bound(plant, counterpart, deficit_bound_s),
        model_versions_agree=(
            plant is not None
            and counterpart is not None
            and plant.model_version != ""
            and plant.model_version == counterpart.model_version
        ),
        frames_correspond=not far_side_physical,
    )


def _deficit_within_bound(
    plant: Operand | None, counterpart: Operand | None, bound_s: float | None
) -> bool:
    """Term 3, which is false today for two independent reasons.

    The bound is unset (ADR-0049 decision 2) and neither side's deficit is
    measured (that record's decision 5 instrument does not exist). Either alone
    is sufficient, and both are checked, so closing one of them does not
    silently turn the term true on the strength of the other.
    """
    if bound_s is None:
        return False
    for side in (plant, counterpart):
        if side is None or side.clock_deficit_s is None:
            return False
        if side.clock_deficit_s > bound_s:
            return False
    return True


def compare(plant: Operand | None, counterpart: Operand | None) -> Comparison:
    """Compare two operands in joint space, whatever the sample's validity.

    Computed rather than skipped when the conjunction fails, so that the
    arithmetic is exercised on every cycle and cannot rot behind a gate that is
    always shut. The caller applies the zeroing rule; this function does not
    know about it.

    Over the joints BOTH operands report. A joint one side has and the other
    does not is not an error of any size — it is two different robots, or one
    side that has not published everything yet — and averaging over a name the
    far side never mentioned would invent a number.
    """
    if plant is None or counterpart is None:
        return Comparison.zeroed()
    joints = tuple(sorted(set(plant.positions) & set(counterpart.positions)))
    if not joints:
        return Comparison.zeroed()
    errors = [abs(plant.positions[name] - counterpart.positions[name]) for name in joints]
    rms = math.sqrt(sum(error * error for error in errors) / len(errors))
    return Comparison(joint_error_rms_rad=rms, joint_error_max_rad=max(errors), joints=joints)
