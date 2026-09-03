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
import math
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
    (
        "5",
        "**The rig quiesces between CYCLES and between BLOCKS, not between TRIALS.** "
        "`criteria.md` section 6 reads `quiesce 30 s between a teardown and the next "
        "launch` and `each is one launch`, which taken together is 104 quiesces across the "
        "105 trials. The rig sleeps 30 s at each cycle boundary inside `measure.py` (12 of "
        "them: one fewer than the cycle count in each of the seven blocks) and 30 s before "
        "each block in `run_campaign.sh` (7), which is **19 x 30 s and not 104 x 30 s**. "
        "NO DECISION QUANTITY MOVES: the rig has no simulator, no physics and no shared "
        "state between launches, every launch is a fresh process group that the previous "
        "trial's teardown has already reaped, and the quiesce is an instrument settling "
        "rather than a step of any bring-up sequence -- the runner gates on the action "
        "servers' own appearance and never on a sleep (P4). The departure is registered "
        "here because `../README.md` rule 2 and V9 require a departure from a frozen clause "
        "to be a NUMBERED DEVIATION whether or not it moves a number, and the campaign is "
        "NOT lengthened to close it: adding 85 further quiesces would add about 42 minutes "
        "of sleep to buy nothing measurable."
    ),
    (
        "6",
        "**V6 is evaluated over `w_reached` against the BLOCK'S OWN GRID STEP, and section "
        "10 states the comparison two ways.** V6 reads `the difference between two blocks "
        "at the same stop is larger than the difference between adjacent stops`; section "
        "7.1 then reads that same clause as `a between-block difference exceeding the 0.05 "
        "mm between adjacent stops`, which is the GRID STEP and not the metric's own "
        "difference between adjacent stops. This analyser takes section 7.1's reading -- "
        "the grid step -- because it is the record's own gloss on its own rule, and derives "
        "that step FROM THE BLOCK'S OBSERVED STOPS rather than from a literal, so a coarse "
        "block is compared against 0.25 mm and a fine block against 0.05 mm without a "
        "branch. The metric's observed adjacent-stop difference is PRINTED BESIDE IT so a "
        "reader can apply the other reading. Under deviation 1 a `block` here is a repeat "
        "CYCLE, which is the index the record carries."
    ),
    (
        "7",
        "**Rule B's conjuncts are evaluated over the SURVIVING repeats at each endpoint, "
        "not over the collected ones, and `criteria.md` does not disambiguate.** Rule B "
        "requires `every repeat at each of those two stops agrees with its stop's verdict` "
        "and `both stops pass V3, V4, V5, V7 and V14`. V4, V5 and V14 EXCLUDE a trial from "
        "every bracket, so by the time rule B is reached the excluded repeats are already "
        "gone -- which means the unanimity clause can print `satisfied` at n = 1 after two "
        "of three repeats were excluded. The other reading, that an excluded repeat makes "
        "the stop fail rule B outright, would make V4/V5/V14 discard the EDGE rather than "
        "the TRIAL, which is not what those rules say they do. THE SURVIVING-REPEATS "
        "READING IS TAKEN. To keep it visible rather than implicit, every BRACKETED line "
        "prints the collected and surviving n at both endpoints, and a bracket resting on a "
        "single surviving repeat is legible as one."
    ),
    (
        "8",
        "**INV1 gains a third state, NOT EVALUABLE, which `criteria.md` section 7.3 does "
        "not register.** That section reads `HELD if holding_F is identical at both "
        "commands at all four stops` and `VIOLATED otherwise`. Applied to a campaign in "
        "which an INV stop has no counterpart at the shipped command -- LO-F or HI-F absent, "
        "discarded, or that stop excluded -- `otherwise` would report VIOLATED for a "
        "comparison that was never made. Reporting HELD instead is worse and was the "
        "defect: it confirms P5 BY NOT LOOKING. The order applied is: any disagreement "
        "among the COMPARED stops gives VIOLATED and rule C applies, because `identical at "
        "all four` is then definitively false whatever the missing stops would have said; "
        "otherwise any unmatched stop gives NOT EVALUABLE; otherwise HELD, over a count of "
        "COMPARED stops. A verdict is never claimed over a comparison that did not happen."
    ),
    (
        "9",
        "**V12 is computed from the provenance's INVARIANT SUBSET and not from the "
        "dictionary as a whole.** V12 asks that `raw/provenance.txt` record the `4ef2d7c` "
        "worktree commit and the sha256 of the binary that produced `holding_S`. The "
        "`superseded` dictionary that travels on every record also carries `built_at`, "
        "which `build_superseded.sh` refreshes on EVERY build -- so a campaign whose blocks "
        "were taken across two builds of the IDENTICAL commit carries two `built_at` values "
        "and one build identity. Comparing the whole dictionary would report complete "
        "provenance as a V12 failure. V12 is therefore computed from "
        "`common.V12_IDENTITY_KEYS` -- the commit, the two source hashes, the front end's "
        "and the binary's -- and any cross-block disagreement in the REST of the "
        "dictionary is reported separately, as a note and not as a V12 finding."
    ),
    (
        "10",
        "**An unevaluable conjunct of rule B is treated as UNSATISFIED for the decision, "
        "while still printing as `not applicable`.** Rule B is a conjunction: an edge is "
        "bracketed when both stops PASS V3, V4, V5, V7 and V14 and rule U showed exactly "
        "one coarse change. A conjunct that could not be evaluated -- rule U with its "
        "coarse block absent or discarded, or V5 on an arm the rule does not cover -- is "
        "not a pass, and letting it through would claim a bracket on a conjunct nobody "
        "checked. The print keeps the three states so that `NOT satisfied` and `not "
        "applicable` stay distinguishable; only the DECISION collapses them."
    ),
    (
        "11",
        "**This analyser prints one rule `criteria.md` does not register: the frozen "
        "contract's own hash.** V1 deliberately does not watch `docs/`, so `criteria.md` "
        "-- which V9 forbids changing once the first trial has run -- lies outside every "
        "path this campaign watches. `common.snapshot` records its sha256 at both ends of "
        "every cycle, and this file compares those readings to each other and to the file "
        "on disk. IT GATES NOTHING and moves no threshold; a disagreement is a V9 finding "
        "for the write-up to carry, and it is printed as a rule either way so that the "
        "campaign's silence about its own contract is not mistaken for a check."
    ),
    (
        "12",
        "**V13's discard path is unreachable and the block dies instead.** V13 registers "
        "that a launch finding a backend other than the production one is DISCARDED. "
        "`measure.py`'s `rig_description` raises before `run_trial`'s `try`, so such a "
        "launch takes the whole block down rather than landing a `v13_ok: False` record. "
        "The consequence is stricter than the rule, not laxer -- nothing wrong is admitted "
        "-- but it COMPOUNDS an aborted block: the n reached is whatever the closed cycles "
        "hold. Recorded rather than changed, because changing it would change what a V13 "
        "failure does after the first trial has run."
    ),
    (
        "13",
        "**`run_block.sh`'s domain guard reads a failed `ros2 node list` as `domain "
        "clear`.** `ros2 node list 2>/dev/null | grep -c ...` returns 0 both when no "
        "controller manager is on the domain and when the command failed outright. The "
        "guard is inherited verbatim from a frozen ancestor and is PROTECTIVE rather than "
        "a datum -- nothing in section 7 reads it -- so it is recorded here and not "
        "changed."
    ),
    (
        "14",
        "**`common.wilson` exists and nothing calls it.** V8 registers that every count is "
        "reported over the trials that actually ran, `with a Wilson 95 % interval WHERE IT "
        "IS A PROPORTION` -- and no figure this campaign decides on is a proportion. LO1, "
        "HI1 and flip_S_lo are set memberships (a stop's verdict, a bracket's two "
        "endpoints), INV1 is an identity over eight points, FLOOR1 is a distance, and CTL "
        "carries no verdict at all. The counts that DO appear -- trials excluded by V4, V5 "
        "and V14 -- are reported as counts with their denominators beside them, and "
        "dressing a procedural exclusion as a proportion with a confidence interval would "
        "give it the appearance of a measured rate. Section 8 lists `A RATE OF ANYTHING` "
        "as not measured here. The instrument is therefore KEPT AND LEFT UNCALLED rather "
        "than deleted, so that a write-up which does report a proportion uses this one "
        "instead of reinventing it, and V8's print states on every run that the verdicts "
        "above carry none."
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
#: `criteria.md` section 10's label. `run_block.sh` tags a shakedown's files with it
#: instead of the block name whose stop kind it borrowed, so a file under `raw/shakedown/`
#: cannot be read as a campaign block's.
SHAKEDOWN_LABEL = "SHAKEDOWN"


def load_blocks(raw: Path) -> dict[str, list[dict]]:
    """Every block's trials, EXCLUDING the shakedown.

    The shakedown is not data (`criteria.md` section 10): it is excluded from every figure
    in section 7 and may not be used to set or adjust any threshold. **The exclusion is
    here, in code, and it is now three independent refusals rather than one convention.**

    1. This lists `raw/*_trials.json` at the TOP LEVEL only, so a recursive glob cannot
       sweep `raw/shakedown/` in.
    2. The `SHAKEDOWN` label is skipped wherever it is found, INCLUDING under `--raw
       raw/shakedown`, which is the invocation `README.md` documents for reading the
       shakedown back.
    3. Any row carrying `is_shakedown` is dropped, whatever its file is called.

    **Only the first of the three existed before, and it was not an exclusion.** It rests
    entirely on the operator having set `CITE_SBF_OUT` to a subdirectory: a shakedown run
    without that variable writes `LO-C_trials.json` straight into `raw/`, at the top level,
    on the campaign grid's own label, and the glob admits it as data. `README.md` and
    `raw/shakedown/NOTES.md` both said the exclusion was in code; 2 and 3 are what make
    that sentence true.
    """
    blocks: dict[str, list[dict]] = {}
    refused: list[tuple[str, int, str]] = []
    for path in sorted(raw.glob("*_trials.json")):
        label = path.name[: -len("_trials.json")]
        every = json.loads(path.read_text())
        if label == SHAKEDOWN_LABEL:
            refused.append((label, len(every), "the SHAKEDOWN label"))
            continue
        rows = [row for row in every if not row.get("is_shakedown")]
        if len(rows) != len(every):
            refused.append((label, len(every) - len(rows), "an is_shakedown row flag"))
        if rows:
            blocks[label] = rows
    # NAMED, not silent. A shakedown that is dropped without a word is indistinguishable
    # from a shakedown that was never there, and section 10 asks for the exclusion to be
    # legible -- `excluded from every figure in section 7` is a statement someone has to be
    # able to check.
    say("Shakedown rows refused (criteria.md section 10 -- IT IS NOT DATA)",
        bool(refused),
        f"{refused or 'none found'}. The shakedown may not be used to set or adjust any "
        f"threshold and is excluded from every figure in section 7. Read what it found in "
        f"raw/shakedown/NOTES.md, which is where it is published.")
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
        # V1's own sentence: "the analyser DROPS ANY ROW without it". A missing flag is a
        # ROW-level drop and not a block-level discard, and the difference decides whether
        # an aborted block reports the n it reached or reports zero.
        #
        # `measure.py` writes the flag at the close of each row's OWN CYCLE, because that
        # is the earliest instant at which V1's conjunction has a value. A block killed
        # part-way therefore leaves flagged rows for every cycle that CLOSED and unflagged
        # rows for the cycle that was open. Discarding the whole block on the unflagged
        # ones -- which is what this did -- threw away every closed cycle with them and
        # made V8's "a block that aborts early is reported with the n it reached" report
        # n = 0 permanently.
        unflagged = [row for row in rows if "v1_clean" not in row]
        rows = [row for row in rows if "v1_clean" in row]
        if unflagged:
            report["unflagged"].append((label, [row["trial"] for row in unflagged]))
        if not rows:
            report["discarded_blocks"][label] = [
                f"every trial lacks the V1 flag ({len(unflagged)} row(s)): no cycle of "
                f"this block ever closed, so V1's conjunction has no value for any of them"]
            say(f"V1/V2/V13 on block {label}", True,
                f"block contributes NOTHING -- all {len(unflagged)} row(s) carry no V1 "
                f"flag, so no cycle closed. V8: the n it reached is 0, and that is "
                f"reported rather than the block being absent.")
            continue
        dirty = [row["trial"] for row in rows if row.get("v1_clean") is False]
        disagreed = [row["trial"] for row in rows
                     if (row.get("v1") or {}).get("disagreed_mid_block")]
        v2_bad = [row["trial"] for row in rows if row.get("v2_ok") is False]
        v2_missing = [row["trial"] for row in rows if row.get("v2_ok") is None]
        v13_bad = [row["trial"] for row in rows if row.get("v13_ok") is False]
        reasons = []
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
            + (f"; V1's two readings DISAGREED on {disagreed}" if disagreed else "")
            + (f"; {len(unflagged)} row(s) DROPPED for a missing V1 flag "
               f"{[row['trial'] for row in unflagged]} -- their cycle never closed, so "
               f"this block ABORTED PART-WAY and is reported with the n it reached (V8)"
               if unflagged else ""))
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
    say("V1 (row level) -- rows carrying no v1_clean flag", bool(report["unflagged"]),
        f"{report['unflagged'] or 'none'}. criteria.md V1: THE ANALYSER DROPS ANY ROW "
        f"WITHOUT IT. A row without the flag is one whose repeat CYCLE never closed, so "
        f"V1's conjunction has no value for it; the block's CLOSED cycles are kept and the "
        f"block is reported with the n it reached (V8), which is what tells an aborted "
        f"block from an absent one.")
    report["excluded"] = excluded
    return kept, report


