#!/usr/bin/env python3
"""Reference implementation of the gripper linkage arithmetic, and the section 2 cross-check.

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/arithmetic.py`,
copied at commit `eeaf903`. That directory is FROZEN
(`docs/measurements/README.md`) and nothing in it is edited from here.

WHAT CHANGED FROM THE SOURCE FILE, and why each change exists:

  * `is_holding` is option F's form -- a window around the interval of declared
    work-piece widths -- and no longer reads the commanded width. The source file's
    command-referenced form is kept beside it as `is_holding_superseded`, because
    `criteria.md` section 2.1 defines `holding_S` and this is where the sweep points that
    bracket the two are chosen.
  * `band_edge_m` is gone. F's window has two DECLARED edges, so there is nothing left to
    bisect for; `WINDOW_LOW_M` and `WINDOW_HIGH_M` state them.
  * `main` reproduces `criteria.md` section 2's table and section 2.2's two predictions
    rather than the 2026-09-01 campaign's.

WHAT THIS IS FOR, AND WHAT IT IS NOT FOR. Unchanged from the source file, and
`criteria.md` section 3 states it again: it is a *reference* implementation, used for
exactly two things --

  1. reproducing `criteria.md` section 2's arithmetic independently;
  2. choosing the sweep points in section 5 before any trial ran.

**No reported campaign figure comes from here.** Every reported figure comes from the
shipped implementation, reached through `predicate_eval` or read off a running node,
because a campaign about a predicate cannot answer itself with a second copy of it.

Run it from anywhere; it needs nothing but the standard library.

    python3 arithmetic.py
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# The L0 declaration, transcribed once.
# model/assets/types/end_effectors/xarm_parallel_gripper.yaml, and the facility
# block of workspace/src/cite_generated/bringup/cell_a_plan.yaml.
# ---------------------------------------------------------------------------
DRIVE_PIVOT_Y_M = 0.035  # linkage.drive_pivot_y_m
DRIVE_PIVOT_Z_M = 0.059098  # linkage.drive_pivot_z_m
FINGER_OFFSET_Y_M = 0.035465  # linkage.finger_offset_y_m
FINGER_OFFSET_Z_M = 0.042039  # linkage.finger_offset_z_m
PAD_INSET_M = 0.026  # linkage.pad_inset_m
TIP_LINK_Z_M = 0.172  # linkage.tip_link_z_m
PAD_FACE_CENTRE_Z_M = 0.041003  # linkage.pad_face_centre_z_m
GOAL_TOLERANCE_RAD = 0.01  # controllers[].parameters.goal_tolerance
DEFAULT_GRASP_WIDTH_M = 0.045  # grasp.default_grasp_width_m
OPEN_POSITION_RAD = 0.0  # grasp.open_position
CLOSED_POSITION_RAD = 0.85  # grasp.closed_position

#: ADR-0052 option F's two declared edges, in the end-effector type.
STALL_BAND_NARROW_M = 0.002385  # grasp.stall_band_narrow_m
STALL_BAND_WIDE_M = 0.002385  # grasp.stall_band_wide_m

#: The facility's declared part interval. Degenerate on this model, and that is
#: today's facility rather than a special case (criteria.md section 8).
NARROWEST_M = 0.050  # plan.workpieces.narrowest_width_m
WIDEST_M = 0.050  # plan.workpieces.widest_width_m

WINDOW_LOW_M = NARROWEST_M - STALL_BAND_NARROW_M
WINDOW_HIGH_M = WIDEST_M + STALL_BAND_WIDE_M

PIVOT_M = DRIVE_PIVOT_Y_M - PAD_INSET_M
CRANK_M = math.hypot(FINGER_OFFSET_Y_M, FINGER_OFFSET_Z_M)
PHASE_RAD = math.atan2(FINGER_OFFSET_Z_M, FINGER_OFFSET_Y_M)

#: criteria.md section 2.2. The MEASURED shortfall of the free-air settle behind the
#: command, and one full `goal_tolerance` as the worst case. Both are drive-joint
#: angles, and both are stated in the criteria before any trial of this campaign ran.
SETTLE_SHORTFALL_MEASURED_RAD = 0.008
SETTLE_SHORTFALL_WORST_RAD = 0.010


def opening_m(q: float) -> float:
    """``gripper_width_for`` -- the jaw opening at drive position ``q``."""
    return 2.0 * (PIVOT_M + CRANK_M * math.cos(q + PHASE_RAD))


def position_for(width_m: float) -> float:
    """``gripper_position_for`` -- the drive position that commands ``width_m``."""
    cosine = min(1.0, max(-1.0, (width_m / 2.0 - PIVOT_M) / CRANK_M))
    position = math.acos(cosine) - PHASE_RAD
    return min(max(position, OPEN_POSITION_RAD), CLOSED_POSITION_RAD)


def pad_plane_offset_m(q: float) -> float:
    """``gripper_pad_plane_offset_m`` -- how far proximal of the tip the pad face sits."""
    axial_reach_m = TIP_LINK_Z_M - DRIVE_PIVOT_Z_M - PAD_FACE_CENTRE_Z_M
    return axial_reach_m - CRANK_M * math.sin(q + PHASE_RAD)


def tolerance_m(q: float) -> float:
    """``gripper_width_tolerance_m`` -- the LINEARISED derivation, at ``q``."""
    return abs(2.0 * CRANK_M * math.sin(q + PHASE_RAD) * GOAL_TOLERANCE_RAD)


def discrimination_margin_m(width_m: float) -> float:
    """``gripper_discrimination_margin_m`` -- the FINITE-DIFFERENCE derivation.

    An exact difference over ``2 * goal_tolerance`` of drive travel towards closed,
    evaluated at the position that was COMMANDED. This is the bound
    ``resolve_grasp_width`` applies to a caller's width, and the identical bound
    ``cite_tools.validate.physical`` applies to the declared default.
    """
    q = position_for(width_m)
    towards_closed = 1.0 if CLOSED_POSITION_RAD >= OPEN_POSITION_RAD else -1.0
    biased = q + towards_closed * 2.0 * GOAL_TOLERANCE_RAD
    return abs(opening_m(q) - opening_m(biased))


def resolve_permits(width_m: float) -> bool:
    """``resolve_grasp_width``'s own condition, for choosing sweep points only.

    `criteria.md` I6 requires the campaign to read this from the SHIPPED function,
    through `predicate_eval`. This transcription exists so section 5.1's grid could be
    chosen before the harness was built, and for no other purpose.
    """
    return NARROWEST_M - width_m >= discrimination_margin_m(width_m)


def largest_permitted_width_m() -> float:
    """The widest width ``resolve_grasp_width`` permits, by bisection on its condition."""
    low, high = 0.0, NARROWEST_M
    for _ in range(200):
        mid = (low + high) / 2.0
        if resolve_permits(mid):
            low = mid
        else:
            high = mid
    return low


def is_holding(reached_q: float, stalled: bool, reached_goal: bool) -> bool:
    """``gripper_is_holding`` at `d3eeac4`, transcribed. Never used for a reported figure."""
    if not stalled or reached_goal:
        return False
    reached = opening_m(reached_q)
    return WINDOW_LOW_M < reached < WINDOW_HIGH_M


def is_holding_superseded(commanded_m: float, reached_q: float, stalled: bool,
                          reached_goal: bool) -> bool:
    """``gripper_is_holding`` at `4ef2d7c`, transcribed.

    The command-referenced form option F replaced. `holding_S` in `ANALYSIS.md` comes
    from a BUILD of that commit and never from here (`criteria.md` V10); this exists so
    that section 5.2's jam positions could be chosen knowing which of them the superseded
    predicate would have admitted.
    """
    if not stalled or reached_goal:
        return False
    return (opening_m(reached_q) - commanded_m) > 2.0 * tolerance_m(reached_q)


def presented_width_m(side_m: float, yaw_deg: float) -> float:
    """How wide a square of side ``side_m`` presents across the pads at ``yaw_deg``.

    `criteria.md` section 2.2. A yaw about the world vertical, and nothing else -- an
    angle without an axis is not a measurement of anything
    (`docs/measurements/README.md`).
    """
    yaw = math.radians(yaw_deg)
    return side_m * (math.cos(yaw) + math.sin(yaw))


def _crossing_yaw_deg(side_m: float, target_m: float) -> float:
    low, high = 0.0, 45.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if presented_width_m(side_m, mid) < target_m:
            low = mid
        else:
            high = mid
    return low


def main() -> None:
    mm = 1000.0

    print("linkage")
    print(f"  pivot  = {PIVOT_M:.9f} m")
    print(f"  crank  = {CRANK_M:.7f} m")
    print(f"  phase  = {PHASE_RAD:.6f} rad")
    print(f"  opening(open_position)   = {opening_m(OPEN_POSITION_RAD) * mm:.3f} mm")
    print(f"  opening(closed_position) = {opening_m(CLOSED_POSITION_RAD) * mm:.3f} mm")
    print()

    print("criteria.md section 2 -- the table, reproduced")
    print(f"  declared part interval                 = {NARROWEST_M * mm:.3f} / {WIDEST_M * mm:.3f} mm")
    print(f"  declared band                          = {STALL_BAND_NARROW_M * mm:.3f} / "
          f"{STALL_BAND_WIDE_M * mm:.3f} mm")
    print(f"  F's window                             = [{WINDOW_LOW_M * mm:.3f}, "
          f"{WINDOW_HIGH_M * mm:.3f}] mm")
    print(f"  window edges as drive positions        = {position_for(WINDOW_LOW_M):.6f} / "
          f"{position_for(WINDOW_HIGH_M):.6f} rad")
    print(f"  discrimination margin at 45.0 mm       = {discrimination_margin_m(0.045) * mm:.5f} mm")
    print(f"  validator ceiling, 50.0 - that margin  = "
          f"{(NARROWEST_M - discrimination_margin_m(0.045)) * mm:.3f} mm")
    print(f"  largest width resolve_grasp_width permits = {largest_permitted_width_m() * mm:.4f} mm")
    settle = position_for(DEFAULT_GRASP_WIDTH_M) - SETTLE_SHORTFALL_MEASURED_RAD
    print(f"  free-air settle at 45.0 mm             = {opening_m(settle) * mm:.3f} mm "
          f"(from q = {settle:.6f} rad)")
    print()

    print("criteria.md section 2.2 -- the free-air prediction across the commanded grid")
    print("  w_cmd_mm   settle@0.008_mm   settle@0.010_mm   inside_window   I6_permits")
    for w_mm in (45.00, 45.25, 45.50, 45.75, 46.00, 46.25, 46.50, 46.75,
                 47.00, 47.25, 47.50, 47.75, 47.85):
        w = w_mm / mm
        q = position_for(w)
        a = opening_m(q - SETTLE_SHORTFALL_MEASURED_RAD)
        b = opening_m(q - SETTLE_SHORTFALL_WORST_RAD)
        inside = (WINDOW_LOW_M < a < WINDOW_HIGH_M, WINDOW_LOW_M < b < WINDOW_HIGH_M)
        print(f"  {w_mm:8.2f}   {a * mm:14.3f}   {b * mm:15.3f}   {str(inside):15s} "
              f"{resolve_permits(w)}")
    print()

    print("criteria.md section 5.2 -- the five jam positions of Arm B")
    for w_mm in (46.0, 48.0, 50.0, 52.0, 54.0):
        w = w_mm / mm
        q = position_for(w)
        print(f"  jam {w_mm:6.2f} mm -> q = {q:.6f} rad   holding_F="
              f"{is_holding(q, True, False)}   holding_S="
              f"{is_holding_superseded(0.056, q, True, False)}")
    print(f"  commanded 56.000 mm -> q = {position_for(0.056):.6f} rad")
    print()

    print("criteria.md section 5.3 -- the presented width of a yawed 50 mm square")
    print(f"  crosses the wide edge at yaw > {_crossing_yaw_deg(0.050, WINDOW_HIGH_M):.3f} deg")
    for yaw in (0.0, 1.5, 2.0, 3.0, 4.5, 5.0, 6.0, 8.0, 10.0, 12.0):
        print(f"  yaw {yaw:5.1f} deg -> presents {presented_width_m(0.050, yaw) * mm:.3f} mm")
    print()

    print("criteria.md section 5.4 -- the pad-plane offset at the two Arm D commands")
    for w_mm in (45.0, 48.0):
        q = position_for(w_mm / mm)
        print(f"  {w_mm:5.1f} mm -> q = {q:.6f} rad, pad plane offset "
              f"{pad_plane_offset_m(q) * mm:.3f} mm")


if __name__ == "__main__":
    main()
