#!/usr/bin/env python3
"""Apply criteria.md 7 and 10 to raw/, and print the tables ANALYSIS.md reports.

Every rule here is the one written down before the first trial. Nothing is chosen
after seeing data: the minimum interesting sizes, the alpha, the resolution rule R,
the mechanism rule S and the block rule V4 are transcribed from criteria.md and are
applied literally, including where they fire against the campaign's convenience.

    .venv/bin/python docs/measurements/2026-09-01-hull-grasp/harness/analyse.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, fisher_exact

RAW = Path(__file__).resolve().parent.parent / "raw"

#: criteria.md 7.1, verbatim. Key -> (minimum interesting size, unit, which family).
MIS = {
    "patch_len_left_mm_median": (2.0, "mm", "M3"),
    "patch_len_right_mm_median": (2.0, "mm", "M3"),
    "normal_approach_component_max": (0.02, "-", "M4"),
    "normal_approach_component_median": (0.02, "-", "M4"),
    "d_approach_mm": (0.20, "mm", "M1"),
    "d_close_mm": (0.20, "mm", "M1"),
    "d_pivot_mm": (0.20, "mm", "M1"),
    "pitch_pivot_deg": (0.50, "deg", "M2"),
    "roll_close_deg": (0.50, "deg", "M2"),
    "yaw_approach_deg": (0.50, "deg", "M2"),
    "twist_max_deg": (5.0, "deg", "C1"),
    "carry_rot_world_vertical_deg": (2.0, "deg", "C2"),
    "q_at_stall_rad": (0.005, "rad", "C4"),
    "place_err_m": (0.010, "m", "C3"),
    "slip_max_mm": (2.0, "mm", "C3"),
    "lift_m": (0.010, "m", "C3"),
    "v_max_mps": (0.050, "m/s", "C3"),
    "pad_separation_mm_mean": (0.5, "mm", "C4"),
}
ALPHA = 0.01                     # criteria.md 7.2
FRAME_RESIDUAL_CEILING_DEG = 5.0  # V3
BODY_MOVE_CEILING_MM = 2.0        # V5
#: Metrics that V3 and V5 gate. Everything else is a carry metric and is unaffected
#: by a bad closure frame.
CLOSURE_METRICS = {"d_approach_mm", "d_close_mm", "d_pivot_mm",
                   "pitch_pivot_deg", "roll_close_deg", "yaw_approach_deg"}


def load(label: str) -> list[dict]:
    path = RAW / f"{label}_trials.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d


def values(rows, key, gated: bool):
    out = []
    for r in rows:
        v = r.get(key)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        if gated:
            fr = r.get("pad_to_pad_axis_angle_deg")
            bm = r.get("body_move_mm")
            if fr is None or fr > FRAME_RESIDUAL_CEILING_DEG:
                continue
            if bm is None or bm > BODY_MOVE_CEILING_MM:
                continue
        out.append(float(v))
    return np.array(out)


def hodges_lehmann(a, b) -> float:
    """Median of every pairwise difference b - a. criteria.md 7.2."""
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    return float(np.median(np.subtract.outer(b, a).ravel()))


def iqr(v) -> float:
    if len(v) < 2:
        return float("nan")
    return float(np.percentile(v, 75) - np.percentile(v, 25))


def trial_success(r: dict) -> bool | None:
    """The friction campaign's verdict, its definitions verbatim."""
    if r.get("z_rest") is None:
        return None
    grasp = bool(r.get("pick_reported_holding"))
    lift = (r.get("lift_m") or 0.0) > 0.05
    held = bool(r.get("held_through_transport"))
    placed = (r.get("place_err_m") if r.get("place_err_m") is not None else 9e9) < 0.10
    flung = (r.get("v_max_mps") or 0.0) > 1.0
    return grasp and lift and held and placed and not flung


