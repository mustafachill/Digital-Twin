#!/usr/bin/env python3
"""`criteria.md` section 7's decision rules, applied to `raw/`.

DERIVED IN SHAPE FROM
`docs/measurements/2026-09-02-option-f-regions/harness/analyse.py`, copied at commit
`e559264` -- the "one function per registered threshold, and the rule prints even when it
does not fire" shape and the `DEVIATIONS` tuple at module top are that file's. Every rule
below is this campaign's own. That directory is FROZEN and nothing in it is edited here.

WRITTEN BEFORE THE FIRST TRIAL, which is the whole point. A rule implemented after the
data has been seen is a rule chosen by the data, and `criteria.md` V9 forbids moving one
afterwards: a threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong,
as a numbered deviation in `ANALYSIS.md`, against data already collected.

EVERY RULE PRINTS WHETHER OR NOT IT FIRES. A rule that only speaks when it triggers is a
rule nobody can audit, and a reader cannot tell it from a rule that was never implemented.

IT READS THE VALIDITY FLAGS OFF THE RECORD AND RE-DERIVES NONE OF THEM. V1's flag is
computed where the block was taken, from two `git` readings taken at both ends of the run;
re-deriving it here would ask a tree that has since moved.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, sets no band, proposes
no ceiling and chooses nothing (`criteria.md` section 0). It prints what the registered
rules say about the runs that ran, and stops. `ANALYSIS.md` is written from that print,
later, by someone else.

    python3 docs/measurements/2026-09-02-scenario-ceilings/harness/analyse.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics

import common
import expected as manifest_module

#: `criteria.md` section 2.2, INHERITED VERBATIM from
#: `2026-08-29-real-time-factor-conditions/criteria.md` section 5. Not reinvented here.
BAND_TIGHT = 1.5
BAND_LOOSE = 10.0

#: `criteria.md` rule NOISY, inherited from 2026-08-29 section 3 where it was numbered V1
#: and renamed here to avoid colliding with this campaign's own V1. A group whose range
#: exceeds this fraction of its median is marked NOISY. It DECORATES and does not overturn
#: the band verdict: the margin is defined on the maximum by design, and a noisy group's
#: maximum is exactly the quantity that definition wants.
NOISY_RANGE_FRACTION = 0.25

#: Rule G's discard. A run whose mangled count exceeds this fraction of its
#: `CITE_TIMING` lines is discarded, because at that point the campaign does not know what
#: it is missing.
RULE_G_MAX_MANGLED_FRACTION = 0.05

#: V4. A run missing more than this fraction of its expected triples is discarded: at that
#: point the campaign does not know whether the scenario ran the waits at all.
V4_MAX_ABSENT_FRACTION = 0.5

#: `criteria.md` section 3, in the order the conditions step down.
CONDITION_ORDER = ("FULL", "C4", "C2", "C1")

#: (scenario, ceiling_s) -> the constant's NAME. Section 2.1 requires every reported margin
#: to name the file as well as the constant: `BRING_UP_CEILING_S` alone is ambiguous across
#: two values and "60 s" alone is ambiguous across two names. The pair is unique.
CEILING_NAMES = {
    ("bringup", 240.0): "BRING_UP_CEILING_S",
    ("bringup", 30.0): "DELIVERY_CEILING_S",
    ("bringup", 60.0): "TRAJECTORY_CEILING_S",
    ("bringup", 120.0): "SKILL_CEILING_S",
    ("pick_and_place", 300.0): "BRING_UP_CEILING_S",
    ("pick_and_place", 60.0): "SETTLE_CEILING_S",
    ("pick_and_place", 420.0): "CYCLE_CEILING_S",
    ("continuous_line", 300.0): "BRING_UP_CEILING_S",
    ("continuous_line", 420.0): "LEG_CEILING_S",
}

#: Rule F's instruments, read from the emitters at `c38a42c`. FIRED is decided from I2's
#: verdict line and the FAILURE TEXT, never from the absence of a record -- a wait that
#: hits its ceiling emits nothing, and so does a wait that was never reached.
FIRED_SPIN = re.compile(r"timed out after (\d+)s waiting for (.+)")
FIRED_CYCLE = re.compile(r"did not finish within CYCLE_CEILING_S=(\d+)s and was killed")
FIRED_LEG = re.compile(
    r"piece (\d+): STOPPED after \d+/\d+ milestones, waiting on (.+) for (\d+)s"
)

#: `criteria.md` V9 -- the deviations known before the first campaign trial ran. A
#: deviation is where an interpretation had to CHANGE, applied literally to data already
#: collected. They are printed at the top of every run so that the write-up carries them
#: and cannot quietly drop one.
DEVIATIONS: tuple[tuple[str, str], ...] = (
    (
        "1",
        "The expected-count derivation for `continuous_line` is RE-IMPLEMENTED on the "
        "host rather than imported from `tests/scenarios/continuous_line.py`. That module "
        "imports `launch_testing` and `rclpy`, which this analyser does not have, and "
        "importing it would also make the analyser depend on the tree V1 forbids editing "
        "in a second way. `expected.py` derives the ladder length and the frame count "
        "from the same generated topology by the same rule, states the derivation in its "
        "own docstring, and this file CROSS-CHECKS it against the milestone descriptions "
        "the records themselves carry -- a disagreement is printed as a finding rather "
        "than silently believed. No count is taken from any run."
    ),
    (
        "2",
        "Rule F is applied LITERALLY, which means `continuous_line.LEG_CEILING_S` is "
        "reported FIRED when it timed out on either of the two waits section 2.3 excludes "
        "from its margin -- the spawn settle and the removal. The rule says 'any "
        "(scenario, ceiling, condition) in which that ceiling timed out in ANY "
        "contributing run', and it names a CEILING rather than an interval. The print "
        "below names which wait fired, so a reader can see which of the two cases it is, "
        "but the FIRED label is not withheld on the strength of that reading."
    ),
)


# ---------------------------------------------------------------------------
# Loading, and the run-level admission rules
# ---------------------------------------------------------------------------
def load_runs(raw: Path) -> list[dict]:
    """Every run document in `raw/`, EXCLUDING `raw/shakedown/`.

    The shakedown is not data (`criteria.md` section 10): it is excluded from every figure
    in section 7 and may not be used to set or adjust any threshold. The exclusion is here,
    in code, rather than in a sentence somebody has to remember -- and it is done by
    listing the top level only, so a shakedown directory cannot be swept in by a recursive
    glob.
    """
    runs = []
    for path in sorted(raw.glob("*.json")):
        try:
            runs.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            print(f"  !! {path.name} does not parse as JSON and is not loaded")
    return runs


def admit(runs: list[dict], raw: Path, root: Path) -> tuple[list[dict], list[dict]]:
    """Section 10's per-run rules, each printed whether or not it fires.

    Returns the admitted runs and the discarded ones. A discarded run is REPORTED with the
    rule that discarded it; V8 forbids topping the condition up to replace it.
    """
    print("\n=== Run admission (criteria.md section 10), every rule printed ===")
    admitted: list[dict] = []
    discarded: list[dict] = []
    if not runs:
        print("  no runs in raw/. Every rule below is vacuous and NOTHING IS ASSESSED.")
    for run in runs:
        label = run.get("label", "<unlabelled>")
        validity = run.get("validity", {})
        reasons: list[str] = []

        # Rule P -- a trial whose console was not captured produced nothing. Not a short
        # table: no data. It is not reconstructed from the junit report, which carries no
        # stdout. Both halves are checked: the run document has to say it parsed a
        # console, AND the console has to still be on disk beside it, because a run
        # document without its log is a table nobody can go back to.
        if run.get("instrument", {}).get("marker_lines") is None:
            reasons.append("rule P: this run document records no captured console")
        elif not (raw / f"{label}.log").exists():
            reasons.append(f"rule P: {label}.log is not in raw/, so the console is gone")

        if not validity.get("v1_clean"):
            reasons.append(
                "V1: a watched path differed from the base commit or was dirty"
                + (
                    " -- AND THE TWO READINGS DISAGREED, so the edit landed MID-RUN"
                    if validity.get("v1_disagreed_mid_run")
                    else ""
                )
            )
        if validity.get("v2_ok") is not True:
            reasons.append(
                f"V2: the running cell did not read back hulls and the throttle "
                f"(v2_ok={validity.get('v2_ok')!r})"
            )
        if validity.get("v5_ok") is not True:
            reasons.append("V5: a gz sim survivor from the previous run was present at start")
        if validity.get("v6_ok") is not True:
            reasons.append(f"V6: {validity.get('v6_note')}")
        if validity.get("g_ok") is not True:
            reasons.append(
                f"rule G: mangled fraction "
                f"{run.get('instrument', {}).get('mangled_fraction', 0.0):.3f} exceeds "
                f"{RULE_G_MAX_MANGLED_FRACTION}"
            )

        # V4 -- record completeness, against I8's manifest.
        workpieces = run.get("environment", {}).get("CITE_LINE_WORKPIECES")
        pieces = int(workpieces) if workpieces else manifest_module.DEFAULT_WORKPIECES
        run_entries, _ = manifest_module.manifest(root, pieces)
        present = _presence(run, run_entries)
        absent = [key for key, (seen, want) in present.items() if seen == 0 and want > 0]
        relevant = [key for key, (_, want) in present.items() if want > 0]
        fraction = (len(absent) / len(relevant)) if relevant else 0.0
        if fraction > V4_MAX_ABSENT_FRACTION:
            reasons.append(
                f"V4: {len(absent)} of {len(relevant)} expected triples absent "
                f"({fraction:.2f} > {V4_MAX_ABSENT_FRACTION})"
            )

        flag = " [V7 LOUD HOST]" if validity.get("v7_load_flag") else ""
        if reasons:
            discarded.append(run)
            print(f"  DISCARDED {label}{flag}")
            for reason in reasons:
                print(f"      {reason}")
        else:
            admitted.append(run)
            print(
                f"  admitted  {label}{flag}  condition={run.get('condition')} "
                f"scenario={run.get('scenario')} verdict={run.get('verdict', {}).get('verdict')} "
                f"records={len(run.get('records', []))}"
            )
    print(f"  -- {len(admitted)} admitted, {len(discarded)} discarded. V8: n is what it "
          "was, and no condition is topped up to replace a discard.")
    return admitted, discarded


def _presence(run: dict, entries: list) -> dict:
    """Rule E -- `k of n` per manifest triple, for one run.

    A PRESENCE CHECK IS NOT ENOUGH. One pattern stands for many records: `piece {n}:
    {milestone}` covers `WORKPIECES x len(ladder)` at full completion, and one surviving
    leg satisfies the pattern. So every triple is counted, not merely looked for.
    """
    counts: dict[tuple[str, str, float], tuple[int, int]] = {}
    records = run.get("records", [])
    scenario = run.get("scenario")
    for entry in entries:
        if entry.scenario != scenario:
            continue
        seen = sum(1 for record in records if entry.matches(record))
        counts[entry.key] = (seen, entry.count)
    return counts


# ---------------------------------------------------------------------------
# Rule E and rule A's premise
# ---------------------------------------------------------------------------
def rule_e(runs: list[dict], root: Path) -> None:
    print("\n=== Rule E -- expected records are ABSENT, not zero, and a PATTERN is k of n ===")
    print("  Against I8's manifest. A triple with no record is an ABSENT EXPECTED KEY with "
          "no value imputed; a triple with fewer records than its expected count is "
          "reported k of n. A ceiling all of whose expected records are absent across "
          "every valid run is NOT ASSESSED under D3.")
    if not runs:
        print("  no admitted runs: rule E has nothing to check, and that is not a pass.")
        return
    for run in runs:
        workpieces = run.get("environment", {}).get("CITE_LINE_WORKPIECES")
        pieces = int(workpieces) if workpieces else manifest_module.DEFAULT_WORKPIECES
        entries, derivation = manifest_module.manifest(root, pieces)
        present = _presence(run, entries)
        print(f"  {run['label']} (workpieces in force: {pieces}, "
              f"ladder from {derivation['ladder']['source']}, "
              f"length {derivation['ladder']['ladder_length']})")
        for entry in entries:
            if entry.scenario != run.get("scenario"):
                continue
            seen, want = present[entry.key]
            mark = "ok " if seen == want else ("ABSENT" if seen == 0 else "PARTIAL")
            print(f"      {mark:7s} {seen} of {want}  {entry.ceiling_name} "
                  f"<- {entry.pattern.pattern}")


def rule_a_premise(runs: list[dict]) -> dict:
    """Rule A's premise: `bringup`'s alphabetically first test absorbs the cold bring-up.

    If the observed first test is not `test_a_skill_moves_the_arm_to_its_home_configuration`,
    the premise has failed and `bringup.BRING_UP_CEILING_S` is reported NOT ASSESSED under
    D3 rather than silently re-keyed.
    """
    print("\n=== Rule A -- bringup's bring-up margin is assessed against ONE what ===")
    print(f"  Contributing what: {manifest_module.RULE_A_WHAT!r}. Every other "
          "BRING_UP_CEILING_S what in that file is dropped, because the first test "
          "alphabetically absorbs the cold bring-up and every later wait measures an "
          "already-running system.")
    holds: dict[str, bool] = {}
    any_bringup = False
    for run in runs:
        if run.get("scenario") != "bringup":
            continue
        any_bringup = True
        records = sorted(run.get("records", []), key=lambda record: record["monotonic_s"])
        first = records[0]["test"] if records else "<no record>"
        ok = first == manifest_module.RULE_A_FIRST_TEST
        holds[run["label"]] = ok
        outcome = (
            "premise holds"
            if ok
            else "PREMISE FAILED -- D3 applies to bringup.BRING_UP_CEILING_S for this run"
        )
        print(f"  {run['label']}: first emitting test = {first} -> {outcome}")
    if not any_bringup:
        print("  no admitted bringup run: the premise is neither confirmed nor refuted.")
    return holds


# ---------------------------------------------------------------------------
# The record-level rules
# ---------------------------------------------------------------------------
def classify(runs: list[dict], rule_a_holds: dict) -> dict:
    """Rules Z, K, A and section 2.3's leg filter, applied before any margin.

    Every drop is counted and reported per (scenario, what), because a `what` that emits
    only dropped records has produced no measurement of its interval at all, and rule D3
    then governs it.
    """
    print("\n=== Rules Z, K and section 2.3's leg filter, applied before any margin ===")
    kept: list[dict] = []
    zero_spin: dict[tuple[str, str], int] = {}
    clock: list[dict] = []
    dropped_a = 0
    dropped_leg = 0
    for run in runs:
        for record in run.get("records", []):
            key = (record["scenario"], record["what"])
            # Rule Z -- the filter is on `spins`, NEVER on `elapsed_s`. A zero-spin record
            # is one evaluation of a predicate, and one of those predicates shells out to
            # a subprocess, so it is not always near zero.
            if int(record["spins"]) == 0:
                zero_spin[key] = zero_spin.get(key, 0) + 1
                continue
            # Rule K -- two clocks. `elapsed_s` is monotonic; the timeout is enforced on
            # the node clock, which is the steppable system clock. A record above its own
            # ceiling is a datum about the two clocks and is excluded from the margin.
            if float(record["elapsed_s"]) > float(record["ceiling_s"]):
                clock.append(record)
                continue
            # Rule A -- drop by `what`, and only in `bringup`'s BRING_UP_CEILING_S.
            if record["scenario"] == "bringup" and float(record["ceiling_s"]) == 240.0:
                if record["what"] != manifest_module.RULE_A_WHAT:
                    dropped_a += 1
                    continue
                if not rule_a_holds.get(run["label"], False):
                    dropped_a += 1
                    continue
            # Section 2.3 -- `LEG_CEILING_S` is used in three places and only one is a leg.
            if record["scenario"] == "continuous_line" and float(record["ceiling_s"]) == 420.0:
                if not record["what"].startswith(manifest_module.LEG_WHAT_PREFIX):
                    dropped_leg += 1
                    continue
            kept.append(record)
    print(f"  rule Z: {sum(zero_spin.values())} zero-spin record(s) discarded"
          + ("" if zero_spin else " -- NONE FIRED"))
    for (scenario, what), count in sorted(zero_spin.items()):
        print(f"      {count:4d}  {scenario}: {what}")
    print(f"  rule K: {len(clock)} record(s) with elapsed_s > ceiling_s"
          + ("" if clock else " -- NONE FIRED"))
    for record in clock:
        print(f"      {record['scenario']}: {record['what']} "
              f"elapsed={record['elapsed_s']} ceiling={record['ceiling_s']} "
              f"(run {record['label']})")
    if len(clock) > 1:
        print("      FINDING: more than one clock-disagreeing record. The clock "
              "disagreement is reported as a finding in its own right (rule K).")
    print(f"  rule A: {dropped_a} bringup BRING_UP_CEILING_S record(s) dropped")
    print(f"  section 2.3: {dropped_leg} non-leg LEG_CEILING_S record(s) dropped")
    print(f"  -- {len(kept)} record(s) survive to the margins")
    return {
        "kept": kept,
        "zero_spin": zero_spin,
        "clock": clock,
        "dropped_a": dropped_a,
        "dropped_leg": dropped_leg,
    }


def band(margin: float) -> str:
    if margin < BAND_TIGHT:
        return "TOO TIGHT"
    if margin <= BAND_LOOSE:
        return "APPROPRIATE"
    return "TOO LOOSE"


def _cell_key(record: dict) -> tuple[str, str, str, str]:
    """(scenario, ceiling name, cold/warm/-, condition).

    The cold and warm halves of `pick_and_place`'s and `continuous_line`'s
    `BRING_UP_CEILING_S` are SEPARATE cells. Pooling them mixes a cold bring-up with a
    warm lookup under one name, which is the same mixture rule A treats as disqualifying
    in `bringup`.
    """
    scenario = record["scenario"]
    name = CEILING_NAMES.get((scenario, float(record["ceiling_s"])), "<unknown>")
    phase = "-"
    cold = manifest_module.COLD_BRING_UP_WHAT.get(scenario)
    if cold is not None and name == "BRING_UP_CEILING_S":
        phase = "cold" if record["what"] == cold else "warm"
    return (scenario, name, phase, record["condition"])


def summarise(values: list[float]) -> dict:
    ordered = sorted(values)
    quartiles = (
        statistics.quantiles(ordered, n=4) if len(ordered) >= 2 else [ordered[0]] * 3
    )
    return {
        "n": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "iqr": quartiles[2] - quartiles[0],
        "max": ordered[-1],
        "range": ordered[-1] - ordered[0],
    }


def fired_ceilings(runs: list[dict], raw: Path) -> dict:
    """Rule F -- which (scenario, ceiling, condition) demonstrably timed out.

    From I2's verdict line and the FAILURE TEXT, never from the absence of a record. A
    margin CAN be computed over the survivors of a run in which a ceiling fired --
    `continuous_line._run_one_piece` emits per milestone and breaks on the one that times
    out, and `bringup`'s eight pre-shutdown test methods keep running after one has failed
    -- so a ceiling that demonstrably fired could otherwise be banded off the instances
    that completed, which would be this campaign's worst possible output.
    """
    print("\n=== Rule F -- a ceiling that fired in ANY contributing run gets NO band ===")
    found: dict[tuple[str, str, str], list[str]] = {}
    for run in runs:
        console_path = raw / f"{run['label']}.log"
        if not console_path.exists():
            continue
        console = common.ANSI_RE.sub("", console_path.read_text(errors="replace"))
        scenario = run["scenario"]
        condition = run["condition"]
        for match in FIRED_SPIN.finditer(console):
            ceiling = float(match.group(1))
            name = CEILING_NAMES.get((scenario, ceiling), "<unknown>")
            found.setdefault((scenario, name, condition), []).append(
                f"{run['label']}: timed out after {match.group(1)}s waiting for "
                f"{match.group(2).strip()}"
            )
        for match in FIRED_CYCLE.finditer(console):
            found.setdefault((scenario, "CYCLE_CEILING_S", condition), []).append(
                f"{run['label']}: {match.group(0)}"
            )
        for match in FIRED_LEG.finditer(console):
            found.setdefault((scenario, "LEG_CEILING_S", condition), []).append(
                f"{run['label']}: {match.group(0)}"
            )
    if not found:
        print("  NONE FIRED. No ceiling timed out in any admitted run.")
    for key, texts in sorted(found.items()):
        print(f"  FIRED {key[0]}.{key[1]} at {key[2]} -- NO BAND is given to this cell")
        for text in texts[:3]:
            print(f"      {text}")
        if len(texts) > 3:
            print(f"      ... and {len(texts) - 3} further occurrence(s)")
    return found


def margins(kept: list[dict], fired: dict) -> dict:
    """Section 7.2 and rule Q -- every margin printed TWICE, with both bands.

    `ceiling / max` is a LOWER bound on the true margin; `ceiling / (max - q)` is an UPPER
    bound. Both are printed beside each other. If they land in different bands the cell is
    INCONCLUSIVE -- the poll quantum spans a band edge -- and both readings and both bands
    are published rather than one being chosen.
    """
    print("\n=== Section 7.2 -- the per-ceiling verdict, with rule Q's two readings ===")
    print("  Bands INHERITED from 2026-08-29 section 5: M < 1.5 TOO TIGHT, "
          "1.5 <= M <= 10 APPROPRIATE, M > 10 TOO LOOSE.")
    print("  q is subtracted from the MAXIMUM only, never from a median or an IQR.")
    cells: dict[tuple[str, str, str, str], dict] = {}
    grouped: dict[tuple[str, str, str, str], list[dict]] = {}
    for record in kept:
        grouped.setdefault(_cell_key(record), []).append(record)
    if not grouped:
        print("  NO CELL HAS A VALID RECORD. Every ceiling is NOT ASSESSED under D3, and "
              "rule N forbids reading that silence as a pass.")
    for key in sorted(grouped):
        scenario, name, phase, condition = key
        records = grouped[key]
        ceiling = float(records[0]["ceiling_s"])
        values = [float(record["elapsed_s"]) for record in records]
        stats = summarise(values)
        quantum = max(common.poll_quantum_s(scenario, record["what"]) for record in records)
        lower = ceiling / stats["max"] if stats["max"] > 0 else float("inf")
        corrected = stats["max"] - quantum
        upper = ceiling / corrected if corrected > 0 else None
        noisy = stats["median"] > 0 and stats["range"] > NOISY_RANGE_FRACTION * stats["median"]

        # Rule X2 -- the same margin over records from PASSING runs only.
        passing = [record for record in records if record.get("verdict") == "passed"]
        passing_band = None
        if passing:
            passing_max = max(float(record["elapsed_s"]) for record in passing)
            passing_band = band(ceiling / passing_max) if passing_max > 0 else None

        verdict = band(lower)
        inconclusive: list[str] = []
        if upper is None:
            inconclusive.append("rule Q: max - q <= 0, so no upper bound exists")
        elif band(upper) != verdict:
            inconclusive.append(
                f"rule Q: the poll quantum spans a band edge ({verdict} / {band(upper)})"
            )
        if passing_band is not None and passing_band != verdict:
            inconclusive.append(
                f"rule X2: all-records band {verdict} differs from passing-only "
                f"band {passing_band}"
            )
        is_fired = (scenario, name, condition) in fired
        label = f"{scenario}.{name}" + (f" [{phase}]" if phase != "-" else "")
        head = "FIRED -- NO BAND" if is_fired else (
            "INCONCLUSIVE" if inconclusive else verdict
        )
        print(f"\n  {label} at {condition}: {head}")
        print(f"      n={stats['n']}  min={stats['min']:.3f}  "
              f"median={stats['median']:.3f}  IQR={stats['iqr']:.3f}  "
              f"max={stats['max']:.3f}  (ceiling {ceiling:.1f} s)")
        print(f"      M = ceiling/max      = {lower:.2f}  -> {band(lower)}   (lower bound)")
        if upper is None:
            print(f"      M = ceiling/(max-q)  = n/a, q={quantum:.1f} s exceeds the maximum")
        else:
            print(f"      M = ceiling/(max-q)  = {upper:.2f}  -> {band(upper)}   "
                  f"(upper bound, q={quantum:.1f} s)")
        if passing_band is not None:
            print(f"      rule X2 passing-only band: {passing_band}")
        else:
            print("      rule X2: no passing-run record in this cell, so the two readings "
                  "cannot be compared here")
        for note in inconclusive:
            print(f"      {note}")
        if noisy:
            print(f"      NOISY: range {stats['range']:.3f} exceeds "
                  f"{NOISY_RANGE_FRACTION:.0%} of the median. It decorates and does not "
                  "overturn the band.")
        if (scenario, name) in manifest_module.SINGLE_SITE_CEILINGS:
            print(f"      this band rests on {stats['n']} record(s)"
                  + (" -- median, IQR and maximum are the same number"
                     if stats["n"] == 1 else ""))
        if is_fired:
            print("      the distribution above is published under the FIRED label "
                  "because it says what the completing instances cost. NO SENTENCE MAY "
                  "DERIVE A VERDICT ON THE CEILING FROM IT.")
        cells[key] = {
            "verdict": head,
            "band_lower": band(lower),
            "band_upper": band(upper) if upper is not None else None,
            "stats": stats,
            "fired": is_fired,
        }
    return cells


def rule_x(runs: list[dict]) -> None:
    print("\n=== Rule X -- CYCLE_CEILING_S contributes only from runs whose verdict passed ===")
    cycle_runs = [
        run
        for run in runs
        if run.get("scenario") == "pick_and_place"
        and any(float(r["ceiling_s"]) == 420.0 for r in run.get("records", []))
    ]
    if not cycle_runs:
        print("  no admitted pick_and_place run carries a CYCLE_CEILING_S record -- "
              "NOTHING TO ADMIT OR REFUSE.")
        return
    refusal = (
        "REFUSED -- a record from a failed run measures a coordinator that exited early "
        "for a reason that is not the interval"
    )
    for run in cycle_runs:
        state = run.get("verdict", {}).get("verdict")
        outcome = "admitted" if state == "passed" else refusal
        print(f"  {run['label']}: verdict={state} -> {outcome}")


def rule_d3_and_n(cells: dict, root: Path) -> None:
    """Rule D3 decides the verdict column; rule N constrains the prose around it."""
    print("\n=== Rule D3 and rule N -- what was NOT assessed, and what may not be said ===")
    entries, _ = manifest_module.manifest(root)
    wanted = set()
    for entry in entries:
        cold = manifest_module.COLD_BRING_UP_WHAT.get(entry.scenario)
        phase = "-"
        if cold is not None and entry.ceiling_name == "BRING_UP_CEILING_S":
            phase = "cold" if entry.pattern.match(cold) else "warm"
        for condition in CONDITION_ORDER:
            wanted.add((entry.scenario, entry.ceiling_name, phase, condition))
    missing = sorted(wanted - set(cells))
    print(f"  {len(cells)} cell(s) assessed, {len(missing)} NOT ASSESSED.")
    for key in missing:
        print(f"      not assessed at n = 0 valid records: {key[0]}.{key[1]}"
              + (f" [{key[2]}]" if key[2] != "-" else "") + f" at {key[3]}")
    print("  RULE N. A ceiling this campaign failed to reach is a ceiling this campaign "
          "HAS NOT TESTED. Its silence there may not be read as a pass, as a validation "
          "of the ceiling's value, as evidence that the ceiling is large enough, or as a "
          "reason to leave the ceiling alone. Never 'fine', never 'loose', never "
          "'unchanged', and never carried over from another condition or another scenario "
          "(rule T).")


def rule_b1(cells: dict) -> None:
    """Section 7.3's crossing, with every branch it can land in named in advance."""
    print("\n=== B1 -- the crossing, as a BRACKET between two measured allocations ===")
    print("  No margin is interpolated between allocations and none is extrapolated below "
          "C1. Every branch prints the four per-condition verdicts and their n in full.")
    names = sorted({(key[0], key[1], key[2]) for key in cells})
    if not names:
        print("  no assessed cell: B1 has nothing to bracket, and that is not a crossing "
              "'below C1'.")
    for scenario, name, phase in names:
        sequence = []
        for condition in CONDITION_ORDER:
            cell = cells.get((scenario, name, phase, condition))
            if cell is None:
                sequence.append(("NOT ASSESSED", 0))
            else:
                sequence.append((cell["verdict"], cell["stats"]["n"]))
        label = f"{scenario}.{name}" + (f" [{phase}]" if phase != "-" else "")
        printed = "  ".join(
            f"{condition}={verdict}(n={n})"
            for condition, (verdict, n) in zip(CONDITION_ORDER, sequence, strict=True)
        )
        verdicts = [verdict for verdict, _ in sequence]
        print(f"\n  {label}")
        print(f"      {printed}")
        print(f"      {_bracket(verdicts)}")