def rule_v6(kept: dict[str, list[dict]]) -> dict[str, bool | None]:
    """V6 -- the block effect, over `w_reached`, the campaign's one continuous metric.

    *If, for any metric, the difference between two blocks at the SAME stop is larger than
    the difference between adjacent stops, that metric's finding is DOWNGRADED TO
    INCONCLUSIVE whatever any test statistic says.* Inherited deliberately: this is the
    rule that fired on the 2026-09-01 campaign's D2.

    **V6 was registered with a decision consequence and was not implemented at all.** The
    string `V6` appeared nowhere in this harness while every other V1-V14 did, and section
    7.1's note -- *"V6 is deliberately not in the conjunction"* -- reads as though it were
    being evaluated somewhere else. It was not.

    Under deviation 1 a `block` here is a repeat CYCLE, which is the index the record
    carries. Each cycle visits each stop once, so the difference between two cycles at one
    stop IS that stop's within-stop `w_reached` spread -- the same quantity rule R reads,
    against a threshold ten times looser, which is section 7.1's reason for keeping V6 out
    of rule B's conjunction.

    Deviation 6 records which quantity `the difference between adjacent stops` is taken to
    be: section 7.1's own gloss, the GRID STEP, derived here from the block's observed
    stops rather than from a literal. The metric's own observed adjacent-stop difference is
    printed beside it so a reader can apply the other reading.

    Returns, per block, whether V6 fired -- `None` where it could not be evaluated.
    """
    print("\n=== V6 -- the block effect (criteria.md V6) ===")
    print("  THE METRIC IS w_reached. The verdicts LO1, HI1 and flip_S_lo are set "
          "memberships in a BOOLEAN predicate, and section 7.1 states that V6 cannot be "
          "the rule that decides a stop -- rule R binds ten times tighter on the same "
          "quantity. What V6 downgrades is a FINDING ABOUT w_reached: P2's spread claim "
          "and rule R's MIS clause. It does not touch a bracket.")
    fired: dict[str, bool | None] = {}
    for label, rows in kept.items():
        grouped = per_stop(rows)
        stops = [stop for stop in grouped if stop is not None]
        if len(stops) < 2:
            say(f"V6 on block {label}", None,
                f"{len(stops)} stop(s) with a declared position: `the difference between "
                f"adjacent stops` has no value on this block, so V6 cannot be evaluated "
                f"here. (Arm CTL declares no stop at all.)")
            fired[label] = None
            continue
        # The block's own grid step, read off its stops rather than branched on its name.
        step_mm = min(high - low for low, high in zip(stops, stops[1:]))
        worst = None
        for stop in stops:
            trials = grouped[stop]
            cycles = {row.get("cycle") for row in trials}
            spread = width_spread_m(trials)
            if spread is None or len(cycles) < 2:
                continue
            if worst is None or spread > worst[1]:
                worst = (stop, spread, sorted(cycles))
        # The metric's OWN difference between adjacent stops, printed for the other reading
        # of V6's clause (deviation 6). It is the smallest step the metric actually took.
        means = []
        for stop in stops:
            widths = [row["i1_reached_width_m"] for row in grouped[stop]
                      if row.get("i1_reached_width_m") is not None]
            means.append((stop, sum(widths) / len(widths) if widths else None))
        observed = [abs(high[1] - low[1]) * 1000.0
                    for low, high in zip(means, means[1:])
                    if low[1] is not None and high[1] is not None]
        observed_min = min(observed) if observed else None
        if worst is None:
            say(f"V6 on block {label}", None,
                f"no stop in this block has w_reached readings from two or more cycles, "
                f"so a between-cycle difference has no value here")
            fired[label] = None
            continue
        between_mm = worst[1] * 1000.0
        did_fire = between_mm > step_mm
        fired[label] = did_fire
        say(f"V6 on block {label}", did_fire,
            f"largest between-cycle w_reached difference at one stop is "
            f"{between_mm:.6f} mm, at stop {worst[0]} over cycles {worst[2]}, against this "
            f"block's own grid step of {step_mm:.3f} mm between adjacent stops"
            + ("" if observed_min is None else
               f" (the METRIC's smallest observed difference between adjacent stops is "
               f"{observed_min:.6f} mm -- deviation 6's other reading, printed so a reader "
               f"can apply it)")
            + (". THE w_reached FINDING FOR THIS BLOCK IS DOWNGRADED TO INCONCLUSIVE "
               "whatever any test statistic says: a between-cycle difference larger than "
               "the step between adjacent stops means the cycle is moving the metric more "
               "than the lever is. P2's spread claim and rule R's MIS clause on this block "
               "are INCONCLUSIVE, and section 7.1 is explicit that this does not decide a "
               "stop -- rule R does that, ten times tighter."
               if did_fire else
               ". The between-cycle difference is at or below the step between adjacent "
               "stops, so no w_reached finding on this block is downgraded."))
    return fired


