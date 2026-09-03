#!/usr/bin/env python3
"""`criteria.md` section 7's decision rules, applied to `raw/`.

DERIVED IN SHAPE FROM
`docs/measurements/2026-09-02-scenario-ceilings/harness/analyse.py`, copied at commit
`98fbbfc`, which took the shape from the 2026-09-02 option-F campaign's `analyse.py` at
`e559264`: **one function per registered threshold, the rule prints even when it does not
fire, and a `DEVIATIONS` tuple at module top printed on every run**. Both directories are
FROZEN (`docs/measurements/README.md`) and nothing in either is edited from here. Every
rule below is this campaign's own.

WRITTEN BEFORE THE FIRST TRIAL, which is the whole point. A rule implemented after the data
has been seen is a rule chosen by the data, and `criteria.md` V9 forbids moving one
afterwards: a threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong,
as a numbered deviation in `ANALYSIS.md`, against data already collected.

EVERY RULE PRINTS WHETHER OR NOT IT FIRES. A rule that only speaks when it triggers is a
rule nobody can audit, and a reader cannot tell it from a rule that was never implemented.

IT READS THE VALIDITY FLAGS OFF THE RECORD AND RE-DERIVES NONE OF THEM. V1's flag is
computed where the block was taken, from two `git` readings taken at both ends of every
cycle; re-deriving it here would ask a tree that has since moved. The window, the floor,
the declared part interval and the travel travel on every record for the same reason.

IT COMPUTES NO GRIPPER ARITHMETIC. Not one line of the predicate, the linkage or the window
is restated here. `arithmetic.py` is not imported, `predicate_eval` is not started, and
every width, edge and floor is read off a record that carries it.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, sets no band, proposes
no value and chooses nothing (`criteria.md` section 0). It prints what the registered rules
say about the trials that ran, and stops. `ANALYSIS.md` is written from that print, later,
by someone else.

**THE PRINT IS THE PRODUCT AND IT IS LONG.** Redirect it to a file; do not pipe it through
`head`. The 2026-09-02 campaign's operator piped a 1034-line report through `head`, saw 143
lines, and `tee` still reported exit 0.

    python3 docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import common

#: `criteria.md` V9 -- the deviations known BEFORE the first campaign trial ran. A deviation
#: is where an interpretation had to CHANGE or had to be made concrete, applied literally to
#: data already collected. **None of these moves a threshold.** They are printed at the top
#: of every run so that the write-up carries them and cannot quietly drop one.
DEVIATIONS: tuple[tuple[str, str], ...] = (
    (
        "1",
        "`criteria.md` section 6 uses the word `block` for two different things -- the "
        "named blocks of its design table (LO-C, HI-C, ...) and the repeat CYCLES inside "
        "them, of which it says `each cycle is a block, and the block index travels on "
        "every record`. V1, V7 and I9 are stated per block. The harness takes I8 and I9 at "
        "both ends of every CYCLE, which is the finer of the two readings and therefore "
        "the STRICTER conjunction: a cycle-level V1 fires on an edit a named-block-level "
        "one would also have caught, and on nothing it would not. Both indices travel on "
        "every record (`cycle` and `block`), so a reader can re-group either way. No "
        "threshold moved."
    ),
    (
        "2",
        "Rule B's V7 clause reads `no reading of that stop's block exceeded 4.0`. Under "
        "deviation 1 that is evaluated over the CYCLE's two readings, which is where the "
        "flag on the record comes from. The second half of the clause -- `or the bracket it "
        "contributes to is identical with and without the flagged trials` -- is computed "
        "literally, by building the bracket twice."
    ),
    (
        "3",
        "**Rule B does not say what happens when MORE THAN ONE adjacent fine-grid pair "
        "carries opposite verdicts of the predicate under refinement.** Rule U covers that "
        "case on the COARSE grid and rule N covers the case of NO such pair; the fine grid "
        "with two changes is registered nowhere. Applied literally, rule B would be "
        "satisfied by each pair and no registered rule chooses between them. This analyser "
        "therefore REPORTS every such pair and declines to claim a bracket, printing the "
        "edge as NOT BRACKETED with the reason stated. It is recorded here, before any "
        "trial, as a hole in the rules layer rather than discovered afterwards as a "
        "judgement."
    ),
    (
        "4",
        "I3 is registered as `the last arm_1_drive_joint sample on /joint_states at or "
        "before the result arrives`. The harness reads the last sample its own executor "
        "held at the instant the result future completed. That executor is the one spinning "
        "the subscription, so the sample is the last DELIVERED at or before the result; a "
        "sample published before the result and delivered after it would not be seen. The "
        "joint is resting on a hard stop in arms LO and HI, so the two readings cannot "
        "differ there -- but the implementation is stated rather than left to be assumed, "
        "and V4 is what would notice if it did."
    ),
)

#: `criteria.md` rule G, printed beside every wide-edge figure this file produces. Quoted
#: rather than paraphrased, because the record requires `ANALYSIS.md` to state it there.
RULE_G = (
    "RULE G -- flip_F_lo and flip_F_hi are properties of THE SHIPPED PREDICATE AS "
    "DELIVERED and of nothing else. They are not properties of the cell: a synthetic stop "
    "puts the drive joint wherever the description says, and a part, a jam or a fouled "
    "finger does not. THIS RIG CAN REACH THE WIDE EDGE PRECISELY BECAUSE IT GRASPS "
    "NOTHING. flip_F_hi is not evidence that stall_band_wide_m is well sized, that any "
    "stall on a part reaches the wide edge, or that the wide edge has been exercised in "
    "the sense ADR-0052 section A.9.5 means. The 2026-09-02 campaign's rule W FIRED on "
    "exactly that question and STANDS UNCHANGED after this campaign, whatever flip_F_hi "
    "reads. The word `validated` may not be used about either band value."
)

#: `criteria.md` rule W, in the words that record requires and no others.
RULE_W = (
    "rule W is not applicable here: this rig produces no grasp, so the population it "
    "quantifies over is empty"
)


def say(name: str, fired: bool | None, text: str) -> None:
    """One rule, printed whether or not it fired.

    `None` is a third state and is not `False`: it means the rule could not be evaluated
    over the trials that ran, which is a different sentence from `it was evaluated and was
    silent`. Reading one as the other is what V14 exists to prevent one level down.
    """
    mark = {True: "FIRED    ", False: "did not fire", None: "NOT EVALUABLE"}[fired]
    print(f"  [{mark}] {name}: {text}")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_blocks(raw: Path) -> dict[str, list[dict]]:
    """Every block's trials, EXCLUDING `raw/shakedown/`.

    The shakedown is not data (`criteria.md` section 10): it is excluded from every figure
    in section 7 and may not be used to set or adjust any threshold. **The exclusion is
    here, in code, rather than in a sentence somebody has to remember**: this lists
    `raw/*_trials.json` at the TOP LEVEL only, so a recursive glob cannot sweep it in.
    """
    blocks: dict[str, list[dict]] = {}
    for path in sorted(raw.glob("*_trials.json")):
        label = path.name[: -len("_trials.json")]
        rows = json.loads(path.read_text())
        if rows:
            blocks[label] = rows
    return blocks


def _stop_key(row: dict) -> float | None:
    return row.get("w_stop_mm")


def _defined(value):
    return value is not None


# ---------------------------------------------------------------------------
# Admission -- V1, V2, V13, and the three trial-level exclusions
# ---------------------------------------------------------------------------
def admit(blocks: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict]:
    """The block rules and the trial rules, in that order, each printed either way."""
    print("\n=== Admission: V1, V2, V13, V4, V5, V14 (criteria.md section 10) ===")
    report: dict = {"discarded_blocks": {}, "excluded": {}, "unflagged": []}

    kept_blocks: dict[str, list[dict]] = {}
    for label, rows in blocks.items():
        missing_flag = [row["trial"] for row in rows if "v1_clean" not in row]
        dirty = [row["trial"] for row in rows if row.get("v1_clean") is False]
        disagreed = [row["trial"] for row in rows
                     if (row.get("v1") or {}).get("disagreed_mid_block")]
        v2_bad = [row["trial"] for row in rows if row.get("v2_ok") is False]
        v2_missing = [row["trial"] for row in rows if row.get("v2_ok") is None]
        v13_bad = [row["trial"] for row in rows if row.get("v13_ok") is False]
        reasons = []
        if missing_flag:
            reasons.append(f"V1 flag absent on trial(s) {missing_flag}")
        if dirty:
            reasons.append(f"V1 not clean on trial(s) {dirty}")
        if v2_bad:
            reasons.append(f"V2 disagreed on trial(s) {v2_bad}")
        if v13_bad:
            reasons.append(f"V13 found a backend that is not production on {v13_bad}")
        if reasons:
            report["discarded_blocks"][label] = reasons
            say(f"V1/V2/V13 on block {label}", True,
                "block DISCARDED and reported -- " + "; ".join(reasons))
            continue
        say(f"V1/V2/V13 on block {label}", False,
            f"{len(rows)} trial(s): V1 clean at both ends of every cycle, V2 read "
            f"{common.HULL_COLLISION_REFERENCES_EXPECTED} hull collision reference(s) off "
            f"the running description, V13 found the production backend before every "
            f"substitution"
            + (f"; V2 UNREAD on trial(s) {v2_missing}" if v2_missing else "")
            + (f"; V1's two readings DISAGREED on {disagreed}" if disagreed else ""))
        kept_blocks[label] = rows

    excluded: dict[str, list[tuple[str, int, str]]] = {
        "V4": [], "V5": [], "V14": [], "V14_loss": [], "V14_disagreement": [],
        "failed": []}
    kept: dict[str, list[dict]] = {}
    for label, rows in kept_blocks.items():
        surviving = []
        for row in rows:
            if not row.get("ok"):
                excluded["failed"].append((label, row["trial"], row.get("error", "")))
                continue
            if row.get("v14_ok") is not True:
                # V14 registers TWO different exclusions and they are counted apart. A
                # trial with no I2 line for its grasp is an INSTRUMENT LOSS -- absent is
                # not `false`. A trial whose I4 disagrees with I2 or with I1 is a
                # DISAGREEMENT: the instruments spoke and did not agree, which is a
                # different sentence. Reporting them as one number would say a line was
                # never read when in fact two readings conflicted.
                kind = "V14_loss" if row.get("v14_instrument_loss") else "V14_disagreement"
                excluded.setdefault(kind, []).append(
                    (label, row["trial"], row.get("v14_reason", "")))
                excluded["V14"].append(
                    (label, row["trial"], row.get("v14_reason", "")))
                continue
            if row.get("v4_ok") is False:
                excluded["V4"].append(
                    (label, row["trial"], f"delta {row.get('v4_delta_m')} m"))
                continue
            if row.get("arm") in ("LO", "HI", "INV") and row.get("v5_valid") is not True:
                excluded["V5"].append(
                    (label, row["trial"],
                     f"i5={row.get('i5_stop_announced')} "
                     f"rests={row.get('i7_rests_at_stop')} "
                     f"i6_refused={row.get('i6_start_refused')}"))
                continue
            surviving.append(row)
        if surviving:
            kept[label] = surviving

    say("V14 (instrument loss) -- no I2 report line was read for the grasp",
        bool(excluded["V14_loss"]),
        f"{len(excluded['V14_loss'])} trial(s) excluded, counted separately from V4's and "
        f"V5's and NEVER recorded as a measured false: {excluded['V14_loss'] or 'none'}")
    say("V14 (disagreement) -- I4 disagrees with I2 or with I1",
        bool(excluded["V14_disagreement"]),
        f"{len(excluded['V14_disagreement'])} trial(s) excluded: "
        f"{excluded['V14_disagreement'] or 'none'}. **Arm CTL is expected here on both "
        f"V14 and V4**: it declares no stop, so the joint is NOT at rest, I3 samples it "
        f"later than I1 and I4's second command moves it further. CTL contributes to no "
        f"bracket, so excluding it removes nothing -- section 7.4's report is printed "
        f"below from the COLLECTED trials.")
    say("V4 -- the two width instruments agree to "
        f"{common.V4_TOLERANCE_M * 1000.0:.3f} mm", bool(excluded["V4"]),
        f"{len(excluded['V4'])} trial(s) excluded: {excluded['V4'] or 'none'}")
    say("V5 -- the stop engaged and the fixture did not manufacture it",
        bool(excluded["V5"]),
        f"{len(excluded['V5'])} trial(s) excluded: {excluded['V5'] or 'none'}")
    say("Trials that did not complete", bool(excluded["failed"]),
        f"{len(excluded['failed'])} recorded failure(s): {excluded['failed'] or 'none'}")
    report["excluded"] = excluded
    return kept, report


def rule_v7(kept: dict[str, list[dict]]) -> set[int]:
    """V7 -- the load is recorded, and a loud host is REPORTED rather than excluded."""
    print("\n=== V7 -- the load (criteria.md section 9 and V7) ===")
    flagged = {id(row) for rows in kept.values() for row in rows if row.get("v7_flagged")}
    readings = [
        (label, row["trial"], (row.get("i9") or {}).get("start", {}).get("load_1m"),
         (row.get("i9") or {}).get("end", {}).get("load_1m"))
        for label, rows in kept.items() for row in rows
    ]
    highest = max(
        (value for _, _, start, end in readings for value in (start, end)
         if isinstance(value, (int, float))),
        default=None)
    say("V7 -- any load reading above "
        f"{common.V7_LOAD_THRESHOLD}", bool(flagged),
        f"{len(flagged)} of {len(readings)} kept trial(s) flagged; highest one-minute "
        f"reading seen {highest}. NO BLOCK IS DISCARDED FOR LOAD -- a load threshold "
        f"chosen after seeing the data is a threshold chosen by the data. Every bracket a "
        f"flagged trial contributes to is reported with and without it below.")
    return flagged


# ---------------------------------------------------------------------------
# The per-stop tables -- section 7.1's reporting requirement
# ---------------------------------------------------------------------------
def per_stop(rows: list[dict]) -> dict[float | None, list[dict]]:
    grouped: dict[float | None, list[dict]] = {}
    for row in rows:
        grouped.setdefault(_stop_key(row), []).append(row)
    return dict(sorted(grouped.items(), key=lambda item: (item[0] is None, item[0])))


def stop_verdict(trials: list[dict], predicate: str) -> bool | None:
    """One stop's verdict in one predicate, or `None` if the repeats disagree or are absent."""
    values = {row.get(predicate) for row in trials}
    values.discard(None)
    if len(values) != 1:
        return None
    return next(iter(values))