def _bracket(verdicts: list[str]) -> str:
    """Section 7.3's branch table, applied literally to one verdict sequence."""
    unusable = {"NOT ASSESSED", "INCONCLUSIVE", "FIRED -- NO BAND"}
    if any(verdict in unusable for verdict in verdicts):
        blocked = [
            CONDITION_ORDER[index]
            for index, verdict in enumerate(verdicts)
            if verdict in unusable
        ]
        return (
            "B1: the bracket is reported OPEN on the side of "
            f"{', '.join(blocked)} -- a bracket MAY NOT SPAN a cell that was not assessed "
            "or is inconclusive, and rule N governs the prose"
        )
    if verdicts[0] == "TOO TIGHT":
        return ("B1: TOO TIGHT THROUGHOUT. No APPROPRIATE allocation was found between 16 "
                "and 1 CPU, and PR1 is refuted")
    if all(verdict == "APPROPRIATE" for verdict in verdicts):
        return ("B1: NOT LOCATED -- not located between 16 and 1 CPU. NEVER 'safe at any "
                "allocation'")
    if all(verdict == "TOO LOOSE" for verdict in verdicts):
        return ("B1: NOT LOCATED -- TOO LOOSE THROUGHOUT. This ceiling was not APPROPRIATE "
                "at any allocation tried; no crossing exists to bracket. Its TOO LOOSE "
                "verdict stands at every condition")
    order = ["TOO LOOSE", "APPROPRIATE", "TOO TIGHT"]
    ranks = [order.index(verdict) for verdict in verdicts]
    if ranks != sorted(ranks):
        return ("B1: NOT LOCATED -- NON-MONOTONE. The sequence is printed above with its n "
                "per cell and NO BRACKET is read from it. At n = 1-2 per cell a "
                "non-monotone sequence is within sampling variation, and this campaign "
                "does not distinguish that from a real non-monotonicity")
    statements = []
    for index in range(len(verdicts) - 1):
        if verdicts[index] == "TOO LOOSE" and verdicts[index + 1] == "APPROPRIATE":
            statements.append(
                f"the TOO LOOSE -> APPROPRIATE crossing is bracketed between "
                f"{CONDITION_ORDER[index]} and {CONDITION_ORDER[index + 1]}"
            )
        if verdicts[index] == "APPROPRIATE" and verdicts[index + 1] == "TOO TIGHT":
            statements.append(
                f"the APPROPRIATE -> TOO TIGHT crossing is bracketed between "
                f"{CONDITION_ORDER[index]} and {CONDITION_ORDER[index + 1]}"
            )
    if "TOO LOOSE" in verdicts and not any("TOO TIGHT" == v for v in verdicts):
        statements.append(
            "and NOT LOCATED for the APPROPRIATE -> TOO TIGHT crossing. Neither statement "
            "is used to summarise the other"
        )
    return "B1: " + "; ".join(statements) if statements else "B1: no crossing found"