def rule_v12(every: list[dict]) -> bool:
    """V12 -- the superseded predicate is a BUILD, not a rewrite.

    *`holding_S` and `flip_S_lo` contribute only if `raw/provenance.txt` records the
    `4ef2d7c` worktree commit and the sha256 of the binary that produced them. Without it,
    `holding_F` is reported alone, block LO-S does not run, FLOOR1 is reported against the
    cited floor only, and the write-up says so. V12 failing does NOT make LO1 or HI1
    unmeasurable: the gate's bullet is about F's flip.*

    **Two defects are fixed here and both mattered.** V12 was PRINTED and never applied:
    nothing gated `flip_S_lo`, FLOOR1's rig-internal form, P3 or P4 on it, which is exactly
    the list the rule names. And it was computed by collapsing the whole `superseded`
    dictionary across every record, which carries `built_at` -- refreshed on every build --
    so a campaign with COMPLETE provenance printed V12 FIRED the moment two builds of the
    identical commit had happened. It is computed from the invariant subset instead
    (deviation 9), and cross-block disagreement in the rest is reported separately.

    Returns whether V12 holds.
    """
    identities = {common.v12_identity(row.get("superseded")) for row in every}
    detail = {
        "identities": [dict(zip(common.V12_IDENTITY_KEYS, identity))
                       for identity in sorted(identities, key=str)],
        "built_at": sorted({(row.get("superseded") or {}).get("built_at")
                            for row in every}, key=str),
    }
    one = len(identities) == 1
    identity = dict(zip(common.V12_IDENTITY_KEYS, next(iter(identities)))) if one else {}
    holds = bool(
        one
        and identity.get("worktree_commit_short") == common.SUPERSEDED_COMMIT
        and identity.get("binary_sha256")
    )
    say("V12 -- the superseded predicate is a BUILD, not a rewrite", not holds,
        f"build identity across every record: {detail['identities']}. V12 requires the "
        f"{common.SUPERSEDED_COMMIT} worktree commit and a binary sha256, identical on "
        f"every record. "
        + ("IT HOLDS, so holding_S, block LO-S, flip_S_lo, FLOOR1's rig-internal form, P3 "
           "and P4 are evaluated below."
           if holds else
           "IT DOES NOT HOLD. holding_F is reported ALONE; flip_S_lo is NOT EVALUABLE "
           "rather than NOT BRACKETED, because the block that would produce it does not "
           "run; FLOOR1 is reported against the cited floor only; P3 and P4 are NOT "
           "EVALUABLE; and the write-up must say so. V12 failing does NOT make LO1 or HI1 "
           "unmeasurable -- the gate's bullet is about F's flip."))
    say("V12 (provenance freshness, reported apart from the rule)",
        len(detail["built_at"]) > 1,
        f"built_at across the records: {detail['built_at']}. This is NOT a V12 finding "
        f"(deviation 9): build_superseded.sh refreshes it on every build, so two values "
        f"mean the identical commit was built twice and say nothing about which predicate "
        f"produced holding_S. The build IDENTITY above is what V12 reads.")
    return holds