def width_spread_m(trials: list[dict]) -> float | None:
    widths = [row["i1_reached_width_m"] for row in trials
              if row.get("i1_reached_width_m") is not None]
    if len(widths) < 1:
        return None
    return max(widths) - min(widths)


def print_stop_table(label: str, rows: list[dict]) -> None:
    """Section 7.1: report, per stop, everything the gate's own phrasing asks for."""
    print(f"\n--- block {label}: per-stop table (criteria.md section 7.1) ---")
    print("  Every field is LABELLED rather than columnar: the number of repeats varies "
          "per block, so a fixed column would misalign and be read wrong.")
    for stop, trials in per_stop(rows).items():
        widths = ", ".join(
            "-" if row.get("i1_reached_width_m") is None
            else f"{row['i1_reached_width_m']:.9f}" for row in trials)
        rest = ", ".join(
            "-" if row.get("i7_rest_error_m") is None
            else f"{row['i7_rest_error_m'] * 1000.0:+.6f}" for row in trials)
        name = "none" if stop is None else f"{stop:.2f}"
        sets = " ".join(
            f"{key}={sorted({str(row.get(field)) for row in trials})}"
            for key, field in (
                ("stalled", "stalled"), ("reached_goal", "reached_goal"),
                ("holding_F", "holding_F"), ("holding_S", "holding_S"),
                ("I5", "i5_stop_announced"), ("I6", "i6_start_refused")))
        print(f"    w_stop={name} mm  n={len(trials)}  w_cmd={trials[0].get('w_cmd_m')} m  "
              f"cycles={sorted({row.get('cycle') for row in trials})}")
        print(f"      w_reached(I1)=[{widths}] m   rest_error(I7)=[{rest}] mm")
        print(f"      {sets}")