def instrument_table(runs: list[dict], discarded: list[dict], drops: dict, root: Path) -> None:
    """Q-D, section 7.4. Published whatever the margins say."""
    print("\n=== Q-D -- the instrument, published whatever the margins say ===")
    total_lines = 0
    total_records = 0
    total_mangled = 0
    for run in runs + discarded:
        instrument = run.get("instrument", {})
        total_lines += instrument.get("marker_lines", 0)
        total_records += instrument.get("records", 0)
        total_mangled += instrument.get("mangled_count", 0)
        print(f"  {run['label']:28s} CITE_TIMING lines={instrument.get('marker_lines')} "
              f"parsed={instrument.get('records')} "
              f"mangled={instrument.get('mangled_count')} "
              f"({instrument.get('mangled_fraction', 0.0):.3f})")
        for raw_line in instrument.get("mangled_sample", []):
            print(f"      mangled: {raw_line[:200]}")
    print(f"  POOLED: lines={total_lines} parsed={total_records} mangled={total_mangled} "
          f"zero-spin={sum(drops['zero_spin'].values())} "
          f"clock-disagreeing={len(drops['clock'])} rule-A dropped={drops['dropped_a']} "
          f"non-leg dropped={drops['dropped_leg']}")
    _cross_check_ladder(runs, root)