def main() -> int:
    blocks = {g: [load(f"{g}_B{b}") for b in (1, 2)] for g in ("VENDOR", "HULL")}
    pooled = {g: [r for blk in blocks[g] for r in blk if r.get("z_rest") is not None]
              for g in blocks}

    print("=" * 78)
    print("n per condition (trials that produced metrics)")
    for g in ("VENDOR", "HULL"):
        per = [len([r for r in blk if r.get("z_rest") is not None]) for blk in blocks[g]]
        print(f"  {g:<7} block n = {per}   pooled n = {len(pooled[g])}")

    # ---- V2, V3, V5 ---------------------------------------------------------
    print("\n" + "=" * 78)
    print("V2/V3/V5 — validity gates")
    for g in ("VENDOR", "HULL"):
        for b, blk in enumerate(blocks[g], start=1):
            rows = [r for r in blk if r.get("z_rest") is not None]
            if not rows:
                continue
            fr = [r.get("pad_to_pad_axis_angle_deg") for r in rows
                  if r.get("pad_to_pad_axis_angle_deg") is not None]
            bm = [r.get("body_move_mm") for r in rows if r.get("body_move_mm") is not None]
            bad_fr = sum(1 for v in fr if v > FRAME_RESIDUAL_CEILING_DEG)
            bad_bm = sum(1 for v in bm if v > BODY_MOVE_CEILING_MM)
            gj = RAW / f"{g}_B{b}_geometry.json"
            geo = json.loads(gj.read_text()) if gj.exists() else {}
            print(f"  {g}_B{b}: geometry_verified={geo.get('geometry_verified')} "
                  f"hull_refs={geo.get('hull_collision_refs')}  "
                  f"frame residual max={max(fr, default=float('nan')):.3f} deg "
                  f"(V3 excludes {bad_fr})  "
                  f"body_move max={max(bm, default=float('nan')):.3f} mm "
                  f"(V5 excludes {bad_bm})")

    # ---- the metric table ---------------------------------------------------
    print("\n" + "=" * 78)
    print("Metrics — criteria.md 7.2 (D), 7.3 (R), 10 (V4)")
    hdr = (f"{'metric':<34}{'family':<7}{'vendor med':>12}{'hull med':>12}"
           f"{'HL shift':>11}{'p':>10}{'vend IQR':>10}{'MIS':>8}  verdict")
    print(hdr)
    print("-" * len(hdr))
    results = {}
    for key, (mis, unit, fam) in MIS.items():
        gated = key in CLOSURE_METRICS
        a = values(pooled["VENDOR"], key, gated)
        b = values(pooled["HULL"], key, gated)
        if len(a) < 3 or len(b) < 3:
            print(f"{key:<34}{fam:<7}{'-':>12}{'-':>12}{'-':>11}{'-':>10}"
                  f"{'-':>10}{mis:>8}  NO DATA")
            results[key] = {"verdict": "NO DATA"}
            continue
        med_a, med_b = float(np.median(a)), float(np.median(b))
        shift = hodges_lehmann(a, b)
        try:
            p = float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
        except ValueError:
            p = 1.0
        vend_iqr = iqr(a)

        # V4 — the block effect, computed on the same gating.
        blk_meds = {}
        for g in ("VENDOR", "HULL"):
            ms = []
            for blk in blocks[g]:
                rows = [r for r in blk if r.get("z_rest") is not None]
                v = values(rows, key, gated)
                ms.append(float(np.median(v)) if len(v) else float("nan"))
            blk_meds[g] = ms
        within = max(
            abs(blk_meds["VENDOR"][0] - blk_meds["VENDOR"][1]),
            abs(blk_meds["HULL"][0] - blk_meds["HULL"][1]),
        )
        between = abs(shift)

        if vend_iqr > mis:
            verdict = "UNRESOLVED (R)"
        elif p < ALPHA and abs(shift) >= mis:
            verdict = "DETECTED"
            if not math.isnan(within) and within > between:
                verdict = "INCONCLUSIVE (V4)"
        else:
            verdict = "not detected"
        results[key] = {
            "family": fam, "vendor_median": med_a, "hull_median": med_b,
            "hl_shift": shift, "p": p, "vendor_iqr": vend_iqr, "mis": mis,
            "unit": unit, "verdict": verdict, "n_vendor": int(len(a)),
            "n_hull": int(len(b)), "block_medians": blk_meds,
            "within_block_spread": within,
        }
        print(f"{key:<34}{fam:<7}{med_a:>12.4f}{med_b:>12.4f}{shift:>11.4f}"
              f"{p:>10.2e}{vend_iqr:>10.4f}{mis:>8}  {verdict}")

    # ---- outcome rules ------------------------------------------------------
    print("\n" + "=" * 78)
    print("T1 / T2 / T4 — criteria.md 7.5")
    outcomes = {}
    for g in ("VENDOR", "HULL"):
        rows = pooled[g]
        n = len(rows)
        succ = [trial_success(r) for r in rows]
        k = sum(1 for s in succ if s)
        slips = [r.get("slip_max_mm") for r in rows if r.get("slip_max_mm") is not None]
        rates = [r.get("slip_rate_mm_per_s") for r in rows
                 if r.get("slip_rate_mm_per_s") is not None]
        over5 = sum(1 for s in slips if s > 5.0)
        pos = sum(1 for r in rates if r > 0)
        flung = sum(1 for r in rows if (r.get("v_max_mps") or 0.0) > 1.0
                    or (r.get("place_err_m") or 0.0) > 0.5)
        holding = sum(1 for r in rows if r.get("pick_reported_holding"))
        picked = sum(1 for r in rows if r.get("pick_succeeded"))
        placed = sum(1 for r in rows if r.get("place_succeeded"))
        outcomes[g] = dict(n=n, success=k, wilson=wilson_lower(k, n),
                           slip_over_5mm=over5, slip_rate_positive=pos,
                           n_rates=len(rates), flung=flung, holding=holding,
                           picked=picked, placed=placed)
        print(f"  {g:<7} n={n:<3} trial_success={k}/{n} "
              f"(Wilson 95% LB {wilson_lower(k, n):.3f})  "
              f"T2 slip>5mm={over5}/{len(slips)}  slip_rate>0={pos}/{len(rates)}  "
              f"T4 flung={flung}  holding={holding}  pick_ok={picked}  place_ok={placed}")

    # C5 — the planning control.
    print("\n" + "=" * 78)
    print("C5 — non-success result codes")
    for g in ("VENDOR", "HULL"):
        rows = pooled[g]
        bad_pick = [r.get("pick_result_code") for r in rows
                    if r.get("pick_result_code") not in (0, None)]
        bad_place = [r.get("place_result_code") for r in rows
                     if r.get("place_result_code") not in (0, None)]
        notes = [r.get("note") for r in rows if r.get("note")]
        print(f"  {g:<7} pick codes != 0: {bad_pick}   place codes != 0: {bad_place}"
              f"   notes: {len(notes)}")
    v, h = outcomes["VENDOR"], outcomes["HULL"]
    table = [[v["success"], v["n"] - v["success"]], [h["success"], h["n"] - h["success"]]]
    try:
        print(f"  Fisher exact on trial_success: p = {fisher_exact(table)[1]:.4f} "
              f"(underpowered by construction; criteria.md 8)")
    except Exception as exc:
        print(f"  Fisher exact unavailable: {exc}")

    # ---- rule S -------------------------------------------------------------
    print("\n" + "=" * 78)
    m3m4 = [k for k, r in results.items()
            if r.get("family") in ("M3", "M4") and r.get("verdict") == "DETECTED"]
    if m3m4:
        print(f"Rule S: satisfied — the mechanism is visible in {m3m4}")
    else:
        print("Rule S FIRES: neither M3 nor M4 detected. The verdict on Q0 is "
              "INCONCLUSIVE, not 'no change'. Report the stall aperture and the "
              "patch's ez extent against the wedges' own ez positions.")

    (RAW / "analysis.json").write_text(json.dumps(
        {"metrics": results, "outcomes": outcomes}, indent=2, default=str))
    print(f"\nwrote {RAW / 'analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