# ---------------------------------------------------------------------------
# Rule R, rule U, rule B, rule N
# ---------------------------------------------------------------------------
def rule_r(label: str, rows: list[dict], predicate: str) -> dict[float | None, str]:
    """Rule R -- resolution, GENERIC in the predicate under refinement.

    If the repeats at a stop disagree in that predicate, or if `w_reached` varies within a
    stop by more than the rest tolerance, that stop is INDETERMINATE; a bracket with an
    indeterminate endpoint is UNRESOLVED at 0.05 mm and rule N applies to that edge.
    """
    states: dict[float | None, str] = {}
    fired = False
    details = []
    for stop, trials in per_stop(rows).items():
        verdict = stop_verdict(trials, predicate)
        spread = width_spread_m(trials)
        reasons = []
        if verdict is None:
            reasons.append(f"the repeats disagree in {predicate} or it is absent")
        if spread is not None and spread > common.REST_TOLERANCE_M:
            reasons.append(f"w_reached spread {spread * 1000.0:.6f} mm exceeds "
                           f"{common.REST_TOLERANCE_M * 1000.0:.3f} mm")
        if reasons:
            states[stop] = "INDETERMINATE"
            fired = True
            details.append(f"{stop}: " + "; ".join(reasons))
        else:
            states[stop] = "DETERMINATE"
    say(f"Rule R on block {label} ({predicate})", fired,
        ("indeterminate stop(s): " + "; ".join(details)) if fired else
        f"every stop's repeats agree in {predicate} and every within-stop w_reached spread "
        f"is at or below {common.REST_TOLERANCE_M * 1000.0:.3f} mm")
    return states


def rule_r_mis(label: str, rows: list[dict]) -> None:
    """Rule R's second sentence, on the MIS rather than on the rest tolerance.

    *For any metric whose within-stop spread exceeds that metric's MIS, a non-detection is
    INCONCLUSIVE for that metric -- never "no difference".* The metric here is `w_reached`
    and its MIS is section 7.0's 0.100 mm. **A bracket is not an MIS**, which is why this is
    a separate print from the one above and not a second use of the same number.
    """
    worst = None
    for stop, trials in per_stop(rows).items():
        spread = width_spread_m(trials)
        if spread is not None and (worst is None or spread > worst[1]):
            worst = (stop, spread)
    if worst is None:
        say(f"Rule R (MIS clause) on block {label}", None,
            "no w_reached readings survived to compare")
        return
    say(f"Rule R (MIS clause) on block {label}", worst[1] > common.MIS_WIDTH_M,
        f"largest within-stop w_reached spread {worst[1] * 1000.0:.6f} mm at stop "
        f"{worst[0]}, against the {common.MIS_WIDTH_M * 1000.0:.3f} mm MIS. A "
        f"non-detection under a spread above the MIS is INCONCLUSIVE for that metric and "
        f"never 'no difference'.")


def transitions(rows: list[dict], predicate: str) -> list[tuple[float, float]]:
    """Adjacent stops carrying opposite verdicts, in stop order."""
    grouped = per_stop(rows)
    ordered = [(stop, stop_verdict(trials, predicate))
               for stop, trials in grouped.items() if stop is not None]
    found = []
    for (low, low_verdict), (high, high_verdict) in zip(ordered, ordered[1:]):
        if low_verdict is None or high_verdict is None:
            continue
        if low_verdict != high_verdict:
            found.append((low, high))
    return found