def _cross_check_ladder(runs: list[dict], root: Path) -> None:
    """Deviation 1's cross-check: does the host derivation match what the emitter emitted?

    The manifest derives the ladder's length from the generated topology because the
    emitting module cannot be imported here. The records carry the milestone descriptions
    themselves, so the two can be compared -- and a disagreement is a finding about the
    manifest, printed rather than believed away.
    """
    _, derivation = manifest_module.manifest(root)
    declared = derivation["ladder"]["ladder_length"]
    observed: set[str] = set()
    for run in runs:
        for record in run.get("records", []):
            if record["scenario"] == "continuous_line" and record["what"].startswith("piece "):
                observed.add(record["what"].split(": ", 1)[-1])
    if not observed:
        print(f"  ladder cross-check: derived length {declared}; NO leg record observed, "
              "so the derivation is unconfirmed by the data (it is not thereby wrong).")
        return
    mark = "agrees" if len(observed) == declared else "DISAGREES -- FINDING"
    print(f"  ladder cross-check: derived length {declared}, distinct milestones observed "
          f"{len(observed)} -> {mark}")


def _prediction(cell: dict | None, wanted: str) -> str:
    """HELD / REFUTED / NOT TESTED for one prediction about one cell's band.

    A cell rule F marked FIRED has NO BAND, so a prediction ABOUT ITS BAND is NOT TESTED
    there -- neither held nor refuted. Reading a FIRED cell's surviving distribution as a
    band is the output rule F exists to prevent, and it must not sneak back in through a
    prediction table.
    """
    if cell is None:
        return "NOT TESTED -- not assessed at this condition (D3), which is not a pass (rule N)"
    if cell["fired"]:
        return "NOT TESTED -- FIRED, so rule F gives this cell no band to test against"
    if cell["verdict"] == "INCONCLUSIVE":
        # `band_upper` is absent when rule Q's `max - q <= 0`, and it is spelled out
        # rather than printed as a Python `None`: this line is read by a person writing
        # ANALYSIS.md, and a repr in it is a value waiting to be copied into prose.
        upper = cell["band_upper"] or "no upper bound (rule Q: max - q <= 0)"
        return (
            f"INCONCLUSIVE -- readings {cell['band_lower']} / {upper}, "
            "so the prediction is neither held nor refuted here"
        )
    return "HELD" if cell["verdict"] == wanted else f"REFUTED -- {cell['verdict']}"


