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

#: `criteria.md` V9 -- a threshold discovered to be wrong is APPLIED LITERALLY and
#: recorded as wrong, as a NUMBERED deviation in `ANALYSIS.md`, against data already
#: collected. These are the deviations known before the first campaign trial ran, found
#: by the shakedown and by the review of the harness that followed it. They are printed
#: at the top of every run so that the write-up carries them and cannot quietly drop one.
#:
#: A deviation is where an interpretation had to CHANGE. Computing the decision
#: quantities from I1 is not on this list: that is the harness being corrected to match
#: what `criteria.md` section 2.1 already said, not a departure from it.
DEVIATIONS = (
    ("1",
     "Section 7.1's A1b in its LITERAL MEDIAN FORM is UNANSWERABLE in Arm A, and the "
     "per-trial I1-based A1b is reported in its place. V4 requires I1 and I3 to agree to "
     "0.100 mm; in free air the drive joint is still MOVING when the controller ends the "
     "goal, so the two read one joint at two instants and sit several times that apart "
     "(0.566 mm and 0.610 mm in the shakedown). V4 is applied literally -- every Arm A "
     "trial is excluded from the DISTRIBUTION -- so no median survives to test. A1b is a "
     "question about where a width fell, it is answered per trial from I1 without any "
     "distribution, and it is printed below as such. A1's own verdict and A1a survive V4 "
     "untouched: both are read from I2's exact booleans, not from a width."),
    ("2",
     "Section 5.1's refinement is registered against the `holding_F` FLIP, which the "
     "shakedown shows does not occur -- free air ends `reached_goal=true`, so `holding_F` "
     "is false at every command and no flip exists to bracket. Section 7.1 registers the "
     "alternative in the same breath: 'or, if A1a is false throughout, at which A1b goes "
     "INSIDE'. So `A_REFINE` brackets the A1b crossing, computed from I1, at the same "
     "registered 0.05 mm step and three trials per point. The step is unchanged; only "
     "which crossing it brackets is."),
    ("3",
     "V4 is UNEVALUABLE rather than failed for Arm D's `Pick` door. `Pick` returns no "
     "`Grasp.Result`, so that close has no I1 and a two-instrument rule cannot be "
     "applied. Those trials stay in the distribution and are counted separately; trials "
     "that HAVE both instruments and fail the comparison are still excluded, literally."),
    ("4",
     "Arm D's `pick45` decision quantity is I3 and not I1, for the same reason: the "
     "shipped production path publishes no `Grasp.Result`, and I2's `%.1f` line is the "
     "COARSE instrument section 4.1 reserves for V4. Every `pick45` record carries "
     "`w_reached_source` saying so. The VERDICT for that door is `Pick.Result.holding`, "
     "which IS the shipped predicate's answer on that close."),
)


def load(raw: Path, prefix: str) -> list[dict]:
    """Every block file for one arm. `A` picks up `A_B1`, `A_B2` and `A_REFINE`.

    One glob, not two: `{prefix}*_trials.json` already matches `{prefix}_trials.json`,
    so the second pass that used to sit here could never add a file the first had not.
    """
    rows: list[dict] = []
    for path in sorted(raw.glob(f"{prefix}*_trials.json")):
        rows.extend(json.loads(path.read_text()))
    return rows


def valid(rows: list[dict]) -> list[dict]:
    """Trials that ran and that V1, V2, V3 and V7 do not discard.

    Each of those rules is evaluated WHERE THE DATA WAS TAKEN and travels on the record,
    so this reads them rather than re-deriving them from a tree that has since moved.

    WHAT EACH CLAUSE BELOW ACTUALLY READS, because this docstring claimed two rules it
    did not apply until 2026-09-02:

      * V1 -- `provenance.v1_clean`, computed per block from `git diff BASE..HEAD` over
        the three watched paths and the worktree's dirtiness in them.
      * V2 and V7 -- `v2_ok` and `v7_ok`, the running cell's own description. A runner
        that brings a cell up ABORTS the block on either, so a discarded block normally
        contributes no trials at all; these are read anyway because a rule enforced only
        by a runner is a rule no reader of `raw/` can check. `None` means the rig has no
        such quantity (Arm B brings no cell up) and is not a failure.
      * V3 -- Arm A's clause only, `v3_no_workpiece`. Arms C and D take V3's other
        clause -- witnessed finger contact -- and apply it in their own sections, where
        the trials that fail it are still needed to report the contact count. Arm B has
        no work-piece and no such field.
    """
    kept = []
    for row in rows:
        if not row.get("ok"):
            continue
        if not row.get("provenance", {}).get("v1_clean", False):
            continue
        if row.get("v2_ok") is False or row.get("v7_ok") is False:
            continue
        # V3, Arm A: "a trial contributes only if I4 reports no contact at all and, for
        # Arm A, no work-piece exists in the world. A trial that finds one is discarded:
        # it is not a free-air trial."
        if row.get("v3_no_workpiece") is False:
            continue
        kept.append(row)
    return kept