def rule_u(label: str, rows: list[dict], predicate: str) -> bool:
    """Rule U -- one flip, or none claimed, GENERIC in the predicate under refinement.

    If an arm's coarse grid shows MORE THAN ONE change in the predicate under refinement,
    every change is reported, no refinement is run on any of them, and that edge is NOT
    BRACKETED under rule N. Returns whether the coarse grid showed EXACTLY ONE change,
    which is rule B's third conjunct.
    """
    changes = transitions(rows, predicate)
    undefined = [stop for stop, trials in per_stop(rows).items()
                 if stop is not None and stop_verdict(trials, predicate) is None]
    fired = len(changes) != 1
    say(f"Rule U on coarse block {label} ({predicate})", fired,
        f"{len(changes)} change(s) of {predicate} across the coarse grid: {changes or 'none'}"
        + (f"; stop(s) with no defined verdict: {undefined}" if undefined else "")
        + ("  -- MORE THAN ONE change, so every change is reported, NO refinement may be "
           "run on any of them, and that edge is NOT BRACKETED under rule N. A window with "
           "two flips on one side is a finding about the predicate or the rig, not a "
           "choice of which flip to refine." if len(changes) > 1 else "")
        + ("  -- NO change at all across the coarse grid." if not changes else ""))
    return len(changes) == 1


def bracket_over(rows: list[dict], predicate: str) -> list[tuple[float, float]]:
    """Rule B's raw candidates: adjacent FINE-grid stops carrying opposite verdicts."""
    found = []
    for low, high in transitions(rows, predicate):
        if abs((high - low) - common.FINE_STEP_MM) < 1e-9:
            found.append((low, high))
    return found


def rule_b(name: str, label: str, rows: list[dict], predicate: str,
           coarse_single_change: bool | None, flagged: set[int]) -> dict:
    """Rule B and rule N -- BRACKETED or NOT BRACKETED, with every conjunct printed.

    An edge is BRACKETED when two adjacent fine-grid stops 0.05 mm apart carry opposite
    verdicts of the predicate under refinement, and: every repeat at each of those two
    stops agrees with its stop's verdict; both stops pass V3, V4, V5, V7 and V14; and the
    coarse grid showed exactly one change of that same predicate in that arm (rule U).
    """
    print(f"\n--- {name}: rule B over block {label}, refining {predicate} ---")
    candidates = bracket_over(rows, predicate)
    say(f"{name}: an adjacent fine-grid pair with opposite verdicts",
        bool(candidates),
        f"{len(candidates)} candidate pair(s): {candidates or 'none'}")

    if not candidates:
        say(f"Rule N on {name}", True,
            f"NOT BRACKETED at {common.BRACKET_STEP_MM} mm, over these stops, at n = "
            f"{len(rows)}, on this rig. The campaign's silence here MAY NOT be read as "
            f"agreement with criteria.md section 2.2's arithmetic, as a validation of "
            f"either band value, or as evidence that the edge is where the declaration "
            f"says. ADR-0052 section A.10 item 2's second bullet is then STILL UNMET and "
            f"the write-up must say so in those words.")
        return {"verdict": "NOT BRACKETED", "interval": None, "reason": "rule N"}
    say(f"Rule N on {name}", False,
        "at least one adjacent fine-grid pair carries opposite verdicts, so rule N's "
        "refusal does not apply to this edge")

    if len(candidates) > 1:
        # DEVIATION 3, registered above and before any trial.
        say(f"{name}: more than one candidate pair", True,
            f"{candidates}. criteria.md registers NO rule that chooses between them "
            f"(deviation 3), so no bracket is claimed and the edge is reported NOT "
            f"BRACKETED with the pairs listed. This is a finding about the predicate or "
            f"the rig, not a choice.")
        return {"verdict": "NOT BRACKETED", "interval": None,
                "reason": "more than one candidate pair; deviation 3"}

    low, high = candidates[0]
    grouped = per_stop(rows)
    conjuncts: dict[str, bool | None] = {}
    for stop in (low, high):
        trials = grouped[stop]
        conjuncts[f"{stop}: repeats unanimous"] = stop_verdict(trials, predicate) is not None
        conjuncts[f"{stop}: V3"] = all(row.get("v3_ok") is True for row in trials)
        conjuncts[f"{stop}: V4"] = all(row.get("v4_ok") is True for row in trials)
        conjuncts[f"{stop}: V5"] = all(
            row.get("v5_valid") is True for row in trials) if trials[0].get("arm") in (
            "LO", "HI", "INV") else None
        conjuncts[f"{stop}: V14"] = all(row.get("v14_ok") is True for row in trials)

    # V7's clause, computed literally: either no reading of the stop's cycle exceeded the
    # threshold, or the bracket is identical with and without the flagged trials.
    any_flagged = any(id(row) in flagged for stop in (low, high) for row in grouped[stop])
    if not any_flagged:
        conjuncts["V7 (no flagged reading)"] = True
        v7_note = "no reading of either stop's cycle exceeded the threshold"
    else:
        unflagged_rows = [row for row in rows if id(row) not in flagged]
        without = bracket_over(unflagged_rows, predicate)
        conjuncts["V7 (bracket identical without flagged trials)"] = (
            without == candidates)
        v7_note = (f"flagged trials present; the bracket with them is {candidates} and "
                   f"without them is {without or 'none'}")
    say(f"{name}: V7's clause", any_flagged, v7_note)

    conjuncts["rule U (exactly one coarse change)"] = coarse_single_change
    for conjunct, value in conjuncts.items():
        say(f"{name}: conjunct {conjunct}", value is not True,
            {True: "satisfied", False: "NOT satisfied", None: "not applicable"}[value])

    unsatisfied = [key for key, value in conjuncts.items() if value is False]
    if unsatisfied:
        say(f"Rule N on {name} (via rule B's conjuncts)", True,
            f"NOT BRACKETED: {unsatisfied}. A bracket with an indeterminate endpoint is "
            f"UNRESOLVED at {common.BRACKET_STEP_MM} mm and rule N applies to this edge.")
        return {"verdict": "NOT BRACKETED", "interval": (low, high),
                "reason": f"unsatisfied conjuncts {unsatisfied}"}

    # The half-open interval, oriented so that the CLOSED end is the side on which the
    # predicate is true -- which is section 2.2's own notation for the three predicted
    # brackets.
    rising = stop_verdict(grouped[high], predicate) is True
    notation = f"({low}, {high}]" if rising else f"[{low}, {high})"
    say(f"{name}: BRACKETED", False,
        f"{notation} mm, width {common.BRACKET_STEP_MM} mm. A bracket narrower than "
        f"{common.BRACKET_STEP_MM} mm is NOT claimed, because the grid cannot produce one. "
        f"Repeats behind the endpoints: "
        f"{[(stop, [row.get(predicate) for row in grouped[stop]]) for stop in (low, high)]}")
    return {"verdict": "BRACKETED", "interval": (low, high), "notation": notation,
            "rising": rising, "reason": None}


