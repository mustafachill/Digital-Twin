#!/usr/bin/env python3
"""Apply `criteria.md` section 7's decision rules to `raw/`, and nothing else.

WRITTEN AFTER THE DATA WAS COLLECTED, and that is stated here rather than left to be
noticed. What it may therefore not do -- and what `ANALYSIS.md` records it did not do --
is introduce a threshold, a metric or an exclusion that `criteria.md` does not already
carry. Every constant below is quoted from that file with its section number beside it,
so the two can be diffed by eye. Where the data made a registered rule read oddly, the
rule is applied LITERALLY and the oddity becomes a numbered deviation in `ANALYSIS.md`.

    .venv/bin/python analyse.py            # writes raw/analysis.json and prints a summary
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

RAW = Path(__file__).resolve().parent / ".." / "raw"
MM = 1000.0

# --- criteria.md 7.1, minimum interesting size -------------------------------------
MIS_WIDTH_MM = 0.100  # any width in mm
MIS_RATIO = 0.05  # the decision quantity
MAT_ARITHMETIC_MM = 0.100  # 7.5 D4 materiality
MIS_Q_RAD = 0.001  # q_at_stall_rad
ALPHA = 0.01  # 7.3

# --- criteria.md 5.1, the four registered commands ---------------------------------
COMMANDS_M = (0.042, 0.045, 0.047, 0.048)
VALIDATOR_CEILING_MM = 47.86  # 5.1 / ADR-0052 2.3
PREDICTED_BAND_EDGE_MM = 47.1215  # criteria.md 2


def wilson(successes: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson 95 % interval. criteria.md V8 requires one wherever a count is a proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def hodges_lehmann(a, b) -> float:
    """Median of pairwise differences a - b. criteria.md 7.3's effect size."""
    if not len(a) or not len(b):
        return float("nan")
    return float(np.median(np.subtract.outer(np.asarray(a), np.asarray(b)).ravel()))


def summarise(values) -> dict:
    values = [v for v in values if v is not None and v == v]
    if not values:
        return {"n": 0}
    array = np.asarray(values, dtype=float)
    q1, q3 = np.percentile(array, [25, 75])
    return {
        "n": int(array.size),
        "min": float(array.min()),
        "median": float(np.median(array)),
        "max": float(array.max()),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
    }


# ===================================================================================
# AR — criteria.md 7.5, D4
# ===================================================================================
def analyse_ar() -> dict:
    path = RAW / "AR_arithmetic.json"
    if not path.exists():
        return {"present": False}
    document = json.loads(path.read_text())

    linearisation = [r["linearisation_term_m"] * MM for r in document["sweep"]]
    widths = [r["w_cmd_m"] * MM for r in document["sweep"]]
    monotone = all(
        linearisation[i] <= linearisation[i + 1] + 1e-12 for i in range(len(linearisation) - 1)
    )
    total = [r["total_disagreement_m"] * MM for r in document["evaluation_point_grid"]]
    disagreeing = [
        r for r in document["evaluation_point_grid"]
        if r["cpp_holding"] != r["validator_would_hold"]
    ]

    largest = max(max(abs(x) for x in linearisation), max(abs(x) for x in total))
    return {
        "present": True,
        "second_pass_bit_identical": document["second_pass_bit_identical"],
        "n_swept": document["n_swept"],
        "swept_range_mm": [min(widths), max(widths)],
        "linearisation_term_mm": {
            "at_narrowest": linearisation[0],
            "at_widest": linearisation[-1],
            "min": min(linearisation),
            "max": max(linearisation),
            "monotone_increasing_in_w_cmd": monotone,
        },
        "evaluation_point_grid": {
            "n": len(total),
            "total_disagreement_mm": summarise(total),
            "verdict_disagreements": len(disagreeing),
        },
        "largest_disagreement_mm": largest,
        "MAT_mm": MAT_ARITHMETIC_MM,
        "D4": "MATERIAL" if largest > MAT_ARITHMETIC_MM else "IMMATERIAL",
    }