def rule_criteria_hash(every: list[dict], raw: Path) -> None:
    """The frozen contract's own hash -- this campaign's only defence of `criteria.md`.

    **`criteria.md` registers no such rule and this one gates nothing** (deviation 11). V1
    watches five paths and `docs/` is deliberately not among them, so the frozen contract
    lies outside every watch this campaign has -- while V9 says nothing in it changes once
    the first trial has run. `common.snapshot` records its sha256, so the reading travels
    at BOTH ENDS of every cycle on every record, and this compares those readings to each
    other and to the file on disk.

    A disagreement is a V9 finding for the write-up. It is printed either way, because a
    campaign that never looked at its own contract and a campaign that looked and found it
    unchanged produce the same silence.
    """
    print("\n=== The frozen contract (criteria.md V9; deviation 11) ===")
    readings: set[str | None] = set()
    for row in every:
        v1 = row.get("v1") or {}
        for end in ("start", "end"):
            snapshot = v1.get(end) or {}
            if "criteria_sha256" in snapshot:
                readings.add(snapshot.get("criteria_sha256"))
        if "criteria_sha256" in v1:
            readings.add(v1.get("criteria_sha256"))
    on_disk = common.sha256(raw.parent / "criteria.md")
    if not readings:
        say("criteria.md unchanged since the first trial", None,
            f"no record carries a criteria.md hash, so nothing can be compared. On disk "
            f"now: {on_disk}. Records written before this reading existed carry none.")
        return
    agree = len(readings) == 1 and next(iter(readings)) == on_disk
    say("criteria.md unchanged since the first trial", not agree,
        f"{len(readings)} distinct hash(es) across every cycle end of every record: "
        f"{sorted(readings, key=str)}; on disk now: {on_disk}. "
        + ("Every reading agrees with every other and with the file on disk, so the "
           "contract these figures were taken against is the contract that is published "
           "beside them."
           if agree else
           "THEY DISAGREE. criteria.md CHANGED while the campaign ran or after it, which "
           "V9 forbids: a threshold discovered to be wrong is applied literally and "
           "recorded as wrong, never edited. THIS GATES NOTHING HERE -- it is a V9 finding "
           "for ANALYSIS.md to carry, and the write-up must state which figures were taken "
           "under which hash."))


