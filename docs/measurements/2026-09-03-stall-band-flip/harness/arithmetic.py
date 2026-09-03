#!/usr/bin/env python3
"""Reference implementation of the gripper linkage, and `criteria.md` section 2's cross-check.

DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/arithmetic.py`, copied
at commit `3235cbc`. That directory is FROZEN (`docs/measurements/README.md`) and nothing
in it is edited from here.

WHAT CHANGED FROM THE SOURCE FILE, and why each change exists:

  * `main` reproduces THIS campaign's section 2 table and section 2.2's four numbers --
    the two window edges, the closed-form floor, the distance between them, and the
    goal-tolerance boundary section 5.1 registers as a fact about arm LO's lowest coarse
    stop. The source file reproduced its own campaign's table, which is a different one.
  * `flip_superseded_m` is new: the closed-form solve of the superseded condition
    `w_reached - w_cmd > 2 * tolerance(q_reached)` at a stated command. Section 2.2 states
    the floor as a computed quantity, and a campaign that took it from a record it cites
    would be differencing another campaign's measurement (rule H).
  * The sweep-point and settle constants the source file carried for its own arms are
    gone. Nothing here needs them.

WHAT THIS IS FOR, AND WHAT IT IS NOT FOR. `criteria.md` section 3 states it: the reference
implementation is used for the section 2 cross-check and for choosing the stop grid before
any trial, and **the value the rig actually declares comes from the shipped
`gripper_position_for` through the compiled front end**, never from here.

**No reported campaign figure comes from this file.** `measure.py` does not import it and
`analyse.py` does not import it. It is checked against the compiled front end by
`measure.py`'s own header cross-check, which asks the shipped program the same questions
and records both answers -- so a disagreement between the reference and the shipped code is
a datum on the record rather than a silence.

Run it from anywhere; it needs nothing but the standard library.

    python3 arithmetic.py
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# The L0 declaration, transcribed once.
# model/assets/types/end_effectors/xarm_parallel_gripper.yaml, and the facility
# block of workspace/src/cite_generated/bringup/cell_a_plan.yaml.
#
# TRANSCRIBED, WHICH IS THE POINT AND ALSO THE LIMIT. A reference implementation whose
# inputs came from the plan would agree with the shipped code for a reason that says
# nothing: both would be reading one file. These are typed in from L0, so the cross-check
# in `measure.py` compares two independent readings of the same declaration.
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

#: The facility's declared part interval. Degenerate on this model, and that is today's
#: facility rather than a special case (`criteria.md` section 8).
NARROWEST_M = 0.050  # plan.workpieces.narrowest_width_m
WIDEST_M = 0.050  # plan.workpieces.widest_width_m

#: The gripper controller's own two settings, from the generated controller configuration.
#: Only P6 needs them, and it needs them to compute a rest position rather than to predict
#: a duration.
STALL_TIMEOUT_S = 0.3  # controllers[].parameters.stall_timeout
MAX_DRIVE_RATE_RAD_S = 1.0  # grasp.max_drive_rate_rad_s

WINDOW_LOW_M = NARROWEST_M - STALL_BAND_NARROW_M
WINDOW_HIGH_M = WIDEST_M + STALL_BAND_WIDE_M

PIVOT_M = DRIVE_PIVOT_Y_M - PAD_INSET_M
CRANK_M = math.hypot(FINGER_OFFSET_Y_M, FINGER_OFFSET_Z_M)
PHASE_RAD = math.atan2(FINGER_OFFSET_Z_M, FINGER_OFFSET_Y_M)


def opening_m(q: float) -> float:
    """`cite_skills::gripper_width_for`, as one cosine."""
    return 2.0 * (PIVOT_M + CRANK_M * math.cos(q + PHASE_RAD))


def position_for(width_m: float) -> float:
    """`cite_skills::gripper_position_for`, clamped exactly as the shipped code clamps."""
    cosine = max(-1.0, min(1.0, (width_m / 2.0 - PIVOT_M) / CRANK_M))
    position = math.acos(cosine) - PHASE_RAD
    lower = min(OPEN_POSITION_RAD, CLOSED_POSITION_RAD)
    upper = max(OPEN_POSITION_RAD, CLOSED_POSITION_RAD)
    return max(lower, min(upper, position))


def width_tolerance_m(q: float) -> float:
    """`cite_skills::gripper_width_tolerance_m` -- |d(opening)/dq| times `goal_tolerance`."""
    return abs(2.0 * CRANK_M * math.sin(q + PHASE_RAD) * GOAL_TOLERANCE_RAD)


def discrimination_margin_m(width_m: float) -> float:
    """`cite_skills::gripper_discrimination_margin_m` -- the biased form, not a slope."""
    towards_closed = 1.0 if CLOSED_POSITION_RAD >= OPEN_POSITION_RAD else -1.0
    position = position_for(width_m)
    biased = position + towards_closed * 2.0 * GOAL_TOLERANCE_RAD
    return abs(opening_m(position) - opening_m(biased))


def is_holding(reached_q: float, stalled: bool, reached_goal: bool) -> bool:
    """Option F, as shipped: a window around the declared interval. The command is not read."""
    if not stalled or reached_goal:
        return False
    if NARROWEST_M <= 0.0 or WIDEST_M <= 0.0:
        return False
    reached = opening_m(reached_q)
    return WINDOW_LOW_M < reached < WINDOW_HIGH_M


def is_holding_superseded(commanded_m: float, reached_q: float, stalled: bool,
                          reached_goal: bool) -> bool:
    """The predicate at `4ef2d7c`: a half-line referenced to the command, with no upper edge."""
    if not stalled or reached_goal:
        return False
    return opening_m(reached_q) - commanded_m > 2.0 * width_tolerance_m(reached_q)


def flip_superseded_m(commanded_m: float = DEFAULT_GRASP_WIDTH_M) -> float:
    """Where the superseded predicate's verdict flips, in closed form, at one command.

    `criteria.md` section 2.2's floor. Solved by bisection on the shipped condition rather
    than by rearranging it: the condition is monotone in the stop width over the interval
    bisected, and a rearrangement would be a third statement of the same inequality.

    THE BRACKET IS THE LINKAGE'S, not a guess. The lower bound is the command itself, where
    the margin is zero and the condition is certainly false; the upper is 60 mm, inside the
    linkage's reach and above every stop in either arm.
    """
    low, high = commanded_m, 0.060

    def satisfied(width_m: float) -> bool:
        q = position_for(width_m)
        return width_m - commanded_m > 2.0 * width_tolerance_m(q)

    assert not satisfied(low) and satisfied(high), (
        "the superseded condition does not change sign over the bracket, so there is "
        "nothing here to solve"
    )
    for _ in range(200):
        middle = (low + high) / 2.0
        if satisfied(middle):
            high = middle
        else:
            low = middle
    return (low + high) / 2.0


def goal_tolerance_boundary_m(commanded_m: float = DEFAULT_GRASP_WIDTH_M) -> float:
    """The widest stop at which the controller still terminates on its goal-tolerance branch.

    `criteria.md` section 5.1 registers arm LO's lowest coarse stop as landing inside this,
    before any trial. A stop whose drive position is within `goal_tolerance` of the
    commanded one is reached, so the controller reports `reached_goal` and never stalls.
    """
    return opening_m(position_for(commanded_m) - GOAL_TOLERANCE_RAD)


def main() -> int:
    """Reproduce `criteria.md` section 2's table and section 2.2's four numbers."""
    floor = flip_superseded_m()
    rows = [
        ("pivot / crank / phase",
         f"{PIVOT_M:.9f} m, {CRANK_M:.9f} m, {PHASE_RAD:.9f} rad"),
        ("opening(0.00) / opening(0.85)",
         f"{opening_m(0.0) * 1000.0:.3f} mm / {opening_m(0.85) * 1000.0:.3f} mm"),
        ("declared part interval",
         f"{NARROWEST_M * 1000.0:.3f} / {WIDEST_M * 1000.0:.3f} mm"),
        ("declared band",
         f"{STALL_BAND_NARROW_M * 1000.0:.3f} / {STALL_BAND_WIDE_M * 1000.0:.3f} mm"),
        ("edge_lo",
         f"{WINDOW_LOW_M * 1000.0:.4f} mm, drive position {position_for(WINDOW_LOW_M):.6f} rad"),
        ("edge_hi",
         f"{WINDOW_HIGH_M * 1000.0:.4f} mm, drive position "
         f"{position_for(WINDOW_HIGH_M):.6f} rad"),
        ("gripper_discrimination_margin_m(45.0 mm)",
         f"{discrimination_margin_m(0.045) * 1000.0:.6f} mm"),
        ("validator ceiling, 50.0 - that margin",
         f"{(NARROWEST_M - discrimination_margin_m(0.045)) * 1000.0:.3f} mm"),
    ]
    print("criteria.md section 2 -- the table, recomputed from the L0 declaration")
    for name, value in rows:
        print(f"  {name:<42} {value}")

    print("\ncriteria.md section 2.2 -- the four numbers computed before any trial")
    print(f"  edge_lo                                    {WINDOW_LOW_M * 1000.0:.4f} mm")
    print(f"  edge_hi                                    {WINDOW_HIGH_M * 1000.0:.4f} mm")
    print(f"  superseded flip at 45.000 mm (the floor)   {floor * 1000.0:.6f} mm")
    print(f"  edge_lo - floor                            "
          f"{(WINDOW_LOW_M - floor) * 1000.0:.4f} mm")

    print("\ncriteria.md section 5.1 -- arm LO's lowest coarse stop")
    boundary = goal_tolerance_boundary_m()
    print(f"  goal-tolerance boundary                    {boundary * 1000.0:.6f} mm")
    for stop_mm in (46.00, 46.25):
        delta = abs(position_for(stop_mm / 1000.0) - position_for(DEFAULT_GRASP_WIDTH_M))
        inside = "inside" if stop_mm / 1000.0 < boundary else "outside"
        print(f"  stop {stop_mm:.2f} mm is {delta:.6f} rad from the command, {inside}")

    print("\ncriteria.md section 7.0 -- what the inherited 0.001 rad is worth in width")
    for name, edge in (("edge_lo", WINDOW_LOW_M), ("edge_hi", WINDOW_HIGH_M)):
        q = position_for(edge)
        per_rad = abs(2.0 * CRANK_M * math.sin(q + PHASE_RAD))
        print(f"  at {name}: 0.001 rad = {per_rad * 0.001 * 1000.0:.4f} mm; "
              f"0.005 mm = {0.000005 / per_rad:.6e} rad")

    print("\ncriteria.md section 7.5 P6 -- the CTL rest position, computed from L0")
    rest = STALL_TIMEOUT_S * MAX_DRIVE_RATE_RAD_S
    print(f"  {STALL_TIMEOUT_S} s x {MAX_DRIVE_RATE_RAD_S} rad/s = {rest:.3f} rad = "
          f"{opening_m(rest) * 1000.0:.3f} mm")
    print(f"  2 * gripper_width_tolerance_m there        "
          f"{2.0 * width_tolerance_m(rest) * 1000.0:.3f} mm")

    print("\nNo figure printed here is campaign data. criteria.md section 3: the reference "
          "implementation\nis for the section 2 cross-check and for choosing the grid. "
          "Every reported figure comes from\nthe shipped code, through predicate_eval or "
          "off a running node.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
