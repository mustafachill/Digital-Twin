#!/usr/bin/env python3
"""`criteria.md` section 7's decision rules, applied to `raw/`.

DERIVED IN SHAPE FROM
`docs/measurements/2026-09-01-grasp-discrimination/harness/analyse.py`, copied at commit
`cab7ca1` -- the "one function per registered threshold, and the rule prints even when it
does not fire" shape is that file's. Every rule below is this campaign's own. That
directory is frozen and nothing in it is edited from here.

WRITTEN BEFORE THE FIRST TRIAL, which is the point. A rule implemented after the data has
been seen is a rule chosen by the data, and `criteria.md` V9 forbids moving one afterwards:
a threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong, as a
numbered deviation in `ANALYSIS.md`.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, sets no band, and
chooses nothing (`criteria.md` section 0). It prints what the registered rules say about
the trials that ran, and stops.

    python3 analyse.py --raw docs/measurements/2026-09-02-option-f-regions/raw
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

MM = 1000.0

#: `criteria.md` section 7.0. Every one derived from the geometry or the system's own
#: declared tolerances, never from campaign data.
MIS_WIDTH_M = 0.0001
MIS_YAW_DEG = 0.5
MIS_DRIVE_RAD = 0.001
REFINE_BRACKET_MM = 0.05

#: Rule W's own size: a campaign with no trial within this of the wide edge HAS NOT
#: TESTED that edge, and its silence there may not be read as a pass.
RULE_W_APPROACH_M = 0.0001


def load(raw: Path, prefix: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(raw.glob(f"{prefix}*_trials.json")):
        rows.extend(json.loads(path.read_text()))
    if not rows:
        for path in sorted(raw.glob(f"{prefix}_trials.json")):
            rows.extend(json.loads(path.read_text()))
    return rows


def valid(rows: list[dict]) -> list[dict]:
    """Trials that ran and whose block was not discarded by V1 or V2.

    V1 and V2 are evaluated where the data was taken and travel on the record, so this
    reads them rather than re-deriving them from a tree that has since moved.
    """
    kept = []
    for row in rows:
        if not row.get("ok"):
            continue
        if not row.get("provenance", {}).get("v1_clean", False):
            continue
        kept.append(row)
    return kept


#: What `criteria.md` V4 assumes, per rig, and where that assumption does not hold.
#:
#: V4 requires two width instruments to agree to 0.100 mm. Its premise is that I1 and I3
#: read ONE close on a joint that has stopped moving. That premise holds in three of the
#: five rigs here and fails in two, for two different structural reasons -- both found in
#: the shakedown, before any campaign trial ran, and NEITHER fixed by moving the rule
#: (V9). The rule is applied literally and this is printed beside every exclusion so that
#: a smaller n is never mistaken for a defect in the cell.
V4_PREMISE = {
    "A": "FAILS BY CONSTRUCTION. The close is the same, but in free air the joint is "
         "still MOVING when `GripperActionController` ends the goal at "
         "|error| < goal_tolerance. I1 is the position at that instant; I3 is the last "
         "sample at or before the result ARRIVES, a few milliseconds later, by which "
         "time the joint has closed further. The gap is bounded by roughly one "
         "goal_tolerance of width, about ten times V4's tolerance, and no action round "
         "trip is short enough to close it.",
    "B": "holds -- the joint is resting on a hard stop and is not moving.",
    "C": "holds -- the joint is stalled on the part.",
    "D/grasp48": "holds -- the joint is stalled on the part.",
    "D/pick45": "FAILS BY CONSTRUCTION. `Pick` produces no `Grasp.Result`, so there is "
                "no I1 for its close at all. What this harness records as I1 is a "
                "SECOND close, on the jaws as they stand after the Pick, and the two "
                "readings are of two events separated by a retreat.",
}


def v4_kept(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """V4 -- a trial whose two width instruments disagree is excluded from the DISTRIBUTION.

    Excluded and reported, never absorbed and never answered by widening the tolerance
    (V9). The pair comes back so that the count of exclusions is printed beside the
    distribution it was taken out of.
    """
    kept = [row for row in rows if row.get("v4_ok")]
    dropped = [row for row in rows if not row.get("v4_ok")]
    return kept, dropped


def edge_of(rows: list[dict], which: str) -> float:
    """F's window edge, read from the block the trials belong to.

    Never a literal. The window is a function of four L0 statements, and a number written
    here would be the fifth place they live (P1). It reaches the record through the
    header the runner wrote beside the trials.
    """
    for row in rows:
        window = row.get("window_m")
        if window:
            return window["edge_lo" if which == "lo" else "edge_hi"]
    raise RuntimeError(
        "no trial in this group carries the window it was judged against, so section "
        "7.1's median form cannot be evaluated without inventing an edge")


def summarise(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    n = len(ordered)

    def quantile(fraction: float) -> float:
        if n == 1:
            return ordered[0]
        position = fraction * (n - 1)
        low = int(math.floor(position))
        high = min(low + 1, n - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {
        "n": n,
        "min": ordered[0],
        "q1": quantile(0.25),
        "median": quantile(0.5),
        "q3": quantile(0.75),
        "iqr": quantile(0.75) - quantile(0.25),
        "max": ordered[-1],
    }


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """A Wilson 95 % interval, which V8 requires wherever a count is a proportion."""
    if n == 0:
        return None
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def block_effect(rows: list[dict], condition_key: str, metric_key: str) -> dict:
    """V6 -- if the between-block difference at one condition exceeds the largest
    between-condition difference, that metric's finding is INCONCLUSIVE whatever any test
    statistic says.
    """
    by_block: dict[tuple, list[float]] = {}
    for row in rows:
        value = row.get(metric_key)
        if value is None:
            continue
        by_block.setdefault((row.get("label"), row.get(condition_key)), []).append(value)
    medians = {key: summarise(values)["median"] for key, values in by_block.items()}
    conditions = {key[1] for key in medians}
    labels = sorted({key[0] for key in medians})
    within = 0.0
    for condition in conditions:
        present = [medians[(label, condition)] for label in labels
                   if (label, condition) in medians]
        if len(present) > 1:
            within = max(within, max(present) - min(present))
    across = 0.0
    for label in labels:
        present = [medians[(label, condition)] for condition in conditions
                   if (label, condition) in medians]
        if len(present) > 1:
            across = max(across, max(present) - min(present))
    return {
        "largest_between_block_difference": within,
        "largest_between_condition_difference": across,
        "v6_downgrades_to_inconclusive": within > across and across > 0.0,
        "blocks": labels,
    }


# ---------------------------------------------------------------------------
# A1 -- the free-air region
# ---------------------------------------------------------------------------
def arm_a(raw: Path) -> None:
    rows = valid(load(raw, "A"))
    print("\n=== Arm A -- criteria.md 7.1, the free-air region ===")
    print(f"V4 premise, Arm A: {V4_PREMISE['A']}")
    if not rows:
        print("no valid Arm A trials")
        return
    permitted = [row for row in rows if row.get("i6_source") != "Refused"]
    refused = [row for row in rows if row.get("i6_source") == "Refused"]

    print(f"{'w_cmd':>7} {'n':>3} {'I6':>8} {'w_reached median':>17} {'IQR':>8} "
          f"{'stalled':>8} {'reached_goal':>13} {'holding_F':>10} {'holding_S':>10} "
          f"{'d_narrow median':>16} {'A1b/trial':>10}")
    widths = sorted({row["commanded_width_mm"] for row in rows})
    for width in widths:
        at = [row for row in rows if row["commanded_width_mm"] == width]
        # V4 excludes a trial from the DISTRIBUTION and reports it. It is expected to
        # fire across this arm for a structural reason -- see `common.v4` -- so the
        # exclusion count is printed rather than left to be inferred from a smaller n.
        kept, dropped = v4_kept(at)
        reached = [row["i3_reached_width_m"] for row in kept
                   if row.get("i3_reached_width_m") is not None]
        narrow = [row["d_narrow_m"] for row in kept if row.get("d_narrow_m") is not None]
        stats = summarise(reached)
        # A1b -- whether `w_reached` fell inside the window, evaluated per trial where the
        # data was taken against the window the RUNNING node was given, and counted here.
        # Independently of A1a's flags: this is the clause that tests `gripper.hpp`'s
        # sentence "It falls below it at every command".
        inside = [row.get("a1b_inside_window") for row in at]
        print(
            f"{width:7.2f} {len(at):3d} {at[0].get('i6_source', '?'):>8} "
            f"{(stats.get('median') or float('nan')) * MM:17.4f} "
            f"{(stats.get('iqr') or float('nan')) * MM:8.4f} "
            f"{sum(1 for r in at if r.get('stalled')):8d} "
            f"{sum(1 for r in at if r.get('reached_goal')):13d} "
            f"{sum(1 for r in at if r.get('holding_F')):10d} "
            f"{sum(1 for r in at if r.get('holding_S')):10d} "
            f"{(summarise(narrow).get('median') or float('nan')) * MM:16.4f} "
            f"{sum(1 for value in inside if value):10d}"
        )
        # A1b as section 7.1 words it: on the MEDIAN, and by more than the 0.100 mm MIS.
        # It is computed on the V4-kept trials, so a command whose trials V4 all excluded
        # has no answer here -- which is reported rather than filled in from the looser
        # per-trial count printed above.
        if stats.get("n"):
            median = stats["median"]
            verdict = ("INSIDE" if (median - edge_of(at, "lo")) > MIS_WIDTH_M
                       and (edge_of(at, "hi") - median) > MIS_WIDTH_M else "OUTSIDE")
            print(f"        A1b (median, section 7.1's literal form): {verdict}")
        else:
            print("        A1b (median, section 7.1's literal form): UNANSWERABLE -- V4 "
                  "excluded every trial at this command")
        if dropped:
            print(f"        V4 excluded {len(dropped)}/{len(at)} trial(s) at "
                  f"{width:.2f} mm from the distribution above; the deltas are on the "
                  f"records and `i3_window_trace` is what explains them")
        if stats.get("iqr", 0.0) > REFINE_BRACKET_MM / MM:
            print(f"        rule R-A: within-command spread at {width:.2f} mm exceeds the "
                  f"0.05 mm bracket -- the flip is an interval, UNRESOLVED at 0.05 mm")
        if stats.get("iqr", 0.0) > MIS_WIDTH_M:
            print(f"        rule R-A: IQR at {width:.2f} mm exceeds the 0.100 mm MIS -- a "
                  f"non-detection here is INCONCLUSIVE, never 'no difference'")

    # A1 -- reproduced if any valid trial at a PERMITTED width reports holding with
    # nothing between the pads and no work-piece in the world.
    hits = [row for row in permitted
            if row.get("holding_F") and row.get("v3_no_workpiece")]
    print(f"\nA1 -- {'REPRODUCED' if hits else 'NOT REPRODUCED'} "
          f"(n = {len(permitted)} at permitted commands)")
    if not hits:
        print("rule N-A: not reproduced at n = "
              f"{len(permitted)}, at these commands, on this machine, on this backend. "
              "It may NEVER be written as 'free air is safe at any command'.")
    flagged = sum(1 for row in permitted
                  if row.get("stalled") and not row.get("reached_goal"))
    print(f"A1a -- trials reporting stalled and not reached_goal: {flagged}/{len(permitted)}")
    if flagged == 0:
        print("        A1a is false everywhere: the FIRST condition is what rejects free "
              "air on this backend and the window is never consulted.")
    insides = [row for row in permitted if row.get("a1b_inside_window")]
    print(f"A1b -- trials whose w_reached lies inside the window: {len(insides)}/"
          f"{len(permitted)}")
    if insides:
        lowest = min(row["commanded_width_mm"] for row in insides)
        print(f"        A1b goes INSIDE from {lowest:.2f} mm; section 2.2 predicts the "
              f"crossing between 46.554 and 46.766 mm")
    flips = [row["commanded_width_mm"] for row in permitted if row.get("holding_F")]
    if flips:
        print(f"        lowest commanded width with holding_F true: {min(flips):.2f} mm")
    if refused:
        print(f"\nWidths I6 returned Refused for, reported outside A1's verdict: "
              f"{sorted({row['commanded_width_mm'] for row in refused})}")
    print(json.dumps(block_effect(rows, "commanded_width_mm", "i3_reached_width_m"),
                     indent=2))


# ---------------------------------------------------------------------------
# B1 -- the region the removed term used to cover
# ---------------------------------------------------------------------------
def arm_b(raw: Path) -> None:
    rows = valid(load(raw, "B"))
    print("\n=== Arm B -- criteria.md 7.2, the jammed OPENING stroke ===")
    print(f"V4 premise, Arm B: {V4_PREMISE['B']}")
    if not rows:
        print("no valid Arm B trials")
        return
    usable = [row for row in rows if row.get("v5_valid")]
    print(f"V5: {len(usable)}/{len(rows)} trials had the stop engage, the joint rest on "
          f"it within {MIS_DRIVE_RAD} rad, and no start-outside-the-stops refusal")
    for row in rows:
        print(
            f"  jam {row['jam_width_mm']:6.2f} mm ({row['condition']:>7}) "
            f"w_reached={(row.get('i3_reached_width_m') or float('nan')) * MM:8.4f} mm "
            f"stalled={row.get('stalled')} reached_goal={row.get('reached_goal')} "
            f"holding_F={row.get('holding_F')} holding_S={row.get('holding_S')} "
            f"I7={row.get('i7_stop_announced')} I8_refused={row.get('i8_start_refused')}"
        )
    if all(row.get("i8_start_refused") for row in rows) and rows:
        print("EVERY LAUNCH CARRIED THE START-OUTSIDE-THE-STOPS REFUSAL. This arm produced "
              "no data at all and is reported as a launch that did not run, not as a null "
              "(criteria.md I8).")
    window_rows = [row for row in usable if row["condition"] == "window"]
    hits = [row for row in window_rows if row.get("holding_F")]
    print(f"\nB1 -- {'REPRODUCED' if hits else 'NOT REPRODUCED'} (n = {len(window_rows)} "
          f"valid in-window jams)")
    if not hits:
        print("rule N-B: not reproduced at n = "
              f"{len(window_rows)} on this rig. It may NOT be written as 'an opening "
              "stroke cannot produce a false positive', and it may not be generalised to "
              "a closing stroke in either direction (criteria.md 5.2's scope limit).")
    # P6 -- the three repeats per jam are expected to be exact replicates.
    for jam in sorted({row["jam_width_mm"] for row in rows}):
        at = [row["i3_q_at_stall_rad"] for row in rows
              if row["jam_width_mm"] == jam and row.get("i3_q_at_stall_rad") is not None]
        if len(at) > 1:
            spread = max(at) - min(at)
            note = "" if spread <= 1e-9 else "  <-- NON-ZERO SPREAD: a finding about the rig"
            print(f"  replicate spread at {jam:.2f} mm: {spread:.3e} rad{note}")


# ---------------------------------------------------------------------------
# C1 -- the wide edge
# ---------------------------------------------------------------------------
def arm_c(raw: Path) -> None:
    rows = valid(load(raw, "C"))
    print("\n=== Arm C -- criteria.md 7.3, the wide edge ===")
    print(f"V4 premise, Arm C: {V4_PREMISE['C']}")
    if not rows:
        print("no valid Arm C trials")
        return
    for yaw in sorted({row["yaw_setpoint_deg"] for row in rows}):
        at = [row for row in rows if row["yaw_setpoint_deg"] == yaw]
        stall_yaw = [row["yaw_at_stall_deg"] for row in at
                     if row.get("yaw_at_stall_deg") is not None]
        kept, dropped = v4_kept(at)
        reached = [row["i3_reached_width_m"] for row in kept
                   if row.get("i3_reached_width_m") is not None]
        presented = [row["presented_width_at_stall_m"] for row in at
                     if row.get("presented_width_at_stall_m") is not None]
        print(
            f"  yaw {yaw:5.1f} deg n={len(at)} "
            f"stall_yaw_median={(summarise(stall_yaw).get('median') or float('nan')):7.3f} deg "
            f"presented_median={(summarise(presented).get('median') or float('nan')) * MM:8.3f} mm "
            f"w_reached_median={(summarise(reached).get('median') or float('nan')) * MM:8.4f} mm "
            f"contact={sum(1 for r in at if r.get('v3_contact_witnessed'))}/{len(at)} "
            f"holding_F={sum(1 for r in at if r.get('holding_F'))} "
            f"v4_excluded={len(dropped)}"
        )
    witnessed = [row for row in rows if row.get("v3_contact_witnessed")]
    crossed = [row for row in witnessed
               if row.get("d_wide_m") is not None and row["d_wide_m"] < 0.0]
    print(f"\nC1 -- {'CROSSED' if crossed else 'NOT CROSSED'} "
          f"({len(witnessed)}/{len(rows)} trials with witnessed finger contact)")
    if len(witnessed) * 2 <= len(rows):
        print("rule S-C: I4 witnessed no finger contact in a majority of valid trials, so "
              "this arm has not measured a genuine grasp and C1 is INCONCLUSIVE whatever "
              "the widths say.")
    # Rule W, over EVERY arm that produced a genuine grasp -- mandatory, and it fires by
    # default rather than on request.
    approaches = []
    # ARMS C AND D ONLY. Rule W is about "every arm that produced a genuine grasp", and
    # neither of the other two produces one: Arm A closes on nothing by construction, and
    # Arm B stops on a synthetic stop with nothing between the pads. Letting either into
    # this set would report a distance to the wide edge measured on a trial that never
    # touched a part, which is the opposite of what the rule is protecting.
    for prefix in ("C", "D"):
        for row in valid(load(raw, prefix)):
            if row.get("d_wide_m") is None or not row.get("v3_contact_witnessed"):
                continue
            approaches.append((row["d_wide_m"], prefix, row.get("label"), row.get("trial")))
    if approaches:
        closest = min(approaches)
        print(f"closest approach to the wide edge, over every genuine grasp: "
              f"{closest[0] * MM:.4f} mm (arm {closest[1]}, {closest[2]} trial {closest[3]})")
        if closest[0] > RULE_W_APPROACH_M:
            print("RULE W FIRES: the campaign produced no trial within 0.100 mm of the "
                  "wide edge, so IT HAS NOT TESTED THAT EDGE. Its silence there may not be "
                  "read as a pass, as a validation of stall_band_wide_m, or as evidence "
                  "that the edge is far enough away. ADR-0052 section A.9.5 stands "
                  "unchanged.")
    else:
        print("RULE W FIRES: no genuine grasp produced a d_wide at all.")
    print(json.dumps(block_effect(rows, "yaw_setpoint_deg", "i3_reached_width_m"), indent=2))
    if any((row.get("yaw_at_stall_deg") is not None
            and abs(row["yaw_at_stall_deg"] - row["yaw_setpoint_deg"]) > MIS_YAW_DEG)
           for row in rows):
        print("the yaw at the stall differs from the setpoint by more than the 0.5 deg "
              "MIS in at least one trial -- the squaring the conveyor-yaw campaign found "
              "is the candidate explanation, and criteria.md 7.3 requires the write-up to "
              "distinguish it from an edge that is simply far away, or to say it cannot.")


# ---------------------------------------------------------------------------
# D1 -- the false-negative side
# ---------------------------------------------------------------------------
def arm_d(raw: Path) -> None:
    rows = valid(load(raw, "D"))
    print("\n=== Arm D -- criteria.md 7.4, the false-negative side ===")
    for door in ("D/pick45", "D/grasp48"):
        print(f"V4 premise, {door}: {V4_PREMISE[door]}")
    if not rows:
        print("no valid Arm D trials")
        return
    refusals = [row for row in rows if row["condition"] == "refusal"]
    grasps = [row for row in rows if row["condition"] != "refusal"]
    for condition in sorted({row["condition"] for row in grasps}):
        at = [row for row in grasps if row["condition"] == condition]
        witnessed = [row for row in at if row.get("v3_contact_witnessed")]
        kept, dropped = v4_kept(witnessed)
        reached = [row["i3_reached_width_m"] for row in kept
                   if row.get("i3_reached_width_m") is not None]
        narrow = [row["d_narrow_m"] for row in kept
                  if row.get("d_narrow_m") is not None]
        empty = sum(1 for row in witnessed if row.get("holding_F") is False)
        interval = wilson(empty, len(witnessed))
        print(f"  {condition}: n={len(at)} witnessed={len(witnessed)} "
              f"v4_excluded={len(dropped)}")
        print(f"    w_reached  {json.dumps(summarise(reached))}")
        print(f"    d_narrow   {json.dumps(summarise(narrow))}")
        print(f"    holding_F false: {empty}/{len(witnessed)}"
              + (f", Wilson 95 % [{interval[0]:.3f}, {interval[1]:.3f}]" if interval else ""))
        print(f"    holding_S true : {sum(1 for row in witnessed if row.get('holding_S'))}")
    pooled = [row for row in grasps if row.get("v3_contact_witnessed")]
    observed = [row for row in pooled if row.get("holding_F") is False]
    print(f"\nD1 -- {'OBSERVED' if observed else 'NOT OBSERVED'} (n = {len(pooled)} with "
          f"witnessed finger contact)")
    minimum = summarise([row["d_narrow_m"] for row in pooled
                         if row.get("d_narrow_m") is not None]).get("min")
    if not observed:
        print("rule M: not observed at n = "
              f"{len(pooled)}, at these commands, on this machine -- NEVER 'the defect "
              f"does not occur'. Minimum observed d_narrow: "
              f"{(minimum or float('nan')) * MM:.4f} mm")
    print("\nthe three Pick-at-48.0 mm refusal trials, reported and not judged:")
    for row in refusals:
        print(f"  code={row.get('pick_result_code')} "
              f"precondition_failed={row.get('pick_precondition_failed')} "
              f"max_joint_movement_rad={row.get('max_joint_movement_rad')}")
        print(f"    detail: {row.get('pick_detail')}")
    print(json.dumps(block_effect(grasps, "condition", "i3_reached_width_m"), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=str(Path(__file__).resolve().parent.parent / "raw"))
    arguments = parser.parse_args()
    raw = Path(arguments.raw)
    print(f"criteria.md section 7, applied to {raw}")
    print("RULE T -- the arms are not each other's evidence. A clean result in one says "
          "nothing about any other, and every verdict below is stated per arm.")
    arm_b(raw)
    arm_a(raw)
    arm_d(raw)
    arm_c(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