# ===================================================================================
# FP — criteria.md 7.6, D5, and rule N
# ===================================================================================
def analyse_fp() -> dict:
    path = RAW / "FP_trials.json"
    if not path.exists():
        return {"present": False}
    rows = json.loads(path.read_text())

    # V6 -- the stop engaged. Both clauses, applied literally.
    def engaged(row) -> bool:
        if not row.get("ok"):
            return False
        if not row.get("stop_announced"):
            return False
        stop = row.get("stop_upper_rad")
        return stop is not None and abs(row["reached_position_rad"] - stop) <= MIS_Q_RAD

    stops = [r for r in rows if r["condition"] == "FP"]
    controls = [r for r in rows if r["condition"] == "FP-C"]
    valid = [r for r in stops if engaged(r)]
    excluded = [r for r in stops if not engaged(r)]

    by_width: dict[float, list] = {}
    for row in valid:
        by_width.setdefault(row["stop_width_mm"], []).append(row)

    per_width = []
    for width in sorted(by_width):
        group = by_width[width]
        positions = [r["reached_position_rad"] for r in group]
        per_width.append(
            {
                "stop_width_mm": width,
                "n": len(group),
                "reached_width_mm": group[0]["reached_width_m"] * MM,
                "margin_mm": group[0]["margin_m"] * MM,
                "threshold_mm": group[0]["threshold_m"] * MM,
                "ratio": group[0]["ratio"],
                "stalled": group[0]["stalled"],
                "reached_goal": group[0]["reached_goal"],
                "predicate_holding": group[0]["predicate_holding"],
                "replicate_spread_rad": max(positions) - min(positions),
                "all_replicates_agree": len({r["predicate_holding"] for r in group}) == 1,
            }
        )

    holding = [r for r in valid if r["predicate_holding"]]
    reproduced = bool(holding)

    # The flip width: the narrowest VALID stop width whose verdict is true, with the
    # widest false one below it, so the bracket is reported rather than a point.
    true_widths = sorted({r["stop_width_mm"] for r in valid if r["predicate_holding"]})
    false_widths = sorted({r["stop_width_mm"] for r in valid if not r["predicate_holding"]})
    below = max((w for w in false_widths if not true_widths or w < true_widths[0]), default=None)
    flip = {
        "last_not_holding_mm": below,
        "first_holding_mm": true_widths[0] if true_widths else None,
        "predicted_band_edge_mm": PREDICTED_BAND_EDGE_MM,
        "bracket_mm": (true_widths[0] - below) if (true_widths and below is not None) else None,
    }

    # Which of the predicate's two conditions rejected each trial -- 7.6's second
    # question, and the one the FP-C control was meant to answer.
    takeover = sorted({r["stop_width_mm"] for r in stops if r.get("reached_goal")})

    return {
        "present": True,
        "n_total": len(rows),
        "n_stop_trials": len(stops),
        "n_valid_after_V6": len(valid),
        "V6_excluded": [
            {
                "trial": r["trial"],
                "stop_width_mm": r["stop_width_mm"],
                "stop_announced": r.get("stop_announced"),
                "reached_position_rad": r.get("reached_position_rad"),
                "declared_stop_rad": r.get("stop_upper_rad"),
                "offset_rad": (r["reached_position_rad"] - r["stop_upper_rad"])
                if r.get("ok") and r.get("stop_upper_rad") is not None else None,
            }
            for r in excluded
        ],
        "per_width": per_width,
        "n_valid_reporting_a_grasp": len(holding),
        "wilson95_of_valid_reporting_a_grasp": wilson(len(holding), len(valid)),
        "flip": flip,
        "reached_goal_takeover_widths_mm": takeover,
        "controls": [
            {
                "trial": r["trial"],
                "reached_width_mm": r["reached_width_m"] * MM,
                "reached_position_rad": r["reached_position_rad"],
                "stalled": r["stalled"],
                "reached_goal": r["reached_goal"],
                "predicate_holding": r["predicate_holding"],
                "stop_announced": r["stop_announced"],
            }
            for r in controls
        ],
        "D5": "REPRODUCED" if reproduced else "NOT REPRODUCED",
        "rule_N": "does not fire" if reproduced else "FIRES -- the false-positive verdict is INCONCLUSIVE",
    }