def rule_v7(kept: dict[str, list[dict]]) -> set[int]:
    """V7 -- the load is recorded, and a loud host is REPORTED rather than excluded."""
    print("\n=== V7 -- the load (criteria.md section 9 and V7) ===")
    flagged = {id(row) for rows in kept.values() for row in rows if row.get("v7_flagged")}
    readings = [
        (label, row["trial"], (row.get("i9") or {}).get("start") or {},
         (row.get("i9") or {}).get("end") or {})
        for label, rows in kept.items() for row in rows
    ]
    # THE REPORTED NUMBER AND THE FLAG MUST BE ABOUT THE SAME QUANTITY. `common.v7` flags
    # on ANY of the three load averages exceeding the threshold; this print scanned
    # `load_1m` ALONE, so a block flagged on its five- or fifteen-minute average was
    # reported beside a "highest reading seen" that was below the threshold -- a flag and a
    # number that contradict each other on the same line. The scan is now over the same
    # three keys, at both ends, and it names WHICH average and WHICH end it came from.
    candidates = [
        (value, f"{key} at the {end_name} of {label} trial {trial}")
        for label, trial, start, end in readings
        for end_name, reading in (("start", start), ("end", end))
        for key in ("load_1m", "load_5m", "load_15m")
        for value in [reading.get(key)]
        if isinstance(value, (int, float)) and not math.isnan(value)
    ]
    highest = max(candidates, default=None)
    say("V7 -- any load reading above "
        f"{common.V7_LOAD_THRESHOLD}", bool(flagged),
        f"{len(flagged)} of {len(readings)} kept trial(s) flagged; highest reading seen "
        f"across ALL THREE load averages at both ends "
        + ("none" if highest is None else f"{highest[0]} ({highest[1]})")
        + ". NO BLOCK IS DISCARDED FOR LOAD -- a load threshold "
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


def rule_r_mis(label: str, rows: list[dict], v6_fired: bool | None = None) -> None:
    """Rule R's second sentence, on the MIS rather than on the rest tolerance.

    *For any metric whose within-stop spread exceeds that metric's MIS, a non-detection is
    INCONCLUSIVE for that metric -- never "no difference".* The metric here is `w_reached`
    and its MIS is section 7.0's 0.100 mm. **A bracket is not an MIS**, which is why this is
    a separate print from the one above and not a second use of the same number.

    **V6's downgrade lands here, and this is where it is spent.** V6 downgrades *that
    metric's finding* to INCONCLUSIVE, and this clause is the campaign's registered
    instrument for a non-detection about `w_reached` -- so a block on which V6 fired reports
    INCONCLUSIVE here whatever the spread says. Section 7.1 is explicit that V6 may not
    decide a stop, so it reaches no bracket.
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
    over_mis = worst[1] > common.MIS_WIDTH_M
    say(f"Rule R (MIS clause) on block {label}",
        None if v6_fired else over_mis,
        f"largest within-stop w_reached spread {worst[1] * 1000.0:.6f} mm at stop "
        f"{worst[0]}, against the {common.MIS_WIDTH_M * 1000.0:.3f} mm MIS. A "
        f"non-detection under a spread above the MIS is INCONCLUSIVE for that metric and "
        f"never 'no difference'."
        + ("  -- AND V6 FIRED ON THIS BLOCK, so the w_reached finding here is INCONCLUSIVE "
           "whatever this spread says and whatever any test statistic says. That is V6's "
           "downgrade, spent where the metric's non-detection is reported; it reaches no "
           "bracket, because section 7.1 is explicit that V6 may not decide a stop."
           if v6_fired else ""))


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
           coarse_single_change: bool | None, flagged: set[int],
           r_states: dict[float | None, str] | None,
           collected: list[dict] | None = None) -> dict:
    """Rule B and rule N -- BRACKETED or NOT BRACKETED, with every conjunct printed.

    An edge is BRACKETED when two adjacent fine-grid stops 0.05 mm apart carry opposite
    verdicts of the predicate under refinement, and: every repeat at each of those two
    stops agrees with its stop's verdict; both stops pass V3, V4, V5, V7 and V14; and the
    coarse grid showed exactly one change of that same predicate in that arm (rule U).

    **`r_states` is rule R's verdict per stop, and rule B could not see it before.** Rule R
    was computed, printed and then DISCARDED at the call site, and rule B's conjuncts did
    not carry the spread clause -- so a stop rule R had just declared INDETERMINATE, on a
    `w_reached` spread above the 0.005 mm rest tolerance, still yielded BRACKETED. Rule R
    is explicit that *a bracket with an indeterminate endpoint is UNRESOLVED at 0.05 mm and
    rule N applies to that edge*, so DETERMINATE at both endpoints is a conjunct here.

    Note that rule R's OTHER clause -- the repeats disagreeing in the predicate -- overlaps
    rule B's own unanimity conjunct. Both are kept and printed separately: they are two
    registered rules and a reader must be able to see each one's answer.
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
        # RULE R, BOUND. `None` where rule R was never evaluated for this stop, which the
        # decision treats as unsatisfied (deviation 10) rather than as a pass.
        conjuncts[f"{stop}: rule R DETERMINATE"] = (
            None if r_states is None or stop not in r_states
            else r_states[stop] == "DETERMINATE")
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

    # THE DECISION TREATS `not True` AS UNSATISFIED, while the print above keeps all three
    # states (deviation 10). Rule B is a conjunction, and a conjunct that could not be
    # evaluated -- rule U with its coarse block absent or discarded, or the V5 branch -- is
    # not a pass. Filtering on `value is False` alone let an unevaluable conjunct through
    # and claimed a bracket on a clause nobody had checked.
    unsatisfied = [key for key, value in conjuncts.items() if value is False]
    unevaluable = [key for key, value in conjuncts.items() if value is None]
    if unsatisfied or unevaluable:
        say(f"Rule N on {name} (via rule B's conjuncts)", True,
            f"NOT BRACKETED. NOT satisfied: {unsatisfied or 'none'}; NOT EVALUABLE: "
            f"{unevaluable or 'none'} -- an unevaluable conjunct is not a pass, and rule B "
            f"is a conjunction (deviation 10). A bracket with an indeterminate endpoint is "
            f"UNRESOLVED at {common.BRACKET_STEP_MM} mm and rule N applies to this edge.")
        return {"verdict": "NOT BRACKETED", "interval": (low, high),
                "reason": f"unsatisfied {unsatisfied}; unevaluable {unevaluable}"}

    # The half-open interval, oriented so that the CLOSED end is the side on which the
    # predicate is true -- which is section 2.2's own notation for the three predicted
    # brackets.
    rising = stop_verdict(grouped[high], predicate) is True
    notation = f"({low}, {high}]" if rising else f"[{low}, {high})"
    # DEVIATION 7, printed on the line the verdict is on. Rule B's conjuncts are evaluated
    # over the SURVIVING repeats, so a `satisfied` unanimity clause at n = 1 after two of
    # three repeats were excluded is legible as one rather than implicit.
    collected_at = per_stop(collected) if collected else {}
    counts = [(stop, len(collected_at.get(stop, [])), len(grouped[stop]))
              for stop in (low, high)]
    say(f"{name}: BRACKETED", False,
        f"{notation} mm, width {common.BRACKET_STEP_MM} mm. A bracket narrower than "
        f"{common.BRACKET_STEP_MM} mm is NOT claimed, because the grid cannot produce one. "
        f"Repeats behind the endpoints: "
        f"{[(stop, [row.get(predicate) for row in grouped[stop]]) for stop in (low, high)]}"
        f". n per endpoint, COLLECTED vs SURVIVING: "
        + ", ".join(f"{stop}: {taken} collected / {alive} surviving"
                    for stop, taken, alive in counts)
        + ". Rule B's conjuncts are evaluated over the SURVIVING repeats (deviation 7), so "
          "read the second number as the n this bracket rests on."
        + ("  ** AT LEAST ONE ENDPOINT RESTS ON A SINGLE SURVIVING REPEAT. **"
           if any(alive < 2 for _, _, alive in counts) else ""))
    return {"verdict": "BRACKETED", "interval": (low, high), "notation": notation,
            "rising": rising, "reason": None, "n": counts}


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
            f"flip_S_lo is {s_bracket['verdict']} ({s_bracket.get('reason')}), so the "
            f"rig-internal distance is not a quantity. It is a SECONDARY quantity: the "
            f"gate does not ask for it, and its absence does not make the gate's bullet "
            f"unmet. Where the reason is V12, criteria.md's own consequence applies -- "
            f"FLOOR1 is reported against the cited floor only and the write-up says so.")


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
    compared = [stop for stop in rows_by_stop if stop in shipped]
    compared_trials = sum(len(rows_by_stop[stop]) for stop in compared)
    if unmatched:
        say("INV1: stops with no shipped-command counterpart", True,
            f"{unmatched} -- the comparison cannot be made at these stops. An INV stop "
            f"whose counterpart is absent, discarded or excluded has NO left-hand side, "
            f"and a verdict read off the remaining stops would be a verdict over a "
            f"comparison that did not happen.")
    else:
        say("INV1: stops with no shipped-command counterpart", False,
            "every INV stop has a counterpart in LO-F or HI-F at the shipped command")
    if not disagreements and unmatched:
        # DEVIATION 8. The defect this replaces produced the sentence `INV1: HELD over 4
        # stop(s) and 12 trial(s)` FROM ZERO COMPARISONS: unmatched stops were `continue`d
        # before reaching `disagreements`, so with all four unmatched the list was empty
        # and HELD was printed. That confirms registered prediction P5 BY NOT LOOKING,
        # which is the exact failure section 10's opening line names.
        say("INV1", None,
            f"NOT EVALUABLE. {len(compared)} of {len(rows_by_stop)} INV stop(s) had a "
            f"shipped-command counterpart to compare against; {unmatched} had none. "
            f"criteria.md section 7.3 registers HELD as `holding_F identical at both "
            f"commands AT ALL FOUR STOPS`, and this campaign cannot say that over stops it "
            f"never compared. NO DISAGREEMENT WAS FOUND AMONG THE {len(compared)} COMPARED "
            f"STOP(S) -- which is not the same sentence as INV1 HELD, and P5 is NOT "
            f"EVALUABLE rather than confirmed. Rule C's applicability is undecided.")
        return
    if disagreements:
        say("INV1", True,
            f"VIOLATED at {disagreements}. RULE C APPLIES: the shipped predicate's verdict "
            f"depends on a value criteria.md section 2 reads it as not consuming. Nothing "
            f"is re-run, no constant is touched, and no bracket derived at either command "
            f"is quietly preferred over the other -- BOTH brackets are reported, and LO1 "
            f"and HI1 are reported at the shipped command with the disagreement stated on "
            f"the same line."
            + (f" NOTE: {unmatched} could not be compared at all; VIOLATED does not depend "
               f"on them, because `identical at all four stops` is already false."
               if unmatched else ""))
    else:
        say("INV1", False,
            f"HELD over {len(compared)} COMPARED stop(s) and {compared_trials} compared "
            f"trial(s), out of {len(rows_by_stop)} INV stop(s) and {len(inv_rows)} INV "
            f"trial(s): holding_F is identical at both commands at every compared stop, "
            f"over all repeats. THE COUNT IS OF COMPARISONS MADE, not of trials collected. "
            f"Rule C does not apply.")


