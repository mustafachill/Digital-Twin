#!/usr/bin/env python3
"""Where the pad face sits relative to the work-piece — the independent variable.

Every constant below is a fact in a file that can be re-checked rather than
believed, and each is named with its source. Nothing here is a fitted number.

  link_tcp                z = 0.172 m from xarm_gripper_base_link
                          xarm_gripper.urdf.xacro, joint_tcp <origin>
  drive pivot             (0, 0.035, 0.059098) from xarm_gripper_base_link
                          xarm_gripper.urdf.xacro, drive_joint <origin>, axis +x
  left_finger_joint       (0, 0.035465, 0.042039) from left_outer_knuckle
                          xarm_gripper.urdf.xacro, axis -x, mimic multiplier 1
  pad face                the y = -0.026003 plane of left_finger.stl, spanning
                          z 0.022253 .. 0.059753 in the left_finger frame:
                          37.500 mm tall, centred at z = 0.041003

The two mimic rotations cancel, so the pad face stays parallel to the tool axis
and only its origin translates. The drive rotation about +x carries the
left_finger origin to

    y(q) = 0.035    + 0.035465*cos(q) - 0.042039*sin(q)
    z(q) = 0.059098 + 0.035465*sin(q) + 0.042039*cos(q)

from which the L0 model's opening(q) = 2*(y(q) - pad_inset) follows unchanged,
and the axial offset this campaign is about follows as

    offset(q) = 0.172 - z(q) - 0.041003
              = 0.0718988 - (0.035465*sin(q) + 0.042039*cos(q))

i.e. how far PROXIMAL of link_tcp the centre of the pad face sits. 29.86 mm
fully open, 19.23 mm at the drive angle a 50 mm part stops the jaws at.
"""

from __future__ import annotations

import math

TCP_Z_M = 0.172
DRIVE_PIVOT_Z_M = 0.059098
FINGER_OFFSET_Y_M = 0.035465
FINGER_OFFSET_Z_M = 0.042039
PAD_INSET_M = 0.026003
PAD_FACE_HEIGHT_M = 0.037500
PAD_FACE_CENTRE_Z_M = 0.041003

#: Median drive angle at which the gripper stalls on the cell's 50 mm reference
#: work-piece, over the 32 published friction trials at max_step_size 0.001 and
#: 0.0005 (`q_at_stall_rad`, 0.4061 .. 0.4176). Used only to choose ONE commanded
#: height before any trial runs; every number reported afterwards is measured
#: from the simulator's own pose feed at the grasp instant, not from this.
Q_STALL_RAD = 0.4085

WORKPIECE_SIZE_M = 0.05
WORKPIECE_CENTRE_ABOVE_SURFACE_M = 0.025


def pad_centre_offset_m(q: float) -> float:
    """How far proximal of `link_tcp` the pad face centre sits, at drive angle q."""
    return TCP_Z_M - (
        DRIVE_PIVOT_Z_M
        + FINGER_OFFSET_Y_M * math.sin(q)
        + FINGER_OFFSET_Z_M * math.cos(q)
    ) - PAD_FACE_CENTRE_Z_M


def opening_m(q: float) -> float:
    """Jaw opening at drive angle q — the L0 model's own map, restated for checks."""
    return 2.0 * (
        0.035
        + FINGER_OFFSET_Y_M * math.cos(q)
        - FINGER_OFFSET_Z_M * math.sin(q)
        - 0.026
    )


def corrected_grasp_height_m(q: float = Q_STALL_RAD) -> float:
    """Commanded `object_pose.position.z` that puts the pad face centre on the
    work-piece's centre of mass at the stall configuration."""
    return WORKPIECE_CENTRE_ABOVE_SURFACE_M - pad_centre_offset_m(q)


def engagement_mm(pad_centre_above_surface_m: float) -> tuple[float, float]:
    """(engaged pad height, centroid of the engaged strip above the part's COM),
    both in mm, for a pad face straddling a work-piece resting on the surface."""
    lo = pad_centre_above_surface_m - PAD_FACE_HEIGHT_M / 2.0
    hi = pad_centre_above_surface_m + PAD_FACE_HEIGHT_M / 2.0
    lo_e, hi_e = max(lo, 0.0), min(hi, WORKPIECE_SIZE_M)
    if hi_e <= lo_e:
        return 0.0, float("nan")
    centroid = (lo_e + hi_e) / 2.0
    return (hi_e - lo_e) * 1000.0, (centroid - WORKPIECE_CENTRE_ABOVE_SURFACE_M) * 1000.0


if __name__ == "__main__":
    for q in (0.0, 0.4056, Q_STALL_RAD, 0.4528, 0.85):
        print(f"q={q:.4f}  opening={opening_m(q)*1000:7.2f} mm  "
              f"pad-centre offset={pad_centre_offset_m(q)*1000:6.2f} mm")
    h = corrected_grasp_height_m()
    print(f"\ncorrected commanded grasp height = {h*1000:.2f} mm")
    for label, height in (("uncorrected (shipped)", 0.030), ("corrected", round(h, 4))):
        pc = height + pad_centre_offset_m(Q_STALL_RAD)
        eng, cen = engagement_mm(pc)
        print(f"  {label:22s} commanded {height*1000:5.1f} mm -> pad centre "
              f"{pc*1000:6.2f} mm above surface, {pc*1000 - 25:+6.2f} mm vs COM, "
              f"{eng:5.2f} mm of {PAD_FACE_HEIGHT_M*1000:.1f} mm engaged, "
              f"engaged centroid {cen:+.2f} mm vs COM")

#: Distal-most point of left_finger.stl in the link frame — the fingertip plane.
#: Used only to measure table clearance; see engagement.py.
FINGER_TIP_Z_M = 0.061003