def stat(values: dict, key: str) -> float:
    """One summary figure, or NaN -- and a legitimate 0.0 is NOT NaN.

    `summarise(...).get(key) or float("nan")` printed NaN for a median of exactly 0.0,
    because 0.0 is falsy. `d_narrow` is a signed distance to a window edge and 0.0 is a
    value it can genuinely take; printing that as "no data" would hide the one reading
    that sits exactly on the edge.
    """
    value = values.get(key)
    return float("nan") if value is None else value


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
    "D/pick45": "UNEVALUABLE: there is no `Grasp.Result` for this door. `Pick` produces "
                "none, so its close has no I1, and a rule comparing two instruments "
                "cannot be applied where only one exists. IT IS NOT FAILED -- a trial "
                "missing an instrument has not exceeded a tolerance, and excluding it "
                "would empty the `w_reached` and `d_narrow` distributions for the SHIPPED "
                "production path, which is what ADR-0052 section A.10 item 2 asks for. "
                "This harness reported it as failing by construction until 2026-09-02, "
                "and that reading was manufactured by the harness comparing I1 from a "
                "SECOND close against I3 from the first; read against the Pick's own I2 "
                "line the two sit about 0.08 mm apart, INSIDE V4's 0.100 mm.",
}


def v4_kept(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """V4 -- a trial whose two width instruments DISAGREE is excluded from the DISTRIBUTION.

    Excluded and reported, never absorbed and never answered by widening the tolerance
    (V9). The three lists come back so that both counts are printed beside the
    distribution they were taken out of.

    THREE OUTCOMES, NOT TWO, and the third is the one this returned wrongly until
    2026-09-02. V4 excludes a trial "exceeding" its tolerance. A trial for which one of
    the two instruments DOES NOT EXIST has not exceeded anything -- the rule is
    unevaluable there, not failed -- so it stays in the distribution and is reported
    under its own count. Folding unevaluable into failed dropped every `pick45` trial,
    which is 8 of Arm D's 16 grasps and the whole of the shipped production path.
    """
    kept = [row for row in rows if row.get("v4_ok") is True]
    dropped = [row for row in rows if row.get("v4_ok") is False]
    unevaluable = [row for row in rows if row.get("v4_ok") is None]
    return kept + unevaluable, dropped, unevaluable


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
    print("w_reached is I1 -- `Grasp.Result.reached_width_m`, which criteria.md 2.1 "
          "defines as the width the predicate CONSUMES. The I3 column beside it is the "
          "same quantity read independently of the skill server (4.1), which is the "
          "cross-check V4 is the rule over, and is NOT what any verdict here is taken "
          "from.")
    if not rows:
        print("no valid Arm A trials")
        return
    permitted = [row for row in rows if row.get("i6_source") != "Refused"]
    refused = [row for row in rows if row.get("i6_source") == "Refused"]

    print(f"{'w_cmd':>7} {'n':>3} {'I6':>8} {'w_reached I1 med':>17} {'IQR':>8} "
          f"{'I3 med':>9} {'stalled':>8} {'reached_goal':>13} {'holding_F':>10} "
          f"{'holding_S':>10} {'d_narrow med':>13} {'A1b/trial':>10}")
    widths = sorted({row["commanded_width_mm"] for row in rows})
    for width in widths:
        at = [row for row in rows if row["commanded_width_mm"] == width]
        # V4 excludes a trial from the DISTRIBUTION and reports it. It is expected to
        # fire across this arm for a structural reason -- see `common.v4` -- so the
        # exclusion count is printed rather than left to be inferred from a smaller n.
        kept, dropped, unevaluable = v4_kept(at)
        reached = [row["i1_reached_width_m"] for row in kept
                   if row.get("i1_reached_width_m") is not None]
        narrow = [row["d_narrow_m"] for row in kept if row.get("d_narrow_m") is not None]
        i3 = [row["i3_reached_width_m"] for row in at
              if row.get("i3_reached_width_m") is not None]
        stats = summarise(reached)
        # I2's booleans are counted over trials whose I2 line actually arrived. A trial
        # whose report never flushed carries `stalled = None`, and `None` is not a
        # measured `false` -- A1a is a count of exactly this boolean.
        read = [row for row in at if not row.get("i2_report_missing")]
        # A1b -- whether `w_reached` fell inside the window, evaluated per trial where the
        # data was taken against the window the RUNNING node was given, and counted here.
        # Independently of A1a's flags: this is the clause that tests `gripper.hpp`'s
        # sentence "It falls below it at every command".
        inside = [row.get("a1b_inside_window") for row in at]
        print(
            f"{width:7.2f} {len(at):3d} {at[0].get('i6_source', '?'):>8} "
            f"{stat(stats, 'median') * MM:17.4f} "
            f"{stat(stats, 'iqr') * MM:8.4f} "
            f"{stat(summarise(i3), 'median') * MM:9.4f} "
            f"{sum(1 for r in read if r.get('stalled')):8d} "
            f"{sum(1 for r in read if r.get('reached_goal')):13d} "
            f"{sum(1 for r in at if r.get('holding_F')):10d} "
            f"{sum(1 for r in at if r.get('holding_S')):10d} "
            f"{stat(summarise(narrow), 'median') * MM:13.4f} "
            f"{sum(1 for value in inside if value):10d}"
        )
        if len(read) != len(at):
            print(f"        {len(at) - len(read)}/{len(at)} trial(s) at {width:.2f} mm "
                  f"produced no I2 report line and are excluded from the two flag counts "
                  f"above rather than counted as `false`")
        # A1b as section 7.1 words it: on the MEDIAN, and by more than the 0.100 mm MIS.
        # It is computed on the V4-kept trials, so a command whose trials V4 all excluded
        # has no answer here -- which is reported rather than filled in from the looser
        # per-trial count printed above. That is deviation 1.
        if stats.get("n"):
            median = stats["median"]
            verdict = ("INSIDE" if (median - edge_of(at, "lo")) > MIS_WIDTH_M
                       and (edge_of(at, "hi") - median) > MIS_WIDTH_M else "OUTSIDE")
            print(f"        A1b (median, section 7.1's literal form): {verdict}")
        else:
            print("        A1b (median, section 7.1's literal form): UNANSWERABLE -- V4 "
                  "excluded every trial at this command. DEVIATION 1: the per-trial "
                  f"I1-based A1b at this command is "
                  f"{sum(1 for value in inside if value)}/{len(at)} INSIDE")
        if dropped:
            print(f"        V4 excluded {len(dropped)}/{len(at)} trial(s) at "
                  f"{width:.2f} mm from the distribution above; the deltas are on the "
                  f"records and `i3_window_trace` is what explains them")
        if unevaluable:
            print(f"        V4 was UNEVALUABLE on {len(unevaluable)}/{len(at)} trial(s) "
                  f"at {width:.2f} mm -- kept in the distribution, not excluded")
        if stats.get("iqr", 0.0) > REFINE_BRACKET_MM / MM:
            print(f"        rule R-A: within-command spread at {width:.2f} mm exceeds the "
                  f"0.05 mm bracket -- the flip is an interval, UNRESOLVED at 0.05 mm")
        if stats.get("iqr", 0.0) > MIS_WIDTH_M:
            print(f"        rule R-A: IQR at {width:.2f} mm exceeds the 0.100 mm MIS -- a "
                  f"non-detection here is INCONCLUSIVE, never 'no difference'")
        # RULE R-A CANNOT FIRE ON AN EMPTY DISTRIBUTION, and an empty one is exactly what
        # V4 leaves in Arm A (deviation 1). The rule is applied literally above, to the
        # V4-kept trials it is registered over; the spread over ALL trials at this command
        # is printed here as an OBSERVATION so that "R-A did not fire" is never read as
        # "the spread is within the bracket". It is not the rule and no verdict uses it.
        if not stats.get("n"):
            everything = summarise([row["i1_reached_width_m"] for row in at
                                    if row.get("i1_reached_width_m") is not None])
            if everything.get("n"):
                print(f"        observation only, NOT rule R-A: over all {everything['n']} "
                      f"trial(s) at this command, including those V4 excluded, the I1 "
                      f"spread is IQR {everything['iqr'] * MM:.4f} mm, "
                      f"min {everything['min'] * MM:.4f}, max {everything['max'] * MM:.4f}")

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
    # A1 and A1a survive V4. Both are read from I2's EXACT booleans and from
    # `Grasp.Result.holding`, not from a width, and V4 excludes a trial "from the
    # distribution" -- which is a statement about widths.
    read_permitted = [row for row in permitted if not row.get("i2_report_missing")]
    flagged = sum(1 for row in read_permitted
                  if row.get("stalled") and not row.get("reached_goal"))
    print(f"A1a -- trials reporting stalled and not reached_goal: {flagged}/"
          f"{len(read_permitted)} (over trials whose I2 line was read; "
          f"{len(permitted) - len(read_permitted)} had none)")
    if flagged == 0:
        print("        A1a is false everywhere: the FIRST condition is what rejects free "
              "air on this backend and the window is never consulted.")
    insides = [row for row in permitted if row.get("a1b_inside_window")]
    print(f"A1b -- trials whose w_reached (I1) lies inside the window: {len(insides)}/"
          f"{len(permitted)}   [DEVIATION 1: this is the per-trial form; the median form "
          f"section 7.1 words is unanswerable wherever V4 excluded every trial]")
    if insides:
        lowest = min(row["commanded_width_mm"] for row in insides)
        print(f"        A1b goes INSIDE from {lowest:.2f} mm; section 2.2 predicts the "
              f"crossing between 46.554 and 46.766 mm")
    # The same crossing read off the CROSS-CHECK instrument, printed so that the size of
    # deviation 1 is visible rather than asserted. It is not a verdict.
    insides_i3 = [row for row in permitted if row.get("a1b_inside_window_i3")]
    if insides_i3:
        print(f"        cross-check only, NOT a verdict: on I3 the same count is "
              f"{len(insides_i3)}/{len(permitted)} and A1b would go INSIDE from "
              f"{min(row['commanded_width_mm'] for row in insides_i3):.2f} mm")
    elif insides:
        print("        cross-check only, NOT a verdict: on I3 no trial lies inside the "
              "window at any command")
    flips = [row["commanded_width_mm"] for row in permitted if row.get("holding_F")]
    if flips:
        print(f"        lowest commanded width with holding_F true: {min(flips):.2f} mm")
    else:
        print("        no commanded width flipped holding_F to true, so section 5.1's "
              "registered refinement has no flip to bracket. DEVIATION 2: A_REFINE "
              "brackets the A1b crossing instead, which is section 7.1's own "
              "alternative, at the same registered 0.05 mm step.")
    if refused:
        print(f"\nWidths I6 returned Refused for, reported outside A1's verdict: "
              f"{sorted({row['commanded_width_mm'] for row in refused})}")
    # V6 is registered over TWO blocks. `A_REFINE` is a third label and is not a block:
    # it is a denser sweep over a bracket the coarse data located, so its rows would
    # enter this as a spurious third block and inflate the between-block difference --
    # making a downgrade to INCONCLUSIVE more likely for a reason V6 is not about.
    blocked = [row for row in rows if row.get("condition") != "refine"]
    print(json.dumps(block_effect(blocked, "commanded_width_mm", "i1_reached_width_m"),
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
            f"w_reached(I1)={stat(row, 'i1_reached_width_m') * MM:8.4f} mm "
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
        kept, dropped, unevaluable = v4_kept(at)
        reached = [row["i1_reached_width_m"] for row in kept
                   if row.get("i1_reached_width_m") is not None]
        presented = [row["presented_width_at_stall_m"] for row in at
                     if row.get("presented_width_at_stall_m") is not None]
        print(
            f"  yaw {yaw:5.1f} deg n={len(at)} "
            f"stall_yaw_median={stat(summarise(stall_yaw), 'median'):7.3f} deg "
            f"presented_median={stat(summarise(presented), 'median') * MM:8.3f} mm "
            f"w_reached_median(I1)={stat(summarise(reached), 'median') * MM:8.4f} mm "
            f"contact={sum(1 for r in at if r.get('v3_contact_witnessed'))}/{len(at)} "
            f"holding_F={sum(1 for r in at if r.get('holding_F'))} "
            f"v4_excluded={len(dropped)} v4_unevaluable={len(unevaluable)}"
        )
    witnessed = [row for row in rows if row.get("v3_contact_witnessed")]
    crossed = [row for row in witnessed
               if row.get("d_wide_m") is not None and row["d_wide_m"] < 0.0]
    print(f"\nC1 -- {'CROSSED' if crossed else 'NOT CROSSED'} "
          f"({len(witnessed)}/{len(rows)} trials with witnessed finger contact)")
    # "No finger contact in a MAJORITY of valid trials" is `n - witnessed > n / 2`, i.e.
    # `2 * witnessed < n`. The `<=` this used to carry also fired at exactly half without
    # contact, which is not a majority, and would have downgraded C1 to INCONCLUSIVE on a
    # tie.
    if 2 * len(witnessed) < len(rows):
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
    print(json.dumps(block_effect(rows, "yaw_setpoint_deg", "i1_reached_width_m"), indent=2))
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
        kept, dropped, unevaluable = v4_kept(witnessed)
        # `w_reached_m` is the decision quantity the RUNNER chose per door and named on
        # every record in `w_reached_source`: I1 for the `Grasp` door, I3 for the `Pick`
        # door, which publishes no `Grasp.Result` at all (deviation 4).
        reached = [row["w_reached_m"] for row in kept
                   if row.get("w_reached_m") is not None]
        narrow = [row["d_narrow_m"] for row in kept
                  if row.get("d_narrow_m") is not None]
        empty = sum(1 for row in witnessed if row.get("holding_F") is False)
        interval = wilson(empty, len(witnessed))
        sources = sorted({row.get("w_reached_source") for row in at})
        print(f"  {condition}: n={len(at)} witnessed={len(witnessed)} "
              f"v4_excluded={len(dropped)} v4_unevaluable={len(unevaluable)}")
        print(f"    w_reached from: {'; '.join(s for s in sources if s)}")
        print(f"    w_reached  {json.dumps(summarise(reached))}")
        print(f"    d_narrow   {json.dumps(summarise(narrow))}")
        print(f"    holding_F false: {empty}/{len(witnessed)}"
              + (f", Wilson 95 % [{interval[0]:.3f}, {interval[1]:.3f}]" if interval else ""))
        print(f"    holding_S true : {sum(1 for row in witnessed if row.get('holding_S'))}")
    pooled = [row for row in grasps if row.get("v3_contact_witnessed")]
    # `holding_F` for a `pick45` trial is `Pick.Result.holding` -- the shipped predicate's
    # verdict on the close the `Pick` itself performed. It was read from a SECOND close
    # until 2026-09-02, which meant the event D1 exists to catch -- that close reporting a
    # real grasp empty -- could not reach this verdict at all.
    observed = [row for row in pooled if row.get("holding_F") is False]
    print(f"\nD1 -- {'OBSERVED' if observed else 'NOT OBSERVED'} (n = {len(pooled)} with "
          f"witnessed finger contact)")
    minimum = summarise([row["d_narrow_m"] for row in pooled
                         if row.get("d_narrow_m") is not None]).get("min")
    if not observed:
        print("rule M: not observed at n = "
              f"{len(pooled)}, at these commands, on this machine -- NEVER 'the defect "
              f"does not occur'. Minimum observed d_narrow: "
              f"{(float('nan') if minimum is None else minimum) * MM:.4f} mm")
    print("\nthe three Pick-at-48.0 mm refusal trials, reported and not judged:")
    for row in refusals:
        print(f"  code={row.get('pick_result_code')} "
              f"precondition_failed={row.get('pick_precondition_failed')} "
              f"max_joint_movement_rad={row.get('max_joint_movement_rad')}")
        print(f"    detail: {row.get('pick_detail')}")
    print(json.dumps(block_effect(grasps, "condition", "w_reached_m"), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=str(Path(__file__).resolve().parent.parent / "raw"))
    arguments = parser.parse_args()
    raw = Path(arguments.raw)
    print(f"criteria.md section 7, applied to {raw}")
    print("RULE T -- the arms are not each other's evidence. A clean result in one says "
          "nothing about any other, and every verdict below is stated per arm.")
    print("\n=== Numbered deviations (criteria.md V9) ===")
    print("A threshold discovered to be wrong is APPLIED LITERALLY and recorded as wrong. "
          "None of these moved a threshold; each records where a registered form could "
          "not be evaluated as worded, and what was reported in its place. Every one was "
          "found BEFORE the first campaign trial ran and `criteria.md` was not touched.")
    for number, text in DEVIATIONS:
        print(f"\n  DEVIATION {number}. {text}")
    arm_b(raw)
    arm_a(raw)
    arm_d(raw)
    arm_c(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
