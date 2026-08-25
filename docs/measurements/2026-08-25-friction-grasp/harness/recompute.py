#!/usr/bin/env python3
"""Recompute every trial's metrics from the saved pose samples.

Separated from the harness so that a corrected definition can be applied to data
already collected, rather than by re-running and hoping the next run behaves the
same. The raw samples are the record; this file is the interpretation of them,
and it is the interpretation that changed.

TWO CORRECTIONS TO THE PRE-REGISTERED DEFINITIONS, both forced by the data and
both recorded in results.md:

1. `flung` was `v_max > 1 m/s over the whole trial`. Every trial that tripped it
   did so AFTER the release, at 3.3 m/s, ending at z = 0.025 -- a 50 mm cube
   resting on the ground plane. That is the conveyor carrying a correctly placed
   part off its far end and the part falling to the floor. It is the belt doing
   its job, not the grasp failing, and reading it as a fling would have made the
   grasp look 25% unreliable for a reason that has nothing to do with friction.
   `flung` is now evaluated over the carry window alone.

2. `place_err` was measured at the end of the recording, by which time the belt
   had moved the part -- for the same reason. It is now measured at the release,
   which is where the skill actually delivered it.
"""
import csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from measure_grasp import (Sample, compose, interpolate, quat_conj_rotate,
                           quat_inv, quat_mul, PAD_LINK, PAD_LINK_R, ARM_MODEL)

ARM = Sample(0.0, (0.0, -0.35, 0.6), (0.0, 0.0, 0.7071067823197225, 0.7071067800533724))
PLACE_XY = (0.45, 0.0)


def load(path):
    tracks = {}
    with Path(path).open() as fh:
        for r in csv.DictReader(fh):
            tracks.setdefault(r["entity"], []).append(
                Sample(float(r["sim_t"]),
                       (float(r["x"]), float(r["y"]), float(r["z"])),
                       (float(r["qx"]), float(r["qy"]), float(r["qz"]), float(r["qw"]))))
    return tracks


def metrics(tracks, row, arm=ARM):
    wp = tracks.get(row["model"], [])
    padl, padr = tracks.get(PAD_LINK, []), tracks.get(PAD_LINK_R, [])
    tg, tr = row.get("t_grasp_sim"), row.get("t_release_sim")
    out = {"trial": row["trial"], "label": row["label"], "model": row["model"],
           "plugin_can_fire": row.get("plugin_can_fire"), "mu": row.get("mu"),
           "pick_succeeded": row.get("pick_succeeded"),
           "pick_reported_holding": row.get("pick_reported_holding"),
           "place_succeeded": row.get("place_succeeded"),
           "q_at_stall_rad": row.get("q_at_stall_rad"),
           "z_rest": row.get("z_rest"), "note": row.get("note", "")}
    if not wp:
        out["usable"] = False
        return out
    z_rest = row["z_rest"]
    out["lift_m"] = max(s.p[2] for s in wp) - z_rest

    if tg is not None and tr is not None:
        out["window"] = "grasp-to-release"
        carry = [s for s in wp if tg <= s.t <= tr]
    else:
        # A Pick that failed reports no PHASE_RETREATING, so there is no grasp
        # instant to measure against. That is the plugin-on case, where the part
        # is welded to a finger and carried while the skill reports an empty
        # gripper -- so the part IS being transported and the transport is still
        # worth measuring. The window is then every sample for which the part is
        # clear of the table, which is what "being carried" means without a
        # skill to ask.
        out["window"] = "airborne"
        air = [s for s in wp if s.p[2] > z_rest + 0.05]
        carry = air
    if len(carry) < 3:
        out["usable"] = False
        return out
    out["usable"] = True
    out["carry_duration_s"] = carry[-1].t - carry[0].t if len(carry) > 1 else 0.0

    # Speed inside the carry only.
    v = 0.0
    for a, b in zip(carry, carry[1:]):
        dt = b.t - a.t
        if dt > 1e-9:
            v = max(v, math.dist(a.p, b.p) / dt)
    out["v_max_carry_mps"] = v
    va = 0.0
    for a, b in zip(wp, wp[1:]):
        dt = b.t - a.t
        if dt > 1e-9:
            va = max(va, math.dist(a.p, b.p) / dt)
    out["v_max_whole_trial_mps"] = va

    # Rigid-grasp residuals: translation in the pad frame, rotation relative to
    # the pad, and the rotation-invariant pad-to-part distance.
    slips, twists, dists = [], [], []
    ref = qref = dref = None
    for s in carry:
        l = interpolate(padl, s.t)
        if l is None:
            continue
        lw = compose(arm, l)
        rel = quat_conj_rotate(lw.q, tuple(s.p[i] - lw.p[i] for i in range(3)))
        rq = quat_mul(quat_inv(lw.q), s.q)
        d = math.dist(s.p, lw.p) * 1000.0
        if ref is None:
            ref, qref, dref = rel, rq, d
            continue
        slips.append((s.t - carry[0].t, math.dist(rel, ref) * 1000.0))
        dq = quat_mul(quat_inv(qref), rq)
        twists.append((s.t - carry[0].t,
                       math.degrees(2 * math.acos(max(-1.0, min(1.0, abs(dq[3])))))))
        dists.append((s.t - carry[0].t, d - dref))
    out["slip_max_mm"] = max((x for _, x in slips), default=None)
    out["slip_final_mm"] = slips[-1][1] if slips else None
    out["twist_max_deg"] = max((x for _, x in twists), default=None)
    out["twist_final_deg"] = twists[-1][1] if twists else None
    out["pad_dist_drift_mm"] = max((abs(x) for _, x in dists), default=None)
    if slips:
        n = len(slips)
        mt = sum(t for t, _ in slips) / n
        mv = sum(x for _, x in slips) / n
        den = sum((t - mt) ** 2 for t, _ in slips)
        out["slip_rate_mm_per_s"] = (
            sum((t - mt) * (x - mv) for t, x in slips) / den if den > 1e-12 else 0.0)

    # Pad separation while holding: the jaw opening, measured between the pads
    # in the simulator rather than inferred from the drive joint.
    seps = []
    w0, w1 = carry[0].t, carry[-1].t
    for s in padl:
        if not (w0 <= s.t <= w1):
            continue
        r = interpolate(padr, s.t)
        if r:
            seps.append(math.dist(compose(arm, s).p, compose(arm, r).p) * 1000.0)
    if seps:
        out["pad_separation_mm_mean"] = sum(seps) / len(seps)
        out["pad_separation_mm_range"] = max(seps) - min(seps)

    at_release = carry[-1]
    out["place_err_at_release_m"] = math.hypot(at_release.p[0] - PLACE_XY[0],
                                               at_release.p[1] - PLACE_XY[1])
    out["final_z"] = wp[-1].p[2]
    out["z_min_during_carry"] = min(s.p[2] for s in carry)
    return out


if __name__ == "__main__":
    rows = []
    for meta in sorted(Path("raw").glob("*_trials.json")):
        for row in json.loads(meta.read_text()):
            if "trial" not in row:
                continue
            samples = Path("raw") / f"{row['label']}_trial{row['trial']:03d}_samples.csv"
            if not samples.exists():
                continue
            rows.append(metrics(load(samples), row))
    fields = sorted({k for r in rows for k in r})
    order = ["label", "trial", "model", "plugin_can_fire", "mu", "usable"]
    fields = order + [f for f in fields if f not in order]
    with open("raw/all_trials_recomputed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote raw/all_trials_recomputed.csv with {len(rows)} trials")