def ctl_rows(kept: dict[str, list[dict]], blocks: dict[str, list[dict]],
             discarded: dict) -> tuple[list[dict], str]:
    """CTL's rows, and WHERE THEY CAME FROM -- with the block-level discard refused.

    Section 7.4 is a reporting requirement, so falling back from the surviving set to the
    COLLECTED set is right when CTL's trials were removed by V4 and V14: those two rules
    exclude a trial FROM EVERY BRACKET, CTL contributes to no bracket, and on a rig with no
    stop they fire structurally rather than on a fault.

    **It is wrong for a block-level discard.** V1, V2 and V13 do not exclude a trial from a
    bracket -- they say the block was taken against a tree, a description or a backend this
    campaign cannot vouch for, and its numbers are not this campaign's. Reporting them
    anyway, which the bare `kept or blocks` fallback did, publishes a table from a block
    the admission stage had just thrown away.
    """
    if "CTL" in discarded:
        return [], "discarded"
    if kept.get("CTL"):
        return kept["CTL"], "surviving"
    if blocks.get("CTL"):
        return blocks["CTL"], "collected"
    return [], "absent"


def ctl(kept: dict[str, list[dict]], blocks: dict[str, list[dict]],
        discarded: dict) -> None:
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
    rows, source = ctl_rows(kept, blocks, discarded)
    if source == "discarded":
        say("CTL", None,
            f"NOT REPORTED. Block CTL was DISCARDED by V1, V2 or V13 "
            f"({discarded.get('CTL')}). Those are BLOCK rules: they say this block was "
            f"taken against a tree, a description or a backend this campaign cannot vouch "
            f"for, so its numbers are not this campaign's. The fallback to the COLLECTED "
            f"trials exists for V4's and V14's structural exclusions on this arm and NOT "
            f"for a block-level discard.")
        return
    if not rows:
        say("CTL", None, "no CTL trials in raw/")
        return
    if source == "collected":
        print("  These are read from the COLLECTED trials rather than from the surviving "
              "set. CTL declares no stop, so the joint is not at rest: I3 samples it later "
              "than I1 and I4's second command moves it further, which makes V4 and V14 "
              "fire STRUCTURALLY here. Those two rules exclude a trial FROM EVERY BRACKET, "
              "and CTL contributes to no bracket, so nothing is lost -- but the exclusion "
              "is named rather than left to look like a rig failure.")
    print("  TWO REST POSITIONS ARE PRINTED AND THEY ARE DIFFERENT QUANTITIES. Section "
          "7.4's registered one is WHERE THE CONTROLLER TERMINATED -- I1's reached width "
          "carried back through the shipped gripper_position_for, which is what P6's "
          "computed 0.300 rad is a prediction about. I3 is the last /joint_states sample "
          "at or before the result arrived; on this arm THERE IS NO STOP, so the joint is "
          "not at rest and I3 can be sampled later and further along than where the "
          "controller finished. Reading I3 as the rest position compares P6 against the "
          "wrong number.")
    for row in rows:
        print(f"    trial {row['trial']}: w_cmd {row.get('w_cmd_m')} m, "
              f"w_reached {row.get('i1_reached_width_m')} m, "
              f"terminated(I1) {row.get('i1_position_rad')} rad, "
              f"I3 sample {row.get('i3_q_at_rest_rad')} rad, "
              f"stalled {row.get('stalled')}, reached_goal {row.get('reached_goal')}, "
              f"holding_F {row.get('holding_F')}, holding_S {row.get('holding_S')}, "
              f"stop warning {row.get('i5_stop_announced')}")
    warned = any(row.get("i5_stop_announced") for row in rows)
    say("CTL: a stop warning appeared", warned,
        "section 7.4 requires that none appear, and "
        + ("one DID" if warned else "none did"))


