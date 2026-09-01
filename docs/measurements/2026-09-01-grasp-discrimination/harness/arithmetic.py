#!/usr/bin/env python3
"""Reference implementation of the gripper linkage arithmetic, and the §2 cross-check.

WHAT THIS IS FOR, AND WHAT IT IS NOT FOR.

It is a *reference* implementation, written from the L0 declaration and from the three
functions in ``cite_skills/src/gripper.cpp``, used for exactly two things:

  1. reproducing ADR-0052's published arithmetic independently, which is `criteria.md` §2;
  2. choosing the sweep points in `criteria.md` §5 before any trial ran.

**No reported campaign figure comes from here.** Every figure in `ANALYSIS.md` is produced
by the shipped implementations — ``cite_skills`` through ``predicate_eval``, and
``cite_tools.validate.physical`` imported directly — because a campaign about two
derivations disagreeing cannot answer itself with a third derivation.

Run it from anywhere; it needs nothing but the standard library.

    python3 arithmetic.py
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# The L0 declaration, transcribed once.
# model/assets/types/end_effectors/xarm_parallel_gripper.yaml
# ---------------------------------------------------------------------------
DRIVE_PIVOT_Y_M = 0.035  # linkage.drive_pivot_y_m
FINGER_OFFSET_Y_M = 0.035465  # linkage.finger_offset_y_m
FINGER_OFFSET_Z_M = 0.042039  # linkage.finger_offset_z_m
PAD_INSET_M = 0.026  # linkage.pad_inset_m
GOAL_TOLERANCE_RAD = 0.01  # controllers[].parameters.goal_tolerance
DEFAULT_GRASP_WIDTH_M = 0.045  # grasp.default_grasp_width_m
OPEN_POSITION_RAD = 0.0  # grasp.open_position
CLOSED_POSITION_RAD = 0.85  # grasp.closed_position
WORKPIECE_WIDTH_M = 0.050  # model/assets/types/workpieces/workpiece.yaml

PIVOT_M = DRIVE_PIVOT_Y_M - PAD_INSET_M
CRANK_M = math.hypot(FINGER_OFFSET_Y_M, FINGER_OFFSET_Z_M)
PHASE_RAD = math.atan2(FINGER_OFFSET_Z_M, FINGER_OFFSET_Y_M)


def opening_m(q: float) -> float:
    """``gripper_width_for`` — the jaw opening at drive position ``q``."""
    return 2.0 * (PIVOT_M + CRANK_M * math.cos(q + PHASE_RAD))


def position_for(width_m: float) -> float:
    """``gripper_position_for`` — the drive position that commands ``width_m``."""
    cosine = min(1.0, max(-1.0, (width_m / 2.0 - PIVOT_M) / CRANK_M))
    position = math.acos(cosine) - PHASE_RAD
    return min(max(position, OPEN_POSITION_RAD), CLOSED_POSITION_RAD)


def tolerance_m(q: float) -> float:
    """``gripper_width_tolerance_m`` — the LINEARISED derivation, at ``q``.

    ``|d(opening)/dq| * goal_tolerance``. This is what ``cite_skills`` computes, and it
    evaluates at the position the joint REACHED.
    """
    return abs(2.0 * CRANK_M * math.sin(q + PHASE_RAD) * GOAL_TOLERANCE_RAD)


def validator_margin_m(width_m: float) -> float:
    """``_grasp_discrimination_margin_m`` — the FINITE-DIFFERENCE derivation.

    An exact difference over ``2 * goal_tolerance`` of drive travel towards closed, and it
    evaluates at the position that was COMMANDED. Two differences from the above, not one.
    """
    q = position_for(width_m)
    towards_closed = 1.0 if CLOSED_POSITION_RAD >= OPEN_POSITION_RAD else -1.0
    biased = q + towards_closed * 2.0 * GOAL_TOLERANCE_RAD
    return abs(opening_m(q) - opening_m(biased))


def is_holding(commanded_m: float, reached_q: float, stalled: bool, reached_goal: bool) -> bool:
    """``gripper_is_holding``, transcribed. Never used for a reported figure."""
    if not stalled or reached_goal:
        return False
    return (opening_m(reached_q) - commanded_m) > 2.0 * tolerance_m(reached_q)


def band_edge_m(commanded_m: float) -> float:
    """The reached width above which ``is_holding`` becomes true, by bisection.

    The band is ``(commanded, band_edge)`` and the predicate is false throughout it.
    """
    lo, hi = commanded_m, 0.0889
    for _ in range(200):
        mid = (lo + hi) / 2.0
        q = position_for(mid)
        if opening_m(q) - commanded_m - 2.0 * tolerance_m(q) < 0.0:
            lo = mid
        else:
            hi = mid
    return lo


def main() -> None:
    mm = 1000.0
    q_cmd = position_for(DEFAULT_GRASP_WIDTH_M)
    q_466 = position_for(0.0466)

    print("linkage")
    print(f"  pivot  = {PIVOT_M:.9f} m")
    print(f"  crank  = {CRANK_M:.7f} m")
    print(f"  phase  = {PHASE_RAD:.6f} rad")
    print(f"  opening(open_position)   = {opening_m(OPEN_POSITION_RAD)*mm:.4f} mm")
    print(f"  opening(closed_position) = {opening_m(CLOSED_POSITION_RAD)*mm:.4f} mm")
    print()
    print("criteria.md section 2 cross-check against ADR-0052")
    print(f"  q at a 45.0 mm command                 = {q_cmd:.6f} rad   (ADR: 0.452793)")
    print(f"  2*tolerance at a 46.6 mm stall         = {2*tolerance_m(q_466)*mm:.4f} mm  (ADR: 2.1244)")
    print(f"  margin at that stall                   = {(0.0466-0.045)*mm:.4f} mm  (ADR: 1.6000)")
    edge = band_edge_m(DEFAULT_GRASP_WIDTH_M)
    print(f"  band edge against a 45.0 mm command    = {edge*mm:.4f} mm  (ADR: 47.1215)")
    print(f"  band width                             = {(edge-DEFAULT_GRASP_WIDTH_M)*mm:.4f} mm  (ADR: 2.1215)")
    one_tol = opening_m(q_cmd - GOAL_TOLERANCE_RAD) - opening_m(q_cmd)
    print(f"  one goal_tolerance of width at command = {one_tol*mm:.4f} mm  (ADR: 1.0650)")
    print(f"  C++ (linearised, at command)           = {2*tolerance_m(q_cmd)*mm:.4f} mm  (ADR: 2.1327)")
    print(f"  validator (finite diff, at command)    = {validator_margin_m(DEFAULT_GRASP_WIDTH_M)*mm:.4f} mm  (ADR: 2.1380)")
    print()
    print("criteria.md section 5.1 -- the four FN commands, against a 49.692 mm stall")
    print("  (49.692 mm is the hull-grasp campaign's hull median, cited not copied into a verdict)")
    q_stall = position_for(0.049692)
    thr = 2.0 * tolerance_m(q_stall)
    print(f"  threshold at that stall                = {thr*mm:.4f} mm")
    print(f"  band edge in COMMANDED terms           = {(0.049692-thr)*mm:.4f} mm")
    print("  w_cmd     margin_mm   ratio")
    for w in (0.042, 0.045, 0.047, 0.048):
        margin = 0.049692 - w
        print(f"  {w*mm:5.1f}     {margin*mm:8.4f}   {margin/thr:6.3f}")
    print()
    print("criteria.md section 5.2 -- the twelve FP stop widths and their drive positions")
    for w_mm in (45.5, 46.0, 46.5, 47.0, 47.05, 47.10, 47.15, 47.20, 47.5, 48.0, 49.0, 50.0):
        w = w_mm / mm
        q = position_for(w)
        margin = w - DEFAULT_GRASP_WIDTH_M
        thr = 2.0 * tolerance_m(q)
        print(
            f"  stop {w_mm:6.2f} mm -> q = {q:.6f} rad   margin {margin*mm:6.4f} mm"
            f"   threshold {thr*mm:6.4f} mm   predicate {is_holding(DEFAULT_GRASP_WIDTH_M, q, True, False)}"
        )
    print()
    print("criteria.md section 5.3 -- the two derivations across the sweep (reference only)")
    print("  w_cmd_mm   cpp_at_cmd_mm   validator_mm   diff_mm")
    for w_mm in (20.0, 30.0, 40.0, 45.0, 47.86, 50.0, 60.0, 70.0, 85.0):
        w = w_mm / mm
        q = position_for(w)
        c = 2.0 * tolerance_m(q) * mm
        v = validator_margin_m(w) * mm
        print(f"  {w_mm:8.2f}   {c:13.4f}   {v:12.4f}   {v-c:+7.4f}")


if __name__ == "__main__":
    main()