# ---------------------------------------------------------------------------
# Rule D, FLOOR1, INV1 and rule C, CTL
# ---------------------------------------------------------------------------
def rule_d(name: str, bracket: dict, predicted_m: float | None, what: str) -> None:
    """Rule D -- the arithmetic and the measurement are allowed to disagree."""
    if bracket["verdict"] != "BRACKETED" or predicted_m is None:
        say(f"Rule D on {name}", None,
            f"no bracket to compare against {what}"
            + ("" if predicted_m is not None else ", and no computed value on the record"))
        return
    low, high = bracket["interval"]
    predicted_mm = predicted_m * 1000.0
    inside = low < predicted_mm < high
    say(f"Rule D on {name}", not inside,
        f"the measured bracket {bracket['notation']} mm "
        + ("CONTAINS" if inside else "DOES NOT CONTAIN")
        + f" the computed {what} of {predicted_mm:.6f} mm"
        + ("" if inside else
           f", a DISAGREEMENT of {min(abs(predicted_mm - low), abs(predicted_mm - high)):.6f}"
           f" mm to the nearer endpoint. NOTHING IS RE-RUN to resolve it, no grid is "
           f"extended in the direction that would make it go away, and no constant "
           f"anywhere in the tree is edited. THE CAMPAIGN DOES NOT ATTRIBUTE IT: the "
           f"delivery chain, the predicate, the linkage model, the fixture and the harness "
           f"are all candidates and none is chosen here. It belongs in ANALYSIS.md's "
           f"verdict line, not in a deviation, because it is a result."))


def floor1(lo_bracket: dict, s_bracket: dict, floor_m: float | None) -> None:
    """FLOOR1 -- the distance from the narrow flip to the floor, as an interval."""
    print("\n=== FLOOR1 (criteria.md section 7.2) ===")
    print("  RULE H -- no MEASURED figure of another campaign is differenced against "
          "anything here. The floor below is the value COMPUTED on this rig by bisection "
          "on the superseded BUILD's own answer; ADR-0052 section A.6's cited 47.1215 mm "
          "is named as an agreement and enters no arithmetic.")
    if lo_bracket["verdict"] != "BRACKETED":
        say("FLOOR1", True,
            "NOT REPORTED. LO1 is not BRACKETED, and a distance from an unlocated flip is "
            "not a quantity.")
        return
    if floor_m is None:
        say("FLOOR1", None,
            "LO1 is BRACKETED but no computed floor is on the record (V12: no superseded "
            "build), so FLOOR1 is reported against the cited floor only and the write-up "
            "must say so.")
        return
    low, high = lo_bracket["interval"]
    floor_mm = floor_m * 1000.0
    distance = (low - floor_mm, high - floor_mm)
    above = low >= floor_mm
    say("FLOOR1", False,
        f"REPORTED. flip_F_lo = {lo_bracket['notation']} mm; computed floor = "
        f"{floor_mm:.6f} mm; distance as an interval = "
        f"({distance[0]:+.6f}, {distance[1]:+.6f}) mm. flip_F_lo lies "
        + ("ABOVE the floor, which is the direction ADR-0052 section A.6's subset argument "
           "depends on." if above else
           "BELOW the floor, WHICH IS A FINDING.")
        + " FLOOR1 carries NO pass/fail: section A.6 sets no minimum distance and this "
          "campaign may not invent one.")
    if s_bracket["verdict"] == "BRACKETED":
        s_low, s_high = s_bracket["interval"]
        say("FLOOR1 (rig-internal form)", False,
            f"flip_S_lo = {s_bracket['notation']} mm, measured on this rig at this "
            f"command; distance from flip_F_lo = ({low - s_high:+.6f}, "
            f"{high - s_low:+.6f}) mm. This is the comparison free of any cross-campaign "
            f"differencing.")
    else:
        say("FLOOR1 (rig-internal form)", None,
            "flip_S_lo is not BRACKETED, so the rig-internal distance is not a quantity. "
            "It is a SECONDARY quantity: the gate does not ask for it, and its absence "
            "does not make the gate's bullet unmet.")


def inv1(kept: dict[str, list[dict]]) -> None:
    """INV1 and rule C -- command invariance at the four straddling stops."""
    print("\n=== INV1 (criteria.md section 7.3) ===")
    print("  WHAT INV CAN AND CANNOT SEPARATE, before any number: INV evaluates FOUR "
          "fixed stops at TWO commands and nothing else. It is a test of those eight "
          "points, not of the predicate's functional form, and IT CANNOT SEPARATE F FROM "
          "A COMMAND-REFERENCED PREDICATE HERE -- criteria.md section 5.2 computes that "
          "the superseded predicate returns true at all eight. INV HELD is evidence that "
          "these four verdicts do not move under this command change, and IS NOT evidence "
          "that the predicate ignores the command.")
    inv_rows = kept.get("INV", [])
    if not inv_rows:
        say("INV1", None, "block INV has no surviving trials, so the comparison has no "
                          "left-hand side")
        return
    shipped: dict[float, list[dict]] = {}
    for label in ("LO-F", "HI-F"):
        for stop, trials in per_stop(kept.get(label, [])).items():
            if stop is not None:
                shipped[stop] = trials
    rows_by_stop = per_stop(inv_rows)
    disagreements = []
    unmatched = []
    for stop, trials in rows_by_stop.items():
        if stop not in shipped:
            unmatched.append(stop)
            continue
        at_inv = stop_verdict(trials, "holding_F")
        at_shipped = stop_verdict(shipped[stop], "holding_F")
        print(f"    stop {stop:8.2f} mm: holding_F at "
              f"{shipped[stop][0].get('w_cmd_m')} m = {at_shipped} "
              f"(w_reached {[row.get('i1_reached_width_m') for row in shipped[stop]]}, "
              f"stalled {[row.get('stalled') for row in shipped[stop]]}, "
              f"reached_goal {[row.get('reached_goal') for row in shipped[stop]]}) | "
              f"at {trials[0].get('w_cmd_m')} m = {at_inv} "
              f"(w_reached {[row.get('i1_reached_width_m') for row in trials]}, "
              f"stalled {[row.get('stalled') for row in trials]}, "
              f"reached_goal {[row.get('reached_goal') for row in trials]})")
        if at_inv is None or at_shipped is None or at_inv != at_shipped:
            disagreements.append((stop, at_shipped, at_inv))
    if unmatched:
        say("INV1: stops with no shipped-command counterpart", True,
            f"{unmatched} -- the comparison cannot be made at these stops")
    else:
        say("INV1: stops with no shipped-command counterpart", False,
            "every INV stop has a counterpart in LO-F or HI-F at the shipped command")
    if disagreements:
        say("INV1", True,
            f"VIOLATED at {disagreements}. RULE C APPLIES: the shipped predicate's verdict "
            f"depends on a value criteria.md section 2 reads it as not consuming. Nothing "
            f"is re-run, no constant is touched, and no bracket derived at either command "
            f"is quietly preferred over the other -- BOTH brackets are reported, and LO1 "
            f"and HI1 are reported at the shipped command with the disagreement stated on "
            f"the same line.")
    else:
        say("INV1", False,
            f"HELD over {len(rows_by_stop)} stop(s) and {len(inv_rows)} trial(s): "
            f"holding_F is identical at both commands at every stop, over all repeats. "
            f"Rule C does not apply.")


