#!/usr/bin/env python3
"""`criteria.md` section 7's decision rules, applied to `raw/`.

DERIVED IN SHAPE FROM `docs/measurements/2026-09-04-following-error/harness/analyse.py`,
copied at commit `0712272` -- the commit that file last landed at -- which took the shape from
the 2026-09-03 and 2026-09-02 campaigns' analysers: **one function per registered threshold,
the rule prints even when it does not fire, and a `DEVIATIONS` tuple at module top printed on
every run**. That directory is FROZEN (`docs/measurements/README.md` rule 2) and nothing in it
is edited from here. Every rule below is this campaign's own.

WRITTEN BEFORE THE FIRST TRIAL, which is the whole point. A rule implemented after the data
has been seen is a rule chosen by the data, and `criteria.md` V9 forbids moving one
afterwards: a threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong, as
a numbered deviation in `ANALYSIS.md`, against data already collected.

EVERY RULE PRINTS WHETHER OR NOT IT FIRES. A rule that only speaks when it triggers is a rule
nobody can audit, and a reader cannot tell it from a rule that was never implemented. `None`
is a THIRD state and is not `False`: it means the rule could not be evaluated over what was
captured, which is a different sentence from "it was evaluated and was silent".

IT READS THE VALIDITY FLAGS OFF THE RECORD AND RE-DERIVES NONE OF THEM. V1's flag is the
conjunction of two `git` readings taken at both ends of the block where the block was taken;
V2's and V3's come from the description the running node published; V4's door is the matched
publisher the recorder saw while the scenario ran; V5's identity was evaluated in the compute
stage against I4's read-back. Re-deriving any of them here would ask a tree, and a cell, that
have since gone away.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, moves no threshold,
selects no geometry, proposes no fix and chooses nothing (`criteria.md` section 0). It prints
what the registered rules say about what was captured, and stops. `ANALYSIS.md` is written
from that print, later, by someone else.

**THE PRINT IS THE PRODUCT AND IT IS LONG.** Redirect it to a file; do not pipe it through
`head`. A previous campaign's operator piped a 1034-line report through `head`, saw 143 lines,
and `tee` still reported exit 0.

    python3 docs/measurements/2026-09-04-waypoint-clearance/harness/analyse.py \\
        > /tmp/waypoint_clearance_analysis.txt
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
        "**V2, V3, V4 and V5 are read PER CAPTURE rather than once per block, and the reading "
        "travels on every row the cell that produced it produced.** `criteria.md` section 4.1 "
        "words I3 and I4 as 'per arm per block' and V2/V3/V4 as block rules, which was written "
        "against the shape the frozen following-error rig had -- one cell per block. Rule C-i's "
        "own restatement establishes the opposite here: each scenario starts its OWN "
        "`move_group` through `IncludeLaunchDescription` inside its own process and EVERY RUN "
        "OWNS ITS OWN CELL, so a block has three cells and there is no single description, no "
        "single scene and no single matched publisher for a block-level reading to be about. "
        "Reading once per block would have recorded whichever cell happened to be up. **No "
        "threshold moved and no rule was weakened**: every clause is applied exactly as "
        "written, to the cell it is a statement about, and a block-level summary is recoverable "
        "from the record by conjunction."
    ),
    (
        "2",
        "**Rule C-i's second clause -- matched BEFORE that arm's first plan -- is evaluated "
        "against the first `Calling Planner` line's own log timestamp, and is NOT EVALUABLE "
        "where that timestamp cannot be parsed.** The rule is stated in terms of an ordering "
        "between two events observed by two different instruments: a matched publisher seen by "
        "the recorder on its own wall clock, and a log line written by `move_group`. Nothing in "
        "the tree emits a common ordering token. The harness records the recorder's wall-clock "
        "instant of the match and the log line verbatim; where the line carries an `rcutils` "
        "timestamp the comparison is made, and where it does not the clause prints NOT "
        "EVALUABLE rather than passing by default. **The ceiling clause is unaffected** and is "
        "always evaluable. No threshold moved."
    ),
    (
        "3",
        "**A trajectory's `is_shakedown` flag, its file name and its label are three "
        "independent refusals and all three are implemented.** `criteria.md` section 10 says "
        "the shakedown is not data. A convention that rested only on which directory the "
        "operator redirected the run into is not an exclusion, and the 2026-09-03 campaign "
        "recorded that discovery; this analyser lists `raw/*_trajectories.json` at the TOP "
        "LEVEL only, skips the `SHAKEDOWN` label wherever it is found, and drops any row "
        "carrying `is_shakedown` whatever its file is called."
    ),
    (
        "4",
        "**V1's flag is written to the rows by a SEAL at the end of the block rather than "
        "stamped on each row as it is written.** V1 requires the conjunction of two `git` "
        "readings taken at both ends of the block, and the closing reading does not exist while "
        "the block is running. Rows therefore carry `v1_clean = None` until the harness seals "
        "them -- at the end of the block, or as the FIRST act of its abort path, which is what "
        "V1 registers so that V8's promise about an aborted block is kept. A harness that died "
        "without sealing leaves `None`, and this file drops those rows and reports the block as "
        "lost with the count it would have contributed. That is V1's own sentence, implemented; "
        "no threshold moved."
    ),
    (
        "5",
        "**The compute stage skips sub-sampling an interval for a (link, object) pair whose "
        "two bracketing distances both exceed a SOUND BOUND on how far any point of that link "
        "moves over the interval.** `criteria.md` section 7.4 says the interval is subdivided; "
        "it does not say every pair of every interval is evaluated at every sub-sample, and the "
        "literal reading would multiply the compute by the sub-sample count for pairs that "
        "provably cannot reach contact. The bound is `sum |delta_j| * reach_j`, where `reach_j` "
        "bounds the distance from joint j's axis to any point of the link; a linear joint-space "
        "interpolation cannot displace a point further than that. **It can only skip a pair "
        "TUNNEL1 could not have fired on**, and TUNNEL1's condition is unchanged. No threshold "
        "moved, and the skipped and taken counts are both published."
    ),
    (
        "6",
        "**REPRO1's byte-identity is checked over the compute stage's own output with the "
        "wall-clock and interpreter fields removed.** The stage records `compute_seconds` and "
        "the interpreter string, which differ between two runs by construction, so a literal "
        "byte comparison of the whole file would fail on the clock and say nothing about the "
        "numbers. Those two fields, and the self-test's own reference string, are excluded from "
        "the comparison and are printed beside it; **every measured quantity is compared "
        "byte-for-byte**. No threshold moved."
    ),
)

RULE_T = (
    "Rule T (inherited): the captures are not each other's evidence. A clean result in one "
    "says nothing about any other, EVERY VERDICT IS STATED PER CAPTURE, and an inconclusive "
    "one belongs in the verdict rather than in a footnote. A scenario's own verdict does not "
    "gate its capture: every trajectory captured before a scenario failed is still a "
    "trajectory this cell produced, and admitting only the runs that passed would select the "
    "trajectories for success."
)

RULE_H = (
    "Rule H (inherited): no cross-campaign differencing and no importing. No measured figure "
    "from any other campaign, and no figure from criteria.md section 2.5's table -- ADR-0028's "
    "support-function and concavity figures, its pad and shoulder figures, #17's 0.077 m per "
    "step at 0.7 m reach -- is differenced against, divided into, or described as an "
    "improvement on anything here. Prior figures may be CITED; they may not be USED."
)

RULE_G = (
    "Rule G: every figure here is a property of THE TRAJECTORIES THESE SCENARIO RUNS "
    "PRODUCED, on this host, at this commit, in this image, with this scene and this arm "
    "model -- and of nothing else. It is not a property of the cell's reachable motions: "
    "another goal, another start state, another physics roll produces another trajectory set. "
    "It is not evidence about hardware; the layout is PROVISIONAL. A clean clearance here is "
    "not a safety case, and hulls may never be cited as margin."
)

RULE_N = (
    "Rule N (inherited): a null is not a clearance. Where a capture is NOT ADMISSIBLE under "
    "rule C, not exercised under rule K, or has a disagreeing FK1, the campaign's silence "
    "about it may NOT be read as agreement with any prior audit, as a clearance of either "
    "geometry, or as evidence that either gate behaves. The verdict names what was not "
    "tested, and the item stays open on that part."
)

RULE_D = (
    "Rule D (inherited): the arithmetic and the measurement are allowed to disagree, and the "
    "disagreement is the finding. Where section 2.4's arithmetic, section 2.3's containment "
    "relation or section 2.0's spacing is contradicted by the measurement, the contradiction "
    "is reported with both numbers, NOTHING IS RE-RUN to resolve it, no constant anywhere in "
    "the tree is edited, and the campaign does not attribute it."
)

RULE_E = (
    "Rule E: one direction is a theorem, so a measurement in it falsifies the instrument. "
    "d_hull <= d_vendor follows from containment. If any evaluated triple has d_hull > "
    "d_vendor + DIFF_FLOOR, DELTA1 is DISAGREEMENT: reported with both numbers and the whole "
    "trace, NOTHING IS RE-RUN, NOTHING IS EDITED, and the campaign DOES NOT ATTRIBUTE IT -- "
    "the mesh reader, the hull provenance, the transform, the triangle-box routine, the broad "
    "phase, MoveIt's link padding and link scaling as I4 recorded them, and the narrow-phase "
    "solver's own tolerance are listed as candidates without choosing."
)

RULE_M = (
    "Rule M: a censored distance is a bound, not a number. Any pair beyond CENSOR (0.500 m) "
    "is reported as '> 0.500 m' and enters no distribution, no minimum and no difference. "
    "Because the bound is identical under both geometries, censoring cannot manufacture or "
    "hide a difference -- but A VERDICT COMPUTED OVER UNCENSORED PAIRS ONLY IS A VERDICT "
    "ABOUT THE NEAR FIELD, and every such verdict is stated with its censored count beside it."
)

RULE_K = (
    "Rule K: the region of interest. K-i -- the hull-versus-vendor question is EXERCISED by a "
    "capture only if at least one admissible (waypoint, link, object) OTHER THAN THE STANDING "
    "PAIR has a distance under the VENDOR set of <= CLOSE_BAND (0.040 m). K-ii -- the "
    "tunnelling question is EXERCISED only if at least one consecutive-waypoint pair has both "
    "a step >= STEP_MID (0.020 m) AND, for some non-standing (link, object) pair, a bracketing "
    "distance <= CLOSE_BAND. Moving fast far from everything tests nothing, and creeping close "
    "to something tests nothing either; the question needs both at once. IF NO CAPTURE "
    "EXERCISES A REGION, THE CAMPAIGN HAS NOT TESTED THAT QUESTION AT ALL."
)

RULE_R = (
    "Rule R (inherited, re-scoped): for any metric whose spread WITHIN ONE CAPTURE IN ONE "
    "BLOCK exceeds that metric's minimum interesting size, a non-detection of a difference is "
    "INCONCLUSIVE for that metric -- never 'no difference'. The comparisons it binds are V6's, "
    "between two blocks of the same capture, and V7's, between the load-flagged and unflagged "
    "subsets of one block. TUNNEL1 is a binary observation, has no spread, and rule R does not "
    "apply to it."
)

STANDING_PAIR_NOTE = (
    "criteria.md section 2.2.1: every arm is bolted to a body that is also a planning-scene "
    "object, and the two overlap by about 132 nm at EVERY configuration under BOTH geometries. "
    "The standing pair (arm_N_link_base, pedestal_N) is reported as its own row and enters NO "
    "aggregate, NO minimum-over-pairs and NO verdict. The exclusion is BY NAME and by nothing "
    "else: no distance threshold drops it, and no tolerance anywhere is widened to make it "
    "disappear -- widening one would hide every other contact of the same size, which is "
    "exactly the class of event open-work #49 asks about."
)


def say(name: str, fired: bool | None, text: str) -> None:
    """One rule, printed whether or not it fired."""
    mark = {True: "FIRED    ", False: "did not fire", None: "NOT EVALUABLE"}[fired]
    print(f"  [{mark}] {name}: {text}")


def verdict(name: str, value: str, text: str) -> None:
    print(f"  [VERDICT] {name} = {value}: {text}")


def wrap(text: str, indent: str = "    ") -> str:
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


def number(value, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_blocks(raw: Path, allow_shakedown: bool) -> dict[str, dict]:
    """Every block's records, EXCLUDING the shakedown unless it is explicitly asked for.

    The shakedown is not data (`criteria.md` section 10). **The exclusion is here, in code,
    and it is three independent refusals rather than one convention.**

    1. This lists `raw/*_trajectories.json` at the TOP LEVEL only, so a recursive glob cannot
       sweep `raw/shakedown/` in.
    2. The `SHAKEDOWN` label is skipped wherever it is found, INCLUDING under
       `--raw raw/shakedown`.
    3. Any row carrying `is_shakedown` is dropped, whatever its file is called.

    `allow_shakedown` lifts 2 and 3 for `--shakedown-dry-run` ONLY, which exists so that this
    analyser can be demonstrated end to end before the campaign's first trial -- the only way
    to know that a rule prints before there is data to print it about.
    """
    blocks: dict[str, dict] = {}
    for path in sorted(raw.glob("*_trajectories.json")):
        label = path.name[: -len("_trajectories.json")]
        if label == "SHAKEDOWN" and not allow_shakedown:
            continue
        rows = json.loads(path.read_text())
        if not allow_shakedown:
            rows = [row for row in rows if not row.get("is_shakedown")]
        blocks[label] = {
            "label": label,
            "rows": rows,
            "captures": _read(raw / f"{label}_captures.json", []),
            "header": _read(raw / f"{label}_header.json", {}),
            "computed": _read(raw / f"{label}_computed.json", {}),
            "fkcheck": _read(raw / f"{label}_fkcheck.json", {}),
            "sealed": _read(raw / f"{label}_sealed.json", {}),
            "complete": _read(raw / f"{label}_complete.json", None),
            "repro": {
                path2.name: _read(path2, {})
                for path2 in sorted(raw.glob(f"{label}_computed_*.json"))
            },
        }
    return blocks


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def admit(blocks: dict[str, dict]) -> tuple[dict[str, dict], dict]:
    """V1, V2, V3 and V14 -- what is admitted, and what each exclusion cost.

    Every flag is READ OFF THE RECORD. A row without `v1_clean` is dropped and its block is
    reported as lost with the count it would have contributed, which is V1's own sentence.
    """
    kept: dict[str, dict] = {}
    report = {
        "dropped_unsealed": {},
        "dropped_v1_dirty": {},
        "dropped_v2": {},
        "dropped_v3": {},
        "dropped_v14": {},
        "kept": {},
    }
    for label, block in blocks.items():
        rows = block["rows"]
        unsealed = [row for row in rows if row.get("v1_clean") is None]
        dirty = [row for row in rows if row.get("v1_clean") is False]
        surviving = [row for row in rows if row.get("v1_clean") is True]

        def failed_v2(row: dict) -> bool:
            reading = row.get("v2") or {}
            return reading.get("v2_ok") is not True

        def failed_v3(row: dict) -> bool:
            reading = row.get("v3") or {}
            return reading.get("v3_ok") is not True

        def failed_v14(row: dict) -> bool:
            return (row.get("v14") or {}).get("v14_ok") is False

        v2_bad = [row for row in surviving if failed_v2(row)]
        v3_bad = [row for row in surviving if failed_v3(row)]
        v14_bad = [row for row in surviving if failed_v14(row)]
        excluded = {id(row) for row in v2_bad + v3_bad + v14_bad}
        final = [row for row in surviving if id(row) not in excluded]

        if unsealed:
            report["dropped_unsealed"][label] = len(unsealed)
        if dirty:
            report["dropped_v1_dirty"][label] = len(dirty)
        if v2_bad:
            report["dropped_v2"][label] = len(v2_bad)
        if v3_bad:
            report["dropped_v3"][label] = len(v3_bad)
        if v14_bad:
            report["dropped_v14"][label] = len(v14_bad)
        report["kept"][label] = len(final)
        kept[label] = {**block, "rows": final, "all_rows": rows}
    return kept, report


# ---------------------------------------------------------------------------
# Per-capture assembly
# ---------------------------------------------------------------------------
def captures_of(kept: dict[str, dict]) -> dict[str, dict]:
    """Everything, grouped by capture. Rule T: every verdict is stated per capture."""
    out: dict[str, dict] = {}
    for label, block in sorted(kept.items()):
        computed = block.get("computed") or {}
        by_capture_pairs = computed.get("pairs") or {}
        by_capture_trajectories: dict[str, list] = {}
        for record in computed.get("trajectories") or []:
            by_capture_trajectories.setdefault(record["capture"], []).append(record)
        tunnel: dict[str, list] = {}
        for event in computed.get("tunnel_events") or []:
            tunnel.setdefault(event["capture"], []).append(event)
        for record in block.get("captures") or []:
            name = record["capture"]
            entry = out.setdefault(
                name,
                {"capture": name, "blocks": {}, "pairs": [], "trajectories": [],
                 "tunnel": [], "capture_records": []},
            )
            entry["blocks"][label] = record
            entry["capture_records"].append({**record, "block": label})
            for arm, rows in (by_capture_pairs.get(name) or {}).items():
                for pair in rows:
                    entry["pairs"].append({**pair, "block": label, "arm": pair.get("arm", arm)})
            for record2 in by_capture_trajectories.get(name, []):
                entry["trajectories"].append({**record2, "block": label})
            for event in tunnel.get(name, []):
                entry["tunnel"].append({**event, "block": label})
        # A row whose capture is None arrived outside every capture window and belongs to no
        # capture's figures. It is counted where the instrument is reported, not here.
    return out


def rows_of(kept: dict[str, dict], capture: str) -> list[dict]:
    return [
        {**row, "block": label}
        for label, block in sorted(kept.items())
        for row in block["rows"]
        if row.get("capture") == capture
    ]


# ---------------------------------------------------------------------------
# 7.1 -- LIVE1 and rule C
# ---------------------------------------------------------------------------
def live1(captures: dict[str, dict], kept: dict[str, dict]) -> dict[str, dict]:
    """Rule C, per capture per block, and LIVE1 over it.

    `ANALYSIS.md` states LIVE1 BEFORE it states any other verdict, per capture, so that no
    clearance can be read without the instrument's own report beside it.
    """
    print("\n=== 7.1 LIVE1 -- a measured capture, or a measured nothing (rule C) ===")
    print(wrap(
        "This is the campaign's central hazard. A subscription that never matched, a topic "
        "that does not exist, a name resolved into the wrong namespace and a scenario that "
        "failed before it planned anything ALL PRODUCE THE SAME EMPTY SET -- and an empty set "
        "reads as 'no trajectory came close to anything', which is the reassuring answer.",
        indent="  "))
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = captures.get(name)
        print(f"\n  -- {name} --")
        if entry is None:
            say(f"{name} rule C", None, "no capture record exists for it")
            out[name] = {"state": None, "why": "no capture record"}
            continue

        rows = rows_of(kept, name)
        trajectories = entry["trajectories"]
        published = sum(record.get("i5_published", 0) for record in entry["capture_records"])
        received = sum(record.get("received_total", 0) for record in entry["capture_records"])

        # C-i, per block per arm.
        door_fail: list[str] = []
        door_unevaluable: list[str] = []
        for record in entry["capture_records"]:
            for arm, door in (record.get("door_by_arm") or {}).items():
                if not door.get("matched_publisher_count"):
                    door_fail.append(f"{record['block']}/{arm}: never matched")
                elif not door.get("within_ceiling"):
                    door_fail.append(
                        f"{record['block']}/{arm}: matched after {number(door.get('waited_s'))}s, "
                        f"ceiling {common.DOOR_CEILING_S}s"
                    )
                first_plan = _first_planner_time(record, arm)
                matched_at = door.get("matched_at_wall")
                if first_plan is None or matched_at is None:
                    door_unevaluable.append(f"{record['block']}/{arm}")
                elif matched_at > first_plan:
                    door_fail.append(
                        f"{record['block']}/{arm}: matched AFTER that arm's first plan"
                    )
        say(f"{name} C-i door", bool(door_fail),
            f"{len(door_fail)} arm-block(s) failed: {door_fail or 'none'}; "
            f"the before-first-plan clause was NOT EVALUABLE on {len(door_unevaluable)} "
            f"arm-block(s) (deviation 2): {door_unevaluable or 'none'}")

        # C-ii, over the block total where the per-arm attribution is unresolved.
        shortfall = max(0, published - received)
        surplus = max(0, received - published)
        say(f"{name} C-ii shortfall", shortfall > 0,
            f"I5 published {published}, received {received}; shortfall k={shortfall} is a "
            f"CAPTURE-LEVEL instrument loss of {shortfall} trajectory(ies), reported on its "
            f"own line and counted toward the {int(common.LOSS_CEILING_SHARE * 100)}% ceiling "
            f"stated over I5's PUBLISHED count")
        say(f"{name} C-ii surplus", surplus > 0,
            f"received > I5 by {surplus}: the log and the graph disagree about what was "
            f"published. A DISAGREEMENT under rule D -- nothing is re-run, and this capture's "
            f"verdicts are stated with it beside them")

        # C-iii and C-iv, per trajectory.
        losses = [record for record in trajectories if record["rule_c"]["instrument_loss"]]
        by_clause: dict[str, int] = {}
        for record in losses:
            for clause in record["rule_c"]["failed_clauses"]:
                by_clause[clause] = by_clause.get(clause, 0) + 1
        say(f"{name} C-iii/C-iv losses", bool(losses),
            f"{len(losses)} of {len(trajectories)} received trajectory(ies) are instrument "
            f"losses, by clause: {json.dumps(by_clause) if by_clause else '{}'}")

        total_losses = len(losses) + shortfall
        share = (total_losses / published) if published else None
        over = share is not None and share > common.LOSS_CEILING_SHARE
        say(f"{name} rule C loss ceiling", bool(over),
            f"{total_losses} instrument loss(es) of any kind against I5's published "
            f"{published} = {number(share, 4)}; ceiling {common.LOSS_CEILING_SHARE}")

        admissible = [record for record in trajectories
                      if not record["rule_c"]["instrument_loss"]]
        waypoints = sum(record["waypoints"] for record in admissible)
        state: bool | None
        if published == 0 and received == 0:
            state = None
        else:
            state = not over and bool(admissible)
        interval = common.wilson(len(admissible), published) if published else None
        verdict(
            f"LIVE1[{name}]",
            {True: "ADMISSIBLE", False: "NOT ADMISSIBLE", None: "NOT EVALUABLE"}[state],
            f"{len(admissible)} admissible trajectory(ies) over {waypoints} waypoint(s); "
            f"received {received}, logged-published {published}, losses {total_losses} "
            f"(C-ii shortfall {shortfall} on its own line); Wilson 95% on "
            f"admissible/published = "
            f"{'n/a' if interval is None else f'[{interval[0]:.3f}, {interval[1]:.3f}]'}; "
            f"admitted rows per block "
            f"{json.dumps({label: sum(1 for row in rows if row['block'] == label) for label in sorted({row['block'] for row in rows})})}; "
            f"scenario verdict lines "
            f"{[line for record in entry['capture_records'] for line in record.get('i9_verdict_lines', [])]}"
        )
        out[name] = {
            "state": state,
            "admissible": admissible,
            "losses": losses,
            "shortfall": shortfall,
            "surplus": surplus,
            "published": published,
            "received": received,
            "waypoints": waypoints,
            "pairs": entry["pairs"],
            "tunnel": entry["tunnel"],
            "rows": rows,
            "capture_records": entry["capture_records"],
            "door_unevaluable": door_unevaluable,
        }
    return out


def _first_planner_time(record: dict, arm: str) -> float | None:
    """The wall-clock instant of the first `Calling Planner` line attributed to `arm`.

    Deviation 2: the harness scrapes the line but nothing in the tree emits a token that
    orders it against the recorder's own clock, so this returns `None` unless the line carries
    a parseable `rcutils` timestamp and the clause prints NOT EVALUABLE rather than passing.
    """
    import re

    for call in record.get("i2c_planner_calls") or []:
        if call.get("arm") != arm:
            continue
        match = re.search(r"\[(\d{9,}\.\d+)\]", call.get("line", ""))
        if match:
            return float(match.group(1))
        return None
    return None


# ---------------------------------------------------------------------------
# Rule K -- the region of interest
# ---------------------------------------------------------------------------
def rule_k(live: dict[str, dict]) -> dict[str, dict]:
    print("\n=== 7.7 Rule K -- the region of interest, defined before anything was captured ===")
    print(wrap(RULE_K, indent="  "))
    print(wrap(STANDING_PAIR_NOTE, indent="  "))
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        pairs = [pair for pair in entry.get("pairs", []) if not pair["standing_pair"]]
        vendor_minima = [
            pair["vendor"]["min"] for pair in pairs if pair["vendor"]["min"] is not None
        ]
        closest_vendor = min(vendor_minima) if vendor_minima else None
        k_i = closest_vendor is not None and closest_vendor <= common.CLOSE_BAND_M
        closest_pair = None
        if closest_vendor is not None:
            closest_pair = min(
                (pair for pair in pairs if pair["vendor"]["min"] is not None),
                key=lambda pair: pair["vendor"]["min"],
            )
        say(f"{name} K-i (#49's region)", not k_i,
            f"exercised={k_i}; closest approach OUTSIDE the standing pair under the VENDOR "
            f"set = {number(closest_vendor)} m"
            + (f" on ({closest_pair['link']}, {closest_pair['object']})" if closest_pair else "")
            + f"; band {common.CLOSE_BAND_M} m. A fired rule means the capture HAS NOT TESTED "
              f"close-approach clearance and its silence may not be read as a pass")

        fast = sum(
            record.get("k_ii_intervals_at_or_above_step_mid", 0)
            for record in entry.get("admissible", [])
        )
        near = any(
            pair["hull"]["min"] is not None and pair["hull"]["min"] <= common.CLOSE_BAND_M
            for pair in pairs
        )
        # K-ii needs BOTH AT ONCE. Whether the same interval carried both is answerable only
        # from a tunnel candidacy record, so the conjunction is stated over the capture and
        # the two halves are printed separately -- a capture failing either half fails K-ii.
        k_ii = bool(fast) and near
        say(f"{name} K-ii (#17's region)", not k_ii,
            f"exercised={k_ii}; {fast} interval(s) with a step >= {common.STEP_MID_M} m, and "
            f"a non-standing pair within {common.CLOSE_BAND_M} m: {near}. Moving fast far "
            f"from everything tests nothing, and creeping close to something tests nothing "
            f"either")
        out[name] = {"k_i": k_i, "k_ii": k_ii, "closest_vendor_m": closest_vendor,
                     "closest_pair": closest_pair, "fast_intervals": fast, "near": near}
    if not any(entry["k_i"] for entry in out.values()):
        say("K-i over the whole campaign", True,
            "NO capture exercised #49's region, so THE CAMPAIGN HAS NOT TESTED THAT QUESTION "
            "AT ALL and ANALYSIS.md says so in its verdict line")
    else:
        say("K-i over the whole campaign", False,
            f"exercised by {[name for name, entry in out.items() if entry['k_i']]}")
    if not any(entry["k_ii"] for entry in out.values()):
        say("K-ii over the whole campaign", True,
            "NO capture exercised #17's region, so open-work #17 STAYS OPEN on this "
            "campaign's evidence, in those words")
    else:
        say("K-ii over the whole campaign", False,
            f"exercised by {[name for name, entry in out.items() if entry['k_ii']]}")
    return out


# ---------------------------------------------------------------------------
# 7.2 -- DELTA1, rule E, FLIP1
# ---------------------------------------------------------------------------
def delta1(live: dict[str, dict], regions: dict[str, dict], fk: dict[str, bool | None]
           ) -> tuple[dict[str, str], dict[str, dict]]:
    print("\n=== 7.2 DELTA1, rule E and FLIP1 -- what the hull changed ===")
    print(wrap(RULE_E, indent="  "))
    verdicts: dict[str, str] = {}
    flips: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        print(f"\n  -- {name} --")
        pairs = entry.get("pairs", [])
        standing = [pair for pair in pairs if pair["standing_pair"]]
        aggregate = [pair for pair in pairs if not pair["standing_pair"]]
        censored = sum(pair["censored"] for pair in pairs)

        for pair in standing:
            print(f"    [standing pair, in NO aggregate] {pair['arm']} "
                  f"({pair['link']}, {pair['object']}): hull min "
                  f"{number(pair['hull']['min'])} m, vendor min {number(pair['vendor']['min'])} "
                  f"m, evaluations {pair['evaluations']}")

        reversed_pairs = [pair for pair in pairs if pair["flip_reversed_count"]]
        hull_only = [pair for pair in aggregate if pair["flip_hull_only_contact_count"]]
        worst_reverse = max(
            (-pair["delta_vendor_minus_hull"]["min"]
             for pair in aggregate if pair["delta_vendor_minus_hull"]["min"] is not None),
            default=None,
        )
        rule_e_fired = worst_reverse is not None and worst_reverse > common.DIFF_FLOOR_M
        say(f"{name} rule E (containment)", bool(rule_e_fired or reversed_pairs),
            f"largest d_hull - d_vendor over evaluated triples = {number(worst_reverse)} m "
            f"against DIFF_FLOOR {common.DIFF_FLOOR_M} m; {len(reversed_pairs)} pair(s) show "
            f"a REVERSED flip. A firing falsifies the INSTRUMENT and never the geometry, and "
            f"the campaign does not attribute it")

        largest = max(
            (pair["delta_vendor_minus_hull"]["max"]
             for pair in aggregate if pair["delta_vendor_minus_hull"]["max"] is not None),
            default=None,
        )
        state = entry.get("state")
        if state is None:
            # NOT EVALUABLE is a THIRD state. Nothing was captured for this capture, which is
            # a different sentence from rule C's loss ceiling firing on what was.
            value = "NOT EVALUABLE"
        elif state is False:
            value = "NOT ADMISSIBLE"
        elif fk.get(name) is False:
            value = "NOT ADMISSIBLE"
        elif not regions[name]["k_i"]:
            value = "NOT EXERCISED"
        elif rule_e_fired or reversed_pairs:
            value = "DISAGREEMENT"
        elif largest is None:
            value = "NOT EXERCISED"
        elif largest <= common.DIFF_FLOOR_M:
            value = "IDENTICAL"
        else:
            value = "SMALLER"
        verdicts[name] = value

        best = max(
            (pair for pair in aggregate
             if pair["largest_delta"] and pair["largest_delta"]["delta_m"] is not None),
            key=lambda pair: pair["largest_delta"]["delta_m"],
            default=None,
        )
        verdict(
            f"DELTA1[{name}]", value,
            f"max(d_vendor - d_hull) over evaluated (waypoint, link, object) = "
            f"{number(largest)} m against DIFF_FLOOR {common.DIFF_FLOOR_M} m"
            + (f"; produced by ({best['link']}, {best['object']}) on {best['arm']} at "
               f"trajectory {best['largest_delta'].get('trajectory')} waypoint "
               f"{best['largest_delta'].get('waypoint')}, where hull = "
               f"{number(best['largest_delta']['hull_m'])} m and vendor = "
               f"{number(best['largest_delta']['vendor_m'])} m" if best else "")
            + f"; {censored} censored pair-evaluation(s) (rule M). NOT EXERCISED takes "
              f"precedence over IDENTICAL: a capture whose closest approach outside the "
              f"standing pair never reached CLOSE_BAND has measured nothing"
        )

        if value == "SMALLER":
            for pair in sorted(aggregate,
                               key=lambda pair: -(pair["delta_vendor_minus_hull"]["max"] or 0.0))[:12]:
                if (pair["delta_vendor_minus_hull"]["max"] or 0.0) <= common.DIFF_FLOOR_M:
                    continue
                print(f"      ({pair['link']}, {pair['object']}) on {pair['arm']}: "
                      f"delta max {number(pair['delta_vendor_minus_hull']['max'])} m, "
                      f"hull min {number(pair['hull']['min'])} m, "
                      f"vendor min {number(pair['vendor']['min'])} m, n={pair['evaluations']}")

        if hull_only:
            flip = "HULL-ONLY CONTACT"
        elif reversed_pairs:
            flip = "REVERSED"
        elif state is not True or not aggregate:
            # A NONE reached by evaluating nothing is the reassuring silence rule C exists to
            # catch. NONE means "neither, OVER EVERY EVALUATED PAIR", and with no evaluated
            # pair there is no such statement to make.
            flip = "NOT EVALUABLE"
        else:
            flip = "NONE"
        verdict(
            f"FLIP1[{name}]", flip,
            f"{len(hull_only)} pair(s) with d_hull <= 0 < d_vendor, "
            f"{len(reversed_pairs)} with d_vendor <= 0 < d_hull. HULL-ONLY CONTACT is a "
            f"FINDING ABOUT GEOMETRY and is open-work #49's feared consequence made visible; "
            f"REVERSED is the direction containment forbids and is a rule-E DISAGREEMENT. "
            f"A NONE verdict may NOT be read as evidence that either geometry is safe, that "
            f"the hull changed nothing, or that #49 is closed"
        )
        for pair in hull_only[:12]:
            for event in pair["flip_hull_only_contact"][:3]:
                print(f"      HULL-ONLY: ({pair['link']}, {pair['object']}) on {pair['arm']} "
                      f"trajectory {event.get('trajectory')} waypoint {event.get('waypoint')}: "
                      f"hull {number(event['hull_m'])} m, vendor {number(event['vendor_m'])} m")
        flips[name] = {"flip": flip, "hull_only": len(hull_only),
                       "reversed": len(reversed_pairs), "censored": censored}
    return verdicts, flips


# ---------------------------------------------------------------------------
# 7.3 -- MARGIN1
# ---------------------------------------------------------------------------
def margin1(live: dict[str, dict], fk: dict[str, bool | None]) -> dict[str, str]:
    print("\n=== 7.3 MARGIN1 -- how close this cell actually passes ===")
    print(wrap(
        "Stated over PER-(link, object) distances. Over an aggregate minimum, TIGHT was "
        "guaranteed and 'the fraction of waypoints inside CLOSE_BAND' was 100% by "
        "construction, because the standing pair's overlap is a configuration-independent "
        "constant at or below zero (criteria.md section 2.2.1). A verdict that cannot come "
        "out the other way measures nothing.", indent="  "))
    out: dict[str, str] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        pairs = [pair for pair in entry.get("pairs", []) if not pair["standing_pair"]]
        tight = [
            pair for pair in pairs
            if pair["hull"]["min"] is not None and pair["hull"]["min"] <= common.CLOSE_BAND_M
        ]
        inside = sum(pair["within_close_band_hull"] for pair in pairs)
        evaluations = sum(pair["evaluations"] for pair in pairs)
        censored = sum(pair["censored"] for pair in entry.get("pairs", []))
        share = (inside / evaluations) if evaluations else None
        interval = common.wilson(inside, evaluations) if evaluations else None

        if entry.get("state") is None:
            value = "NOT EVALUABLE"
        elif entry.get("state") is False or fk.get(name) is False:
            value = "NOT ADMISSIBLE"
        elif not pairs:
            # CLEAR means "no non-standing pair reached the band", which is a statement about
            # pairs that were evaluated. With none, there is nothing to be clear of.
            value = "NOT EVALUABLE"
        elif tight:
            value = "TIGHT"
        else:
            value = "CLEAR"
        out[name] = value
        verdict(
            f"MARGIN1[{name}]", value,
            f"{len(tight)} non-standing pair(s) came within {common.CLOSE_BAND_M} m under "
            f"the SHIPPED HULL set; {inside} of {evaluations} (waypoint, pair) evaluations "
            f"inside the band = {number(share, 4)}"
            + (f", Wilson 95% [{interval[0]:.4f}, {interval[1]:.4f}]" if interval else "")
            + f"; {censored} censored (rule M -- this is a verdict about the NEAR FIELD). "
              f"A CLEAR verdict carries rule K with it: it says these trajectories never came "
              f"within the thinnest object's thickness of anything BUT the arm's own "
              f"pedestal, and it does NOT say the cell cannot"
        )
        for pair in sorted(tight, key=lambda pair: pair["hull"]["min"])[:20]:
            closest = pair["closest_hull"] or {}
            print(f"      TIGHT on ({pair['link']}, {pair['object']}) / {pair['arm']}: "
                  f"min {number(pair['hull']['min'])} m at trajectory "
                  f"{closest.get('trajectory')} waypoint {closest.get('waypoint')} "
                  f"[block {closest.get('block', pair.get('block'))}], "
                  f"median {number(pair['hull']['median'])} m, n={pair['evaluations']}")
        if not tight:
            print("      (no non-standing pair reached the band; the standing pair is "
                  "excluded BY NAME and its exclusion is not a threshold)")
    return out


# ---------------------------------------------------------------------------
# 7.4 -- STEP1, TUNNEL1, GRIP1
# ---------------------------------------------------------------------------
def step1(live: dict[str, dict], kept: dict[str, dict]) -> dict[str, dict]:
    print("\n=== 7.4 STEP1 -- the per-waypoint tool-point Cartesian step, per pipeline ===")
    print(wrap(
        "The quantity is the step of arm_N_link_tcp, the tip_link the generated bring-up "
        "plan hands the skill server. Stated PER PIPELINE because open-work #17 is a "
        "statement about Pilz: an OMPL trajectory is re-timed by "
        "AddTimeOptimalParameterization, and although both pipelines land on 0.1 s the "
        "quantity is a different one. The attribution is I2 reading (c), the `Calling Planner` "
        "line. Reading (a), the interior spacing, is a CORROBORATION that can say 'consistent "
        "with 0.1 s' and nothing more, and a trajectory it disagrees with is REPORTED AND "
        "KEPT. STEP1 is not compared against max_trans_vel: 0.25, which bounds nothing here.",
        indent="  "))
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        print(f"\n  -- {name} --")
        admissible = entry.get("admissible", [])
        attribution = _pipeline_attribution(entry, kept)
        populations: dict[str, list[float]] = {"pilz": [], "ompl": []}
        unattributed = 0
        spacing_disagreements = 0
        for record in admissible:
            pipeline = attribution.get(
                (record["block"], record["capture"], record["arm"],
                 record.get("receive_index_in_arm"))
            )
            spacing_disagreements += record.get(
                "intervals_disagreeing_with_registered_spacing", 0
            )
            if pipeline in populations:
                populations[pipeline].extend(record.get("steps_m") or [])
            else:
                unattributed += 1

        say(f"{name} I2(a) corroboration", bool(spacing_disagreements),
            f"{spacing_disagreements} interior interval(s) differ from the registered "
            f"{common.SAMPLING_TIME_S} s spacing. Reading (a) is a CORROBORATION ONLY and a "
            f"trajectory it disagrees with is reported and KEPT, in the population reading "
            f"(c) assigns it")
        say(f"{name} unattributable trajectories", bool(unattributed),
            f"{unattributed} admissible trajectory(ies) could not be attributed to a pipeline "
            f"by reading (c). They are reported on their own line and enter NEITHER "
            f"population, and their count sits beside LIVE1")

        out[name] = {"unattributed": unattributed, "per_pipeline": {}}
        for pipeline in ("pilz", "ompl"):
            steps = populations[pipeline]
            spread = common.distribution(steps)
            if entry.get("state") is None:
                value = "NOT EVALUABLE"
            elif entry.get("state") is False:
                value = "NOT ADMISSIBLE"
            elif not steps:
                value = "NOT EXERCISED"
            elif spread["max"] >= common.STEP_HIGH_M:
                value = "EXCEEDS"
            elif spread["max"] >= common.STEP_MID_M:
                value = "COMPARABLE"
            else:
                value = "FAR BELOW"
            out[name]["per_pipeline"][pipeline] = {"verdict": value, "distribution": spread}
            verdict(
                f"STEP1[{name}/{pipeline}]", value,
                f"max step {number(spread['max'])} m, median {number(spread['median'])} m, "
                f"p95 {number(spread['p95'])} m over n={spread['n']} interval(s); "
                f"STEP_HIGH {common.STEP_HIGH_M} m, STEP_MID {common.STEP_MID_M} m. "
                f"FAR BELOW says these trajectories stepped that far and no further; it does "
                f"NOT say that a motion exists in this cell that cannot step further"
            )
    return out


def _pipeline_attribution(entry: dict, kept: dict) -> dict:
    """I2 reading (c): the k-th `Calling Planner` line on an arm names the k-th publication.

    Where a line's arm cannot be resolved from the launch process prefix, that arm's calls are
    incomplete and the trajectories are left UNATTRIBUTED rather than guessed at -- STEP1's
    own rule, which counts them on their own line and puts them in neither population.
    """
    del kept
    out: dict = {}
    for record in entry.get("capture_records", []):
        block = record["block"]
        for arm in common.ARMS:
            calls = [call for call in record.get("i2c_planner_calls") or []
                     if call.get("arm") == arm]
            for index, call in enumerate(calls, start=1):
                out[(block, record["capture"], arm, index)] = call.get("pipeline")
    return out


def tunnel1(live: dict[str, dict], regions: dict[str, dict], kept: dict[str, dict]
            ) -> dict[str, dict]:
    print("\n=== 7.4 TUNNEL1 -- does a body pass strictly between two checked waypoints ===")
    print(wrap(
        "Between each consecutive waypoint pair the configuration is interpolated LINEARLY IN "
        "JOINT SPACE, which is what MoveIt itself would do. OBSERVED iff, FOR SOME (link, "
        "object) PAIR OTHER THAN THE STANDING PAIR, a sub-sample's distance for that pair is "
        "<= 0 while BOTH bracketing waypoints are > 0 FOR THAT SAME PAIR -- exactly ADR-0027's "
        "residual, measured on the trajectories the cell produced. This is NOT a claim about "
        "the path the arm physically followed: what TUNNEL1 measures is what ValidateSolution "
        "did not look at.", indent="  "))
    sub = {}
    for block in kept.values():
        sub = (block.get("computed") or {}).get("tunnel_sub_sampling") or sub
    say("Sub-sampling ceiling", bool(sub.get("intervals_hitting_the_ceiling")),
        f"{sub.get('intervals_hitting_the_ceiling', 0)} interval(s) hit SUB_CEILING "
        f"({common.SUB_CEILING}); target sub-step {common.SUB_STEP_M} m, achieved "
        f"{json.dumps(sub.get('achieved_sub_step_m', {}), default=str)}; "
        f"{sub.get('sub_intervals_taken', 0)} sub-interval(s) taken in total")
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        events = entry.get("tunnel", [])
        for geometry in common.GEOMETRIES:
            mine = [event for event in events if event["geometry"] == geometry]
            if entry.get("state") is None:
                value = "NOT EVALUABLE"
            elif entry.get("state") is False:
                value = "NOT ADMISSIBLE"
            elif mine:
                value = "OBSERVED"
            elif not entry.get("admissible"):
                # NOT OBSERVED is a statement about intervals that were sub-sampled. With no
                # admissible trajectory there is no interval and no such statement.
                value = "NOT EVALUABLE"
            else:
                value = "NOT OBSERVED"
            out[f"{name}/{geometry}"] = {"verdict": value, "events": len(mine)}
            verdict(
                f"TUNNEL1[{name}/{geometry}]", value,
                f"{len(mine)} sub-sample contact(s) between two waypoints clear for that same "
                f"pair; region exercised (K-ii) = {regions[name]['k_ii']}. "
                + ("NOT OBSERVED carries rule K with it and may NOT be reported as a "
                   "clearance of ADR-0027's residual" if value == "NOT OBSERVED"
                   else "OBSERVED is a direct measurement of open-work #17")
            )
            for event in mine[:10]:
                print(f"      ({event['link']}, {event['object']}) on {event['arm']} "
                      f"trajectory {event['trajectory']} interval {event['interval']}: "
                      f"bracketing {number(event['bracketing_before_m'])} / "
                      f"{number(event['bracketing_after_m'])} m, sub-sample "
                      f"{number(event['sub_sample_m'])} m at fraction "
                      f"{number(event['sub_fraction'], 3)}, tool step "
                      f"{number(event['tool_step_m'])} m")
    return out


def grip1(live: dict[str, dict]) -> dict[str, dict]:
    print("\n=== 7.4 GRIP1 -- the gripper completion's sensitivity, DECIDING NOTHING ===")
    print(wrap(
        "Every distance involving one of the SIX moving gripper links is recomputed with the "
        "drive joint at 0 and at 0.85 rad, WITH ALL FIVE MIMIC FOLLOWERS MOVED WITH IT at "
        "multiplier 1 and offset 0 (criteria.md section 5.4). It SETS NO VERDICT: it exists so "
        "that the completion assumption is a measured sensitivity rather than an argument. "
        "arm_N_xarm_gripper_base_link is FIXED and is not in GRIP1's scope; it is in every "
        "other distribution like any other link.", indent="  "))
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        rows = [pair for pair in entry.get("pairs", []) if pair.get("grip1_largest_change")]
        largest = max(
            (pair["grip1_largest_change"]["change_m"] for pair in rows), default=None
        )
        say(f"GRIP1[{name}]", bool(rows),
            f"{len(rows)} gripper-link pair(s) measured; largest change over the drive "
            f"joint's declared range {common.GRIPPER_RANGE_RAD} = {number(largest)} m. "
            f"REPORTED AND DECIDING NOTHING")
        for pair in sorted(rows, key=lambda pair: -pair["grip1_largest_change"]["change_m"])[:10]:
            change = pair["grip1_largest_change"]
            print(f"      ({pair['link']}, {pair['object']}) on {pair['arm']}: "
                  f"{number(change['change_m'])} m at trajectory {change.get('trajectory')} "
                  f"waypoint {change.get('waypoint')}, drive {number(change.get('drive_rad'))}")
        out[name] = {"pairs": len(rows), "largest_change_m": largest}
    return out


# ---------------------------------------------------------------------------
# 7.5 -- REFUSE1
# ---------------------------------------------------------------------------
def refuse1(live: dict[str, dict]) -> dict[str, dict]:
    print("\n=== 7.5 REFUSE1 -- what the gate refused while we watched ===")
    print(wrap(
        "A count, with NO threshold. A refusal's GEOMETRY IS NOT MEASURABLE THROUGH THIS DOOR "
        "-- MoveIt's pipeline breaks the response-adapter chain on the first failure and "
        "ValidateSolution stands before DisplayMotionPath, so a refused trajectory is never "
        "published. REFUSE1 locates refusals in time and says nothing about how close anything "
        "was. A COUNT OF ZERO DOES NOT ESTABLISH THAT THE HULL SET REFUSES NOTHING. This "
        "campaign cannot answer whether the shipped hull set refuses a motion the vendor set "
        "would have accepted, and section 8 names what would.", indent="  "))
    out: dict[str, dict] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        records = entry.get("capture_records", [])
        codes = sorted({code for record in records for code in record.get("i6_codes", [])})
        fallbacks = [row for record in records for row in record.get("i2b_fallbacks", [])]
        # A count over no capture record is NOT the count zero: nothing was watched, so
        # nothing can be said about what the gate refused.
        total = sum(record.get("i6_refusals", 0) for record in records) if records else None
        say(f"REFUSE1[{name}]", None if total is None else bool(total),
            f"{'no capture record: nothing was watched' if total is None else total} "
            f"ValidateSolution refusal(s), codes {codes or 'none'}; "
            f"{len(fallbacks)} `planner fallback:` WARN(s) (I2b): {fallbacks[:8]}. A COUNT OF "
            f"ZERO DOES NOT ESTABLISH THAT THE HULL SET REFUSES NOTHING")
        out[name] = {"refusals": total, "codes": codes, "fallbacks": len(fallbacks)}
    return out


# ---------------------------------------------------------------------------
# 7.6 -- FK1, VALID1, REPRO1
# ---------------------------------------------------------------------------
def fk1(kept: dict[str, dict]) -> dict[str, bool | None]:
    print("\n=== 7.6 FK1 -- the instrument checking itself ===")
    print(wrap(
        "I11 is a reimplementation and a reimplementation that nothing checks is where a "
        "silently wrong frame convention lives. I12 is MoveIt's own RobotModel, which is what "
        "the cell used. THEY ARE NOT AVERAGED AND NEITHER CORRECTS THE OTHER. FK1 is a "
        "CONJUNCTION over the registered sample, so a single disagreement is the result, and "
        "NO DISTANCE VERDICT IN 7.2-7.4 IS STATED FOR A CAPTURE WHOSE FK1 DISAGREES.",
        indent="  "))
    per_capture: dict[str, bool | None] = {}
    worst_position = 0.0
    worst_angle = 0.0
    checked = 0
    unanswered = 0
    disagreeing: list[dict] = []
    drawn = 0
    for block in kept.values():
        report = block.get("fkcheck") or {}
        drawn += report.get("fk_sample_drawn", 0)
        for arm_report in (report.get("arms") or {}).values():
            for row in arm_report.get("rows") or []:
                agrees = row["fk"].get("agrees")
                if agrees is None:
                    unanswered += 1
                    per_capture[row["capture"]] = per_capture.get(row["capture"], None)
                    continue
                checked += 1
                worst_position = max(worst_position,
                                     row["fk"].get("worst_position_residual_m") or 0.0)
                worst_angle = max(worst_angle, row["fk"].get("worst_angle_residual_rad") or 0.0)
                if not agrees:
                    disagreeing.append(row)
                    per_capture[row["capture"]] = False
                elif per_capture.get(row["capture"]) is not False:
                    per_capture[row["capture"]] = True

    say("FK1 sample", checked == 0,
        f"{drawn} waypoint(s) drawn with seed {common.FK1_SEED} against the registered "
        f"{common.FK1_SAMPLE}; {checked} answered, {unanswered} unanswered by move_group")
    # A "worst residual" over zero compared waypoints is 0.0 by the identity of `max`, and
    # printing it reads as a perfect agreement nobody measured. NOT EVALUABLE is the third
    # state, and the residuals print as n/a rather than as zero.
    say("FK1 agreement", bool(disagreeing) if checked else None,
        f"{checked} waypoint(s) compared; worst position residual "
        f"{number(worst_position) if checked else 'n/a'} m against {common.FK_TOLERANCE_M} m, "
        f"worst angular residual {number(worst_angle) if checked else 'n/a'} rad against "
        f"{common.FK_TOLERANCE_RAD} rad; {len(disagreeing)} disagreeing waypoint(s)")
    for row in disagreeing[:10]:
        print(f"      DISAGREES {row['capture']} {row['arm']} trajectory {row['trajectory']} "
              f"waypoint {row['waypoint']}: {number(row['fk']['worst_position_residual_m'])} m "
              f"on {row['fk'].get('worst_link')}, "
              f"{number(row['fk']['worst_angle_residual_rad'])} rad")
    for name in common.CAPTURE_NAMES:
        state = per_capture.get(name)
        verdict(f"FK1[{name}]",
                {True: "AGREES", False: "DISAGREES", None: "NOT EVALUABLE"}[state],
                "a disagreement is a result under rule D: it is reported with the worst case, "
                "nothing is re-run, and the capture falls to rule N")
        per_capture[name] = state
    return per_capture


def valid1(kept: dict[str, dict]) -> dict[str, str]:
    print("\n=== 7.6 VALID1 -- MoveIt's predicate against the compute stage's sign ===")
    print(wrap(
        "Three clauses, and the SECOND is the one that carries information. Forward: a "
        "waypoint the compute stage puts at d > 0 for EVERY pair must come back valid -- "
        "registered in the knowledge that it may have no instances. Reverse: for each pair the "
        "compute stage puts at d <= 0, MoveIt is expected to report that pair among its "
        "contacts; THE STANDING PAIR IS EXPECTED TO VIOLATE THIS and is KNOWN-DIVERGENT, and "
        "ANY OTHER PAIR VIOLATING IT IS INCONSISTENT AND IS A RESULT. Neither is resolved by "
        "choosing: INCONSISTENT is reported with the scene's recorded link_padding and "
        "link_scale beside it, nothing is re-run and no tolerance is widened.", indent="  "))
    forward_instances = 0
    forward_violations: list[dict] = []
    known_divergent = 0
    inconsistent: list[dict] = []
    unanswered = 0
    for block in kept.values():
        for arm_report in ((block.get("fkcheck") or {}).get("arms") or {}).values():
            for row in arm_report.get("rows") or []:
                validity = row["validity"]
                if not validity.get("answered"):
                    unanswered += 1
                    continue
                if row.get("compute_stage_all_pairs_positive"):
                    forward_instances += 1
                    if validity.get("valid") is not True:
                        forward_violations.append(row)
                reported = set(validity.get("touched_scene_objects") or [])
                for pair in row.get("compute_stage_nonpositive_pairs") or []:
                    if pair["object"] in reported:
                        continue
                    if pair["standing_pair"]:
                        known_divergent += 1
                    else:
                        inconsistent.append({**pair, "capture": row["capture"],
                                             "arm": row["arm"],
                                             "trajectory": row["trajectory"],
                                             "waypoint": row["waypoint"]})

    say("VALID1 forward clause", bool(forward_violations),
        f"{forward_instances} sampled waypoint(s) had every pair positive; "
        f"{len(forward_violations)} of them came back NOT valid. Registered in the knowledge "
        f"that this clause may have NO INSTANCES at all")
    say("VALID1 reverse clause", bool(inconsistent),
        f"{known_divergent} non-reported contact(s) on the STANDING PAIR (KNOWN-DIVERGENT, "
        f"not an inconsistency); {len(inconsistent)} on any other pair")
    say("VALID1 unanswered", bool(unanswered),
        f"{unanswered} sampled waypoint(s) got no answer from check_state_validity")
    for row in inconsistent[:10]:
        print(f"      INCONSISTENT ({row['link']}, {row['object']}) {row['capture']} "
              f"{row['arm']} trajectory {row['trajectory']} waypoint {row['waypoint']}: "
              f"compute stage {number(row['distance_m'])} m, MoveIt reported no such contact")
    padding = [
        (block["label"], key, reading.get("link_padding"), reading.get("link_scale"))
        for block in kept.values()
        for record in block.get("captures") or []
        for key, reading in (record.get("i4_scene") or {}).items()
    ]
    nonzero = [
        row for row in padding
        if any(entry.get("padding") for entry in row[2] or [])
        or any((entry.get("scale") or 1.0) != 1.0 for entry in row[3] or [])
    ]
    say("VALID1 padding/scaling context", bool(nonzero),
        f"{len(nonzero)} of {len(padding)} scene read-back(s) carry a non-zero link_padding or "
        f"a link_scale other than 1.0. A non-zero padding is a SUFFICIENT EXPLANATION for an "
        f"INCONSISTENT and the campaign states it rather than assuming it; rule E's candidate "
        f"list applies here too")
    out: dict[str, str] = {}
    for name in common.CAPTURE_NAMES:
        mine = [row for row in inconsistent if row["capture"] == name]
        forward_mine = [row for row in forward_violations if row["capture"] == name]
        answered = sum(
            1
            for block in kept.values()
            for arm_report in ((block.get("fkcheck") or {}).get("arms") or {}).values()
            for row in arm_report.get("rows") or []
            if row.get("capture") == name and row["validity"].get("answered")
        )
        if not answered:
            # CONSISTENT is a statement about compared waypoints. Reaching it by comparing
            # none is the reassuring silence this campaign's whole section 7.1 exists to
            # prevent, and NOT EVALUABLE is the honest third state.
            value = "NOT EVALUABLE"
        elif mine or forward_mine:
            value = "INCONSISTENT"
        elif known_divergent:
            value = "KNOWN-DIVERGENT"
        else:
            value = "CONSISTENT"
        out[name] = value
        verdict(f"VALID1[{name}]", value,
                f"{answered} sampled waypoint(s) answered; {len(mine)} non-standing reverse "
                f"violation(s), {len(forward_mine)} forward violation(s). Nothing is re-run "
                f"and no tolerance is widened (V9)")
    return out


def repro1(kept: dict[str, dict], raw: Path) -> bool | None:
    print("\n=== 7.6 REPRO1 -- the compute stage is a pure function ===")
    print(wrap(
        "Run TWICE in the same interpreter and required to produce BYTE-IDENTICAL output, and "
        "ONCE MORE in a second interpreter with a different numpy, required to agree to "
        "1e-12 m. A failure of either is reported and NO FIGURE FROM THAT RUN IS PUBLISHED AS "
        "A MEASUREMENT. Deviation 6: the wall clock and the interpreter string are excluded "
        "from the byte comparison; every measured quantity is compared byte-for-byte.",
        indent="  "))
    volatile = ("compute_seconds", "interpreter", "numpy")

    def canonical(document: dict) -> str:
        stripped = {key: value for key, value in document.items() if key not in volatile}
        stripped.pop("distance_kernel_self_test", None)
        return json.dumps(stripped, indent=2, sort_keys=True, default=str)

    results: dict[str, bool | None] = {}
    for label, block in sorted(kept.items()):
        base = block.get("computed") or {}
        repeats = block.get("repro") or {}
        same_interpreter = [
            name for name in repeats
            if name != f"{label}_computed.json" and "repro" in name and "second" not in name
        ]
        cross = [name for name in repeats if "second" in name]
        if not base:
            say(f"REPRO1[{label}] base", None, "no computed record exists")
            results[label] = None
            continue
        if not same_interpreter:
            say(f"REPRO1[{label}] same interpreter", None,
                "no second run in the same interpreter is present; run compute.py again with "
                "--suffix _repro")
            identical = None
        else:
            identical = all(
                canonical(repeats[name]) == canonical(base) for name in same_interpreter
            )
            say(f"REPRO1[{label}] same interpreter", not identical,
                f"{len(same_interpreter)} repeat run(s); byte-identical (volatile fields "
                f"excluded) = {identical}")
        if not cross:
            say(f"REPRO1[{label}] second interpreter", None,
                "no cross-interpreter run is present; run compute.py under the other named "
                "interpreter with --suffix _second")
            agrees = None
        else:
            worst = max(
                _worst_numeric_difference(base, repeats[name]) for name in cross
            )
            agrees = worst <= common.REPRO_TOLERANCE_M
            say(f"REPRO1[{label}] second interpreter", not agrees,
                f"worst numeric difference {number(worst)} against "
                f"{common.REPRO_TOLERANCE_M} m; numpy "
                f"{[repeats[name].get('numpy') for name in cross]} against "
                f"{base.get('numpy')}")
        results[label] = None if identical is None or agrees is None else (identical and agrees)
        verdict(f"REPRO1[{label}]",
                {True: "REPRODUCED", False: "NOT REPRODUCED", None: "NOT EVALUABLE"}[
                    results[label]],
                "NOT EVALUABLE means the repeat runs were not taken, which is a different "
                "sentence from 'the stage did not reproduce'")
    del raw
    return None if not results else (
        None if any(value is None for value in results.values())
        else all(results.values())
    )


def _worst_numeric_difference(left, right) -> float:
    """The largest absolute difference between two structurally identical documents."""
    worst = 0.0
    if isinstance(left, dict) and isinstance(right, dict):
        for key in set(left) | set(right):
            if key in ("compute_seconds", "interpreter", "numpy",
                       "distance_kernel_self_test"):
                continue
            worst = max(worst, _worst_numeric_difference(left.get(key), right.get(key)))
    elif isinstance(left, list) and isinstance(right, list):
        for a, b in zip(left, right):
            worst = max(worst, _worst_numeric_difference(a, b))
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)) \
            and not isinstance(left, bool) and not isinstance(right, bool):
        worst = max(worst, abs(float(left) - float(right)))
    return worst


# ---------------------------------------------------------------------------
# The validity rules
# ---------------------------------------------------------------------------
def validity_rules(kept: dict[str, dict], report: dict, raw: Path,
                   live: dict[str, dict]) -> dict:
    print("\n=== Section 10 -- the validity rules, each printed whether or not it fires ===")
    out: dict = {}

    lost = report["dropped_unsealed"]
    dirty = report["dropped_v1_dirty"]
    say("V1 v1_clean", bool(lost or dirty),
        f"{sum(dirty.values())} row(s) dropped for a dirty two-ended reading {dirty}; "
        f"{sum(lost.values())} row(s) carry no flag at all and are LOST BLOCKS {lost}. The "
        f"flag is READ OFF THE RECORD and re-derived nowhere")
    disagreed = {
        label: (block.get("sealed") or {}).get("v1", {}).get("disagreed_mid_block")
        for label, block in kept.items()
    }
    say("V1 mid-block edit", any(bool(value) for value in disagreed.values()),
        f"the two readings disagreed in {json.dumps(disagreed)} -- an edit that landed "
        f"mid-block is a DIFFERENT finding from a block that was dirty throughout")
    pin = {
        label: (block.get("sealed") or {}).get("v1", {}).get("vendor_pin_held")
        for label, block in kept.items()
    }
    say("V1 vendor pin", any(value is False for value in pin.values()),
        f"the pinned SHA held at both ends: {json.dumps(pin)}. That tree is ONE OF THE TWO "
        f"GEOMETRIES this campaign measures, so a moved pin changes the comparison and not "
        f"merely the cell")
    out["v1"] = {"dropped": dirty, "lost": lost, "pin": pin}

    say("V2 geometry that ran", bool(report["dropped_v2"]),
        f"{report['dropped_v2']} row(s) dropped for a description that did not carry "
        f"{common.HULL_COLLISION_REFERENCES_EXPECTED} collision-mesh reference(s) under the "
        f"hull root. `read_ok` is separate from `v2_ok`: a rig that could not read is a "
        f"different finding from a cell built wrongly")
    unread = [
        f"{block['label']}/{record['capture']}/{arm}"
        for block in kept.values()
        for record in block.get("captures") or []
        for arm, reading in (record.get("v2") or {}).items()
        if not reading.get("read_ok")
    ]
    say("V2 description read-back", bool(unread),
        f"{len(unread)} arm-capture(s) read the description back as zero characters: {unread}. "
        f"THE 2026-09-03 CAMPAIGN LOST EIGHTEEN TRIALS TO EXACTLY THIS")
    say("V3 backend that ran", bool(report["dropped_v3"]),
        f"{report['dropped_v3']} row(s) dropped for a backend that was not "
        f"{common.PRODUCTION_PLUGIN} alone")

    doors = [
        (block["label"], record["capture"], arm, door)
        for block in kept.values()
        for record in block.get("captures") or []
        for arm, door in (record.get("door_by_arm") or {}).items()
    ]
    two_publishers = [row for row in doors if row[3].get("matched_publisher_count") == 2]
    other = [row for row in doors
             if row[3].get("matched_publisher_count") not in (2, 0)]
    say("V4 matched publishers", bool(other),
        f"section 2.1 registers TWO publishers per arm -- one per pipeline, each loading its "
        f"own DisplayMotionPath instance. {len(two_publishers)} of {len(doors)} arm-capture(s) "
        f"saw exactly two; {len(other)} saw another non-zero count: "
        f"{[(row[0], row[1], row[2], row[3].get('matched_publisher_count')) for row in other][:10]}")

    v5 = [
        (label, key, value)
        for label, block in sorted(kept.items())
        for key, value in ((block.get("computed") or {}).get("v5") or {}).items()
    ]
    fired = [row for row in v5 if row[2].get("v5_ok") is False]
    empty = [row for row in v5 if row[2].get("empty_readback")]
    say("V5 scene agreement", bool(fired),
        f"{len(fired)} of {len(v5)} arm-capture read-back(s) disagree with the generated file "
        f"beyond {common.V5_TOLERANCE_M} m. THE ACCOUNTING IS THE GENERATED STATIC "
        f"TRANSFORM'S OWN VALUE and not pi/2, which is the choice V5 registers and under "
        f"which V5 is expected to pass; a firing is stated with the pair and the residual, no "
        f"tolerance is widened, and the block's distances stand against the READ-BACK")
    for label, key, value in fired[:8]:
        print(f"      {label} {key}: worst {number(value.get('worst_residual_m'))} m, "
              f"{value.get('pairs_above_tolerance')} pair(s) above tolerance, accounting: "
              f"{value.get('accounting')}")
    say("V5 empty read-back", bool(empty),
        f"{len(empty)} arm-capture(s) read an EMPTY scene back. A plan validated against an "
        f"empty world is not the gate this campaign is about, and such a block is discarded")
    out["v5"] = {"fired": len(fired), "empty": len(empty), "evaluated": len(v5)}

    # V6 -- the block effect, evaluated for EVERY metric section 7.0 assigns a size to. Rule R
    # assigns one per metric and all three are applied here; TUNNEL1 has none because a binary
    # observation has no spread, and V6 governs it by its own wording instead.
    v6: dict[str, dict[str, bool | None]] = {}
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        per_metric: dict[str, dict[str, list[float]]] = {
            "MARGIN1": {}, "DELTA1": {}, "STEP1": {}
        }
        for pair in entry.get("pairs", []):
            if pair["standing_pair"]:
                continue
            if pair["hull"]["min"] is not None:
                per_metric["MARGIN1"].setdefault(pair["block"], []).append(pair["hull"]["min"])
            if pair["delta_vendor_minus_hull"]["max"] is not None:
                per_metric["DELTA1"].setdefault(pair["block"], []).append(
                    pair["delta_vendor_minus_hull"]["max"]
                )
        for record in entry.get("admissible", []):
            if record.get("step_m", {}).get("max") is not None:
                per_metric["STEP1"].setdefault(record["block"], []).append(
                    record["step_m"]["max"]
                )
        v6[name] = {}
        for metric, per_block in per_metric.items():
            size = common.RULE_R_SIZES[metric]
            if len(per_block) < 2 or size is None:
                v6[name][metric] = None
                continue
            extremes = {
                label: (min(values) if metric == "MARGIN1" else max(values))
                for label, values in per_block.items() if values
            }
            spread = max(extremes.values()) - min(extremes.values()) if len(extremes) > 1 else None
            v6[name][metric] = spread is not None and spread > size
    say("V6 block effect", any(bool(value) for row in v6.values() for value in row.values()),
        f"per capture and per metric, the spread BETWEEN BLOCKS against rule R's size for that "
        f"metric ({json.dumps({k: v for k, v in common.RULE_R_SIZES.items()})}): "
        f"{json.dumps(v6)}. A firing DOWNGRADES that metric's finding to INCONCLUSIVE whatever "
        f"any statistic says. TUNNEL1 has no size because a binary observation has no spread")
    out["v6"] = v6

    flagged = sorted({
        row["block"] for block in kept.values() for row in block["rows"]
        if row.get("v7_any")
    })
    say("V7 load", bool(flagged),
        f"blocks whose load exceeded {common.V7_LOAD_THRESHOLD} at either end: {flagged}. "
        f"NO BLOCK IS DISCARDED FOR LOAD; every verdict a flagged block contributes to is "
        f"reported with and without them, and a verdict that differs is INCONCLUSIVE under "
        f"rule R")
    out["v7_flagged"] = flagged

    partial = sorted(label for label, block in kept.items() if block.get("complete") is None)
    say("V8 n is what it was", bool(partial),
        f"{partial or 'no'} block(s) have no _complete.json and therefore ABORTED part-way. "
        f"They are reported with the n they reached and are NEVER topped up")

    hashes = sorted({
        str(row.get("v1", {}).get("criteria_sha256"))
        for block in kept.values() for row in block["rows"] if row.get("v1")
    })
    on_disk = common.sha256(raw.parent / "criteria.md")
    moved = len(hashes) > 1 or (hashes and on_disk and hashes[0] != on_disk)
    say("V9 no threshold moves", bool(moved),
        f"criteria.md hashes carried on the records: {hashes}; on disk now: {on_disk}. "
        f"A threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong")

    heads = sorted({
        str(row.get("v1", {}).get("head_moved_mid_block"))
        for block in kept.values() for row in block["rows"] if row.get("v1")
    })
    say("V10 one writer", any(value == "True" for value in heads),
        f"HEAD moved mid-block on: {heads}. docs/measurements/ may advance while the campaign "
        f"runs and nothing else may; a concurrent agent editing a watched path flips v1_clean "
        f"and silently discards the block, and a campaign that loses blocks this way REPORTS "
        f"THE LOSS rather than re-running until it stops happening")

    provenance = raw / "provenance.txt"
    builds = provenance.read_text().count("# ---- ./scripts/build ----") if provenance.exists() else 0
    say("V11 no rebuild mid-campaign", builds > 1,
        f"{builds} build block(s) in provenance.txt. More than one is a numbered deviation, "
        f"and every block before it is reported separately from every block after it")

    gz = sorted({
        str(row.get("v12_gz_calls")) for block in kept.values() for row in block["rows"]
    })
    say("V12 Gazebo partition", any(value not in ("0", "None") for value in gz),
        f"the harness's own Gazebo-transport call count, carried on every row: {gz}. It "
        f"constructs no Gazebo environment; the scenarios carry the partition themselves "
        f"(ADR-0042). An unpartitioned `gz model --list` reaches no world and EXITS 0, so a "
        f"raw call would produce plausible silence rather than an error")

    sleeps = sorted({
        str((row.get("v13") or {}).get("sleeps_to_sequence_bringup"))
        for block in kept.values() for row in block["rows"]
    })
    say("V13 readiness is an event", any(value == "True" for value in sleeps),
        f"carried on every row: {sleeps}. The scenarios' own bring-up gates are the event and "
        f"the recorder waits for a matched publisher and for nothing else (P4)")

    domains = sorted({
        (str((row.get("v14") or {}).get("ros_domain_id_env")),
         str((row.get("v14") or {}).get("resolved_from_plan")),
         str((row.get("v14") or {}).get("v14_ok")))
        for block in kept.values() for row in block["rows"]
    })
    say("V14 recorder on the cell's graph", bool(report["dropped_v14"]),
        f"(env, plan-resolved, ok) seen on the records: {domains}; "
        f"{report['dropped_v14']} row(s) dropped. A recorder on another domain produces a "
        f"COMPLETE, EMPTY, PLAUSIBLE capture, which is the failure this rule exists for")

    nonmonotonic = [
        row for block in kept.values() for row in block["rows"]
        if row.get("header_stamp_s") is not None and row.get("received_at_wall") is not None
        and row["header_stamp_s"] < 0
    ]
    say("V15 one clock for labels and none for decisions", bool(nonmonotonic),
        f"{len(nonmonotonic)} record(s) carry a non-monotonic stamp. Both the receive time and "
        f"the header stamp are LABELS: no verdict in section 7 depends on a clock -- every "
        f"decision quantity is a distance, a step or a count computed offline")

    stragglers = [
        row for block in kept.values() for row in block["rows"] if row.get("straggler")
    ]
    say("Trajectories outside any capture window", bool(stragglers),
        f"{len(stragglers)} trajectory(ies) arrived between or after the captures and carry "
        f"capture=None. They enter no capture's figures (rule T) and their existence is a "
        f"finding about the instrument")
    return out


# ---------------------------------------------------------------------------
# The instrument's own residual, and the mesh provenance
# ---------------------------------------------------------------------------
def instrument(kept: dict[str, dict]) -> None:
    print("\n=== The instrument's own residual, measured rather than asserted ===")
    for label, block in sorted(kept.items()):
        computed = block.get("computed") or {}
        test = computed.get("distance_kernel_self_test") or {}
        residual = test.get("worst_residual_m")
        say(f"{label} distance kernel", residual is not None and residual > common.DIFF_FLOOR_M,
            f"worst residual against the independent method = {number(residual)} m, over "
            f"{test.get('random_disjoint')} disjoint random case(s) plus "
            f"{len(test.get('analytic') or [])} analytic case(s); reference "
            f"{test.get('reference')}. It must sit far below DIFF_FLOOR "
            f"({common.DIFF_FLOOR_M} m) and REPRO1's tolerance "
            f"({common.REPRO_TOLERANCE_M} m) for either to mean anything")
        for key, provenance in sorted((computed.get("mesh_provenance") or {}).items()):
            say(f"{label} {key} mesh sets",
                (provenance.get("worst_aabb_corner_residual_m") or 0.0) > 0.0
                or (provenance.get("worst_origin_radius_residual_m") or 0.0) > 0.0,
                f"{provenance.get('collision_links')} collision link(s); "
                f"{provenance.get('hull_triangles_total')} hull triangle(s) against "
                f"{provenance.get('vendor_triangles_total')} vendor; worst AABB-corner "
                f"residual {number(provenance.get('worst_aabb_corner_residual_m'))} m and "
                f"worst origin-radius residual "
                f"{number(provenance.get('worst_origin_radius_residual_m'))} m between the "
                f"two sets. Those two being zero is what makes the broad phase SYMMETRIC, so "
                f"censoring can never manufacture or hide a difference")


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------
def predictions(delta: dict[str, str], flips: dict[str, dict], margin: dict[str, str],
                steps: dict[str, dict], tunnels: dict[str, dict],
                regions: dict[str, dict], fk: dict[str, bool | None],
                repro: bool | None) -> None:
    print("\n=== Predictions registered before any trial, so that this campaign can be wrong ===")
    smaller = [name for name, value in delta.items() if value == "SMALLER"]
    say("PRED1 (DELTA1 = SMALLER on at least one capture, confined to gripper links)",
        not smaller,
        f"SMALLER on {smaller or 'no capture'}. Refuted by IDENTICAL everywhere, or by a "
        f"difference on link_base, link1..link5 -- either says the mechanism is not the one "
        f"predicted. The per-pair rows above are where the link is named")
    disagreement = [name for name, value in delta.items() if value == "DISAGREEMENT"]
    say("PRED2 (DELTA1 is never DISAGREEMENT)", bool(disagreement),
        f"DISAGREEMENT on {disagreement or 'no capture'}. A firing would falsify the "
        f"INSTRUMENT, not the geometry, and is the most informative failure this campaign "
        f"could have")
    nonnone = {name: entry["flip"] for name, entry in flips.items() if entry["flip"] != "NONE"}
    say("PRED3 (FLIP1 = NONE on every capture, and a NONE evidences nothing)", bool(nonnone),
        f"{nonnone or 'NONE everywhere'}. A HULL-ONLY CONTACT is a geometry finding and would "
        f"be this campaign's most valuable observation; a REVERSED is a rule-E DISAGREEMENT")
    not_far = {
        name: entry["per_pipeline"]["pilz"]["verdict"]
        for name, entry in steps.items()
        if entry["per_pipeline"]["pilz"]["verdict"] in ("COMPARABLE", "EXCEEDS")
    }
    say("PRED4 (STEP1 = FAR BELOW on the Pilz trajectories of every capture)", bool(not_far),
        f"{not_far or 'FAR BELOW or not exercised everywhere'}. THE WEAKEST PREDICTION HERE: "
        f"it is a bare guess against an arithmetic scale, and 0.36415 m is neither an upper "
        f"nor a lower bound on what the cell produces")
    observed = {key: entry["verdict"] for key, entry in tunnels.items()
                if entry["verdict"] == "OBSERVED"}
    k_ii_fired = [name for name, entry in regions.items() if not entry["k_ii"]]
    say("PRED5 (TUNNEL1 = NOT OBSERVED everywhere AND rule K-ii fires)",
        bool(observed) or not k_ii_fired,
        f"OBSERVED on {observed or 'nothing'}; K-ii fired on {k_ii_fired}. The prediction is "
        f"that the campaign will NOT HAVE TESTED the question, and a NOT OBSERVED that rule K "
        f"refuses is the honest expected outcome -- it must not be reported as a clearance of "
        f"ADR-0027's residual")
    fk_bad = [name for name, value in fk.items() if value is False]
    say("PRED6 (FK1 = AGREES and REPRO1 = REPRODUCED)",
        bool(fk_bad) or repro is False,
        f"FK1 disagreed on {fk_bad or 'no capture'}; REPRO1 = "
        f"{{True: 'REPRODUCED', False: 'NOT REPRODUCED', None: 'NOT EVALUABLE'}}"
        f"[{repro}]. Either failing means NO DISTANCE VERDICT IS PUBLISHED for the affected "
        f"captures")
    say("MARGIN1 summary", any(value == "TIGHT" for value in margin.values()),
        f"{json.dumps(margin)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=str(common.RAW),
                        help="the directory of *_trajectories.json to read")
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
    print("criteria.md section 7 -- the waypoint-clearance campaign's registered decision rules")
    print("EVERY RULE BELOW PRINTS WHETHER OR NOT IT FIRES. `NOT EVALUABLE` is a THIRD state")
    print("and is not `did not fire`: it means the rule could not be evaluated over what was")
    print("captured.")
    print("THE PRINT IS THE PRODUCT AND IT IS LONG -- redirect it, do not pipe it to `head`.")
    print(f"raw = {raw}")
    print("=" * 100)

    print("\n=== Deviations known before the first campaign trial (criteria.md V9) ===")
    for number_, text in DEVIATIONS:
        print(f"\n  Deviation {number_}:")
        print(wrap(text, indent="    "))

    print("\n=== The rules that are quoted rather than paraphrased ===")
    for name, text in (("Rule T", RULE_T), ("Rule H", RULE_H), ("Rule D", RULE_D),
                       ("Rule M", RULE_M), ("Rule R", RULE_R)):
        print(f"\n  {name}:")
        print(wrap(text, indent="    "))

    print("\n=== Loading ===")
    blocks = load_blocks(raw, arguments.shakedown_dry_run)
    if arguments.shakedown_dry_run:
        campaign_rows = [
            row for block in blocks.values() for row in block["rows"]
            if not row.get("is_shakedown")
        ]
        if campaign_rows:
            print("\nABORT: --shakedown-dry-run found campaign rows. It exists only to "
                  "demonstrate the analyser on the shakedown, and it may not be pointed at a "
                  "directory holding data.", file=sys.stderr)
            return 2
        print("\n" + "#" * 100)
        print("## SHAKEDOWN DRY RUN -- THIS OUTPUT IS NOT DATA (criteria.md section 10).")
        print("## The shakedown is excluded from every figure in section 7 and may not be")
        print("## used to set or adjust any threshold. Nothing below may appear in")
        print("## ANALYSIS.md as a figure. It is printed to demonstrate that every")
        print("## registered rule is implemented and prints, before the first real trial.")
        print("#" * 100)

    if not blocks:
        say("Blocks found", None, f"no *_trajectories.json at the top level of {raw}")

    kept, report = admit(blocks)
    print(f"\n  admitted: "
          f"{json.dumps({label: len(block['rows']) for label, block in sorted(kept.items())})}")
    print(f"  exclusions: {json.dumps(report, default=str)}")

    instrument(kept)
    captures = captures_of(kept)
    live = live1(captures, kept)
    regions = rule_k(live)
    fk = fk1(kept)
    delta, flips = delta1(live, regions, fk)
    margin = margin1(live, fk)
    steps = step1(live, kept)
    tunnels = tunnel1(live, regions, kept)
    grip = grip1(live)
    refusals = refuse1(live)
    validity = valid1(kept)
    repro = repro1(kept, raw)
    rules = validity_rules(kept, report, raw, live)

    predictions(delta, flips, margin, steps, tunnels, regions, fk, repro)

    print("\n" + "=" * 100)
    print("=== Summary -- every verdict, and what none of them means ===")
    print("=" * 100)
    for name in common.CAPTURE_NAMES:
        entry = live.get(name) or {}
        state = {True: "ADMISSIBLE", False: "NOT ADMISSIBLE", None: "NOT EVALUABLE"}[
            entry.get("state")
        ]
        print(f"  {name:>10}: LIVE1={state}  DELTA1={delta.get(name)}  "
              f"FLIP1={flips.get(name, {}).get('flip')}  MARGIN1={margin.get(name)}  "
              f"VALID1={validity.get(name)}  FK1={fk.get(name)}")
        print(f"  {'':>10}  STEP1 pilz="
              f"{steps.get(name, {}).get('per_pipeline', {}).get('pilz', {}).get('verdict')}"
              f" ompl="
              f"{steps.get(name, {}).get('per_pipeline', {}).get('ompl', {}).get('verdict')}"
              f"  TUNNEL1 hull={tunnels.get(f'{name}/hull', {}).get('verdict')}"
              f" vendor={tunnels.get(f'{name}/vendor', {}).get('verdict')}"
              f"  REFUSE1={refusals.get(name, {}).get('refusals')}"
              f"  GRIP1 largest={number(grip.get(name, {}).get('largest_change_m'))} m")
        print(f"  {'':>10}  K-i exercised={regions.get(name, {}).get('k_i')}  "
              f"K-ii exercised={regions.get(name, {}).get('k_ii')}")
    print(f"  REPRO1={{True: 'REPRODUCED', False: 'NOT REPRODUCED', None: 'NOT EVALUABLE'}}"
          f"[{repro}]  V6={json.dumps(rules.get('v6'))}  "
          f"V7 flagged={rules.get('v7_flagged')}  V5 fired={rules.get('v5', {}).get('fired')}")
    print()
    print(wrap(RULE_G, indent="  "))
    print()
    print(wrap(RULE_N, indent="  "))
    print()
    print(wrap(STANDING_PAIR_NOTE, indent="  "))
    print()
    print(wrap(
        "THIS CAMPAIGN CHOOSES NOTHING. It moves no threshold, no tolerance and no ceiling; it "
        "selects no geometry; it promotes no record; and it proposes no fix for open-work #17 "
        "-- lowering a velocity scaling, densifying a trajectory before validation and "
        "changing the layout are the levers that item names, and this campaign evaluates none "
        "of them, recommends none of them and may not be cited as support for any of them. It "
        "closes AT MOST PART of two items, and only under rules C and K. #49's REFUSAL "
        "question stays open and this campaign does not narrow it by one millimetre: the "
        "capture door is a response adapter that stands AFTER ValidateSolution, so a refused "
        "trajectory is never published and its geometry is not measurable here. Nothing here "
        "is a P2 result -- it samples the simulated cell, the layout is PROVISIONAL and the "
        "physical scan is Phase 3.", indent="  "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
