#!/usr/bin/env python3
"""`criteria.md` section 7's decision rules, applied to `raw/`.

DERIVED IN SHAPE FROM `docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py`,
copied at commit `8a35a03` -- the commit that file last landed at -- which took the shape
from the 2026-09-02 campaigns' analysers:
**one function per registered threshold, the rule prints even when it does not fire, and a
`DEVIATIONS` tuple at module top printed on every run**. That directory is FROZEN
(`docs/measurements/README.md` rule 2) and nothing in it is edited from here. Every rule
below is this campaign's own.

WRITTEN BEFORE THE FIRST TRIAL, which is the whole point. A rule implemented after the data
has been seen is a rule chosen by the data, and `criteria.md` V9 forbids moving one
afterwards: a threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong, as
a numbered deviation in `ANALYSIS.md`, against data already collected.

EVERY RULE PRINTS WHETHER OR NOT IT FIRES. A rule that only speaks when it triggers is a rule
nobody can audit, and a reader cannot tell it from a rule that was never implemented. `None`
is a THIRD state and is not `False`: it means the rule could not be evaluated over the trials
that ran, which is a different sentence from "it was evaluated and was silent".

IT READS THE VALIDITY FLAGS OFF THE RECORD AND RE-DERIVES NONE OF THEM. V1's flag is the
conjunction of two `git` readings taken at both ends of the block where the block was taken;
V2's and V3's come from the description the running node published; V5's identity was
evaluated on the unrounded doubles inside the recorder's own process. Re-deriving any of them
here would ask a tree, and a cell, that have since gone away.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, moves no tolerance,
proposes no value and chooses nothing (`criteria.md` section 0). It prints what the
registered rules say about the trials that ran, and stops. `ANALYSIS.md` is written from that
print, later, by someone else.

**THE PRINT IS THE PRODUCT AND IT IS LONG.** Redirect it to a file; do not pipe it through
`head`. A previous campaign's operator piped a 1034-line report through `head`, saw 143
lines, and `tee` still reported exit 0.

    python3 docs/measurements/2026-09-04-following-error/harness/analyse.py \\
        > /tmp/following_error_analysis.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

#: `criteria.md` V9 -- the deviations known BEFORE the first campaign trial ran. A deviation
#: is where an interpretation had to CHANGE or had to be made concrete, applied literally to
#: data already collected. **None of these moves a threshold.** They are printed at the top of
#: every run so that the write-up carries them and cannot quietly drop one.
DEVIATIONS: tuple[tuple[str, str], ...] = (
    (
        "1",
        "**`load_active` is evaluated as a statement about every INSTANT of arm_1's moving "
        "window, not about a single load goal.** `criteria.md` section 3 registers it as "
        "`true iff both load arms had an accepted, unfinished MoveTo goal for the whole of "
        "arm_1's moving window`. A load arm's own goal is comparable in length to arm_1's, so "
        "reading `a goal` as `one goal` would make the flag structurally false on almost "
        "every trial and CONC1 unevaluable by construction -- a rule that can only ever "
        "return one answer. The harness therefore takes the UNION of each load arm's accepted "
        "goal intervals, in the controller's own simulated clock, and requires it to cover "
        "the window. Both readings are recoverable from the record: every interval is "
        "published, and `covered_fraction` is reported beside the flag. No threshold moved."
        " **THE UNION INCLUDES THE GOAL THAT WAS STILL RUNNING WHEN THE SNAPSHOT WAS TAKEN, "
        "closed at the reading's own simulated instant.** A closed interval only exists once "
        "a goal has RETURNED, and arm_1's moving window ends while a load arm is mid-goal on "
        "almost every trial, so an arm publishing closed intervals alone is silent about "
        "exactly the goal that spans the window's tail -- `load_active` was systematically "
        "false there, and CONC1's population is `load_active is True`. `open_goal` and "
        "`snapshot_sim_t` travel on every load-arm snapshot, so the closed goals and the "
        "synthesised tail are separable by any reader."
    ),
    (
        "2",
        "**Rule L's four clauses and V5's identity are COMPUTED WHERE THE BLOCK IS TAKEN and "
        "their outcomes travel on the record; this file applies section 7.0's thresholds to "
        "the quantities those computations published.** V5's tolerance is 1e-9 rad, an "
        "arithmetic identity in double precision, and the per-sample arrays published in "
        "`raw/` are rounded to 9 decimal places for readability -- so an identity check "
        "re-run here would be a check on the rounding and not on the message. The unrounded "
        "check is the one that ran, inside the recorder's process, and `v5_share`, "
        "`l_iv_peak_ok` and the four clause flags are what it produced. No threshold moved, "
        "and no rounding is compared against anything in section 7."
    ),
    (
        "3",
        "**A trial's `is_shakedown` flag, its file name and its label are three independent "
        "refusals and all three are implemented.** `criteria.md` section 10 says the "
        "shakedown is not data. A convention that rested only on which directory the operator "
        "redirected the run into is not an exclusion, and the 2026-09-03 campaign recorded "
        "that discovery; this analyser lists `raw/*_trials.json` at the TOP LEVEL only, skips "
        "the `SHAKEDOWN` label wherever it is found, and drops any row carrying "
        "`is_shakedown` whatever its file is called."
    ),
    (
        "4",
        "**V1's flag is written to the rows by a SEAL at the end of the block rather than "
        "stamped on each row as it is written.** V1 requires the conjunction of two `git` "
        "readings taken at both ends of the block, and the closing reading does not exist "
        "while the block is running. Rows therefore carry `v1_clean = None` until the harness "
        "seals them -- at the end of the block, or as the FIRST act of its abort path, which "
        "is what V1 registers so that V8's promise about an aborted block is kept. A harness "
        "that died without sealing leaves `None`, and this file drops those rows and reports "
        "the block as lost with the trial count it would have contributed. That is V1's own "
        "sentence, implemented; no threshold moved."
    ),
    (
        "5",
        "**`criteria.md` section 6 says a work-piece is spawned at the start of each CARRY "
        "CYCLE and removed at the end of that cycle; the harness removes it immediately after "
        "the cycle's `Place` rather than after CONC's four goals.** Both are inside the "
        "cycle, and the part is on the conveyor infeed either way. Removing it before CONC "
        "means arm_2 -- whose station picks from `conveyor_1`'s outfeed -- cannot encounter a "
        "part left by CARRY, so CONC's load condition is the same in every cycle instead of "
        "differing between the first and the rest. NO DECISION QUANTITY MOVES: nothing in "
        "section 7 reads the part, and CARRY's own two trials are complete before the removal."
    ),
    (
        "7",
        "**A NON-TRIAL REPOSITIONING MOVE PRECEDES EACH ARM'S REGISTERED GOAL SET, and it is "
        "a defect the one permitted shakedown found.** `criteria.md` section 3 registers "
        "CRUISE, FAST and CONC as `home -> above pick -> above place -> home` and section 6 "
        "puts those sets back to back, so FAST opens with `home` immediately after CRUISE "
        "ended at `home`: the 2026-09-04 shakedown recorded 14 samples and a peak of exactly "
        "0.000000 for that goal -- an instrument loss under rule L clauses L-i and L-iii, "
        "**one FAST trial in four by construction**, which is 25 % against rule L's 20 % "
        "ceiling and would have made FAST NOT ADMISSIBLE before the campaign began. It also "
        "broke section 3's own controlled comparison: CONC's control is CRUISE and `arm_1 "
        "does the identical thing in both`, while CRUISE's first goal was home-to-home and "
        "CONC's was conveyor-to-home. The harness now sends a `MoveTo` to 0.10 m above "
        "`cell_a__conveyor_1__infeed` at default scaling before each arm's set. **It is not a "
        "trial** (section 5.3), it enters no distribution, it is written to "
        "`<label>_setup.json` where no glob over `*_trials.json` can reach it, and it "
        "introduces no pose the registered sets do not already visit. NO THRESHOLD MOVED."
    ),
    (
        "8",
        "**I3(b) AND I3(c) ARE ATTRIBUTED TO arm_1 AND TO NOTHING ELSE, and this too is a "
        "shakedown finding.** Under CONC three arms are commanded at once and all three log "
        "into the one launch log. The 2026-09-04 shakedown caught `arm_3` genuinely violating "
        "its own path tolerance -- a `Position Error: <value>, Position Tolerance: <value>` "
        "line on the shared `tolerances` logger, naming no arm -- while arm_1 was mid-goal, "
        "and an unattributed scrape recorded it against arm_1's trial. **The line's SHAPE is "
        "what this deviation is about and the figure is not reprinted here**: it is a "
        "following-error reading, it belongs to a load arm about which rule T states no "
        "verdict, and a number from the shakedown does not travel in the frozen rig even "
        "where it sets nothing. It is in `raw/shakedown/` with the run that produced it. That is QUIET1 = FIRED, **the campaign's headline verdict, manufactured out "
        "of a load arm** about which rule T says no verdict is stated at all. I3(c)'s three "
        "lines all name the arm and are filtered on it. **I3(b) names no arm**: every "
        "controller manager in this cell lives in the `gz` process and shares one "
        "`tolerances` logger, so an I3(b) line is attributed by the controller warning that "
        "follows it within eight lines -- the caller that emitted it. An event that cannot be "
        "attributed is counted as UNATTRIBUTED and treated as POSSIBLY arm_1's, so it can "
        "only make a QUIET claim harder and never easier. Every other arm's event is kept in "
        "`i3_other_arm_events` and reported rather than dropped. NO THRESHOLD MOVED."
    ),
    (
        "9",
        "**The harness waits for both load arms to have had a goal ACCEPTED before arm_1's "
        "first CONC goal, and any residual coverage shortfall is published rather than "
        "closed.** The 2026-09-04 shakedown sent arm_1's first CONC goal while arm_2 was "
        "still planning its first -- `goals_sent 1, goals_accepted 0`, coverage 0.0 -- so "
        "that trial's `load_active` recorded the harness's starting order rather than the "
        "load condition. The wait is an EVENT with a ceiling and never a sleep (P4). "
        "**CORRECTED 2026-09-04, AFTER REVIEW AND BEFORE ANY CAMPAIGN TRIAL: this deviation "
        "attributed the residual to `the gaps between a load arm's consecutive goals -- "
        "planning time, and a replan after an abort`, AND THERE ARE NO SUCH GAPS.** A load "
        "arm's recorded intervals are contiguous to the microsecond -- in the shakedown's "
        "trial 14 every inter-goal gap is exactly 0.0 s on both arms -- because planning "
        "happens INSIDE the goal the interval already covers. The real cause was that the "
        "goal still in flight was published by nothing, and it is fixed rather than carried; "
        "see Deviation 1. **The prose asserted a mechanism the code did not have, and it is "
        "what would have hidden the defect.** What remains true is this deviation's own "
        "content: `covered_fraction` travels on every CONC row beside `load_active`, NO "
        "THRESHOLD MOVED, and no CONC trial is excluded for a false flag -- section 3 is "
        "explicit that a CONC trial without `load_active` is not an instrument loss."
    ),
    (
        "6",
        "**GOAL1's settle is measured from the first sample of the GOAL WINDOW, which "
        "section 7.1 defines as the first sample after the moving window's last -- not from "
        "`the last trajectory point`, which is not a field of the recorded message.** Section "
        "7.3 states the settle `from the last trajectory point`, and section 7.1 was amended "
        "on 2026-09-04 to define every domain on fields of the message precisely so that the "
        "harness could not choose one after seeing data. The two coincide up to one sample "
        "interval, which section 7.3 already registers as the resolution below which a CLEAR "
        "carries no information. No threshold moved."
    ),
    (
        "10",
        "**A TOLERANCE EVENT OUTRANKS RULE L'S REFUSAL in QUIET1 and GOAL1, and the frozen "
        "criteria can be read both ways, so BOTH READINGS ARE STATED HERE.** Reading A, "
        "applied: section 5.3 says in capitals that a trial with a path- or goal-tolerance "
        "violation is NEVER excluded and that `the arm's QUIET1 or GOAL1 verdict becomes "
        "FIRED`, and section 7.2's clause order matches -- QUIET carries the admissibility "
        "precondition explicitly, FIRED carries none, NOT ADMISSIBLE is `otherwise`. Reading "
        "B, not applied: section 7.1's rule L says that above the 20 % loss ceiling `that "
        "arm's QUIET1 and BAND1 are NOT ADMISSIBLE`, full stop, which would suppress the "
        "event. The analyser used to implement B by clause order and nothing said so. A is "
        "applied because rule L bounds what the instrument MISSED and can never unsay what it "
        "SAW, and because B lets an arm's instrument losses delete the campaign's headline. "
        "**NEITHER READING IS LOST FROM THE OUTPUT**: a FIRED verdict on a rule-L-refused arm "
        "prints `LIVE1 admissible = False` and says in capitals that the arm's quantitative "
        "distributions stay NOT ADMISSIBLE, so a reader applying B can recover B's verdict "
        "from this file's own text. NO THRESHOLD MOVED -- rule L's 20 % is untouched and "
        "still governs every distribution."
    ),
    (
        "11",
        "**A GOAL WINDOW THAT ENDED WITH THE ERROR STILL OUTSIDE THE GOAL TOLERANCE IS A "
        "MEASUREMENT, NOT A MISSING ONE, and where it cannot be resolved GOAL1 reports NOT "
        "EVALUABLE -- a value section 7.3 does not register.** `goal_settle` returns "
        "`settle_s = None` for three causes and only one is adverse; the analyser kept the "
        "non-`None` settles and fell through to CLEAR, so the strongest evidence for TIGHT "
        "this campaign can produce -- a trial that never settled, which would refute section "
        "2.2's law as well as PRED4 -- was read as a pass. `unresolved` now separates the "
        "adverse cause from the two benign ones. An unresolved settle over a goal window "
        "LONGER than the 0.25 s line proves the settle exceeded it: TIGHT, which is section "
        "7.3's own value. Over a window NO LONGER than the line the settle is unknown and "
        "unbounded, and neither CLEAR nor TIGHT is provable: the analyser states NOT "
        "EVALUABLE rather than pick one, because reading a threshold off a window that never "
        "reached it would be inventing the measurement. Section 7.3's CLEAR clause -- `every "
        "healthy trial's settle interval is <= 0.25 s` -- is what this restores. NO THRESHOLD "
        "MOVED."
    ),
    (
        "12",
        "**V6's `None` IS TREATED AS BINDING AND NOT AS `did not bind`.** `rule_v6` returns "
        "None when the block effect could not be evaluated for an arm -- one block, or no "
        "admissible trial in a second -- and its own docstring calls that a third state. "
        "CONC1 combined it with `bool()`, which collapses None onto False, so an UNCHECKED "
        "conjunct read as a SATISFIED one and CONC1 could be stated INDISTINGUISHABLE as "
        "though the block effect had been ruled out. This campaign treats an unevaluable "
        "guard as a failed guard: CONC1 is INCONCLUSIVE and its reason names the arms V6 "
        "could not be evaluated for. This is STRICTER than the frozen text, which does not "
        "say what an unevaluable V6 means. NO THRESHOLD MOVED."
    ),
    (
        "13",
        "**V3 AND V4 REFUSE A BLOCK BEFORE ITS FIRST GOAL, not only at analysis.** Both are "
        "computed where the block is taken and both used to travel on the header and be "
        "enforced only here, so a block that ran on mock hardware, or whose controller_state "
        "subscription never matched, executed all 42 of its trials and the operator learned "
        "after the whole campaign. Section 10's V4 registers that `a block that sends a goal "
        "without it is discarded`; the runner now raises before the first goal and exits "
        "non-zero, which stops the campaign and discards 0 trials instead of 42, and writes "
        "no record at all for the refused block. **THE ANALYSER STILL APPLIES V2, V3, V4, V12 "
        "AND V13 TO WHATEVER REACHES IT** and is still the authority on admission -- the "
        "refusal duplicates two of those predicates where they can still act, and replaces "
        "neither. NO THRESHOLD MOVED, and the two predicates are read from the same two "
        "readings the analyser reads."
    ),
    (
        "14",
        "**RULE R IS APPLIED OVER AN ARM'S WHOLE TRIAL SET, POOLING ITS FOUR GOAL KINDS, "
        "where section 7's rule R says `within one arm AT ONE GOAL`.** `goal_kind` is on "
        "every row, so the registered per-goal spread is computable; it is not computed. "
        "**The direction is conservative and that is why it stands**: pooling four goal kinds "
        "can only make the spread larger, so rule R binds at least as often as the registered "
        "form and CONC1 is stated INCONCLUSIVE at least as often. Narrowing it would make "
        "this campaign LESS conservative than its own frozen text after the text was frozen, "
        "which is not a change a harness makes to itself. The deviation was undeclared until "
        "2026-09-04 and is declared here rather than removed. NO THRESHOLD MOVED -- the "
        "0.005 rad minimum interesting size is untouched."
    ),
    (
        "15",
        "**V14 CHECKS THAT EVERY RECORDED STAMP IS MONOTONIC; IT DOES NOT CHECK THAT THE "
        "STAMP IS A SIMULATED ONE.** Section 10's V14 is about one clock -- that no wall-clock "
        "reading enters a simulated-time quantity -- and monotonicity is necessary for that "
        "and not sufficient: a wall clock is monotonic too. A magnitude bound would close it, "
        "and none is applied, because a bound chosen now would be a new exclusion rule added "
        "to a frozen criteria after the fact. **What stands in its place is structural**: "
        "every stamp published to a trial comes from the controller's own message and every "
        "load-arm interval from `Driver.sim_now()`, which reads the node clock under "
        "`use_sim_time`, and `criteria.md` section 7.1 defines each domain on a field of the "
        "message. That is an argument from source, not a measurement, and it is recorded as "
        "such. NO THRESHOLD MOVED."
    ),
)

#: `criteria.md` rule G, printed beside every verdict in sections 7.2 and 7.3, in that
#: record's own words rather than paraphrased.
RULE_G = (
    "RULE G -- every figure here is a property of gz_ros2_control 1.2.19's command "
    "conversion, at this gain, this controller-manager rate, this world's 1 ms step and this "
    "host, and of NOTHING ELSE. It is not a property of the arm: the lag is the plugin's, not "
    "UFACTORY's, and the coefficient that predicts the reported error is one term from the "
    "plugin and one from the controller's own lookahead. A quiet path tolerance here is NOT "
    "evidence that it stays quiet on hardware and NOT evidence that it fires there either -- "
    "open-work #20's asymmetry is not resolved in either direction by a simulation-only "
    "sample, and the word `validated` may not be used about the tolerance on either backend. "
    "It is not evidence about the firing half (criteria.md section 1.1): nothing here shows "
    "the detector CAN detect anything under this backend."
)

#: `criteria.md` rule M, printed beside every FAR verdict with that arm's achieved rate.
RULE_M = (
    "RULE M -- publish_state runs at the end of every update(), but through a realtime "
    "publisher's try_publish, and the tolerance check runs in update() WHETHER OR NOT the "
    "message is delivered. A FIRED verdict rests on a positive event the controller itself "
    "reports and is as strong as the controller; a QUIET verdict rests on the absence of that "
    "event and is equally strong; but BAND1's peak is a maximum over the samples that "
    "ARRIVED, and is a LOWER BOUND on the maximum the controller actually compared. A FAR "
    "verdict is therefore WEAKER than a SHORT one."
)

#: `criteria.md` rule N, printed wherever an arm is NOT ADMISSIBLE or NOT STRESSED.
RULE_N = (
    "RULE N -- a null is not a clearance. Where an arm is NOT ADMISSIBLE under rule L, or NOT "
    "STRESSED under rule X, this campaign's silence about it may NOT be read as agreement "
    "with section 2.2's arithmetic, as a clearance of the tolerance, or as evidence the "
    "detector behaves. The verdict names what was not tested, and open-work #20 stays open on "
    "that part."
)

#: `criteria.md` rule T, printed once above the per-arm verdicts.
RULE_T = (
    "RULE T -- the arms are not each other's evidence. A clean result in one says nothing "
    "about any other, every verdict is stated per arm, and an inconclusive one belongs in the "
    "verdict rather than in a footnote. In particular CRUISE staying quiet says NOTHING about "
    "FAST, and FAST is the arm the interesting prediction is about. Arms 2 and 3 are CONC's "
    "load and no verdict is stated about them at all."
)

#: `criteria.md` rule H, printed once.
RULE_H = (
    "RULE H -- no cross-campaign differencing. No measured figure from any other campaign is "
    "differenced against any figure here. ADR-0036's 73 mrad is admitted into section 2.2 "
    "ONLY as a DERIVATION this campaign reproduces from source, named as an agreement between "
    "two derivations, and it enters no arithmetic."
)

#: `criteria.md` section 7.2's scoping sentence, printed beside FAST's BAND1 and nowhere else.
FAST_SCOPE = (
    "ADR-0036 asks for the sample across `pick_and_place` and `continuous_line`, which run at "
    "the configured 0.35 scaling. CRUISE, CARRY and CONC are inside that scoping; FAST IS "
    "NOT. FAST is reported against the same band because the band is the only registered line "
    "there is. A SHORT on FAST does not make that record's sentence false and may not be "
    "written as though it did."
)

SHAKEDOWN_LABEL = "SHAKEDOWN"

#: `criteria.md` section 3's four arms, in section 6's registered cycle order.
ARMS = ("CRUISE", "FAST", "CARRY", "CONC")

#: LIVE1's three states, spelled ONCE. `None` is not `False`: it means the rule could not be
#: evaluated over the trials that ran, which is a different sentence from "it was evaluated
#: and was silent".
LIVE1_WORDS = {True: "ADMISSIBLE", False: "NOT ADMISSIBLE", None: "NOT EVALUABLE"}


def say(name: str, fired: bool | None, text: str) -> None:
    """One rule, printed whether or not it fired."""
    mark = {True: "FIRED    ", False: "did not fire", None: "NOT EVALUABLE"}[fired]
    print(f"  [{mark}] {name}: {text}")


def verdict(name: str, value: str, text: str) -> None:
    print(f"  [VERDICT] {name} = {value}: {text}")


def wrap(text: str, indent: str = "    ") -> str:
    """The long quoted rules, folded so that the print is readable at 100 columns."""
    words = text.split()
    lines: list[str] = []
    line = indent
    for word in words:
        if len(line) + len(word) + 1 > 98:
            lines.append(line)
            line = indent + word
        else:
            line = f"{line} {word}" if line.strip() else indent + word
    lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_blocks(raw: Path, allow_shakedown: bool) -> dict[str, list[dict]]:
    """Every block's trials, EXCLUDING the shakedown unless it is explicitly asked for.

    The shakedown is not data (`criteria.md` section 10): it is excluded from every figure in
    section 7 and may not be used to set or adjust any threshold. **The exclusion is here, in
    code, and it is three independent refusals rather than one convention.**

    1. This lists `raw/*_trials.json` at the TOP LEVEL only, so a recursive glob cannot sweep
       `raw/shakedown/` in.
    2. The `SHAKEDOWN` label is skipped wherever it is found, INCLUDING under
       `--raw raw/shakedown`.
    3. Any row carrying `is_shakedown` is dropped, whatever its file is called.

    `allow_shakedown` lifts 2 and 3 for `--shakedown-dry-run` ONLY, which exists so that the
    analyser can be shown to work end to end before the campaign's first trial, prints a
    NOT-DATA banner on every section, and refuses to run if any campaign row is present.
    """
    blocks: dict[str, list[dict]] = {}
    refused: list[tuple[str, int, str]] = []
    for path in sorted(raw.glob("*_trials.json")):
        label = path.name[: -len("_trials.json")]
        every = json.loads(path.read_text())
        if label == SHAKEDOWN_LABEL and not allow_shakedown:
            refused.append((label, len(every), "the SHAKEDOWN label"))
            continue
        rows = [row for row in every if allow_shakedown or not row.get("is_shakedown")]
        if len(rows) != len(every):
            refused.append((label, len(every) - len(rows), "an is_shakedown row flag"))
        if rows:
            blocks[label] = rows
    say(
        "Shakedown rows refused (criteria.md section 10 -- IT IS NOT DATA)",
        bool(refused),
        f"{refused or 'none found'}. The shakedown may not be used to set or adjust any "
        f"threshold and is excluded from every figure in section 7. Read what it found in "
        f"raw/shakedown/NOTES.md, which is where it is published.",
    )
    return blocks


# ---------------------------------------------------------------------------
# Admission -- the block rules, then the trial rules, each printed either way
# ---------------------------------------------------------------------------
def admit(blocks: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict]:
    """V1, V2, V3, V4, V12, V13 at the block; V1's row drop, V14 and rule L at the trial."""
    print("\n=== Admission: V1, V2, V3, V4, V12, V13, V14 (criteria.md section 10) ===")
    report: dict = {
        "discarded_blocks": {},
        "dropped_rows": {},
        "v14_excluded": {},
    }

    kept: dict[str, list[dict]] = {}
    for label, rows in sorted(blocks.items()):
        reasons: list[str] = []
        head = rows[0]
        v2 = head.get("v2") or {}
        v3 = head.get("v3") or {}
        v4 = head.get("v4") or {}
        v13 = head.get("v13") or {}

        if not v2.get("v2_ok"):
            reasons.append(
                f"V2: the running description carried {v2.get('hull_collision_refs')} hull "
                f"collision references, not {common.HULL_COLLISION_REFERENCES_EXPECTED} "
                f"(read_ok={v2.get('read_ok')}, chars={v2.get('description_chars')})"
            )
        if not v3.get("v3_ok"):
            reasons.append(
                f"V3: the backend that ran was not {common.PRODUCTION_PLUGIN} alone -- "
                f"production={v3.get('production_plugin_refs')} "
                f"fixture={v3.get('fixture_plugin_refs')} mock={v3.get('mock_plugin_refs')}"
            )
        if not v4.get("v4_ok"):
            reasons.append(
                f"V4: the controller_state subscription had "
                f"{v4.get('matched_publisher_count')} matched publisher(s) and had received "
                f"{v4.get('messages_received_before_first_goal')} message(s) before the "
                f"block's first goal"
            )
        # V13 AND V12 FAIL CLOSED, THE WAY V2, V3 AND V4 ABOVE ALREADY DO. A default of True
        # and an `== 0` test both PASS a block whose reading is missing, which is the one
        # thing a campaign built against silence must not do: a record written by a harness
        # that never took the reading would be admitted as one that took it and was clean.
        v13_within = v13.get("within_ceiling")
        if v13_within is not True:
            reasons.append(
                f"V13: an L3 server was waited on past the rig's ceiling, or the reading is "
                f"missing (within_ceiling={v13_within!r}; a reading that is absent is refused "
                f"and never assumed clean): {v13}"
            )
        v12_count = head.get("v12_gz_topic_count")
        if not isinstance(v12_count, int) or v12_count == 0:
            reasons.append(
                f"V12: the harness's Gazebo probe reached no world, or the count is missing "
                f"(v12_gz_topic_count={v12_count!r}) -- an unpartitioned `gz topic -l` "
                f"returns an empty list and exits 0, so this is the partition finding and "
                f"not a fact about the world"
            )

        if reasons:
            report["discarded_blocks"][label] = {"reasons": reasons, "trials": len(rows)}
            continue

        # V1's own sentence: "the analyser DROPS ANY ROW without it". A missing or false flag
        # is a ROW-level drop, not a block-level discard, and the difference decides whether a
        # partially sealed block loses everything or loses what it should.
        surviving = [row for row in rows if row.get("v1_clean") is True]
        if len(surviving) != len(rows):
            report["dropped_rows"][label] = {
                "dropped": len(rows) - len(surviving),
                "of": len(rows),
                "unsealed": sum(1 for row in rows if row.get("v1_clean") is None),
                "dirty": sum(1 for row in rows if row.get("v1_clean") is False),
            }
        if surviving:
            kept[label] = surviving

    say(
        "V2 -- the description that actually ran (13 hull collision references)",
        any("V2:" in r for entry in report["discarded_blocks"].values() for r in entry["reasons"]),
        f"{len(blocks) - len(report['discarded_blocks'])} of {len(blocks)} block(s) passed "
        f"every block rule; discards: {json.dumps(report['discarded_blocks'], indent=2)}",
    )
    say(
        "V3 -- THE BACKEND THAT ACTUALLY RAN",
        any("V3:" in r for entry in report["discarded_blocks"].values() for r in entry["reasons"]),
        "mock hardware mirrors commands into states and produces a following error of exactly "
        "zero, so a rig that silently ran on it would produce a perfect, perfectly "
        "meaningless silence. Every kept block asserted "
        f"{common.PRODUCTION_PLUGIN} off the description the running node published, with no "
        "fixture and no mock plugin in it.",
    )
    say(
        "V4 -- the subscription matched AND received before the block's first goal",
        any("V4:" in r for entry in report["discarded_blocks"].values() for r in entry["reasons"]),
        "reliable QoS is a promise to MATCHED subscribers. The publisher's resolved endpoint "
        "QoS travels on every block record: "
        + json.dumps(
            {
                label: (rows[0].get("v4") or {}).get("matched_publishers")
                for label, rows in sorted(kept.items())
            }
        ),
    )
    say(
        "V12 -- every Gazebo-transport call went through cite_bringup.gz (ADR-0042)",
        any("V12:" in r for entry in report["discarded_blocks"].values() for r in entry["reasons"]),
        "an unpartitioned `gz topic -l` reaches no world and EXITS 0. Topics reached per "
        "block: "
        + json.dumps(
            {label: rows[0].get("v12_gz_topic_count") for label, rows in sorted(kept.items())}
        ),
    )
    say(
        "V13 -- the cell announced readiness as an EVENT and no server was waited on past the "
        "ceiling",
        any("V13:" in r for entry in report["discarded_blocks"].values() for r in entry["reasons"]),
        "the CITE_SIDE_READY token is `run_cell_block.sh`'s gate (I5, ADR-0047, P4) and "
        "nothing in the harness sleeps to sequence bring-up. Per-block server waits: "
        + json.dumps(
            {label: (rows[0].get("v13") or {}).get("server_wait_s")
             for label, rows in sorted(kept.items())}
        ),
    )
    say(
        "V1 -- v1_clean, the conjunction of two git readings taken at both ends of the block",
        bool(report["dropped_rows"]),
        f"rows dropped for a missing or false flag: {json.dumps(report['dropped_rows'])}. "
        f"An UNSEALED row is a block whose harness died before its closing reading could be "
        f"taken; V1 registers those as a LOST BLOCK with the trial count they would have "
        f"contributed, and they are not re-run (V8).",
    )

    # V14 -- one clock. A trial whose samples carry a non-monotonic stamp is EXCLUDED and
    # REPORTED, and it is a different exclusion from rule L's instrument loss.
    final: dict[str, list[dict]] = {}
    for label, rows in sorted(kept.items()):
        good = []
        bad = []
        for row in rows:
            if row["summary"].get("v14_stamps_monotonic"):
                good.append(row)
            else:
                bad.append(row["trial"])
        if bad:
            report["v14_excluded"][label] = bad
        final[label] = good
    say(
        "V14 -- one clock; every recorded stamp is the controller's simulated time",
        bool(report["v14_excluded"]),
        f"trials excluded for a non-monotonic stamp: "
        f"{json.dumps(report['v14_excluded']) or 'none'}. A wall-clock rate is never divided "
        f"into a simulation-time error; the only place a wall clock appears in this campaign "
        f"is I9's ratio, which enters no verdict.",
    )
    return final, report