def ctl(kept: dict[str, list[dict]], blocks: dict[str, list[dict]]) -> None:
    """Section 7.4 -- CTL is reported and carries no verdict of its own."""
    print("\n=== CTL (criteria.md sections 5.3 and 7.4) -- REPORTED, NO VERDICT ===")
    print("  CTL changes TWO things at once -- it removes the stop AND swaps "
          "JointStopSystem for mock_components/GenericSystem -- so it cannot separate 'the "
          "stop produces the stall' from 'the plugin does'. It does not need to: the "
          "2026-09-01 campaign established, with the mechanism in its own log, that plain "
          "GenericSystem DOES fabricate a stall. What CTL is: the controlled comparison "
          "whose quantity is WHERE THE JOINT COMES TO REST, which is what shows the rest "
          "position is the fixture's and not the controller's.")
    print("  CTL IS NOT THE INSTRUMENT THAT SETTLES docs/open-work.md #25, it is not "
          "powered to, and its result may not be written up as evidence about it in either "
          "direction.")
    rows = kept.get("CTL") or blocks.get("CTL") or []
    if not rows:
        say("CTL", None, "no CTL trials in raw/")
        return
    if not kept.get("CTL") and blocks.get("CTL"):
        print("  These are read from the COLLECTED trials rather than from the surviving "
              "set. CTL declares no stop, so the joint is not at rest: I3 samples it later "
              "than I1 and I4's second command moves it further, which makes V4 and V14 "
              "fire STRUCTURALLY here. Those two rules exclude a trial FROM EVERY BRACKET, "
              "and CTL contributes to no bracket, so nothing is lost -- but the exclusion "
              "is named rather than left to look like a rig failure.")
    for row in rows:
        print(f"    trial {row['trial']}: w_cmd {row.get('w_cmd_m')} m, "
              f"w_reached {row.get('i1_reached_width_m')} m, "
              f"rest {row.get('i3_q_at_rest_rad')} rad, "
              f"stalled {row.get('stalled')}, reached_goal {row.get('reached_goal')}, "
              f"holding_F {row.get('holding_F')}, holding_S {row.get('holding_S')}, "
              f"stop warning {row.get('i5_stop_announced')}")
    warned = any(row.get("i5_stop_announced") for row in rows)
    say("CTL: a stop warning appeared", warned,
        "section 7.4 requires that none appear, and "
        + ("one DID" if warned else "none did"))


def p6(kept: dict[str, list[dict]], blocks: dict[str, list[dict]]) -> None:
    """P6 -- CTL's registered outcome, computed from L0 and reproduced or not."""
    rows = kept.get("CTL") or blocks.get("CTL") or []
    if not rows:
        say("P6", None, "no CTL trials to compare against")
        return
    expected = (rows[0].get("p6") or {})
    rest_rad = expected.get("rest_position_rad")
    outcome = {
        "stalled": {row.get("stalled") for row in rows},
        "reached_goal": {row.get("reached_goal") for row in rows},
        "holding_F": {row.get("holding_F") for row in rows},
        "holding_S": {row.get("holding_S") for row in rows},
    }
    rests = [row.get("i3_q_at_rest_rad") for row in rows]
    matches = (
        outcome["stalled"] == {True} and outcome["reached_goal"] == {False}
        and outcome["holding_F"] == {False} and outcome["holding_S"] == {True}
    )
    say("P6", not matches,
        f"registered: stalled=true, reached_goal=false, rest about {rest_rad} rad "
        f"({(expected.get('rest_width_m') or 0) * 1000.0:.3f} mm), holding_F=false, "
        f"holding_S=true, no stop warning. Observed: {outcome}, rest {rests}. "
        + ("Reproduced -- and section 7.4 says this is a RIG CHECK AND NOT A RESULT: it "
           "says the fixture behaves as the published mechanism says, and nothing more."
           if matches else
           "NOT reproduced. That is a datum about the plugin and is reported as one, "
           "WITHOUT attribution and without any reading about open-work #25 in either "
           "direction."))


