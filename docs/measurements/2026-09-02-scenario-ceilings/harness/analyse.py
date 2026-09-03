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

#: Rule F's SECOND instrument, and the reason it has to exist. `FIRED_SPIN` above keys on
#: `_spin_until`'s own assertion, which bounds `BRING_UP_CEILING_S` and
#: `DELIVERY_CEILING_S` only. `bringup.TRAJECTORY_CEILING_S` (five call sites) and
#: `bringup.SKILL_CEILING_S` (one) are bounded ONLY by `_await_future`, whose docstring at
#: `c38a42c` says it "asserts nothing, deliberately": its expiry surfaces as the CALLER's
#: own `assertIsNotNone` message, which `FIRED_SPIN`'s regex does not match. `unittest`
#: continues after a failed method, so without these six a run in which one of those two
#: ceilings demonstrably expired would still be banded off the waits that completed --
#: the output section 7.3 calls this campaign's worst possible one, and on a ceiling PR2
#: makes a headline verdict.
#:
#: THE SIX STRINGS ARE READ FROM THE CALLERS AT `c38a42c`, `tests/scenarios/bringup.py`
#: lines 425, 430, 534, 539, 612 and 617. Each is the message of the `assertIsNotNone`
#: that immediately follows an `_await_future` under the named ceiling, and each can fail
#: only when that future had no result -- which is what the wait expiring means. The
#: direction of any error is toward WITHHOLDING a band, which is the safe direction: rule
#: F's whole purpose is to refuse one.
FIRED_AWAIT: tuple[tuple[str, str, str], ...] = (
    ("bringup", "TRAJECTORY_CEILING_S", "the gripper goal was never accepted"),
    ("bringup", "TRAJECTORY_CEILING_S", "the gripper never reported a result"),
    ("bringup", "TRAJECTORY_CEILING_S", "the trajectory goal was never accepted"),
    ("bringup", "TRAJECTORY_CEILING_S", "the trajectory never returned a result"),
    ("bringup", "TRAJECTORY_CEILING_S", "the MoveTo goal was never accepted"),
    ("bringup", "SKILL_CEILING_S", "MoveTo never returned a result"),
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
    (
        "3",
        "I4's SECOND reading, and with it V6's end-of-run confirmation, is taken from "
        "the LAST LIVE SAMPLE rather than `at the end of the run` as criteria.md I4 "
        "registers it. `scripts/_lib.sh` starts a scenario with `compose run --rm`, so "
        "the container is REMOVED the instant `./scripts/scenario` exits and every "
        "`docker` call after that reads `No such container`: the registered form is "
        "structurally unobtainable, not merely inconvenient. `run_trial.py` therefore "
        "samples I4 throughout the run and keeps the last reading that reached a LIVE "
        "container, recording how long before the exit it was taken "
        "(`i4_last_live_before_exit_s`) and keeping the failed post-exit attempt beside "
        "it (`i4_post_exit_attempt`) so that the substitute cannot be mistaken for a "
        "reading taken after the process ended. V6's end-of-run clause is evaluated "
        "against that substitute, and a run for which NO live reading survives is NOT "
        "ESTABLISHED and is discarded rather than passed. No threshold moved; what "
        "changed is which instant `at the end` names, and a reader of ANALYSIS.md must "
        "not see V6 satisfied without seeing that."
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


def _workpieces_in_force(run: dict) -> dict:
    """`CITE_LINE_WORKPIECES` as it was IN FORCE, from the authoritative field.

    `criteria.md` section 5 asks for the value in force, and the run document carries TWO
    candidates. `run["environment"]["CITE_LINE_WORKPIECES"]` is what the HOST SHELL
    exported and says so in its own `host_shell_note`; the authority is
    `run["container"]["cite_environment_in_force"]`, read out of the process that actually
    ran. `scripts/_lib.sh` forwards every `CITE_`-prefixed host variable into the
    container, so a variable set on the host is present in the container reading too --
    which is why the two agree in every configuration this campaign reaches. The
    authoritative one is read FIRST so that they need not agree for this to be right, and
    the source is returned so that the print says which was used.

    A container reading that succeeded and does not carry the variable is the answer
    `unset`, not a reason to consult the host shell: had the host set it, `_lib.sh` would
    have forwarded it.
    """
    container = (run.get("container") or {}).get("cite_environment_in_force")
    if isinstance(container, dict) and container.get("read_ok"):
        raw_value = container.get("CITE_LINE_WORKPIECES")
        source = "container env, the value in force"
    else:
        raw_value = (run.get("environment") or {}).get("CITE_LINE_WORKPIECES")
        source = "host shell -- THE CONTAINER ENV COULD NOT BE READ"
    if raw_value in (None, ""):
        return {
            "value": manifest_module.DEFAULT_WORKPIECES,
            "source": f"{source}: unset, so the scenario's own default applies",
        }
    try:
        return {"value": int(raw_value), "source": source}
    except (TypeError, ValueError):
        return {
            "value": manifest_module.DEFAULT_WORKPIECES,
            "source": f"{source}: {raw_value!r} is not an integer, so the default applies",
        }


def admit(runs: list[dict], raw: Path, root: Path) -> tuple[list[dict], list[dict]]:
    """Section 10's per-run rules, EVERY ONE PRINTED FOR EVERY RUN, fired or not.

    Returns the admitted runs and the discarded ones. A discarded run is REPORTED with the
    rule that discarded it; V8 forbids topping the condition up to replace it.

    AN ADMITTED RUN USED TO PRINT ONE LINE AND NOTHING ABOUT THE RULES IT PASSED, which
    broke this module's own contract -- a rule that only speaks when it triggers is a rule
    nobody can audit, and a reader cannot tell it from a rule that was never implemented.
    `v6_note` was the sharpest case: it is the evidence V6 rests on for every loaded run,
    and it printed ONLY on discard, so whether the allocation actually held was invisible
    for exactly the runs that contribute.
    """
    print("\n=== Run admission (criteria.md section 10), every rule printed for every run ===")
    print("  rule P, V1, V2, V4, V5, V6 and rule G can DISCARD. V3 and V7 never discard: "
          "V3 records the verdict rules X and X2 spend, and V7 FLAGS a loud host, whose "
          "effect on a band is reported per cell in section 7.2 rather than by exclusion.")
    admitted: list[dict] = []
    discarded: list[dict] = []
    if not runs:
        print("  no runs in raw/. Every rule below is vacuous and NOTHING IS ASSESSED.")
    for run in runs:
        label = run.get("label", "<unlabelled>")
        validity = run.get("validity", {})
        checks: list[tuple[str, bool | None, str]] = []

        # Rule P -- a trial whose console was not captured produced nothing. Not a short
        # table: no data. It is not reconstructed from the junit report, which carries no
        # stdout. Both halves are checked: the run document has to say it parsed a
        # console, AND the console has to still be on disk beside it, because a run
        # document without its log is a table nobody can go back to.
        if run.get("instrument", {}).get("marker_lines") is None:
            checks.append(("rule P", False, "this run document records no captured console"))
        elif not (raw / f"{label}.log").exists():
            checks.append(("rule P", False, f"{label}.log is not in raw/, so the console is gone"))
        else:
            checks.append((
                "rule P",
                True,
                f"{label}.log is on disk beside the record and the document parsed "
                f"{run['instrument']['marker_lines']} marker line(s)",
            ))

        checks.append((
            "V1",
            bool(validity.get("v1_clean")),
            (
                "both I6 readings clean over "
                f"{len(run.get('i6', {}).get('watched_paths', [])) or 5} watched path(s) "
                f"against {run.get('i6', {}).get('base_commit', '<base?>')}"
                if validity.get("v1_clean")
                else "a watched path differed from the base commit or was dirty"
                + (
                    " -- AND THE TWO READINGS DISAGREED, so the edit landed MID-RUN"
                    if validity.get("v1_disagreed_mid_run")
                    else ""
                )
            ),
        ))

        configuration = run.get("i7") or {}
        checks.append((
            "V2",
            validity.get("v2_ok") is True,
            f"v2_ok={validity.get('v2_ok')!r}: the running cell read "
            f"{configuration.get('hull_collision_refs')} hull collision reference(s) and "
            f"world_throttle_declared={configuration.get('world_throttle_declared')!r}",
        ))

        # V3 never discards. It is printed because rule X and rule X2 both spend it, and a
        # reader has to be able to see the value they spent.
        checks.append((
            "V3",
            None,
            f"verdict={run.get('verdict', {}).get('verdict')!r}, attached to "
            f"{len(run.get('records', []))} record(s). Rule X and rule X2 consume it",
        ))

        # V4 -- record completeness, against I8's manifest.
        pieces = _workpieces_in_force(run)
        run_entries, _ = manifest_module.manifest(root, pieces["value"])
        present = _presence(run, run_entries)
        absent = [key for key, (seen, want) in present.items() if seen == 0 and want > 0]
        relevant = [key for key, (_, want) in present.items() if want > 0]
        fraction = (len(absent) / len(relevant)) if relevant else 0.0
        checks.append((
            "V4",
            fraction <= V4_MAX_ABSENT_FRACTION,
            f"{len(absent)} of {len(relevant)} expected triples absent "
            f"({fraction:.2f} against {V4_MAX_ABSENT_FRACTION}); workpieces in force "
            f"{pieces['value']} from {pieces['source']}",
        ))

        checks.append((
            "V5",
            validity.get("v5_ok") is True,
            (
                f"{run.get('survivors_before', {}).get('gz_sim_count')} gz sim survivor(s) "
                f"at start, looked_ok="
                f"{run.get('survivors_before', {}).get('looked_ok')!r}"
            ),
        ))

        # V6's note is the evidence, and it prints on every run rather than only on a
        # discard. `v6_limit_held_at_end` is printed beside it because None there is NOT
        # ESTABLISHED and is a different answer from False.
        checks.append((
            "V6",
            validity.get("v6_ok") is True,
            f"{validity.get('v6_note')}; limit_held_at_end="
            f"{validity.get('v6_limit_held_at_end')!r}",
        ))

        # V7 never discards. The flag travels to section 7.2, where every cell it touches
        # is banded with and without it.
        checks.append((
            "V7",
            None,
            f"pre-run load_1m={validity.get('v7_load_1m')} against a flag at "
            f"{common.V7_LOAD_FLAG} -> "
            + ("FLAGGED, and every cell it contributes to is banded twice"
               if validity.get("v7_load_flag") else "not flagged"),
        ))

        instrument = run.get("instrument", {})
        checks.append((
            "rule G",
            validity.get("g_ok") is True,
            f"mangled fraction {instrument.get('mangled_fraction', 0.0):.3f} against "
            f"{RULE_G_MAX_MANGLED_FRACTION} "
            f"({instrument.get('mangled_count')} of {instrument.get('marker_lines')} "
            "marker line(s))",
        ))

        reasons = [f"{name}: {note}" for name, ok, note in checks if ok is False]
        flag = " [V7 LOUD HOST]" if validity.get("v7_load_flag") else ""
        if reasons:
            discarded.append(run)
            head = f"  DISCARDED {label}{flag}"
        else:
            admitted.append(run)
            head = (
                f"  admitted  {label}{flag}  condition={run.get('condition')} "
                f"scenario={run.get('scenario')} "
                f"verdict={run.get('verdict', {}).get('verdict')} "
                f"records={len(run.get('records', []))}"
            )
        print(head)
        for name, ok, note in checks:
            mark = "ok      " if ok is True else ("DISCARD " if ok is False else "recorded")
            print(f"      {mark} {name:7s} {note}")
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
        pieces = _workpieces_in_force(run)
        entries, derivation = manifest_module.manifest(root, pieces["value"])
        present = _presence(run, entries)
        print(f"  {run['label']} (workpieces in force: {pieces['value']} "
              f"[{pieces['source']}], "
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
    """Rules Z, K, A, X and section 2.3's leg filter, applied before any margin.

    Every drop is counted and reported per (scenario, what), because a `what` that emits
    only dropped records has produced no measurement of its interval at all, and rule D3
    then governs it. Every drop is ALSO counted against the section 7.2 cell it would
    have landed in, because that section requires each margin to be reported with `n
    discarded by each of rules Z, A, X, K and E` beside it.

    RULE X IS APPLIED HERE AND NOT ONLY PRINTED. Section 7.1 registers it among the rules
    "applied before any margin is computed", and it used to be printed as a verdict on
    each run while the records themselves went straight into the margin. That is the
    defect the emitter itself warns about at `c38a42c`: `pick_and_place._run_cycle` emits
    "whenever the coordinator exited AT ALL, a crash two seconds in included", so a failed
    run contributes a SHORT `elapsed_s` and inflates `M = 420/max` toward TOO LOOSE. Rule
    F does not catch it -- a crash is not a timeout -- and rule X2's safety net is silent
    in exactly this case, because with no passing record in the cell there is no second
    band to disagree with the first.
    """
    print("\n=== Rules Z, K, A, X and section 2.3's leg filter, applied before any margin ===")
    kept: list[dict] = []
    zero_spin: dict[tuple[str, str], int] = {}
    clock: list[dict] = []
    dropped_a = 0
    dropped_leg = 0
    dropped_x = 0
    x_runs: list[str] = []
    # Per-cell discard counts, keyed exactly as the margin cells are, so that section
    # 7.2's "n discarded by rule ..." lands in the same table cell as the margin.
    per_cell: dict[tuple[str, str, str, str], dict[str, int]] = {}

    def drop(record: dict, rule: str) -> None:
        cell = per_cell.setdefault(_cell_key(record), {})
        cell[rule] = cell.get(rule, 0) + 1

    for run in runs:
        # Rule X reads the RUN's verdict (I2), which is what the rule names. The same
        # value is copied onto every record by the runner, and rule X2 reads it there.
        run_verdict = run.get("verdict", {}).get("verdict")
        for record in run.get("records", []):
            key = (record["scenario"], record["what"])
            # Rule Z -- the filter is on `spins`, NEVER on `elapsed_s`. A zero-spin record
            # is one evaluation of a predicate, and one of those predicates shells out to
            # a subprocess, so it is not always near zero.
            if int(record["spins"]) == 0:
                zero_spin[key] = zero_spin.get(key, 0) + 1
                drop(record, "Z")
                continue
            # Rule K -- two clocks. `elapsed_s` is monotonic; the timeout is enforced on
            # the node clock, which is the steppable system clock. A record above its own
            # ceiling is a datum about the two clocks and is excluded from the margin.
            if float(record["elapsed_s"]) > float(record["ceiling_s"]):
                clock.append(record)
                drop(record, "K")
                continue
            # Rule X -- CYCLE_CEILING_S contributes only from runs whose verdict passed.
            if record["scenario"] == "pick_and_place" and float(record["ceiling_s"]) == 420.0:
                if run_verdict != "passed":
                    dropped_x += 1
                    if run["label"] not in x_runs:
                        x_runs.append(run["label"])
                    drop(record, "X")
                    continue
            # Rule A -- drop by `what`, and only in `bringup`'s BRING_UP_CEILING_S.
            if record["scenario"] == "bringup" and float(record["ceiling_s"]) == 240.0:
                if record["what"] != manifest_module.RULE_A_WHAT:
                    dropped_a += 1
                    drop(record, "A")
                    continue
                if not rule_a_holds.get(run["label"], False):
                    dropped_a += 1
                    drop(record, "A")
                    continue
            # Section 2.3 -- `LEG_CEILING_S` is used in three places and only one is a leg.
            if record["scenario"] == "continuous_line" and float(record["ceiling_s"]) == 420.0:
                if not record["what"].startswith(manifest_module.LEG_WHAT_PREFIX):
                    dropped_leg += 1
                    drop(record, "leg")
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
    print(f"  rule X: {dropped_x} pick_and_place CYCLE_CEILING_S record(s) dropped from "
          f"run(s) whose verdict was not 'passed'"
          + ("" if dropped_x else " -- NONE FIRED"))
    for label in x_runs:
        print(f"      {label}")
    print(f"  rule A: {dropped_a} bringup BRING_UP_CEILING_S record(s) dropped")
    print(f"  section 2.3: {dropped_leg} non-leg LEG_CEILING_S record(s) dropped")
    print(f"  -- {len(kept)} record(s) survive to the margins")
    return {
        "kept": kept,
        "zero_spin": zero_spin,
        "clock": clock,
        "dropped_a": dropped_a,
        "dropped_leg": dropped_leg,
        "dropped_x": dropped_x,
        "dropped_x_runs": x_runs,
        "per_cell": per_cell,
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
        # The `_await_future` half. `_spin_until`'s assertion above covers
        # BRING_UP_CEILING_S and DELIVERY_CEILING_S only; TRAJECTORY_CEILING_S and
        # SKILL_CEILING_S are bounded by a helper that asserts nothing, so their expiry
        # is visible only as the caller's own message.
        for site_scenario, name, message in FIRED_AWAIT:
            if site_scenario != scenario or message not in console:
                continue
            found.setdefault((scenario, name, condition), []).append(
                f"{run['label']}: {message!r} -- the caller's own assertion after an "
                "_await_future under this ceiling, so that wait did not complete"
            )
    print(f"  Two instruments: _spin_until's own timeout assertion, and the "
          f"{len(FIRED_AWAIT)} caller assertion(s) that are the ONLY surface an "
          "_await_future expiry has.")
    if not found:
        print("  NONE FIRED. No ceiling timed out in any admitted run.")
    for key, texts in sorted(found.items()):
        print(f"  FIRED {key[0]}.{key[1]} at {key[2]} -- NO BAND is given to this cell")
        for text in texts[:3]:
            print(f"      {text}")
        if len(texts) > 3:
            print(f"      ... and {len(texts) - 3} further occurrence(s)")
    return found


def _band_of_max(ceiling: float, values: list[float]) -> tuple[float | None, str | None]:
    """`M = ceiling / max` and its band, or `(None, None)` when there is nothing to band."""
    if not values:
        return None, None
    highest = max(values)
    if highest <= 0:
        return float("inf"), band(float("inf"))
    margin = ceiling / highest
    return margin, band(margin)


def margins(kept: list[dict], fired: dict, per_cell: dict, expected: dict) -> dict:
    """Section 7.2, rule Q, rule E's `k of n`, rule NOISY and V7 -- all printed per cell.

    `ceiling / max` is a LOWER bound on the true margin; `ceiling / (max - q)` is an UPPER
    bound. Both are printed beside each other. If they land in different bands the cell is
    INCONCLUSIVE -- the poll quantum spans a band edge -- and both readings and both bands
    are published rather than one being chosen.

    V7 IS A DECISION AND NOT A LABEL. Section 10 V7: no run is discarded for load, but a
    flagged run's margins are "reported with and without it, and if the band verdict
    differs, that cell is INCONCLUSIVE". The flag used to reach the admission line and stop
    there. It is partitioned here.
    """
    print("\n=== Section 7.2 -- the per-ceiling verdict, with rule Q's two readings ===")
    print("  Bands INHERITED from 2026-08-29 section 5: M < 1.5 TOO TIGHT, "
          "1.5 <= M <= 10 APPROPRIATE, M > 10 TOO LOOSE.")
    print("  q is subtracted from the MAXIMUM only, never from a median or an IQR.")
    print("  Each cell carries its rule Z / A / X / K / leg discards and rule E's k of n, "
          "because section 7.2 requires them in the same cell as the margin.")
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

        # V7 -- the partition, which is a decision. A cell touched by a flagged run is
        # banded again over the unflagged records only; a differing band makes the cell
        # INCONCLUSIVE.
        flagged = [record for record in records if record.get("v7_load_flag")]
        unflagged = [record for record in records if not record.get("v7_load_flag")]
        v7_line = "V7: no flagged run contributes to this cell"
        if flagged:
            _, without_band = _band_of_max(
                ceiling, [float(record["elapsed_s"]) for record in unflagged]
            )
            if without_band is None:
                v7_line = (
                    f"V7: ALL {len(flagged)} record(s) in this cell come from V7-flagged "
                    "run(s). There is no unflagged reading to compare, so the two bands "
                    "cannot differ and the cell is NOT made inconclusive by V7 -- but "
                    "this band rests entirely on a loud host and rule N governs the prose"
                )
            else:
                without_max = max(float(record["elapsed_s"]) for record in unflagged)
                v7_line = (
                    f"V7: {len(flagged)} of {len(records)} record(s) are from a flagged "
                    f"run. Without them: max={without_max:.3f} "
                    f"M={ceiling / without_max:.2f} -> {without_band}; with them: "
                    f"{verdict}"
                )
                if without_band != verdict:
                    inconclusive.append(
                        f"V7: the band differs with ({verdict}) and without "
                        f"({without_band}) the loud-host run(s)"
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
        drops_here = per_cell.get(key, {})
        print("      discarded before this margin: "
              + "  ".join(
                  f"{rule}={drops_here.get(rule, 0)}"
                  for rule in ("Z", "A", "X", "K", "leg")
              ))
        want = expected.get(key)
        if want is None:
            print("      rule E: this cell has NO manifest entry, so no k of n exists "
                  "for it -- a FINDING about the manifest, not about the ceiling")
        else:
            mark = "" if want["k"] == want["n"] else "   <- PARTIAL"
            print(f"      rule E: {want['k']} of {want['n']} expected record(s) present "
                  f"over {len(want['labels'])} contributing run(s){mark}")
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
        print(f"      {v7_line}")
        for note in inconclusive:
            print(f"      {note}")
        if noisy:
            print(f"      NOISY: range {stats['range']:.3f} exceeds "
                  f"{NOISY_RANGE_FRACTION:.0%} of the median. It decorates and does not "
                  "overturn the band.")
        else:
            print(f"      rule NOISY: not noisy -- range {stats['range']:.3f} is within "
                  f"{NOISY_RANGE_FRACTION:.0%} of the median {stats['median']:.3f}")
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


def rule_x(runs: list[dict], drops: dict) -> None:
    """Rule X's per-run table. THE FILTER ITSELF IS IN `classify`, above.

    This block exists so that the rule is auditable run by run -- which run was admitted,
    which refused and on what verdict. It reports the count `classify` actually dropped
    beside it, so that a reader can see the two agree; a table that says REFUSED while the
    records reach the margin anyway is worse than no table at all, and that is what this
    function used to be.
    """
    print("\n=== Rule X -- CYCLE_CEILING_S contributes only from runs whose verdict passed ===")
    print(f"  APPLIED IN classify(): {drops['dropped_x']} record(s) dropped from "
          f"{len(drops['dropped_x_runs'])} run(s). The per-run table follows.")
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


def _entry_phase(entry) -> str:
    """The cold/warm half a manifest entry's records land in, per section 7.2.

    The same derivation `_cell_key` applies to a record, applied to the PATTERN instead:
    an entry whose pattern matches its scenario's cold `what` is the cold half and every
    other `BRING_UP_CEILING_S` entry in that scenario is the warm one.
    """
    cold = manifest_module.COLD_BRING_UP_WHAT.get(entry.scenario)
    if cold is not None and entry.ceiling_name == "BRING_UP_CEILING_S":
        return "cold" if entry.pattern.match(cold) else "warm"
    return "-"


def _entry_contributes(entry) -> bool:
    """Do this entry's records survive rule A and section 2.3's leg filter?

    Rule E's `k of n` has to be the `k of n` OF THE RECORDS THE MARGIN WAS COMPUTED FROM
    (section 7.1), so an entry whose records `classify` drops wholesale must not be
    counted into the cell's denominator. Both exclusions name a concrete `what`, so the
    entry's own pattern is tested against it rather than against a hand-written list:
    rule A keeps only `RULE_A_WHAT`, and section 2.3 keeps only the `piece ` prefix.
    """
    if entry.scenario == "bringup" and entry.ceiling_s == 240.0:
        return bool(entry.pattern.match(manifest_module.RULE_A_WHAT))
    if entry.scenario == "continuous_line" and entry.ceiling_s == 420.0:
        return bool(entry.pattern.match(f"{manifest_module.LEG_WHAT_PREFIX}1: probe"))
    return True


def expectations(runs: list[dict], root: Path) -> dict:
    """Rule E's `k of n`, keyed by the SAME cell key section 7.2's margin uses.

    Section 7.1: "every margin computed from a pattern carries the `k of n` of the records
    it was computed from, in the same table cell as the margin. A margin resting on a
    fraction of its expected records is not wrong, but it is a different claim from one
    resting on all of them, and the reader is not asked to work out which they are looking
    at." `rule_e` above prints the per-run table; this is the same count folded onto the
    cells, which is where the requirement actually bites -- threat 12's case is a
    `LEG_CEILING_S` margin resting on 2 of 30 legs printing `n=2` with nothing saying 30
    were expected.

    `n` is summed over EVERY admitted run of that (scenario, condition), including a run
    that emitted none of them: an absent expected key is absent, not zero, and a
    denominator that only counted the runs that answered would hide exactly that.
    """
    table: dict[tuple[str, str, str, str], dict] = {}
    for run in runs:
        pieces = _workpieces_in_force(run)
        entries, _ = manifest_module.manifest(root, pieces["value"])
        records = run.get("records", [])
        for entry in entries:
            if entry.scenario != run.get("scenario") or not _entry_contributes(entry):
                continue
            key = (entry.scenario, entry.ceiling_name, _entry_phase(entry), run["condition"])
            cell = table.setdefault(key, {"k": 0, "n": 0, "labels": [], "patterns": []})
            cell["k"] += sum(1 for record in records if entry.matches(record))
            cell["n"] += entry.count
            if run["label"] not in cell["labels"]:
                cell["labels"].append(run["label"])
            if entry.pattern.pattern not in cell["patterns"]:
                cell["patterns"].append(entry.pattern.pattern)
    return table


def rule_d3_and_n(cells: dict, root: Path) -> None:
    """Rule D3 decides the verdict column; rule N constrains the prose around it."""
    print("\n=== Rule D3 and rule N -- what was NOT assessed, and what may not be said ===")
    entries, _ = manifest_module.manifest(root)
    wanted = set()
    for entry in entries:
        for condition in CONDITION_ORDER:
            wanted.add((entry.scenario, entry.ceiling_name, _entry_phase(entry), condition))
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
        # `or 0`, not a default: rule P discards a run whose `marker_lines` is null, and
        # this table pools the discarded runs deliberately. `.get(k, 0)` returns the None
        # that is actually stored and the sum then raises, so the whole instrument table
        # -- the one section 7.4 publishes WHATEVER the margins say -- would be lost to
        # the run that most needed reporting.
        total_lines += instrument.get("marker_lines") or 0
        total_records += instrument.get("records") or 0
        total_mangled += instrument.get("mangled_count") or 0
        print(f"  {run['label']:28s} CITE_TIMING lines={instrument.get('marker_lines')} "
              f"parsed={instrument.get('records')} "
              f"mangled={instrument.get('mangled_count')} "
              f"({instrument.get('mangled_fraction', 0.0):.3f})")
        for raw_line in instrument.get("mangled_sample", []):
            print(f"      mangled: {raw_line[:200]}")
    print(f"  POOLED: lines={total_lines} parsed={total_records} mangled={total_mangled} "
          f"zero-spin={sum(drops['zero_spin'].values())} "
          f"clock-disagreeing={len(drops['clock'])} rule-A dropped={drops['dropped_a']} "
          f"rule-X dropped={drops['dropped_x']} "
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


def predictions(
    cells: dict, drops: dict, runs: list[dict], fired: dict, collected: list[dict]
) -> None:
    """Section 7.6. A refuted prediction is a RESULT and is reported as one.

    None of the seven is a threshold; the thresholds are sections 7.1 to 7.3, and they do
    not move if a prediction fails.

    `runs` is the ADMITTED set and `collected` is every run in `raw/`, admitted or not.
    The distinction is PR6's: a mangled record is a finding about the instrument, and a
    run discarded FOR mangling is the loudest evidence there is that the instrument
    mangled something. Summing PR6 over the admitted runs alone let it print HELD over a
    campaign that had produced mangled records -- the one outcome the prediction exists to
    detect. `instrument_table` above already pools both sets for the same reason.
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

    mangled = sum(
        (run.get("instrument", {}).get("mangled_count") or 0) for run in collected
    )
    pr6 = (
        "HELD"
        if mangled == 0 and not drops["clock"]
        else "REFUTED -- a finding about the instrument in its own right"
    )
    print("  PR6  rule G's mangled count and rule K's are both zero across the campaign: "
          f"mangled={mangled} over all {len(collected)} collected run(s) "
          f"(admitted AND discarded), clock-disagreeing={len(drops['clock'])} over the "
          f"{len(runs)} admitted -> {pr6}")

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
    rule_x(admitted, drops)
    fired = fired_ceilings(admitted, raw)
    cells = margins(
        drops["kept"], fired, drops["per_cell"], expectations(admitted, root)
    )
    rule_d3_and_n(cells, root)
    rule_b1(cells)
    instrument_table(admitted, discarded, drops, root)
    predictions(cells, drops, admitted, fired, admitted + discarded)

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
