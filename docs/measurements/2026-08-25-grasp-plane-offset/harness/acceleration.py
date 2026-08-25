#!/usr/bin/env python3
"""H6 — does the carry's horizontal acceleration drive the twist?

Within one block the height, the lever arm and the contact area are all fixed;
the only thing that varies between trials is the trajectory the unseeded OMPL
returned. If the twist is driven by a torque `F·h` about the pad-to-pad axis,
with `h` the height of the engaged strip above the centre of mass, then within a
block the twist must track the horizontal acceleration of the carry. If it is
driven only by how much pad face is in contact, it must not.

Acceleration is taken from the work-piece's own pose trace, in the PAD frame, so
that "horizontal" means the direction whose torque is about the pad-to-pad axis
rather than a world direction the arm happens to move along. The trace is
differentiated twice over a fixed time window rather than sample to sample:
double-differencing at the publication rate is dominated by quantisation, and a
window wide enough to survive it is still far shorter than the carry.
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

from measure_grasp import PAD_LINK, compose, interpolate, quat_conj_rotate  # noqa: E402
from recompute import ARM, load  # noqa: E402

#: Half-width of the local quadratic fit, in seconds of simulation time.
#:
#: A three-point second difference on this feed is not usable. The pose feed
#: publishes every sixteenth physics step, so its interval is 9.5 ms at
#: max_step_size 0.0005, 18 ms at 0.001 and 32 ms at 0.002 -- and a second
#: difference amplifies that timing jitter by 1/dt^2, which would make an
#: "acceleration" that scales with the timestep rather than with the motion. A
#: quadratic fitted over a fixed WINDOW of TIME uses whatever samples fall in it,
#: so the estimate means the same thing at every timestep and simply gets
#: quieter where the feed is denser. 0.1 s is two to ten samples wide and is far
#: shorter than the ~1 s over which the planned trajectory's acceleration varies.
WINDOW_S = 0.1


def _fit_acceleration(ts: list[float], xs: list[float]) -> float:
    """Second derivative of the least-squares quadratic through (ts, xs)."""
    n = len(ts)
    t0 = sum(ts) / n
    u = [t - t0 for t in ts]
    s0, s1, s2 = float(n), sum(u), sum(v * v for v in u)
    s3, s4 = sum(v ** 3 for v in u), sum(v ** 4 for v in u)
    b0, b1, b2 = sum(xs), sum(x * v for x, v in zip(xs, u)), sum(x * v * v for x, v in zip(xs, u))
    # Normal equations for x = a0 + a1*u + a2*u^2; acceleration is 2*a2.
    m = [[s0, s1, s2], [s1, s2, s3], [s2, s3, s4]]
    rhs = [b0, b1, b2]
    for i in range(3):
        pivot = max(range(i, 3), key=lambda r: abs(m[r][i]))
        if abs(m[pivot][i]) < 1e-18:
            return float("nan")
        m[i], m[pivot] = m[pivot], m[i]
        rhs[i], rhs[pivot] = rhs[pivot], rhs[i]
        for r in range(i + 1, 3):
            f = m[r][i] / m[i][i]
            for c in range(i, 3):
                m[r][c] -= f * m[i][c]
            rhs[r] -= f * rhs[i]
    a2 = rhs[2] / m[2][2]
    return 2.0 * a2


def carry_acceleration(tracks: dict, row: dict) -> dict:
    """Peak, RMS and integrated horizontal acceleration of the work-piece over
    the carry, in the pad frame."""
    wp = tracks.get(row["model"], [])
    pad = tracks.get(PAD_LINK, [])
    tg, tr = row.get("t_grasp_sim"), row.get("t_release_sim")
    out = {"trial": row["trial"], "label": row["label"]}
    if not wp or not pad or tg is None or tr is None:
        out["measured"] = False
        return out

    # The part's world position, rotated into the pad's orientation at the same
    # instant, so that "x" is the direction whose torque acts about the
    # pad-to-pad axis rather than a world direction the arm happens to move in.
    pts = []
    for s in wp:
        if not (tg <= s.t <= tr):
            continue
        p = interpolate(pad, s.t)
        if p is None:
            continue
        pw = compose(ARM, p)
        pts.append((s.t, quat_conj_rotate(pw.q, s.p)))
    if len(pts) < 12:
        out["measured"] = False
        return out

    acc = []
    lo = 0
    for i, (t, _) in enumerate(pts):
        while pts[lo][0] < t - WINDOW_S:
            lo += 1
        hi = i
        while hi + 1 < len(pts) and pts[hi + 1][0] <= t + WINDOW_S:
            hi += 1
        if hi - lo < 3:
            continue
        ts = [pts[k][0] for k in range(lo, hi + 1)]
        ax = _fit_acceleration(ts, [pts[k][1][0] for k in range(lo, hi + 1)])
        if ax == ax:   # not NaN
            acc.append((t, ax))
    if len(acc) < 5:
        out["measured"] = False
        return out

    span = acc[-1][0] - acc[0][0]
    out["measured"] = True
    out["a_peak_mps2"] = max(abs(a) for _, a in acc)
    out["a_rms_mps2"] = math.sqrt(sum(a * a for _, a in acc) / len(acc))
    out["a_integral_mps"] = out["a_rms_mps2"] * span
    out["a_samples"] = len(acc)

    # THE SAME QUANTITY, TAKEN FROM THE PAD INSTEAD, AND WHY IT IS THE ONE TO USE.
    #
    # Everything above is differentiated from the WORK-PIECE's trace, and the
    # work-piece is the thing whose motion is in question: a part that twists and
    # slips between the jaws moves relative to the pad, and that relative motion
    # lands in its second derivative as "acceleration". Correlating twist against
    # it would then be partly correlating twist against itself, and would report
    # a mechanism where there is only an identity.
    #
    # The pad is driven by the arm through the trajectory the planner returned.
    # It is upstream of the grasp: the 0.2 kg part cannot meaningfully perturb a
    # six-axis arm's tracked trajectory, and the published campaign measured the
    # pads turning 0.14 deg while the part turned 30. So the pad's acceleration
    # is the DISTURBANCE the grasp is asked to withstand, uncontaminated by the
    # response. This is the predictor H6 is tested on; the work-piece figures
    # above are kept only so the difference between the two can be seen.
    pad_pts = []
    for s_ in pad:
        if not (tg <= s_.t <= tr):
            continue
        pw = compose(ARM, s_)
        pad_pts.append((s_.t, quat_conj_rotate(pw.q, pw.p)))
    if len(pad_pts) >= 12:
        pacc = []
        lo = 0
        for i, (t, _) in enumerate(pad_pts):
            while pad_pts[lo][0] < t - WINDOW_S:
                lo += 1
            hi = i
            while hi + 1 < len(pad_pts) and pad_pts[hi + 1][0] <= t + WINDOW_S:
                hi += 1
            if hi - lo < 3:
                continue
            ts = [pad_pts[k][0] for k in range(lo, hi + 1)]
            ax = _fit_acceleration(ts, [pad_pts[k][1][0] for k in range(lo, hi + 1)])
            if ax == ax:
                pacc.append(ax)
        if len(pacc) >= 5:
            out["a_pad_peak_mps2"] = max(abs(a) for a in pacc)
            out["a_pad_rms_mps2"] = math.sqrt(sum(a * a for a in pacc) / len(pacc))
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
            rows.append(carry_acceleration(load(samples), row))
    for r in rows:
        print(json.dumps(r, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