def predictions(cells: dict, drops: dict, runs: list[dict], fired: dict) -> None:
    """Section 7.6. A refuted prediction is a RESULT and is reported as one.

    None of the seven is a threshold; the thresholds are sections 7.1 to 7.3, and they do
    not move if a prediction fails.
    """
    print("\n=== PR1-PR7 -- pre-registered predictions, each printed either way ===")
    # FIRED cells are excluded because rule F gives them NO BAND at all. INCONCLUSIVE
    # cells are NOT excluded: rule Q publishes both of their readings and both of their
    # bands, so a lower reading below 1.5 there is an assessed margin below 1.5 and PR1
    # has to see it.
    at_full = {
        key: cell
        for key, cell in cells.items()
        if key[3] == "FULL" and not cell["fired"]
    }
    tight = [
        key
        for key, cell in at_full.items()
        if "TOO TIGHT" in {cell["band_lower"], cell["band_upper"]}
    ]
    if tight:
        pr1 = "REFUTED by " + ", ".join(str(key) for key in tight)
    elif at_full:
        pr1 = "HELD"
    else:
        pr1 = "NOT TESTED -- no assessed FULL cell"
    print(f"  PR1  no assessed margin is TOO TIGHT at FULL: {pr1}")

    pr2 = []
    for name in ("DELIVERY_CEILING_S", "TRAJECTORY_CEILING_S"):
        cell = cells.get(("bringup", name, "-", "FULL"))
        pr2.append(f"{name}={_prediction(cell, 'TOO LOOSE')}")
    print("  PR2  bringup.DELIVERY_CEILING_S and bringup.TRAJECTORY_CEILING_S are TOO "
          f"LOOSE at FULL: {', '.join(pr2)}")

    settle_zero = sum(
        count
        for (scenario, what), count in drops["zero_spin"].items()
        if scenario == "pick_and_place" and what == "the work-piece to settle"
    )
    settle_cells = [
        key for key in cells if key[0] == "pick_and_place" and key[1] == "SETTLE_CEILING_S"
    ]
    if settle_cells:
        pr3 = "REFUTED -- a non-zero-spin settle record exists"
    elif settle_zero:
        pr3 = "HELD"
    else:
        pr3 = "NOT TESTED -- no settle record of either kind"
    print("  PR3  pick_and_place.SETTLE_CEILING_S is NOT ASSESSED everywhere, every record "
          f"discarded by rule Z: {settle_zero} zero-spin settle record(s), "
          f"{len(settle_cells)} assessed cell(s) -> {pr3}")

    # PR4 is read from rule F's own finding and NOT from the cell table, because the
    # predicted outcome leaves NO CELL AT ALL: `_run_cycle` returns on its deadline branch
    # before reaching `_emit_timing`, so a cycle that times out emits nothing. A
    # prediction of a timeout that consulted only the margins would report itself
    # untested exactly when it came true.
    cycle_c1_fired = ("pick_and_place", "CYCLE_CEILING_S", "C1") in fired
    cycle_c1_cell = cells.get(("pick_and_place", "CYCLE_CEILING_S", "-", "C1"))
    if cycle_c1_fired:
        pr4 = "HELD -- FIRED at C1, and rule F gives that cell no band"
    elif cycle_c1_cell is not None:
        pr4 = "REFUTED -- the cycle completed at C1 and emitted a record"
    else:
        pr4 = "NOT TESTED -- no C1 pick_and_place run reached the cycle either way"
    print(f"  PR4  pick_and_place times out on CYCLE_CEILING_S at C1: {pr4}")

    leg_full = cells.get(("continuous_line", "LEG_CEILING_S", "-", "FULL"))
    print("  PR5  continuous_line.LEG_CEILING_S is APPROPRIATE at FULL: "
          f"{_prediction(leg_full, 'APPROPRIATE')}")

    mangled = sum(run.get("instrument", {}).get("mangled_count", 0) for run in runs)
    pr6 = (
        "HELD"
        if mangled == 0 and not drops["clock"]
        else "REFUTED -- a finding about the instrument in its own right"
    )
    print("  PR6  rule G's mangled count and rule K's are both zero across the campaign: "
          f"mangled={mangled}, clock-disagreeing={len(drops['clock'])} -> {pr6}")

    counts = []
    for run in runs:
        if run.get("scenario") != "bringup":
            continue
        contributing = sum(
            1
            for record in run.get("records", [])
            if float(record["ceiling_s"]) == 240.0
            and record["what"] == manifest_module.RULE_A_WHAT
            and int(record["spins"]) > 0
        )
        counts.append((run["label"], contributing))
    bad = [entry for entry in counts if entry[1] != 1]
    if not counts:
        pr7 = "NOT TESTED -- no admitted bringup run"
    elif bad:
        pr7 = f"REFUTED -- {bad}, which falsifies rule A's premise"
    else:
        pr7 = "HELD"
    print("  PR7  bringup.BRING_UP_CEILING_S yields exactly one contributing record per "
          f"run after rule A: {pr7}")