def flat(kept: dict[str, list[dict]]) -> list[dict]:
    return [row for rows in kept.values() for row in rows]


def by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    return {arm: [row for row in rows if row.get("arm") == arm] for arm in ARMS}


# ---------------------------------------------------------------------------
# 7.1 -- rule L and LIVE1
# ---------------------------------------------------------------------------
def rule_l(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Rule L, applied per trial from the quantities the block published.

    Returns (admissible, losses). A trial failing ANY of the four clauses is an INSTRUMENT
    LOSS: excluded from every distribution, counted and reported separately from every other
    exclusion, and NEVER recorded as a quiet trial.
    """
    admissible = [row for row in rows if row["summary"].get("rule_l_admissible")]
    losses = [row for row in rows if not row["summary"].get("rule_l_admissible")]
    return admissible, losses


def live1(kept: dict[str, list[dict]]) -> dict[str, dict]:
    """LIVE1 -- ADMISSIBLE / NOT ADMISSIBLE, stated per arm, BEFORE QUIET1.

    `criteria.md` section 7.1: `ANALYSIS.md` states LIVE1 before it states QUIET1, for every
    arm, so that no quietness verdict can be read without the instrument's own report beside
    it. That ordering is enforced here by this function running first and its result being
    what every later verdict is gated on.
    """
    print("\n=== 7.1 LIVE1 -- measured quiet, or measured nothing ===")
    print(wrap(
        "THE CENTRAL HAZARD. A subscriber that never matched, a topic that does not exist, a "
        "QoS mismatch, a controller that never activated, and a rig that quietly ran on mock "
        "hardware all produce the same empty or zero set -- and every one of them reads as "
        "'the tolerance stayed quiet'."))
    out: dict[str, dict] = {}
    grouped = by_arm(flat(kept))
    for arm in ARMS:
        rows = grouped[arm]
        admissible, losses = rule_l(rows)
        share = (len(losses) / len(rows)) if rows else None
        by_cause: dict[str, int] = {}
        for row in losses:
            for reason in row["summary"].get("rule_l_failed") or ["unstated"]:
                key = reason.split(" ")[0]
                by_cause[key] = by_cause.get(key, 0) + 1
        rates = [
            row["summary"].get("window_rate_per_sim_s")
            for row in rows
            if row["summary"].get("window_rate_per_sim_s") is not None
        ]
        peaks = [
            row["summary"].get("max_abs_error_rad")
            for row in rows
            if row["summary"].get("max_abs_error_rad") is not None
        ]
        counts = [row["summary"].get("window_samples") or 0 for row in rows]
        if not rows:
            state = None
        elif share is not None and share > common.L_LOSS_CEILING_SHARE:
            state = False
        else:
            state = True
        out[arm] = {
            "trials": len(rows),
            "admissible": admissible,
            "losses": losses,
            "loss_share": share,
            "loss_by_cause": by_cause,
            "state": state,
        }
        say(
            f"Rule L over {arm}",
            bool(losses),
            f"n={len(rows)} trials, {len(losses)} instrument loss(es) "
            f"({'n/a' if share is None else f'{share:.1%}'} against the "
            f"{common.L_LOSS_CEILING_SHARE:.0%} ceiling), by cause {by_cause or 'none'}; "
            f"window samples min/median/max = "
            f"{min(counts) if counts else None}/"
            f"{common.percentile([float(c) for c in counts], 50.0) if counts else None}/"
            f"{max(counts) if counts else None}; achieved rate per simulated second "
            f"min/median/max = {min(rates) if rates else None}/"
            f"{common.percentile(rates, 50.0) if rates else None}/"
            f"{max(rates) if rates else None} against the L-ii floor of "
            f"{common.L_II_MIN_RATE_PER_SIM_S}; max_j|error_j| over the arm's trials "
            f"min/max = {min(peaks) if peaks else None}/{max(peaks) if peaks else None}",
        )
        verdict(
            f"LIVE1 [{arm}]",
            LIVE1_WORDS[state],
            f"{len(admissible)} of {len(rows)} trials satisfy all four clauses of rule L"
            + (
                ""
                if state is not False
                else f" -- above the {common.L_LOSS_CEILING_SHARE:.0%} ceiling, so this "
                     f"arm's QUIET1 and BAND1 are NOT ADMISSIBLE and rule N applies"
            ),
        )
        if state is not True:
            print(wrap(RULE_N))
    return out


# ---------------------------------------------------------------------------
# 7.2 -- QUIET1, BAND1, CONC1
# ---------------------------------------------------------------------------
def tolerance_readings(row: dict) -> dict:
    """I3's three readings for one trial, each reported and none inferred from another."""
    return {
        "a_status": row.get("i3a_status"),
        "a_result_code": row.get("i3a_result_code"),
        "a_detail": row.get("i3a_detail"),
        "b_tolerance_events": row.get("i3b_tolerance_events") or 0,
        "b_joints": row.get("i3b_tolerance_event_joints") or [],
        "b_unattributed": row.get("i3b_unattributed") or 0,
        "b_unattributed_joints": row.get("i3b_unattributed_joints") or [],
        "c_path_aborts": row.get("i3c_path_aborts") or 0,
        "c_goal_time_aborts": row.get("i3c_goal_time_aborts") or [],
        "c_moveit_aborts": row.get("i3c_moveit_aborts") or [],
        "other_arms": row.get("i3_other_arm_events"),
    }


def rule_t_other_arms(rows: list[dict]) -> int:
    """Rule T -- what the OTHER arms did, reported and never read as a finding about arm_1.

    Under CONC three arms are commanded at once. A load arm's own tolerance violation is a real
    event and it is published here in full; it is **not** arm_1's, it enters no verdict, and no
    verdict is stated about arms 2 and 3 at all. The 2026-09-04 shakedown is why this function
    exists: an unattributed scrape had recorded exactly such an event as arm_1's.
    """
    print("\n=== Rule T -- events belonging to the LOAD ARMS ===")
    found = [
        {
            "trial": row["trial"],
            "block": row["block"],
            "arm_under_test": row["arm"],
            "other": row["i3_other_arm_events"],
        }
        for row in rows
        if row.get("i3_other_arm_events")
    ]
    say(
        "Load-arm tolerance events during arm_1's trials",
        bool(found),
        f"{len(found)} trial(s) had a tolerance event belonging to another arm in their log "
        f"segment: {json.dumps(found, default=str)}. These are REPORTED and are not a finding "
        f"about arm_1. A record taken before 2026-09-04's shakedown fix carries no such field "
        f"at all, and reads here as none found rather than as none present.",
    )
    return len(found)


def quiet1(live: dict[str, dict]) -> dict[str, str]:
    """QUIET1 -- QUIET / FIRED / FIRED (unassigned) / NOT ADMISSIBLE, stated per arm."""
    print("\n=== 7.2 QUIET1 -- did the path tolerance fire ===")
    out: dict[str, str] = {}
    for arm in ARMS:
        entry = live[arm]
        events = [
            row
            for row in entry["admissible"] + entry["losses"]
            if row.get("tolerance_event")
        ]
        path_attributed = [
            row
            for row in events
            if (row.get("i3c_path_aborts") or 0) > 0
            or any(
                item.get("code") == "PATH_TOLERANCE_VIOLATED"
                for item in (row.get("i3c_moveit_aborts") or [])
            )
        ]
        # ORDER: A TOLERANCE EVENT OUTRANKS RULE L'S REFUSAL. Section 5.3 registers in
        # capitals that a trial with a path- or goal-tolerance violation is NEVER excluded --
        # "an exclusion rule that filtered out the event the campaign exists to detect would
        # manufacture the silence it is trying to measure" -- and that the arm's verdict
        # BECOMES FIRED. Section 7.2's clauses read the same way: QUIET carries the
        # admissibility precondition explicitly, FIRED carries none, and NOT ADMISSIBLE is
        # "otherwise". Rule L's own sentence in section 7.1 pulls the other way, so the frozen
        # text is genuinely ambiguous; see Deviation 10, which states both readings. The
        # reading applied here keeps the positive detection, because rule L bounds what the
        # instrument MISSED and can never unsay what it SAW -- and rule L's state is reported
        # in this verdict's own reason, so the other reading is recoverable from this output.
        if path_attributed:
            value = "FIRED"
        elif events:
            value = "FIRED (unassigned)"
        elif entry["state"] is not True:
            value = "NOT ADMISSIBLE"
        else:
            value = "QUIET"
        out[arm] = value
        say(
            f"QUIET1 [{arm}] -- I3's three readings",
            bool(events),
            f"{len(events)} trial(s) produced a tolerance event on any reading; "
            f"{len(path_attributed)} attributed by I3(c) to the PATH check. Readings: "
            + json.dumps([tolerance_readings(row) for row in events], default=str),
        )
        verdict(
            f"QUIET1 [{arm}]",
            value,
            {
                "QUIET": "LIVE1 is ADMISSIBLE for this arm and no trial of it produced a "
                         "tolerance violation on any of I3's three readings",
                "FIRED": (
                    f"a violation was seen and I3(c) attributes it to the path check -- this "
                    f"is the campaign's headline and is reported in full with its whole error "
                    f"trace. Section 5.3: such a trial is NEVER excluded. Rule L's state for "
                    f"this arm is reported beside it and does not suppress the event: LIVE1 "
                    f"admissible = {entry['state']}"
                    + (
                        ". RULE L REFUSES THIS ARM'S TRIALS, so the quantitative "
                        "distributions in section 7.2 stay NOT ADMISSIBLE for it and only "
                        "the positive detection is stated here"
                        if entry["state"] is not True
                        else ""
                    )
                ),
                "FIRED (unassigned)": (
                    f"a violation was seen on I3(a) or I3(b) and I3(c) was silent; section "
                    f"2.0 shows those two readings cannot separate the path check from the "
                    f"goal-time abort, so the event is reported WITHOUT being attributed and "
                    f"is NEVER attributed by assumption. LIVE1 admissible = {entry['state']}"
                    + (
                        ". RULE L REFUSES THIS ARM'S TRIALS, so the quantitative "
                        "distributions in section 7.2 stay NOT ADMISSIBLE for it and only "
                        "the unattributed detection is stated here"
                        if entry["state"] is not True
                        else ""
                    )
                ),
                "NOT ADMISSIBLE": "rule L refuses this arm's trials, and no trial of it "
                                  "produced a tolerance violation on any of I3's three "
                                  "readings, so no quietness claim is admissible for it",
            }[value],
        )
        print(wrap(RULE_G))
    return out


def pooled(rows: list[dict], joints: list[str]) -> list[dict]:
    """Section 7.2's per-joint distribution over the moving window, POOLED across trials.

    Pooled from the published per-sample arrays rather than from the per-trial percentiles: a
    percentile of percentiles is not a percentile of anything.
    """
    columns: list[list[float]] = [[] for _ in joints]
    for row in rows:
        for sample in row["summary"].get("abs_error_series") or []:
            for index, value in enumerate(sample):
                if index < len(columns):
                    columns[index].append(value)
    out = []
    for index, joint in enumerate(joints):
        values = sorted(columns[index])
        out.append(
            {
                "joint": joint,
                "n_samples": len(values),
                "min": values[0] if values else None,
                "median": common.percentile(values, 50.0),
                "p95": common.percentile(values, 95.0),
                "p99": common.percentile(values, 99.0),
                "max": values[-1] if values else None,
            }
        )
    return out


def band1(live: dict[str, dict]) -> dict[str, str]:
    """BAND1 -- FAR / SHORT, stated per arm, against ADR-0036's own 0.100 rad line."""
    print("\n=== 7.2 BAND1 -- how far below ADR-0036's own line the healthy peak sits ===")
    out: dict[str, str] = {}
    for arm in ARMS:
        entry = live[arm]
        healthy_rows = [row for row in entry["admissible"] if row.get("healthy")]
        joints = []
        for row in healthy_rows:
            joints = row["summary"].get("joints") or []
            if joints:
                break
        distribution = pooled(healthy_rows, joints) if joints else []
        peaks = [
            (row["summary"]["max_abs_error_rad"], row)
            for row in healthy_rows
            if row["summary"].get("max_abs_error_rad") is not None
        ]
        rates = [
            row["summary"].get("window_rate_per_sim_s")
            for row in healthy_rows
            if row["summary"].get("window_rate_per_sim_s") is not None
        ]
        if entry["state"] is not True or not peaks:
            value = "NOT ADMISSIBLE" if entry["state"] is not True else "NOT EVALUABLE"
            out[arm] = value
            say(
                f"BAND1 [{arm}]",
                None,
                f"{len(healthy_rows)} healthy admissible trial(s); no peak to compare "
                f"against the {common.PATH_TOLERANCE_LINE_RAD} rad line",
            )
            verdict(f"BAND1 [{arm}]", value, "rule N applies")
            print(wrap(RULE_N))
            continue

        top, top_row = max(peaks, key=lambda pair: pair[0])
        value = "FAR" if top <= common.PATH_TOLERANCE_LINE_RAD else "SHORT"
        out[arm] = value
        say(
            f"BAND1 [{arm}] -- peak against {common.PATH_TOLERANCE_LINE_RAD} rad",
            value == "SHORT",
            f"n={len(healthy_rows)} healthy admissible trials, "
            f"{sum(row['summary']['window_samples'] for row in healthy_rows)} samples. "
            f"peak={top} rad on joint {top_row['summary']['peak']['joint']} at trial "
            f"{top_row['trial']} (block {top_row['block']}, cycle {top_row['cycle']}, "
            f"goal {top_row['goal_kind']}), with |feedback.velocities| peak "
            f"{top_row['summary']['v_peak_feedback_rad_s']} rad/s and "
            f"|reference.velocities| peak "
            f"{top_row['summary']['v_peak_reference_rad_s']} rad/s. Per-joint pooled "
            f"distribution over the moving window: {json.dumps(distribution)}",
        )
        # SECTION 7.2 ASKS FOR "the block and cycle index of EVERY peak", AND THIS PRINTS
        # EVERY ONE. It used to print the ten largest. No evidence was lost -- every
        # per-trial peak is in `raw/` -- but this print is declared to be the campaign's
        # product, and a product that silently truncates a report the criteria states
        # exhaustively is the shape that cost a previous campaign 143 lines of a 1034-line
        # print. The count is stated in the label so that the reader can check the list
        # against `n` rather than take the word "every" on trust.
        ordered = sorted(peaks, key=lambda pair: -pair[0])
        print(f"    peaks with their block and cycle -- ALL {len(ordered)} of them, "
              f"section 7.2 asks for every one: " + json.dumps(
            [
                {
                    "trial": row["trial"],
                    "block": row["block"],
                    "cycle": row["cycle"],
                    "goal": row["goal_kind"],
                    "peak_rad": peak,
                    "joint": row["summary"]["peak"]["joint"],
                }
                for peak, row in ordered
            ]
        ))
        verdict(
            f"BAND1 [{arm}]",
            value,
            f"the arm's peak |error| over all healthy trials is {top} rad against "
            f"{common.PATH_TOLERANCE_LINE_RAD} rad"
            + (
                ". A SHORT verdict is reported and acted on by NOBODY here: whether the value "
                "is wrong is ADR-0036's question and the project owner's, not this "
                "campaign's. This campaign reports the margin and proposes nothing."
                if value == "SHORT"
                else ""
            ),
        )
        if value == "FAR":
            print(wrap(RULE_M))
            print(wrap(
                f"    this arm's achieved sample rate per simulated second: "
                f"min={min(rates) if rates else None} "
                f"median={common.percentile(rates, 50.0) if rates else None} "
                f"max={max(rates) if rates else None}"))
        if arm == "FAST":
            print(wrap(FAST_SCOPE))
        print(wrap(RULE_G))
    return out


def trial_peak_median(rows: list[dict]) -> float | None:
    values = [
        row["summary"]["max_abs_error_rad"]
        for row in rows
        if row["summary"].get("max_abs_error_rad") is not None
    ]
    return common.percentile(values, 50.0) if values else None


def conc1(live: dict[str, dict], v6_fired: dict[str, bool | None]) -> str:
    """CONC1 -- INDISTINGUISHABLE / DIFFERENT / INCONCLUSIVE, stated ONCE, over arm_1 only.

    The statistic is named in `criteria.md` and is not chosen here: the MEDIAN OVER TRIALS OF
    THAT TRIAL'S PEAK `|error|`, over CONC trials carrying `load_active` and over CRUISE
    trials, both restricted to trials admissible under rule L.
    """
    print("\n=== 7.2 CONC1 -- does concurrent load move arm_1's distribution ===")
    cruise = [row for row in live["CRUISE"]["admissible"] if row.get("healthy")]
    conc_all = [row for row in live["CONC"]["admissible"] if row.get("healthy")]
    loaded = [row for row in conc_all if row.get("load_active") is True]
    unloaded = [row for row in conc_all if row.get("load_active") is not True]

    say(
        "load_active -- both load arms held an accepted, unfinished MoveTo goal across the "
        "whole of arm_1's moving window",
        bool(unloaded),
        f"{len(loaded)} of {len(conc_all)} admissible healthy CONC trials carry it; "
        f"{len(unloaded)} do not. A CONC trial without it is NOT an instrument loss -- "
        f"arm_1's samples are still arm_1's and LIVE1, QUIET1 and BAND1 use them -- it is "
        f"simply not a sample of the load condition. Coverage on the trials that lack it: "
        + json.dumps(
            [
                {
                    "trial": row["trial"],
                    "covered": [
                        {"arm": entry["arm"], "fraction": entry.get("covered_fraction")}
                        for entry in (row.get("load") or {}).get("arms", [])
                    ],
                }
                for row in unloaded
            ]
        ),
    )

    load_failures = [
        {"trial": row["trial"], "arms": [
            {"arm": entry["arm"], "failures": entry.get("failures")}
            for entry in (row.get("load") or {}).get("arms", [])
            if entry.get("failures")
        ]}
        for row in conc_all
        if any(
            entry.get("failures") for entry in (row.get("load") or {}).get("arms", [])
        )
    ]
    say(
        "Rule T -- a load arm's goal that failed is REPORTED and is not a finding about arm_1",
        bool(load_failures),
        json.dumps(load_failures) if load_failures else "no load-arm goal failed",
    )

    a = trial_peak_median(loaded)
    b = trial_peak_median(cruise)
    both_admissible = (
        live["CONC"]["state"] is True and live["CRUISE"]["state"] is True
    )
    if a is None or b is None or not both_admissible:
        say("CONC1's statistic", None,
            f"CONC (loaded) median-of-trial-peaks = {a}, CRUISE = {b}; one of the two could "
            f"not be formed")
        verdict("CONC1", "INCONCLUSIVE", "rule N applies -- the comparison could not be made")
        print(wrap(RULE_N))
        return "INCONCLUSIVE"

    difference = abs(a - b)
    conc_spread = spread(loaded)
    cruise_spread = spread(cruise)
    resolution_binds = (
        (conc_spread is not None and conc_spread > common.MIS_RAD)
        or (cruise_spread is not None and cruise_spread > common.MIS_RAD)
    )
    # V6 HAS THREE STATES AND `bool(None)` COLLAPSES TWO OF THEM. `rule_v6` returns None when
    # the block effect COULD NOT BE EVALUATED -- one block, or an arm with no admissible trial
    # in a second block -- and its own docstring calls that "a THIRD state and not False".
    # Reading it as False makes an UNCHECKED conjunct read as a SATISFIED one, and CONC1 could
    # be stated INDISTINGUISHABLE as though the block effect had been ruled out. That is the
    # unevaluable-conjunct class, and it is treated as BINDING: an unevaluable guard is not a
    # passed guard.
    v6_conc = v6_fired.get("CONC")
    v6_cruise = v6_fired.get("CRUISE")
    v6_unevaluable = [
        arm for arm, value in (("CONC", v6_conc), ("CRUISE", v6_cruise)) if value is None
    ]
    v6_binds = bool(v6_conc) or bool(v6_cruise) or bool(v6_unevaluable)

    say(
        "Rule R -- resolution, over CONC1's own statistic",
        resolution_binds,
        f"within-arm spread of the trial-peak: CONC(loaded)={conc_spread}, "
        f"CRUISE={cruise_spread}, against the {common.MIS_RAD} rad minimum interesting size. "
        f"criteria.md registers in advance that rule R is EXPECTED to bind here.",
    )
    say(
        "V6 -- the block effect over CONC1's two arms",
        v6_binds,
        f"CONC={v6_conc}, CRUISE={v6_cruise}. `None` means the block effect COULD NOT BE "
        f"EVALUATED for that arm and is treated as BINDING, not as `did not bind`: "
        f"unevaluable for {v6_unevaluable or 'neither arm'}.",
    )
    say(
        "CONC1's statistic",
        difference >= common.MIS_RAD,
        f"median-of-trial-peaks: CONC(loaded)={a} rad over n={len(loaded)}, "
        f"CRUISE={b} rad over n={len(cruise)}; |difference| = {difference} rad against the "
        f"{common.MIS_RAD} rad minimum interesting size. Reported beside it and DECIDING "
        f"NOTHING: max CONC={maximum(loaded)} CRUISE={maximum(cruise)}; "
        f"p95 CONC={p95(loaded)} CRUISE={p95(cruise)}.",
    )

    if resolution_binds or v6_binds:
        value = "INCONCLUSIVE"
        parts = []
        if resolution_binds:
            parts.append("rule R binds on the within-arm spread")
        if v6_unevaluable:
            parts.append(
                f"V6's block effect could NOT BE EVALUATED for {v6_unevaluable}, and an "
                f"unevaluable conjunct is not a satisfied one"
            )
        elif v6_binds:
            parts.append("V6's block effect binds")
        why = " and ".join(parts)
    elif difference < common.MIS_RAD:
        value = "INDISTINGUISHABLE"
        why = f"the two medians differ by {difference} rad, below {common.MIS_RAD} rad"
    else:
        value = "DIFFERENT"
        why = (
            f"the two medians differ by {difference} rad, at or above {common.MIS_RAD} rad. "
            f"A DIFFERENT verdict is a finding ABOUT THE BACKEND and not about arms 2 and 3, "
            f"about which no verdict is stated at all (rule T)."
        )
    verdict("CONC1", value, why)
    print(wrap(RULE_G))
    return value


def spread(rows: list[dict]) -> float | None:
    values = [
        row["summary"]["max_abs_error_rad"]
        for row in rows
        if row["summary"].get("max_abs_error_rad") is not None
    ]
    return (max(values) - min(values)) if len(values) >= 2 else None


def maximum(rows: list[dict]) -> float | None:
    values = [
        row["summary"]["max_abs_error_rad"]
        for row in rows
        if row["summary"].get("max_abs_error_rad") is not None
    ]
    return max(values) if values else None


def p95(rows: list[dict]) -> float | None:
    values = [
        row["summary"]["max_abs_error_rad"]
        for row in rows
        if row["summary"].get("max_abs_error_rad") is not None
    ]
    return common.percentile(values, 95.0) if values else None


# ---------------------------------------------------------------------------
# 7.3 -- GOAL1 and SVT
# ---------------------------------------------------------------------------
def goal1(live: dict[str, dict]) -> dict[str, str]:
    """GOAL1 -- CLEAR / TIGHT / FIRED, stated per arm."""
    print("\n=== 7.3 GOAL1 -- the goal tolerance and the settle ===")
    out: dict[str, str] = {}
    for arm in ARMS:
        entry = live[arm]
        healthy_rows = [row for row in entry["admissible"] if row.get("healthy")]
        aborts = [
            row
            for row in entry["admissible"] + entry["losses"]
            if (row.get("i3c_goal_time_aborts") or [])
            or any(
                item.get("code") == "GOAL_TOLERANCE_VIOLATED"
                for item in (row.get("i3c_moveit_aborts") or [])
            )
        ]
        unassigned = [
            row
            for row in entry["admissible"] + entry["losses"]
            if row.get("tolerance_event")
            and not (row.get("i3c_goal_time_aborts") or [])
            and not (row.get("i3c_path_aborts") or 0)
            and not (row.get("i3c_moveit_aborts") or [])
        ]
        settles = [
            (row["goal_settle"].get("settle_s"), row)
            for row in healthy_rows
            if row["goal_settle"].get("settle_s") is not None
        ]
        unsettled = [
            row for row in healthy_rows if row["goal_settle"].get("settle_s") is None
        ]
        long_ones = [pair for pair in settles if pair[0] > common.GOAL_SETTLE_LINE_S]

        # A GOAL WINDOW THAT ENDED WITH THE ERROR STILL OUTSIDE THE GOAL TOLERANCE IS A
        # MEASUREMENT AND NOT A MISSING ONE. `settles` keeps only the trials that produced a
        # number, so an unresolved settle used to leave no trace in this verdict at all and
        # fell through to CLEAR -- the strongest evidence for TIGHT this campaign can produce,
        # and the case PRED4 is registered against, read as a pass. Section 7.3's CLEAR is
        # "no goal-tolerance abort occurred AND EVERY healthy trial's settle interval is
        # <= 0.25 s", and a settle that does not exist is not <= 0.25 s.
        unresolved = [
            row for row in healthy_rows if row["goal_settle"].get("unresolved")
        ]
        # Whether an unresolved settle PROVES the line was exceeded depends on how long the
        # goal window was. A window longer than the line ended with the error still outside
        # after more than 0.25 s, so the settle -- whatever it eventually was -- exceeded the
        # line: that is TIGHT, proven. A window at or below the line ran out before the line
        # was reached, so the settle is unknown and unbounded: that is not CLEAR either, and
        # claiming TIGHT from it would be reading a threshold off a window that never reached
        # it. NO THRESHOLD MOVES in either branch.
        unresolved_over_line = [
            row for row in unresolved
            if (row["goal_settle"].get("goal_window_span_s") or 0.0)
            > common.GOAL_SETTLE_LINE_S
        ]
        unresolved_undecidable = [
            row for row in unresolved if row not in unresolved_over_line
        ]

        # ORDER: a tolerance abort outranks rule L's refusal. Section 5.3 registers IN
        # CAPITALS that a trial with a path- or goal-tolerance violation is NEVER excluded and
        # that "the arm's QUIET1 or GOAL1 verdict becomes FIRED", and section 7.3's own clause
        # order puts the abort clause above the "NOT ADMISSIBLE otherwise". See Deviation 10:
        # rule L's state is carried in the verdict's reason either way, so both readings of
        # the frozen text are recoverable from this output.
        if aborts:
            value = "FIRED"
        elif entry["state"] is not True:
            value = "NOT ADMISSIBLE"
        elif long_ones or unresolved_over_line:
            value = "TIGHT"
        elif unresolved_undecidable:
            value = "NOT EVALUABLE"
        elif settles or healthy_rows:
            value = "CLEAR"
        else:
            value = "NOT EVALUABLE"
        out[arm] = value

        measured = [pair[0] for pair in settles]
        at_or_below_one_interval = [
            pair for pair in settles if pair[0] <= common.SAMPLE_INTERVAL_S
        ]
        say(
            f"GOAL1 [{arm}] -- settle against {common.GOAL_SETTLE_LINE_S} s "
            f"(half the declared goal_time of {common.DECLARED_GOAL_TIME_S} s)",
            bool(long_ones or aborts or unresolved),
            f"n={len(healthy_rows)} healthy admissible trials; {len(settles)} carry a "
            f"measured settle, {len(unsettled)} do not "
            f"({json.dumps([row['goal_settle'].get('reason') for row in unsettled])}); "
            f"of those, {len(unresolved)} ended the goal window with the error STILL OUTSIDE "
            f"the goal tolerance -- {len(unresolved_over_line)} over a goal window longer "
            f"than the line, which proves the settle exceeded it, and "
            f"{len(unresolved_undecidable)} over a shorter one, where the settle is unknown "
            f"and unbounded and no CLEAR may be stated; "
            f"settle min/median/max = "
            f"{min(measured) if measured else None}/"
            f"{common.percentile(measured, 50.0) if measured else None}/"
            f"{max(measured) if measured else None} s; "
            f"{len(at_or_below_one_interval)} of {len(settles)} are at or below one sample "
            f"interval ({common.SAMPLE_INTERVAL_S:.6f} s); "
            f"{len(aborts)} goal-time abort(s); {len(unassigned)} tolerance event(s) that "
            f"I3(c) could not attribute",
        )
        verdict(
            f"GOAL1 [{arm}]",
            value,
            {
                "CLEAR": "no goal-tolerance abort occurred and every healthy trial's settle "
                         "is at or below the line",
                "TIGHT": (
                    f"no abort occurred but some trial's settle exceeded the line -- the "
                    f"goal window is being used up rather than sat comfortably inside "
                    f"({len(long_ones)} measured above the line, "
                    f"{len(unresolved_over_line)} that never came inside the goal tolerance "
                    f"at all over a goal window longer than the line)"
                ),
                "FIRED": (
                    f"a trial aborted on the goal check. Section 5.3: such a trial is NEVER "
                    f"excluded and this verdict becomes FIRED. Rule L's state for this arm "
                    f"is reported beside it and does not suppress the event: "
                    f"LIVE1 admissible = {entry['state']}"
                ),
                "NOT ADMISSIBLE": "rule L refuses this arm's trials, and no trial of it "
                                  "aborted on the goal check",
                "NOT EVALUABLE": (
                    f"{len(unresolved_undecidable)} healthy trial(s) ended the goal window "
                    f"with the error still outside the goal tolerance, over a goal window no "
                    f"longer than the line, so the settle is unknown and unbounded and "
                    f"neither CLEAR nor TIGHT can be stated"
                    if unresolved_undecidable
                    else "no healthy admissible trial to measure a settle over"
                ),
            }[value],
        )
        if value == "CLEAR" and len(at_or_below_one_interval) == len(settles):
            print(wrap(
                "REGISTERED BEFORE ANY TRIAL, AND IT EVIDENCES NOTHING: a CLEAR whose "
                "measured settle is at or below one sample interval is reported in the rule-N "
                "shape. Section 7.3 predicts exactly this -- the reported error at the last "
                "trajectory point is the deceleration term alone, already inside the 0.01 rad "
                "goal tolerance before the goal window opens -- so it is NOT evidence that "
                "the goal tolerance behaves, that the goal window is comfortable, or that "
                "anything was exercised."))
            print(wrap(RULE_N))
        if value == "CLEAR":
            print(wrap(RULE_M))
        print(wrap(RULE_G))
    say(
        "SVT -- stopped_velocity_tolerance",
        None,
        "NOT MEASURED, and registered as not measured rather than measured as a constant. It "
        "CANNOT fire on this controller for two independent reasons read in source, either "
        "alone sufficient: this controller commands position only, so state_error_'s "
        "velocities stay at the zeros they were sized to; and the generated value is 0.0, "
        "which check_state_tolerance_per_joint does not apply. This campaign samples nothing "
        "for it.",
    )
    return out


# ---------------------------------------------------------------------------
# 7.4 -- rule X and X1
# ---------------------------------------------------------------------------
def x1(live: dict[str, dict]) -> dict[str, str]:
    """X1 -- STRESSED / NOT STRESSED, stated per arm, against rule X's derived speed."""
    print("\n=== 7.4 X1 -- did the campaign stress the path tolerance at all ===")
    print(wrap(
        f"Rule X's stress speed is {common.STRESS_SPEED_RAD_S:.4f} rad/s, DERIVED and not "
        f"chosen: it is {common.PATH_TOLERANCE_LINE_RAD} / (1/k - 1/R) with k = "
        f"{common.K_PER_S} 1/s and R = {common.R_HZ} Hz, the speed at which the predicted "
        f"REPORTED error equals ADR-0036's own line. Below it the criterion cannot be missed "
        f"by the lag mechanism at all."))
    out: dict[str, str] = {}
    for arm in ARMS:
        entry = live[arm]
        speeds = [
            row["summary"]["v_peak_feedback_rad_s"]
            for row in entry["admissible"]
            if row["summary"].get("v_peak_feedback_rad_s") is not None
        ]
        top = max(speeds) if speeds else None
        if entry["state"] is not True:
            value = "NOT ADMISSIBLE"
        elif top is None:
            # Admissible under rule L but carrying no measured speed at all. That is a
            # different sentence from "rule L refused this arm", and reading one as the other
            # is what the third state exists to prevent.
            value = "NOT EVALUABLE"
        elif top >= common.STRESS_SPEED_RAD_S:
            value = "STRESSED"
        else:
            value = "NOT STRESSED"
        out[arm] = value
        say(
            f"Rule X over {arm}",
            value == "STRESSED",
            f"peak measured joint speed over the arm's admissible trials = {top} rad/s "
            f"against {common.STRESS_SPEED_RAD_S:.4f} rad/s; the arm's peak speeds "
            f"min/median/max = {min(speeds) if speeds else None}/"
            f"{common.percentile(speeds, 50.0) if speeds else None}/{top}",
        )
        verdict(
            f"X1 [{arm}]",
            value,
            "this arm reached the stress speed"
            if value == "STRESSED"
            else "rule N applies -- this arm's quietness is a statement about the speeds it "
                 "ran at and about nothing faster",
        )
        if value != "STRESSED":
            print(wrap(RULE_N))
    if not any(value == "STRESSED" for value in out.values()):
        best = max(
            (
                row["summary"]["v_peak_feedback_rad_s"]
                for arm in ARMS
                for row in live[arm]["admissible"]
                if row["summary"].get("v_peak_feedback_rad_s") is not None
            ),
            default=None,
        )
        verdict(
            "X1 (campaign)",
            "NOT STRESSED",
            f"NO ARM IS STRESSED, so THE CAMPAIGN HAS NOT TESTED THE PATH TOLERANCE. Its "
            f"verdict reads: not tested above a peak joint speed of {best} rad/s, over these "
            f"trials, on this rig. Its silence may NOT be read as a pass, as a clearance of "
            f"the detector, or as evidence that the tolerance is inert. Open-work #20's "
            f"healthy half is then STILL OPEN, and ANALYSIS.md must say so in those words.",
        )
    return out


# ---------------------------------------------------------------------------
# 7.5 -- rule D
# ---------------------------------------------------------------------------
def rule_d(live: dict[str, dict]) -> dict[str, int]:
    """Rule D -- the arithmetic against the measurement, per trial, at the 25 % band."""
    print("\n=== 7.5 Rule D -- the arithmetic and the measurement are allowed to disagree ===")
    print(wrap(
        f"Per trial, the measured peak |error| against v_peak * (1/k - 1/R) = "
        f"{common.ERROR_PER_SPEED_S:.4f} * v_peak, with v_peak that trial's OWN measured peak "
        f"joint speed. The band is {common.RULE_D_BAND:.0%} and IT DOES NOT MOVE."))
    counts: dict[str, int] = {}
    for arm in ARMS:
        entry = live[arm]
        disagreements = []
        compared = 0
        for row in entry["admissible"]:
            summary = row["summary"]
            speed = summary.get("v_peak_feedback_rad_s")
            measured = summary.get("max_abs_error_rad")
            if speed is None or measured is None or speed <= 0:
                continue
            predicted = common.ERROR_PER_SPEED_S * speed
            compared += 1
            if predicted <= 0:
                continue
            if abs(measured - predicted) > common.RULE_D_BAND * predicted:
                disagreements.append(
                    {
                        "trial": row["trial"],
                        "block": row["block"],
                        "cycle": row["cycle"],
                        "goal": row["goal_kind"],
                        "v_peak_rad_s": speed,
                        "predicted_rad": predicted,
                        "measured_rad": measured,
                        "ratio": measured / predicted,
                        "peak_sample": summary.get("peak"),
                    }
                )
        counts[arm] = len(disagreements)
        say(
            f"Rule D over {arm}",
            bool(disagreements),
            f"{len(disagreements)} of {compared} compared trial(s) disagree by more than "
            f"{common.RULE_D_BAND:.0%}: " + json.dumps(disagreements, default=str),
        )
        if disagreements:
            print(wrap(
                "A DISAGREEMENT is reported with both numbers and the whole trace that "
                "produced it. NOTHING IS RE-RUN to resolve it, no goal is retuned in the "
                "direction that would make it go away, and no constant anywhere in the tree "
                "is edited. THE CAMPAIGN DOES NOT ATTRIBUTE IT: whether the cause is the "
                "gain, the update rate, the physics engine's handling of the velocity "
                "command, the time parameterisation or the harness is not decided here, and "
                "the write-up lists the candidates without choosing. It belongs in "
                "ANALYSIS.md's VERDICT LINE and not in a deviation, because it is a result "
                "and not a procedural exception."))
    return counts


# ---------------------------------------------------------------------------
# The remaining validity rules that are evaluated over the whole campaign
# ---------------------------------------------------------------------------
def rule_v6(kept: dict[str, list[dict]]) -> dict[str, bool | None]:
    """V6 -- the block effect, per arm, over the trial-peak statistic.

    If for any metric the difference between two BLOCKS within one arm is larger than the
    difference between two ARMS, that metric's finding is downgraded to INCONCLUSIVE whatever
    any test statistic says.
    """
    print("\n=== V6 -- the block effect ===")
    per_arm_block: dict[str, dict[str, float]] = {}
    for arm in ARMS:
        per_arm_block[arm] = {}
        for label, rows in sorted(kept.items()):
            trials = [
                row
                for row in rows
                if row.get("arm") == arm and row["summary"].get("rule_l_admissible")
            ]
            median = trial_peak_median(trials)
            if median is not None:
                per_arm_block[arm][label] = median

    arm_medians = {
        arm: common.percentile(list(values.values()), 50.0)
        for arm, values in per_arm_block.items()
        if values
    }
    between_arms = (
        max(arm_medians.values()) - min(arm_medians.values())
        if len(arm_medians) >= 2
        else None
    )

    out: dict[str, bool | None] = {}
    for arm in ARMS:
        values = list(per_arm_block[arm].values())
        within = (max(values) - min(values)) if len(values) >= 2 else None
        if within is None or between_arms is None:
            out[arm] = None
        else:
            out[arm] = within > between_arms
        say(
            f"V6 [{arm}]",
            out[arm],
            f"per-block median of the trial-peak: {json.dumps(per_arm_block[arm])}; "
            f"within-arm block spread = {within}, between-arm spread = {between_arms}",
        )
    return out


def rule_v7(kept: dict[str, list[dict]]) -> set[str]:
    """V7 -- the load is recorded and a loud host is REPORTED rather than excluded."""
    print("\n=== V7 -- host load ===")
    flagged = {
        label
        for label, rows in kept.items()
        if any(row.get("v7_any") for row in rows)
    }
    say(
        f"V7 -- any load average above {common.V7_LOAD_THRESHOLD} on 16 cores",
        bool(flagged),
        f"flagged blocks: {sorted(flagged) or 'none'}. NO BLOCK IS DISCARDED FOR LOAD, "
        f"because a load threshold chosen after seeing the data is a threshold chosen by the "
        f"data. Every verdict a flagged trial contributes to must be reported WITH and "
        f"WITHOUT those trials, and if a verdict differs it is INCONCLUSIVE under rule R.",
    )
    if flagged:
        print(wrap(
            "    ANALYSIS.md must carry the with-and-without pair for every affected verdict. "
            "This analyser reports which blocks are flagged; recomputing every verdict twice "
            "is the write-up's job and is not silently done here."))
    return flagged


def rule_v8(live: dict[str, dict]) -> None:
    """V8 -- n is what it was, with a Wilson 95 % interval where a count is a proportion."""
    print("\n=== V8 -- n is what it was ===")
    for arm in ARMS:
        entry = live[arm]
        n = entry["trials"]
        admissible = len(entry["admissible"])
        interval = common.wilson(admissible, n) if n else None
        say(
            f"V8 [{arm}]",
            None,
            f"{admissible} of {n} trials admissible under rule L; Wilson 95 % interval on "
            f"that proportion = {interval}. No arm is topped up to match another, and a block "
            f"that aborted early is reported with the n it reached.",
        )


def rule_v9(rows: list[dict], raw: Path) -> bool | None:
    """V9 -- nothing in `criteria.md` changed once the first trial had run.

    Not a gate. The hash travels on every record from the block that produced it; this
    compares those against the file on disk now, so that an edit after the first trial is
    visible rather than invisible. A finding here belongs to V9 in `ANALYSIS.md`.
    """
    print("\n=== V9 -- criteria.md is frozen from the first trial ===")
    on_disk = common.sha256(raw.parent / "criteria.md")
    if on_disk is None:
        # `--raw raw/shakedown` puts `criteria.md` one level further up. Looked for rather
        # than assumed, because reporting "no hash" for a file that is there would be the
        # silence this campaign is built against.
        on_disk = common.sha256(raw.parent.parent / "criteria.md")
    recorded = sorted({row.get("v1", {}).get("criteria_sha256") for row in rows if row.get("v1")})
    if not recorded or on_disk is None:
        say("V9", None, f"on disk {on_disk}; recorded on the rows {recorded}")
        return None
    fired = any(value != on_disk for value in recorded)
    say(
        "V9",
        fired,
        f"criteria.md sha256 on disk = {on_disk}; recorded on the blocks = {recorded}. A "
        f"threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong, as a "
        f"numbered deviation, against data already collected.",
    )
    return fired


def rule_v10(kept: dict[str, list[dict]]) -> bool | None:
    """V10 -- one writer at a time, read off the evidence V1 already collects."""
    print("\n=== V10 -- one writer in this checkout ===")
    moved = {
        label: {
            "head_moved_mid_block": rows[0]["v1"]["head_moved_mid_block"],
            "disagreed_mid_block": rows[0]["v1"]["disagreed_mid_block"],
        }
        for label, rows in sorted(kept.items())
        if rows and rows[0].get("v1")
    }
    fired = any(entry["disagreed_mid_block"] for entry in moved.values()) if moved else None
    say(
        "V10",
        fired,
        f"per block: {json.dumps(moved)}. `head_moved_mid_block` is EXPECTED -- this "
        f"campaign's own criteria, harness and raw land on this branch while it runs, so HEAD "
        f"necessarily advances and V1 deliberately does not watch `docs/`. "
        f"`disagreed_mid_block` is the one that matters: it is an edit to a watched path that "
        f"landed inside a block. The campaign operator states in ANALYSIS.md whether the "
        f"one-writer rule held; a campaign that loses blocks this way REPORTS the loss rather "
        f"than re-running until it stops happening.",
    )
    return fired


def rule_v11(raw: Path) -> bool | None:
    """V11 -- `./scripts/build` ran once, before the first trial."""
    print("\n=== V11 -- no rebuild mid-campaign ===")
    provenance = raw / "provenance.txt"
    if not provenance.exists():
        provenance = raw.parent / "provenance.txt"
    if not provenance.exists():
        say("V11", None, f"no provenance.txt beside {raw}")
        return None
    text = provenance.read_text()
    builds = text.count("# ---- ./scripts/build ----")
    exits = [line for line in text.splitlines() if line.startswith("build_exit=")]
    fired = builds > 1
    say(
        "V11",
        fired,
        f"{builds} build block(s) recorded in {provenance}, exits {exits}. If a rebuild "
        f"became necessary it is a numbered deviation, and every block before it is reported "
        f"separately from every block after it.",
    )
    return fired


def rule_v5_second_clause(live: dict[str, dict]) -> int:
    """V5's second clause -- the peak sample against the nearest `/joint_states` reading.

    REPORTED AND EXCLUDING NOTHING. The two publishers are sampled independently and are not
    obliged to coincide in time, so this is a difference to state and never a filter.
    """
    print("\n=== V5 second clause -- the peak against an independent publisher (I4) ===")
    reported = 0
    for arm in ARMS:
        rows = live[arm]["admissible"]
        differences = []
        for row in rows:
            clause = row.get("v5_second_clause") or {}
            peak = clause.get("peak_feedback_positions")
            nearest = clause.get("nearest_joint_state")
            if not peak or not nearest or not nearest.get("positions"):
                continue
            deltas = [
                abs(a - b)
                for a, b in zip(peak, nearest["positions"])
                if a is not None and b is not None
            ]
            if deltas:
                reported += 1
                differences.append(
                    {
                        "trial": row["trial"],
                        "dt_s": nearest.get("dt_from_peak_s"),
                        "max_abs_difference_rad": max(deltas),
                    }
                )
        values = [entry["max_abs_difference_rad"] for entry in differences]
        say(
            f"V5 second clause [{arm}]",
            None,
            f"{len(differences)} trial(s) compared; max difference between the peak sample's "
            f"feedback and the nearest /joint_states reading min/median/max = "
            f"{min(values) if values else None}/"
            f"{common.percentile(values, 50.0) if values else None}/"
            f"{max(values) if values else None} rad. A disagreement here is REPORTED and "
            f"EXCLUDES NOTHING.",
        )
    return reported


def symbol_disagreements(rows: list[dict]) -> list[dict]:
    """Section 5.3's defect: the goal status and the ResultCode payload disagreeing."""
    print("\n=== 5.3 -- the two symbols a result carries ===")
    bad = [
        {
            "trial": row["trial"],
            "block": row["block"],
            "arm": row["arm"],
            "status": row.get("i3a_status"),
            "result_code": row.get("i3a_result_code"),
            "detail": row.get("i3a_detail"),
        }
        for row in rows
        if row.get("symbols_disagree")
    ]
    say(
        "Status and payload agree",
        bool(bad),
        f"{len(bad)} trial(s) where STATUS_SUCCEEDED and ResultCode.SUCCESS disagree: "
        f"{json.dumps(bad)}. A DISAGREEMENT IS A DEFECT: it is reported in full and NEVER "
        f"resolved by reading one of the two.",
    )
    return bad


def unhealthy_categories(rows: list[dict]) -> dict[str, int]:
    """Section 5.3's exclusion accounting, by category, per arm."""
    print("\n=== 5.3 -- unhealthy trials, counted and reported by category ===")
    totals: dict[str, int] = {}
    for arm in ARMS:
        counts: dict[str, int] = {}
        for row in rows:
            if row.get("arm") != arm or row.get("healthy"):
                continue
            key = row.get("unhealthy_category") or "unstated"
            counts[key] = counts.get(key, 0) + 1
            totals[key] = totals.get(key, 0) + 1
        say(
            f"Unhealthy trials [{arm}]",
            bool(counts),
            f"{json.dumps(counts) if counts else 'none'}. A trial whose goal failed WITH a "
            f"path- or goal-tolerance violation is NEVER excluded -- it is the headline "
            f"finding and it is counted under `tolerance_event`, not filtered away.",
        )
    return totals


def i9_context(kept: dict[str, list[dict]], raw: Path) -> None:
    """I9 -- the simulated-to-wall ratio per block. CONTEXT ONLY; it enters no verdict."""
    print("\n=== I9 -- the simulated-to-wall clock ratio (context only) ===")
    ratios = {}
    for label in sorted(kept):
        path = raw / f"{label}_complete.json"
        if path.exists():
            ratios[label] = json.loads(path.read_text()).get("i9")
    say(
        "I9",
        None,
        f"{json.dumps(ratios, default=str)}. Computed from I1's own header stamps against the "
        f"wall clock. Gazebo's own real_time_factor field is NEVER quoted -- the 2026-08-29 "
        f"campaign established that it over-reports under starvation, and that finding is "
        f"cited and not copied (rule H). I9 ENTERS NO VERDICT.",
    )


# ---------------------------------------------------------------------------
# The predictions
# ---------------------------------------------------------------------------
def predictions(
    quiet: dict[str, str],
    band: dict[str, str],
    goal: dict[str, str],
    conc: str,
    stress: dict[str, str],
    live: dict[str, dict],
) -> None:
    """`criteria.md` section 7.5's six predictions, so that this campaign can be wrong."""
    print("\n=== The predictions, registered before any trial ===")

    p1 = all(value == "QUIET" for value in quiet.values() if value != "NOT ADMISSIBLE")
    evaluable = [value for value in quiet.values() if value != "NOT ADMISSIBLE"]
    say(
        "PRED1 -- QUIET1 = QUIET on every arm",
        None if not evaluable else (not p1),
        f"{json.dumps(quiet)}. A sustained REPORTED error of 1.0 rad needs a joint speed of "
        f"{1.0 / common.ERROR_PER_SPEED_S:.3f} rad/s, 5.308x the description's own joint "
        f"limit. Any path-tolerance violation would refute the mechanism as well as the "
        f"prediction.",
    )

    slow = [arm for arm in ("CRUISE", "CARRY", "CONC") if band.get(arm) in ("FAR", "SHORT")]
    peaks = {
        arm: maximum([row for row in live[arm]["admissible"] if row.get("healthy")])
        for arm in ("CRUISE", "CARRY", "CONC")
    }
    say(
        "PRED2 -- BAND1 = FAR on CRUISE, CARRY and CONC, peaks near 0.066 rad and in "
        "0.063-0.066 rad",
        None if not slow else any(band.get(arm) == "SHORT" for arm in slow),
        f"verdicts {json.dumps({arm: band.get(arm) for arm in ('CRUISE', 'CARRY', 'CONC')})}; "
        f"peaks {json.dumps(peaks)}. Refuted by a peak above "
        f"{common.PATH_TOLERANCE_LINE_RAD} rad on any of the three.",
    )

    fast_peak = maximum([row for row in live["FAST"]["admissible"] if row.get("healthy")])
    say(
        "PRED3 -- BAND1 = SHORT on FAST, peak near 0.116 rad and in 0.113-0.129 rad",
        None if band.get("FAST") in (None, "NOT ADMISSIBLE", "NOT EVALUABLE")
        else (band.get("FAST") != "SHORT"),
        f"FAST BAND1 = {band.get('FAST')}, peak = {fast_peak} rad. Registered as THE "
        f"UNCOMFORTABLE OUTCOME before any trial. Refuted by a FAST peak at or below "
        f"{common.PATH_TOLERANCE_LINE_RAD} rad.",
    )

    say(
        "PRED4 -- GOAL1 = CLEAR on every arm, AND THE PREDICTION IS UNINFORMATIVE BY "
        "CONSTRUCTION",
        None if not [v for v in goal.values() if v != "NOT ADMISSIBLE"]
        else any(value in ("TIGHT", "FIRED") for value in goal.values()),
        f"{json.dumps(goal)}. The reported error at the last trajectory point is the "
        f"deceleration term alone -- 0.0027 rad at default scaling and 0.0076 rad at full -- "
        f"both already inside the {common.DECLARED_GOAL_TOLERANCE_RAD} rad goal tolerance, so "
        f"the predicted settle is at most one sample interval. A CLEAR HERE EVIDENCES "
        f"NOTHING; it is registered so that it cannot later be read as evidence. Refuted by "
        f"any settle above {common.GOAL_SETTLE_LINE_S} s or any goal-tolerance abort.",
    )

    say(
        "PRED5 -- CONC is indistinguishable from CRUISE at the 0.005 rad minimum interesting "
        "size",
        None if conc == "INCONCLUSIVE" else (conc == "DIFFERENT"),
        f"CONC1 = {conc}. The argument is from the plugin's structure: the controller manager "
        f"is stepped by the simulator in SIMULATION time, so concurrent load stretches wall "
        f"clock and leaves the loop's simulated cadence alone. Refuted by a difference above "
        f"{common.MIS_RAD} rad, which would be a finding about the backend and not about the "
        f"arms.",
    )

    say(
        "PRED6 -- X1 = STRESSED on FAST and NOT STRESSED on the other three",
        None if stress.get("FAST") == "NOT ADMISSIBLE"
        else not (
            stress.get("FAST") == "STRESSED"
            and all(stress.get(arm) != "STRESSED" for arm in ("CRUISE", "CARRY", "CONC"))
        ),
        f"{json.dumps(stress)}. Section 2.3 predicts a FAST apex of 2.019 rad/s against rule "
        f"X's {common.STRESS_SPEED_RAD_S:.4f} rad/s. Refuted by FAST failing to reach it -- in "
        f"which case rule X fires over the whole campaign and open-work #20's healthy half is "
        f"still open.",
    )


# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        default=str(common.RAW),
        help="the directory of *_trials.json to read (default: this campaign's raw/)",
    )
    parser.add_argument(
        "--shakedown-dry-run",
        action="store_true",
        help="READ THE SHAKEDOWN BACK. criteria.md section 10: THE SHAKEDOWN IS NOT DATA. "
             "This exists ONLY to demonstrate that this analyser runs end to end before the "
             "campaign's first trial. It refuses to run if any campaign row is present, it "
             "prints a NOT-DATA banner, and nothing it prints may appear as a figure in "
             "ANALYSIS.md or be used to set or adjust any threshold.",
    )
    arguments = parser.parse_args()
    raw = Path(arguments.raw)

    print("=" * 100)
    print("criteria.md section 7 -- the following-error campaign's registered decision rules")
    print("EVERY RULE BELOW PRINTS WHETHER OR NOT IT FIRES. `NOT EVALUABLE` is a THIRD state")
    print("and is not `did not fire`: it means the rule could not be evaluated over the")
    print("trials that ran.")
    print("THE PRINT IS THE PRODUCT AND IT IS LONG -- redirect it, do not pipe it to `head`.")
    print(f"raw = {raw}")
    print("=" * 100)

    print("\n=== Deviations known before the first campaign trial (criteria.md V9) ===")
    for number, text in DEVIATIONS:
        print(f"\n  Deviation {number}:")
        print(wrap(text, indent="    "))

    print("\n=== The rules that are quoted rather than paraphrased ===")
    for name, text in (("Rule T", RULE_T), ("Rule H", RULE_H)):
        print(f"\n  {name}:")
        print(wrap(text, indent="    "))

    print("\n=== Loading ===")
    blocks = load_blocks(raw, arguments.shakedown_dry_run)
    if arguments.shakedown_dry_run:
        campaign_rows = [
            row for rows in blocks.values() for row in rows if not row.get("is_shakedown")
        ]
        if campaign_rows:
            print(
                "\nABORT: --shakedown-dry-run found campaign rows. It exists only to "
                "demonstrate the analyser on the shakedown, and it may not be pointed at a "
                "directory holding data.",
                file=sys.stderr,
            )
            return 2
        print("\n" + "#" * 100)
        print("## SHAKEDOWN DRY RUN -- THIS OUTPUT IS NOT DATA (criteria.md section 10).")
        print("## The shakedown is excluded from every figure in section 7 and may not be")
        print("## used to set or adjust any threshold. Nothing below may appear in")
        print("## ANALYSIS.md as a figure. It is printed to demonstrate that every")
        print("## registered rule is implemented and prints, before the first real trial.")
        print("#" * 100)

    if not blocks:
        say("Blocks found", None, f"no *_trials.json at the top level of {raw}")

    kept, report = admit(blocks)
    every = flat(kept)
    print(f"\n  admitted: {sum(len(rows) for rows in kept.values())} trial(s) across "
          f"{len(kept)} block(s): "
          f"{json.dumps({label: len(rows) for label, rows in sorted(kept.items())})}")

    v9_fired = rule_v9(every, raw)
    v10_fired = rule_v10(kept)
    v11_fired = rule_v11(raw)
    v7_flagged = rule_v7(kept)
    v6 = rule_v6(kept)

    disagreements = symbol_disagreements(every)
    categories = unhealthy_categories(every)
    other_arm_events = rule_t_other_arms(every)

    live = live1(kept)
    v5_pairs = rule_v5_second_clause(live)
    quiet = quiet1(live)
    band = band1(live)
    conc = conc1(live, v6)
    goal = goal1(live)
    stress = x1(live)
    d_counts = rule_d(live)
    rule_v8(live)
    i9_context(kept, raw)

    predictions(quiet, band, goal, conc, stress, live)

    print("\n" + "=" * 100)
    print("=== Summary -- every verdict, and what none of them means ===")
    print("=" * 100)
    for arm in ARMS:
        state = LIVE1_WORDS[live[arm]["state"]]
        print(
            f"  {arm:>6}: LIVE1={state}  QUIET1={quiet[arm]}  BAND1={band[arm]}  "
            f"GOAL1={goal[arm]}  X1={stress[arm]}  ruleD_disagreements={d_counts[arm]}"
        )
    print(f"  CONC1={conc}")
    print(
        f"  V6={json.dumps(v6)}  V7 flagged blocks={sorted(v7_flagged)}  V9 fired={v9_fired}  "
        f"V10 fired={v10_fired}  V11 fired={v11_fired}"
    )
    print(
        f"  section 5.3: {len(disagreements)} status/payload disagreement(s); unhealthy by "
        f"category {json.dumps(categories)}; V5 second clause compared on {v5_pairs} trial(s); "
        f"rule T: {other_arm_events} trial(s) carried a LOAD ARM's tolerance event, which is "
        f"reported and is not a finding about arm_1"
    )
    print(
        f"  discarded blocks: {json.dumps(report['discarded_blocks'], default=str)}; "
        f"dropped rows: {json.dumps(report['dropped_rows'])}; V14 exclusions: "
        f"{json.dumps(report['v14_excluded'])}"
    )
    print()
    print(wrap(RULE_G, indent="  "))
    print()
    print(wrap(RULE_N, indent="  "))
    print()
    print(wrap(
        "THIS CAMPAIGN CHOOSES NOTHING. It moves no tolerance, promotes no record, and "
        "decides nothing about whether the firing half should be built. It closes ONE HALF of "
        "ONE ITEM at most -- open-work #20's healthy-run direction, and only under rule L and "
        "rule X. The firing half stays open and this campaign does not narrow it by one "
        "millimetre. Nothing here is a P2 result: it samples one backend, and it is not "
        "evidence about the physical arm in either direction.", indent="  "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
