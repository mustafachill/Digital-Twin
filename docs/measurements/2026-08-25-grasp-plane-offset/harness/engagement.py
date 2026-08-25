#!/usr/bin/env python3
"""Measure — not assume — where the pad face sat relative to the work-piece.

The commanded grasp height is the knob. This is the quantity the knob is
supposed to move, read back out of the simulator's own pose feed at the instant
the grasp was established, so that a block which failed to move it is visible as
such rather than being reported as a null result.

For each trial:
  * compose the left pad's link pose (published in the arm model's frame)
    through the arm's constant world pose, exactly as the published campaign's
    harness does;
  * carry the pad-face centre, a fixed point in the left_finger link frame, into
    the world;
  * subtract the work-piece's centre of mass, at the same instant.

Run from the campaign directory. Imports the published campaign's harness so
that the frame composition is the same code, not a re-implementation of it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE.parent.parent / "2026-08-25-friction-grasp" / "harness"
sys.path.insert(0, str(PUBLISHED))
sys.path.insert(0, str(HERE))

from measure_grasp import PAD_LINK, compose, interpolate, quat_rotate  # noqa: E402
from recompute import ARM, load  # noqa: E402
import geometry as g  # noqa: E402

#: The centre of the pad face, in the left_finger link frame. See geometry.py.
PAD_FACE_CENTRE_IN_LINK = (0.0, -g.PAD_INSET_M, g.PAD_FACE_CENTRE_Z_M)

#: World z of the pick station's surface — cell_a__table_pick__surface, from the
#: generated static-frame table. The work-piece rests on it.
PICK_SURFACE_Z = 0.6


def pad_face_centre_world(pad_sample, arm=ARM):
    pad_w = compose(arm, pad_sample)
    d = quat_rotate(pad_w.q, PAD_FACE_CENTRE_IN_LINK)
    return (pad_w.p[0] + d[0], pad_w.p[1] + d[1], pad_w.p[2] + d[2])


def trial_engagement(tracks: dict, row: dict) -> dict:
    """Pad-face geometry at the grasp instant, in millimetres above the surface."""
    wp = tracks.get(row["model"], [])
    pad = tracks.get(PAD_LINK, [])
    t_grasp = row.get("t_grasp_sim")
    out = {"trial": row["trial"], "label": row["label"]}
    if not wp or not pad or t_grasp is None:
        out["measured"] = False
        return out
    wp_s = interpolate(wp, t_grasp)
    pad_s = interpolate(pad, t_grasp)
    if wp_s is None or pad_s is None:
        out["measured"] = False
        return out
    pad_c = pad_face_centre_world(pad_s)
    out["measured"] = True
    out["pad_centre_above_surface_mm"] = (pad_c[2] - PICK_SURFACE_Z) * 1000.0
    out["part_com_above_surface_mm"] = (wp_s.p[2] - PICK_SURFACE_Z) * 1000.0
    out["pad_offset_vs_com_mm"] = (pad_c[2] - wp_s.p[2]) * 1000.0
    # Lateral placement of the pad face on the part, for completeness: a pad that
    # is off-centre along the part's other two axes would be a second couple.
    out["pad_lateral_x_mm"] = (pad_c[0] - wp_s.p[0]) * 1000.0
    # Table clearance. The corrected grasp puts the fingertips a few millimetres
    # above the pick surface; a tip that reaches it adds a contact the block did
    # not intend and would explain a quiet grasp for a reason unrelated to where
    # the pads sit. Measured, so that it cannot be assumed away.
    pad_w = compose(ARM, pad_s)
    tip = quat_rotate(pad_w.q, (0.0, 0.0, g.FINGER_TIP_Z_M))
    out["finger_tip_above_surface_mm"] = (pad_w.p[2] + tip[2] - PICK_SURFACE_Z) * 1000.0
    eng, cen = g.engagement_mm(out["pad_centre_above_surface_mm"] / 1000.0)
    out["pad_face_engaged_mm"] = eng
    out["engaged_centroid_vs_com_mm"] = cen
    q = row.get("q_at_stall_rad")
    if q is not None:
        out["predicted_offset_vs_com_mm"] = (
            row.get("commanded_grasp_height_m", 0.03) + g.pad_centre_offset_m(q)
            - g.WORKPIECE_CENTRE_ABOVE_SURFACE_M) * 1000.0
    return out


def main(raw_dir: str = "raw") -> int:
    raw = Path(raw_dir)
    rows = []
    for meta in sorted(raw.glob("*_trials.json")):
        for row in json.loads(meta.read_text()):
            if "trial" not in row:
                continue
            samples = raw / f"{row['label']}_trial{row['trial']:03d}_samples.csv"
            if not samples.exists():
                continue
            rows.append(trial_engagement(load(samples), row))
    for r in rows:
        print(json.dumps(r, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