# ===================================================================================
# FN — criteria.md 7.2, 7.3, 7.4, 7.7, and rules M, R, S
# ===================================================================================
def analyse_fn() -> dict:
    rows = []
    blocks = []
    for path in sorted(RAW.glob("FN_B*_trials.json")):
        loaded = json.loads(path.read_text())
        blocks.append({"file": path.name, "n": len(loaded)})
        rows.extend(loaded)
    if not rows:
        return {"present": False}

    def i1_close(row):
        """The Pick's own report line for THE GRASP CLOSE, not for the jaw opening.

        `Pick`'s first physical act is to OPEN the jaws, and the skill server reports
        that close too -- one line at the gripper's full 88.9 mm opening, `stalled=false,
        reached_goal=true, -> empty`. Taking the first line in the segment would compare
        I2 against the opening rather than against the grasp and exclude every trial
        under V4. The grasp close is identified by its commanded width matching the
        goal's, to half the log's own resolution; anything ambiguous returns None and
        the trial is excluded by V4 rather than guessed at.
        """
        wanted = row["commanded_width_m"] * MM
        matches = [
            report for report in (row.get("pick_reports") or [])
            if abs(report["commanded_mm"] - wanted) <= MIS_WIDTH_MM / 2.0
        ]
        return matches[-1] if len(matches) == 1 else None

    exclusions = {"V2": [], "V3": [], "V4": [], "failed": []}
    valid = []
    for row in rows:
        if not row.get("ok"):
            exclusions["failed"].append({"trial": row["trial"], "label": row.get("label"),
                                         "error": row.get("error")})
            continue
        # V3 -- the close happened.
        if not row.get("reached_grasping_phase"):
            exclusions["V3"].append({"trial": row["trial"], "label": row.get("label"),
                                     "pick_result_code": row.get("pick_result_code")})
            continue
        # V2 -- the part was in the jaws.
        if not row.get("finger_contact_points_max"):
            exclusions["V2"].append({"trial": row["trial"], "label": row.get("label"),
                                     "contact_messages": row.get("contact_messages")})
            continue
        # V4 -- the two instruments agree, to the log's own resolution.
        report = i1_close(row)
        i2 = row.get("reached_width_m_i2")
        if report is None or i2 is None:
            exclusions["V4"].append({"trial": row["trial"], "label": row.get("label"),
                                     "reason": "one instrument produced nothing",
                                     "i1": report, "i2_mm": (i2 * MM) if i2 else None})
            continue
        gap = abs(i2 * MM - report["reached_mm"])
        if gap > MIS_WIDTH_MM:
            exclusions["V4"].append({"trial": row["trial"], "label": row.get("label"),
                                     "reason": "instruments disagree", "gap_mm": gap,
                                     "i1_mm": report["reached_mm"], "i2_mm": i2 * MM})
            continue
        row = dict(row)
        row["_i1"] = report
        row["_instrument_gap_mm"] = gap
        valid.append(row)

    by_command: dict[float, list] = {}
    for row in valid:
        by_command.setdefault(round(row["commanded_width_m"], 6), []).append(row)

    per_command = []
    for command in sorted(by_command):
        group = by_command[command]
        ratios = [r["ratio_i2"] for r in group]
        in_band = [r for r in group if r["ratio_i2"] is not None and r["ratio_i2"] < 1.0]
        per_command.append(
            {
                "w_cmd_mm": command * MM,
                "n": len(group),
                "reached_width_mm": summarise([r["reached_width_m_i2"] * MM for r in group]),
                "margin_mm": summarise([r["margin_m_i2"] * MM for r in group]),
                "threshold_mm": summarise([r["threshold_m_i2"] * MM for r in group]),
                "ratio": summarise(ratios),
                "q_at_stall_rad": summarise([r["q_at_stall_rad"] for r in group]),
                "n_in_band": len(in_band),
                "wilson95_in_band": wilson(len(in_band), len(group)),
                "D1": "OBSERVED" if in_band else "NOT OBSERVED",
                "predicate_i2_true": sum(1 for r in group if r.get("predicate_i2")),
                "pick_reported_holding": sum(1 for r in group if r.get("pick_reported_holding")),
                "pick_result_codes": sorted({r.get("pick_result_code") for r in group},
                                            key=lambda v: (v is None, v)),
                "i1_verdict_holding": sum(1 for r in group if r["_i1"]["verdict"] == "holding"),
                "i4_holding": sum(1 for r in group if r.get("i4_holding")),
                "instrument_gap_mm": summarise([r["_instrument_gap_mm"] for r in group]),
            }
        )

    # D2 -- does the distribution move with the commanded width?
    groups = [[r["reached_width_m_i2"] * MM for r in by_command[c]] for c in sorted(by_command)]
    kruskal = None
    if len(groups) >= 2 and all(len(g) >= 2 for g in groups):
        statistic, p = stats.kruskal(*groups)
        kruskal = {"H": float(statistic), "p": float(p)}
    anchor = round(0.045, 6)
    shifts = []
    if anchor in by_command:
        reference = [r["reached_width_m_i2"] * MM for r in by_command[anchor]]
        for command in sorted(by_command):
            if command == anchor:
                continue
            other = [r["reached_width_m_i2"] * MM for r in by_command[command]]
            shifts.append(
                {
                    "w_cmd_mm": command * MM,
                    "HL_shift_mm": hodges_lehmann(other, reference),
                    "mannwhitney_p": float(stats.mannwhitneyu(other, reference).pvalue)
                    if other and reference else None,
                }
            )
    largest_shift = max((abs(s["HL_shift_mm"]) for s in shifts), default=float("nan"))
    detected = (
        kruskal is not None
        and kruskal["p"] < ALPHA
        and largest_shift == largest_shift
        and largest_shift >= MIS_WIDTH_MM
    )

    # Rule R -- resolution. Applied to every metric, reported for every metric.
    resolution = []
    for entry in per_command:
        for metric, mis in (("reached_width_mm", MIS_WIDTH_MM), ("margin_mm", MIS_WIDTH_MM),
                            ("threshold_mm", MIS_WIDTH_MM), ("ratio", MIS_RATIO)):
            iqr = entry[metric].get("iqr")
            resolution.append(
                {
                    "w_cmd_mm": entry["w_cmd_mm"],
                    "metric": metric,
                    "iqr": iqr,
                    "MIS": mis,
                    "UNRESOLVED": iqr is not None and iqr > mis,
                }
            )

    # V5 -- the block effect, on `reached_width_mm` at each command.
    block_effect = []
    for command in sorted(by_command):
        per_block: dict[str, list] = {}
        for row in by_command[command]:
            per_block.setdefault(row["label"], []).append(row["reached_width_m_i2"] * MM)
        if len(per_block) == 2:
            (first, second) = list(per_block.values())
            block_effect.append(
                {
                    "w_cmd_mm": command * MM,
                    "within_block_HL_mm": abs(hodges_lehmann(first, second)),
                    "labels": list(per_block),
                }
            )
    within = max((b["within_block_HL_mm"] for b in block_effect), default=float("nan"))
    v5_downgrade = (
        within == within and largest_shift == largest_shift and within > largest_shift
    )

    # D3 -- the band edge against the distribution.
    all_reached = [r["reached_width_m_i2"] * MM for r in valid]
    all_threshold = [r["threshold_m_i2"] * MM for r in valid]
    band_edge_cmd_mm = (
        float(np.median(all_reached) - np.median(all_threshold)) if all_reached else float("nan")
    )
    reached_iqr = summarise(all_reached).get("iqr", float("nan"))
    d3 = {
        "pooled_reached_width_mm": summarise(all_reached),
        "pooled_threshold_mm": summarise(all_threshold),
        "band_edge_in_commanded_terms_mm": band_edge_cmd_mm,
        "distance_from_shipped_45mm_mm": band_edge_cmd_mm - 45.0,
        "distance_in_pooled_IQR_of_reached": (
            (band_edge_cmd_mm - 45.0) / reached_iqr if reached_iqr else float("nan")
        ),
        "validator_ceiling_mm": VALIDATOR_CEILING_MM,
        "band_edge_below_validator_ceiling": band_edge_cmd_mm < VALIDATOR_CEILING_MM,
    }

    # D6 -- the unvalidated caller-supplied width.
    at48 = next((e for e in per_command if abs(e["w_cmd_mm"] - 48.0) < 1e-6), None)
    at45 = next((e for e in per_command if abs(e["w_cmd_mm"] - 45.0) < 1e-6), None)
    d6 = {
        "at_48mm": at48,
        "at_45mm": at45,
        "D6": (
            "DEMONSTRATED"
            if at48 and at45 and at48["n_in_band"] > 0 and at45["n_in_band"] == 0
            else "NOT DEMONSTRATED"
        ),
        "48mm_is_above_validator_ceiling": 48.0 > VALIDATOR_CEILING_MM,
    }

    any_in_band = any(e["n_in_band"] for e in per_command)
    minimum_ratio = min((e["ratio"].get("min", float("inf")) for e in per_command
                         if e["ratio"].get("n")), default=float("nan"))
    contact_witnessed = sum(1 for r in rows if r.get("finger_contact_points_max"))

    return {
        "present": True,
        "blocks": blocks,
        "n_trials": len(rows),
        "n_valid": len(valid),
        "exclusions": exclusions,
        "per_command": per_command,
        "D2": {
            "kruskal": kruskal,
            "shifts_against_45mm": shifts,
            "largest_HL_shift_mm": largest_shift,
            "MIS_mm": MIS_WIDTH_MM,
            "verdict": "DETECTED" if detected else "NOT DETECTED",
        },
        "V5_block_effect": {
            "per_command": block_effect,
            "largest_within_block_HL_mm": within,
            "downgrade_D2_to_INCONCLUSIVE": v5_downgrade,
        },
        "rule_R": resolution,
        "D3": d3,
        "D6": d6,
        "rule_M": (
            "does not fire" if any_in_band
            else f"FIRES -- no trial fell in the band; minimum ratio {minimum_ratio}"
        ),
        "rule_S": (
            "does not fire"
            if contact_witnessed > len(rows) / 2
            else "FIRES -- I5 witnessed contact in a minority of trials; Q1 is INCONCLUSIVE"
        ),
        "contact_witnessed_trials": contact_witnessed,
    }


def main() -> int:
    analysis = {"AR": analyse_ar(), "FP": analyse_fp(), "FN": analyse_fn()}
    (RAW / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str))
    print(json.dumps(analysis, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