# ---------------------------------------------------------------------------
# The predictions
# ---------------------------------------------------------------------------
def predictions(brackets: dict, kept: dict[str, list[dict]], window: dict,
                floor_m: float | None, blocks: dict[str, list[dict]]) -> None:
    print("\n=== Predictions (criteria.md section 7.5), so that this campaign can be wrong ===")
    lo, hi, s = brackets["LO1"], brackets["HI1"], brackets["flip_S_lo"]

    # A prediction is REFUTED by data, and a prediction about a bracket is evaluable only
    # when the block that would produce that bracket actually ran. NOT EVALUABLE is the
    # third state `say` carries for exactly this: a prediction that could not be tested is
    # not a prediction that was refuted, and it is not one that survived either. The
    # shakedown found this: run against a directory holding no refinement block at all, an
    # earlier form of this function reported P1 and P3 REFUTED.
    have_data = any(rows for rows in kept.values())

    def ran(label: str) -> bool:
        return bool(blocks.get(label))

    edge_lo_mm = (window.get("edge_lo") or 0) * 1000.0
    edge_hi_mm = (window.get("edge_hi") or 0) * 1000.0
    p1_ok = (
        lo["verdict"] == "BRACKETED" and hi["verdict"] == "BRACKETED"
        and lo["interval"][0] < edge_lo_mm < lo["interval"][1]
        and hi["interval"][0] < edge_hi_mm < hi["interval"][1]
    )
    say("P1", None if not (ran("LO-F") and ran("HI-F")) else not p1_ok,
        f"LO1 = {lo['verdict']} {lo.get('notation')}, HI1 = {hi['verdict']} "
        f"{hi.get('notation')}, against computed edges {edge_lo_mm:.4f} / "
        f"{edge_hi_mm:.4f} mm. Refuted by either bracket landing elsewhere, or either edge "
        f"NOT BRACKETED.")

    spreads = [
        (label, stop, width_spread_m(trials))
        for label, rows in kept.items()
        for stop, trials in per_stop(rows).items()
    ]
    worst = max((entry for entry in spreads if entry[2] is not None),
                key=lambda entry: entry[2], default=None)
    disagreeing = [
        (label, stop) for label, rows in kept.items()
        for stop, trials in per_stop(rows).items()
        if stop_verdict(trials, "holding_F") is None
    ]
    p2_ok = (worst is not None and worst[2] <= common.REST_TOLERANCE_M
             and not disagreeing)
    say("P2", None if not have_data else not p2_ok,
        f"largest within-stop w_reached spread "
        + ("none measured" if worst is None
           else f"{worst[2] * 1000.0:.6f} mm at {worst[0]} stop {worst[1]}")
        + f"; stop(s) whose holding_F repeats disagree: {disagreeing or 'none'}. Refuted "
          f"by any spread above the {common.REST_TOLERANCE_M * 1000.0:.3f} mm rest "
          f"tolerance, or any within-stop verdict disagreement -- EITHER OF WHICH IS A "
          f"FINDING ABOUT THE RIG.")

    floor_mm = None if floor_m is None else floor_m * 1000.0
    p3_ok = (
        s["verdict"] == "BRACKETED" and floor_mm is not None
        and s["interval"][0] < floor_mm < s["interval"][1]
        and lo["verdict"] == "BRACKETED" and lo["interval"][0] >= s["interval"][1]
    )
    say("P3", None if not ran("LO-S") else not p3_ok,
        f"flip_S_lo = {s['verdict']} {s.get('notation')} against the computed floor "
        + ("(absent)" if floor_mm is None else f"{floor_mm:.6f} mm")
        + f"; flip_F_lo = {lo.get('notation')}. Refuted by either bracket landing "
          f"elsewhere, or flip_F_lo below flip_S_lo.")

    wide_false = [
        (label, row["trial"], row.get("w_stop_mm"))
        for label in ("HI-C", "HI-F")
        for row in kept.get(label, [])
        if row.get("holding_S") is False
    ]
    wide_unknown = any(row.get("holding_S") is None
                       for label in ("HI-C", "HI-F") for row in kept.get(label, []))
    wide_rows = [row for label in ("HI-C", "HI-F") for row in kept.get(label, [])]
    say("P4", None if not wide_rows else bool(wide_false),
        f"holding_S is false on {len(wide_false)} wide-arm trial(s): {wide_false or 'none'}"
        + ("; some wide-arm trials carry no holding_S at all (V12)" if wide_unknown else "")
        + ". The superseded predicate is a half-line with no upper edge at all, so any "
          "wide-arm trial with holding_S false refutes this.")

    print("  P5 is INV1 above, and P6 is the CTL block above. Both are printed there with "
          "their own observed values rather than restated here.")


# ---------------------------------------------------------------------------
def _one(records: list[dict], key: str):
    """One block-level value carried on every record, or `None` if the blocks disagree."""
    values = {json.dumps(row.get(key), sort_keys=True, default=str) for row in records}
    if len(values) != 1:
        return None
    return json.loads(values.pop())