def p6(kept: dict[str, list[dict]], blocks: dict[str, list[dict]],
       discarded: dict, v12_holds: bool) -> None:
    """P6 -- CTL's registered outcome, computed from L0 and reproduced or not.

    **P6 has SIX registered terms and this tested four.** Section 7.5 registers *`stalled =
    true`, `reached_goal = false`, a rest position of about 0.300 rad -- 60.915 mm of
    opening -- and therefore `holding_F = false`, the rest lying above `edge_hi`, with
    `holding_S = true`; and no stop warning.* The stop-warning term is folded in here. The
    rest term is STATED AND NOT TESTED, because `about` carries no registered tolerance and
    inventing one after the data exists is a threshold chosen by the data (V9, section 0).

    **The rest quantity printed is where the controller TERMINATED**, not I3's later
    `/joint_states` sample. Section 7.4 asks for `the rest position in radians beside P6's
    computed 0.300 rad`, and P6's 0.300 rad is `stall_timeout x max_drive_rate_rad_s` --
    the position at which the controller stopped driving. Arm CTL declares no stop, so the
    joint is not at rest and I3 is sampled later and further along; comparing P6 against it
    compares the prediction with the wrong number. Both are printed.
    """
    rows, source = ctl_rows(kept, blocks, discarded)
    if source == "discarded":
        say("P6", None,
            "block CTL was DISCARDED by V1, V2 or V13, so there is no CTL result this "
            "campaign vouches for to compare the prediction against")
        return
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
        "stop_warning": {bool(row.get("i5_stop_announced")) for row in rows},
    }
    terminated = [row.get("i1_position_rad") for row in rows]
    i3_samples = [row.get("i3_q_at_rest_rad") for row in rows]
    terms = {
        "stalled = true": outcome["stalled"] == {True},
        "reached_goal = false": outcome["reached_goal"] == {False},
        "holding_F = false": outcome["holding_F"] == {False},
        # V12 gates `holding_S`: without the superseded BUILD it is `None` on every record,
        # and a term read off an absent instrument is not a term that was tested.
        "holding_S = true": (outcome["holding_S"] == {True}) if v12_holds else None,
        "no stop warning": outcome["stop_warning"] == {False},
    }
    for term, value in terms.items():
        say(f"P6 term: {term}", value is not True,
            {True: "reproduced", False: "NOT reproduced",
             None: "not evaluable -- V12 does not hold, so holding_S is absent"}[value])
    say("P6 term: rest about 0.300 rad", None,
        f"STATED, NOT TESTED. Registered as `about {rest_rad} rad "
        f"({(expected.get('rest_width_m') or 0) * 1000.0:.3f} mm)`, and `about` carries NO "
        f"REGISTERED TOLERANCE. Choosing one now would be a threshold chosen by the data "
        f"(V9, section 0). Observed, where the controller TERMINATED (I1 through the "
        f"shipped gripper_position_for): {terminated}. Observed, I3's later /joint_states "
        f"sample, which is a DIFFERENT QUANTITY on an arm with no stop: {i3_samples}. The "
        f"write-up states the difference and does not convert it into a pass or a fail.")
    matches = all(value is True for value in terms.values())
    say("P6", not matches,
        f"registered: stalled=true, reached_goal=false, rest about {rest_rad} rad, "
        f"holding_F=false, holding_S=true, no stop warning -- SIX terms, of which five "
        f"have a truth value and the rest term is stated only. Observed: {outcome}. "
        + ("Reproduced -- and section 7.4 says this is a RIG CHECK AND NOT A RESULT: it "
           "says the fixture behaves as the published mechanism says, and nothing more."
           if matches else
           "NOT reproduced on every evaluable term. That is a datum about the plugin and "
           "is reported as one, WITHOUT attribution and without any reading about "
           "open-work #25 in either direction."))