def main() -> int:
    parser = argparse.ArgumentParser(description="criteria.md section 7, applied to raw/")
    parser.add_argument("--raw", default=str(common.RAW))
    arguments = parser.parse_args()
    raw = Path(arguments.raw)
    root = common.repo_root()

    print(f"criteria.md section 7, applied to {raw}")
    print("RULE T -- a condition is not another condition's evidence, and a scenario is "
          "not another scenario's. Every verdict below is stated per "
          "(scenario, ceiling, condition).")
    print("RULE H -- the 2026-08-29 figures are on a different machine. No margin here "
          "may be subtracted from, divided by, or described as an improvement on one there.")
    print("SECTION 0 -- this campaign decides nothing. No ceiling, threshold, tolerance or "
          "band moves because it ran, and none may be widened to absorb anything found here.")
    print("SECTION 8 -- censoring biases every margin UP, toward TOO LOOSE, and never "
          "toward TOO TIGHT: a wait that times out emits no record, so every censored "
          "instance removes a candidate for the maximum.")

    print("\n=== Numbered deviations (criteria.md V9) ===")
    print("  A threshold discovered to be wrong is APPLIED LITERALLY and recorded as "
          "wrong. None of these moved a threshold; each records where a registered form "
          "could not be evaluated as worded, and what was reported in its place.")
    for number, text in DEVIATIONS:
        print(f"\n  DEVIATION {number}. {text}")

    runs = load_runs(raw)
    entries, derivation = manifest_module.manifest(root)
    print(f"\n=== I8 manifest ===\n  {derivation['entries']} triple(s); "
          f"{derivation['records_at_full_completion']} record(s) at full completion "
          f"across the three scenarios; ladder derived from "
          f"{derivation['ladder']['source']} at length "
          f"{derivation['ladder']['ladder_length']} with "
          f"{derivation['ladder']['frames']} distinct frame(s).")

    del entries
    admitted, discarded = admit(runs, raw, root)
    rule_e(admitted, root)
    holds = rule_a_premise(admitted)
    drops = classify(admitted, holds)
    rule_x(admitted)
    fired = fired_ceilings(admitted, raw)
    cells = margins(drops["kept"], fired)
    rule_d3_and_n(cells, root)
    rule_b1(cells)
    instrument_table(admitted, discarded, drops, root)
    predictions(cells, drops, admitted, fired)

    print("\n=== V8, V9, V10, V11 ===")
    print(f"  V8  n is what it was: {len(admitted)} admitted run(s) over "
          f"{len(runs)} collected. No condition was topped up.")
    print("  V9  no threshold moved. Every rule above was written before the first trial.")
    print("  V10 one writer at a time: V1's two readings are what make a concurrent edit "
          "visible, and any run whose readings disagreed is named in the admission block.")
    print("  V11 no rebuild mid-campaign: a rebuild is a numbered deviation and would "
          "split the runs before it from the runs after it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