def main() -> int:
    parser = argparse.ArgumentParser(description="criteria.md section 7, applied to raw/")
    parser.add_argument("--raw", default=str(common.RAW))
    arguments = parser.parse_args()
    raw = Path(arguments.raw)

    print(f"criteria.md section 7, applied to {raw}")
    print("\nRULE T -- the arms are not each other's evidence. A clean result in one says "
          "nothing about any other, EVERY VERDICT BELOW IS STATED PER ARM, and an "
          "inconclusive one belongs in the verdict rather than in a footnote. In "
          "particular, arm HI locating a flip says nothing about whether any part or any "
          "jam ever reaches it -- rule G is what carries that.")
    print(f"\n{RULE_G}")
    # VERBATIM, and not upper-cased. `criteria.md` rule W says `ANALYSIS.md` must state
    # this "in these words", and ANALYSIS.md is written from this print -- so the print
    # carries the sentence exactly as that record spells it, with the emphasis in the line
    # beside it rather than in the quotation.
    print(f'\nRULE W -- "{RULE_W}".')
    print("  The 2026-09-02 campaign's rule W STANDS UNCHANGED and STANDS FIRED, and "
          "nothing this campaign produces touches it. A SILENCE IS NOT REPORTED HERE, "
          "because a silence is read as a clearance.")
    print("\nSECTION 0 -- this campaign decides nothing. It sets no band, proposes no "
          "value, moves no ADR status, decides nothing about the removed monotonicity "
          "term, and NEITHER EDGE MAY BE WIDENED TO MAKE A RUN PASS.")
    print("SECTION 1 -- this is a VERIFICATION campaign, not a discovery campaign. What it "
          "verifies is DELIVERY: that the band L0 declares reaches the running predicate "
          "unchanged. Rule D is what makes that a question rather than a formality.")

    print("\n=== Numbered deviations (criteria.md V9) ===")
    print("  A threshold discovered to be wrong is APPLIED LITERALLY and recorded as "
          "wrong. None of these moved a threshold; each records where a registered form "
          "had to be made concrete, and what was done in its place.")
    for number, text in DEVIATIONS:
        print(f"\n  DEVIATION {number}. {text}")

    blocks = load_blocks(raw)
    print(f"\n=== Blocks collected ({len(blocks)}) ===")
    for label, rows in blocks.items():
        print(f"  {label}: {len(rows)} trial(s), cycles "
              f"{sorted({row.get('cycle') for row in rows})}, arm {rows[0].get('arm')}, "
              f"command {rows[0].get('w_cmd_m')} m")
    if not blocks:
        print("  none. raw/ holds no top-level *_trials.json, so there is nothing to "
              "apply section 7 to. (raw/shakedown/ is excluded here in code, not in a "
              "sentence: criteria.md section 10 makes it not data.)")

    every = [row for rows in blocks.values() for row in rows]
    window = _one(every, "window_m") or {}
    floor_m = _one(every, "floor_m")
    parts = _one(every, "parts") or {}
    superseded = _one(every, "superseded") or {}
    print("\n=== The four L0 statements option F is made of, as the records carry them ===")
    print(f"  declared part interval : {parts}")
    print(f"  window                 : {window}")
    print(f"  computed floor         : {floor_m}")
    if window == {} or floor_m is None:
        print("  NOTE: the blocks disagree about one of these, or none carries it. Every "
              "figure below that needs it is reported NOT EVALUABLE rather than computed "
              "from a value this file chose.")

    say("V12 -- the superseded predicate is a BUILD, not a rewrite",
        not bool(superseded.get("available")),
        f"provenance on the records: {superseded}. Without it, holding_F is reported "
        f"alone, block LO-S does not run, FLOOR1 is reported against the cited floor only, "
        f"and the write-up says so. V12 failing does NOT make LO1 or HI1 unmeasurable: the "
        f"gate's bullet is about F's flip.")

    kept, admission = admit(blocks)
    flagged = rule_v7(kept)

    print("\n=== Section 2 cross-check, as each block recorded it ===")
    for label, rows in blocks.items():
        header = raw / f"{label}_header.json"
        if not header.exists():
            say(f"section 2 cross-check on {label}", None, "no header file beside the trials")
            continue
        check = json.loads(header.read_text()).get("section_2_cross_check", {})
        bad = [name for name, entry in check.items()
               if isinstance(entry, dict) and not entry["agrees"]]
        say(f"section 2 cross-check on {label}", bool(bad),
            f"the shipped code {'DISAGREES with' if bad else 'reproduces'} criteria.md "
            f"section 2's table"
            + (f" on {bad}: "
               f"{ {name: check[name] for name in bad} }" if bad else ""))

    # Section 7.1's table is a REPORTING requirement, not a bracket input, so a block
    # whose trials were all excluded is still printed -- labelled as excluded, so that a
    # reader can see what was there rather than an absence.
    for label, rows in blocks.items():
        if kept.get(label):
            print_stop_table(label, kept[label])
        else:
            print_stop_table(
                f"{label} (NO SURVIVING TRIALS -- printed for reporting only; these "
                f"contribute to nothing)", rows)

    print("\n=== Rule U -- one flip, or none claimed (criteria.md section 7.1) ===")
    coarse_single = {}
    for label, predicate in (("LO-C", "holding_F"), ("HI-C", "holding_F"),
                             ("LO-C", "holding_S")):
        rows = kept.get(label)
        if not rows:
            say(f"Rule U on {label} ({predicate})", None,
                "no surviving trials in this coarse block")
            coarse_single[(label, predicate)] = None
            continue
        coarse_single[(label, predicate)] = rule_u(label, rows, predicate)

    print("\n=== Rule R -- resolution (criteria.md section 7.1) ===")
    for label, rows in kept.items():
        for predicate in ("holding_F", "holding_S"):
            rule_r(label, rows, predicate)
        rule_r_mis(label, rows)

    brackets = {}
    for name, label, predicate, coarse in (
        ("LO1", "LO-F", "holding_F", ("LO-C", "holding_F")),
        ("HI1", "HI-F", "holding_F", ("HI-C", "holding_F")),
        ("flip_S_lo", "LO-S", "holding_S", ("LO-C", "holding_S")),
    ):
        rows = kept.get(label)
        if not rows:
            print(f"\n--- {name}: rule B over block {label}, refining {predicate} ---")
            say(f"Rule N on {name}", True,
                f"NOT BRACKETED at {common.BRACKET_STEP_MM} mm: block {label} has no "
                f"surviving trials, so no pair of adjacent fine-grid stops exists. The "
                f"campaign's silence here MAY NOT be read as agreement with section 2.2's "
                f"arithmetic or as evidence that the edge is where the declaration says.")
            brackets[name] = {"verdict": "NOT BRACKETED", "interval": None,
                              "reason": f"block {label} produced no surviving trials"}
            continue
        brackets[name] = rule_b(name, label, rows, predicate,
                                coarse_single.get(coarse), flagged)

    print("\n=== LO1 and HI1, stated separately (criteria.md section 7.1) ===")
    print("  ADR-0052 section A.10 names the flip SINGULAR; this campaign reports TWO, and "
          "one of them being bracketed says nothing about the other (rule T).")
    for name in ("LO1", "HI1"):
        say(name, brackets[name]["verdict"] != "BRACKETED",
            f"{brackets[name]['verdict']}"
            + (f" at {brackets[name]['notation']} mm" if brackets[name].get("notation")
               else f" -- {brackets[name].get('reason')}"))
    print(f"  {RULE_G}")

    print("\n=== Rule D -- the arithmetic and the measurement may disagree ===")
    rule_d("LO1", brackets["LO1"], window.get("edge_lo"), "edge_lo")
    rule_d("HI1", brackets["HI1"], window.get("edge_hi"), "edge_hi")
    rule_d("flip_S_lo", brackets["flip_S_lo"], floor_m, "closed-form floor")
    print("  A disagreement at the NARROW edge would also mean ADR-0052 section A.6's "
          "derivation and the shipped band do not meet where the record says, which is a "
          "finding for that record and the owner and NOT for this campaign to act on.")

    floor1(brackets["LO1"], brackets["flip_S_lo"], floor_m)
    inv1(kept)
    ctl(kept, blocks)

    predictions(brackets, kept, window, floor_m, blocks)
    p6(kept, blocks)

    print("\n=== V8, V9, V10, V11 ===")
    total = sum(len(rows) for rows in blocks.values())
    surviving = sum(len(rows) for rows in kept.values())
    print(f"  V8  n is what it was: {surviving} surviving trial(s) over {total} collected, "
          f"across {len(kept)} block(s). NO STOP WAS TOPPED UP and no block that aborted "
          f"early was re-run; every count above is over the trials that actually ran. "
          f"Wilson 95 % intervals are printed beside any proportion this campaign reports; "
          f"the verdicts above are set memberships rather than proportions and carry none.")
    print("  V9  no threshold moved. Every rule above was written before the first trial, "
          "and a threshold discovered to be wrong is applied literally and recorded as "
          "wrong.")
    print("  V10 one writer at a time: V1's two readings per cycle are what make a "
          "concurrent edit visible, and any block whose readings disagreed is named in the "
          "admission block above. The campaign operator states in ANALYSIS.md whether one "
          "writer held.")
    print("  V11 no rebuild mid-campaign: ./scripts/build runs once before the first "
          "trial. A rebuild is a numbered deviation and splits the blocks before it from "
          "the blocks after it.")
    print(f"  Discarded blocks: {admission['discarded_blocks'] or 'none'}")

    print("\n=== Honesty bounds (criteria.md section 11) ===")
    print("  This campaign chooses nothing. It closes ONE BULLET OF ONE ITEM of one gate "
          "at most -- ADR-0052 section A.10 item 2's SECOND bullet. A null is not a pass. "
          "Nothing here is a P2 result, nothing here is a grasp result, and nothing here "
          "says where a real jam stops. One machine, one image, one commit, one checkout, "
          "one arm, one facility with one declared part width, no physics, AND IT IS NOT A "
          "RATE. Figures stay in this directory; cite the directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