# ---------------------------------------------------------------------------
# The predictions
# ---------------------------------------------------------------------------
def predictions(brackets: dict, kept: dict[str, list[dict]], window: dict,
                floor_m: float | None, blocks: dict[str, list[dict]],
                v12_holds: bool, v6_fired: dict[str, bool | None]) -> None:
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
        """Whether this block has SURVIVING trials, not whether a file was collected.

        A block that was collected and then wholly discarded by V1, V2 or V13, or whose
        every trial was excluded by V4, V5 or V14, produces no evidence at all -- and
        keying a prediction's evaluability on `blocks` made it REFUTED or CONFIRMED on no
        data. `kept` is the set the verdicts above are computed over, so it is the set the
        predictions about those verdicts are evaluable over.
        """
        return bool(kept.get(label))

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
          f"FINDING ABOUT THE RIG."
        + (f"  -- V6 FIRED on block(s) "
           f"{[label for label, value in v6_fired.items() if value]}, so the w_reached "
           f"finding on those blocks is INCONCLUSIVE whatever this line reads. P2 is a "
           f"prediction ABOUT w_reached, so the write-up carries the downgrade with it."
           if any(v6_fired.values()) else ""))

    floor_mm = None if floor_m is None else floor_m * 1000.0
    p3_ok = (
        s["verdict"] == "BRACKETED" and floor_mm is not None
        and s["interval"][0] < floor_mm < s["interval"][1]
        and lo["verdict"] == "BRACKETED" and lo["interval"][0] >= s["interval"][1]
    )
    # P3 IS A CONJUNCTION OVER TWO BLOCKS: `flip_S_lo` is BRACKETED at (47.10, 47.15] AND
    # `flip_F_lo` LIES ABOVE IT. The second half is LO-F's, so guarding only on LO-S
    # printed P3 REFUTED whenever LO-F was absent -- refuting a prediction on the strength
    # of a block that was never run. And without V12 there is no superseded build, so LO-S
    # does not run at all and P3 has no subject.
    p3_evaluable = v12_holds and ran("LO-S") and ran("LO-F")
    say("P3", None if not p3_evaluable else not p3_ok,
        f"flip_S_lo = {s['verdict']} {s.get('notation')} against the computed floor "
        + ("(absent)" if floor_mm is None else f"{floor_mm:.6f} mm")
        + f"; flip_F_lo = {lo.get('notation')}. Refuted by either bracket landing "
          f"elsewhere, or flip_F_lo below flip_S_lo."
        + ("" if p3_evaluable else
           "  -- NOT EVALUABLE: P3 needs BOTH halves, and "
           + ("V12 does not hold, so block LO-S does not run. " if not v12_holds else "")
           + ("LO-S has no surviving trials. " if v12_holds and not ran("LO-S") else "")
           + ("LO-F has no surviving trials, so `flip_F_lo lies above it` has no "
              "left-hand side. " if not ran("LO-F") else "")))

    wide_false = [
        (label, row["trial"], row.get("w_stop_mm"))
        for label in ("HI-C", "HI-F")
        for row in kept.get(label, [])
        if row.get("holding_S") is False
    ]
    wide_unknown = any(row.get("holding_S") is None
                       for label in ("HI-C", "HI-F") for row in kept.get(label, []))
    wide_rows = [row for label in ("HI-C", "HI-F") for row in kept.get(label, [])]
    # V12 GATES P4. Without the superseded build `holding_S` is `None` on every record, so
    # `wide_false` is empty and P4 would print `did not fire` -- surviving as a prediction
    # by having no instrument, which is the shape section 10's opening line refuses.
    say("P4", None if not (v12_holds and wide_rows) else bool(wide_false),
        f"holding_S is false on {len(wide_false)} wide-arm trial(s): {wide_false or 'none'}"
        + ("; some wide-arm trials carry no holding_S at all (V12)" if wide_unknown else "")
        + ". The superseded predicate is a half-line with no upper edge at all, so any "
          "wide-arm trial with holding_S false refutes this."
        + ("" if v12_holds else
           "  -- NOT EVALUABLE: V12 does not hold, so holding_S was never computed and "
           "this prediction has no instrument. An empty list of counter-examples read off "
           "an absent measurement is not a surviving prediction.")
        + ("" if wide_rows or not v12_holds else
           "  -- NOT EVALUABLE: no wide-arm trial survived."))

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
    print("\n=== The four L0 statements option F is made of, as the records carry them ===")
    print(f"  declared part interval : {parts}")
    print(f"  window                 : {window}")
    print(f"  computed floor         : {floor_m}")
    if window == {} or floor_m is None:
        print("  NOTE: the blocks disagree about one of these, or none carries it. Every "
              "figure below that needs it is reported NOT EVALUABLE rather than computed "
              "from a value this file chose.")

    v12_holds = rule_v12(every) if every else False
    if not every:
        say("V12 -- the superseded predicate is a BUILD, not a rewrite", None,
            "no records at all, so there is no provenance to read")
    # V12 gates the FLOOR as well as the block. `floor_m` is solved by bisection ON THE
    # SUPERSEDED BUILD's own answer, so without that build it is not a quantity this
    # campaign computed and FLOOR1 falls back to the cited floor only.
    if not v12_holds:
        floor_m = None

    kept, admission = admit(blocks)
    discarded = admission["discarded_blocks"]
    flagged = rule_v7(kept)
    v6_fired = rule_v6(kept)
    rule_criteria_hash(every, raw)

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

    # THE ONE TABLE. `common.REFINED_PREDICATE` is the registered mapping from a refinement
    # block to the predicate it refines, and this file restated it twice as literals -- a
    # value in two places, which is exactly what P1 forbids and what rules B, U and R being
    # GENERIC in the predicate was supposed to prevent. Each edge is named once, with its
    # fine block, its coarse block, and the predicate read out of `common`.
    edges = tuple(
        (name, fine, coarse, common.REFINED_PREDICATE[fine])
        for name, fine, coarse in (
            ("LO1", "LO-F", "LO-C"),
            ("HI1", "HI-F", "HI-C"),
            ("flip_S_lo", "LO-S", "LO-C"),
        )
    )

    print("\n=== Rule U -- one flip, or none claimed (criteria.md section 7.1) ===")
    coarse_single: dict[tuple[str, str], bool | None] = {}
    for _, _, label, predicate in edges:
        if (label, predicate) in coarse_single:
            continue
        rows = kept.get(label)
        if predicate == "holding_S" and not v12_holds:
            say(f"Rule U on {label} ({predicate})", None,
                "V12 does not hold, so holding_S was never computed. Every stop's verdict "
                "in it is absent, which a change-counter reads as `no change at all` -- a "
                "silence that would be indistinguishable from a measured one.")
            coarse_single[(label, predicate)] = None
            continue
        if not rows:
            say(f"Rule U on {label} ({predicate})", None,
                "no surviving trials in this coarse block")
            coarse_single[(label, predicate)] = None
            continue
        coarse_single[(label, predicate)] = rule_u(label, rows, predicate)

    print("\n=== Rule R -- resolution (criteria.md section 7.1) ===")
    print("  RULE R'S RESULT IS BOUND AND CARRIED INTO RULE B. A stop declared "
          "INDETERMINATE here is an endpoint rule B may not bracket on: criteria.md is "
          "explicit that a bracket with an indeterminate endpoint is UNRESOLVED at "
          "0.05 mm and that rule N applies to that edge.")
    rule_r_states: dict[tuple[str, str], dict] = {}
    for label, rows in kept.items():
        for predicate in ("holding_F", "holding_S"):
            if predicate == "holding_S" and not v12_holds:
                continue
            rule_r_states[(label, predicate)] = rule_r(label, rows, predicate)
        rule_r_mis(label, rows, v6_fired.get(label))

    brackets = {}
    for name, label, coarse_label, predicate in edges:
        if predicate == "holding_S" and not v12_holds:
            print(f"\n--- {name}: rule B over block {label}, refining {predicate} ---")
            say(f"{name}", None,
                f"NOT EVALUABLE. criteria.md V12: without the superseded BUILD, holding_F "
                f"is reported ALONE and BLOCK {label} DOES NOT RUN. This is NOT `NOT "
                f"BRACKETED` -- rule N is a refusal about DATA, and there is no data here "
                f"because the block the rule would read was never taken. FLOOR1 is "
                f"reported against the cited floor only and the write-up says so. V12 "
                f"failing does NOT make LO1 or HI1 unmeasurable.")
            brackets[name] = {"verdict": "NOT EVALUABLE", "interval": None,
                              "reason": "V12 does not hold; block LO-S does not run"}
            continue
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
        brackets[name] = rule_b(
            name, label, rows, predicate,
            coarse_single.get((coarse_label, predicate)), flagged,
            rule_r_states.get((label, predicate)), blocks.get(label))

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
    ctl(kept, blocks, discarded)

    predictions(brackets, kept, window, floor_m, blocks, v12_holds, v6_fired)
    p6(kept, blocks, discarded, v12_holds)

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
