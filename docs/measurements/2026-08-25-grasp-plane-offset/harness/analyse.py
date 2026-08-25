#!/usr/bin/env python3
"""Consolidate this campaign's blocks and evaluate the pre-registered thresholds.

Metrics come from the published campaign's `recompute.py` — imported, not
re-implemented — so that every number here means what the same-named number in
`../2026-08-25-friction-grasp/results.md` means. This file adds only the
comparison between blocks and the tests `criteria.md` registered in advance.

    python3 analyse.py            # from the campaign directory

Writes `raw/all_trials.csv` and prints the verdict table.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE.parent.parent / "2026-08-25-friction-grasp" / "harness"
sys.path.insert(0, str(PUBLISHED))
sys.path.insert(0, str(HERE))

from recompute import load, metrics  # noqa: E402
from engagement import trial_engagement  # noqa: E402
from acceleration import carry_acceleration  # noqa: E402
import geometry as g  # noqa: E402

PERMUTATIONS = 100_000
SEED = 20260825
TWIST_FLOOR_DEG = 1.0


# -- statistics, written out rather than imported, because scipy is not a
#    dependency of this workspace and adding one for a p-value would be a
#    supply-chain change to answer a measurement question. ---------------------

def median(xs):
    return statistics.median(xs) if xs else float("nan")


def permutation_p(a: list[float], b: list[float]) -> float:
    """Two-sided permutation test on the difference of medians."""
    observed = abs(median(a) - median(b))
    pool = list(a) + list(b)
    n = len(a)
    rng = random.Random(SEED)
    hits = 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(pool)
        if abs(median(pool[:n]) - median(pool[n:])) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (PERMUTATIONS + 1)


def bootstrap_median_ratio(a: list[float], b: list[float], reps: int = 20000):
    """95% percentile interval for median(b)/median(a) and for median(b)-median(a).

    A null result has to say which effect sizes it excludes, or it is only the
    absence of a number. This is what turns "no difference" into a bound.
    """
    rng = random.Random(SEED + 1)
    ratios, diffs = [], []
    for _ in range(reps):
        ra = [a[rng.randrange(len(a))] for _ in a]
        rb = [b[rng.randrange(len(b))] for _ in b]
        ma, mb = median(ra), median(rb)
        diffs.append(mb - ma)
        if ma > 0:
            ratios.append(mb / ma)
    ratios.sort()
    diffs.sort()
    q = lambda v, f: v[max(0, min(len(v) - 1, int(f * len(v))))]
    return (q(ratios, 0.025), q(ratios, 0.975)), (q(diffs, 0.025), q(diffs, 0.975))


#: Cut between the two modes the twist distribution actually has. POST-HOC: it
#: was chosen after reading the published campaign's per-trial values, where at
#: max_step_size 0.001 the trials fall into a low group (0.3-8.6 deg) and a high
#: group (10.6-30.1 deg), at 0.0005 all twelve are high, and at 0.002 all twelve
#: sit at 0.5-0.8 deg. It is reported as a descriptor beside the rank test, which
#: needs no threshold, never as the basis of a verdict.
HIGH_TWIST_DEG = 10.0


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval on a proportion — the same interval the published
    campaign used for its success rate."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]]."""
    from math import comb
    n = a + b + c + d
    row1, col1 = a + b, a + c
    def prob(x):
        return (comb(row1, x) * comb(n - row1, col1 - x)) / comb(n, col1)
    observed = prob(a)
    total = 0.0
    for x in range(max(0, col1 - (n - row1)), min(row1, col1) + 1):
        pk = prob(x)
        if pk <= observed + 1e-12:
            total += pk
    return min(1.0, total)


def mann_whitney(a: list[float], b: list[float]):
    """U, the rank-biserial effect size, and a permutation p-value.

    Reported alongside the pre-registered median test because the per-trial
    distribution turned out to be bimodal -- a trial either twists 20-30 deg or
    barely twists -- and a median is an unstable summary of a mixture. A rank
    test asks the question a bimodal sample can actually answer: does a trial
    drawn from one condition tend to twist more than one drawn from the other?
    """
    na, nb = len(a), len(b)
    def u_of(x, y):
        u = 0.0
        for xi in x:
            for yi in y:
                u += 1.0 if xi > yi else (0.5 if xi == yi else 0.0)
        return u
    u = u_of(a, b)
    effect = 2.0 * u / (na * nb) - 1.0        # rank-biserial, -1 .. +1
    observed = abs(u - na * nb / 2.0)
    pool = list(a) + list(b)
    rng = random.Random(SEED + 2)
    hits = 0
    reps = 20000
    for _ in range(reps):
        rng.shuffle(pool)
        if abs(u_of(pool[:na], pool[na:]) - na * nb / 2.0) >= observed - 1e-9:
            hits += 1
    return u, effect, (hits + 1) / (reps + 1)


def spearman(xs: list[float], ys: list[float]) -> float:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


# -- loading -------------------------------------------------------------------

def collect(raw: Path) -> list[dict]:
    rows = []
    for meta in sorted(raw.glob("*_trials.json")):
        for row in json.loads(meta.read_text()):
            if "trial" not in row:
                continue
            samples = raw / f"{row['label']}_trial{row['trial']:03d}_samples.csv"
            if not samples.exists():
                continue
            if row["label"].startswith("smoke_"):
                continue   # the smoke run is data, but it is not a block
            tracks = load(samples)
            m = metrics(tracks, row)
            m.update({k: v for k, v in trial_engagement(tracks, row).items()
                      if k not in ("trial", "label")})
            m.update({k: v for k, v in carry_acceleration(tracks, row).items()
                      if k not in ("trial", "label", "measured")})
            m["commanded_grasp_height_m"] = row.get("commanded_grasp_height_m")
            m["carry_duration_s"] = m.get("carry_duration_s")
            m["wall_s"] = row.get("wall_s")
            rows.append(m)
    return rows


def block_summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("usable")]
    tw = [r["twist_max_deg"] for r in ok if r.get("twist_max_deg") is not None]
    sl = [r["slip_max_mm"] for r in ok if r.get("slip_max_mm") is not None]
    sr = [r["slip_rate_mm_per_s"] for r in ok if r.get("slip_rate_mm_per_s") is not None]
    pe = [r["place_err_at_release_m"] for r in ok if r.get("place_err_at_release_m") is not None]
    q = [r["q_at_stall_rad"] for r in ok if r.get("q_at_stall_rad") is not None]
    cd = [r["carry_duration_s"] for r in ok if r.get("carry_duration_s")]
    off = [r["pad_offset_vs_com_mm"] for r in ok if r.get("pad_offset_vs_com_mm") is not None]
    eng = [r["pad_face_engaged_mm"] for r in ok if r.get("pad_face_engaged_mm") is not None]
    tip = [r["finger_tip_above_surface_mm"] for r in ok
           if r.get("finger_tip_above_surface_mm") is not None]
    sep = [r["pad_separation_mm_mean"] for r in ok if r.get("pad_separation_mm_mean")]
    vmax = [r["v_max_carry_mps"] for r in ok if r.get("v_max_carry_mps") is not None]
    lift = [r["lift_m"] for r in ok if r.get("lift_m") is not None]
    return {
        "n": len(rows), "n_usable": len(ok),
        "held": sum(1 for r in rows if r.get("pick_reported_holding")),
        "picked": sum(1 for r in rows if r.get("pick_succeeded")),
        "placed": sum(1 for r in rows if r.get("place_succeeded")),
        "height_m": rows[0].get("commanded_grasp_height_m") if rows else None,
        "twist": tw, "slip": sl,
        "twist_median": median(tw), "twist_min": min(tw, default=None),
        "twist_max": max(tw, default=None),
        "slip_median": median(sl), "slip_max": max(sl, default=None),
        "slip_rate_median": median(sr), "slip_rate_positive": sum(1 for x in sr if x > 0),
        "place_err_median_mm": median(pe) * 1000 if pe else None,
        "place_err_max_mm": max(pe, default=0) * 1000 if pe else None,
        "q_stall_median": median(q), "q_stall_min": min(q, default=None),
        "q_stall_max": max(q, default=None),
        "carry_median_s": median(cd),
        "pad_offset_median_mm": median(off), "pad_offset_min_mm": min(off, default=None),
        "pad_offset_max_mm": max(off, default=None),
        "engaged_median_mm": median(eng),
        "tip_clearance_min_mm": min(tip, default=None),
        "pad_separation_mean_mm": sum(sep) / len(sep) if sep else None,
        "v_max_carry": max(vmax, default=None),
        "lift_min_m": min(lift, default=None),
    }


def main() -> int:
    raw = Path("raw")
    rows = collect(raw)
    if not rows:
        print("no trials found under raw/", file=sys.stderr)
        return 1

    fields = sorted({k for r in rows for k in r})
    order = ["label", "trial", "commanded_grasp_height_m", "pad_offset_vs_com_mm",
             "pad_face_engaged_mm", "twist_max_deg", "slip_max_mm"]
    fields = order + [f for f in fields if f not in order]
    with (raw / "all_trials.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote raw/all_trials.csv with {len(rows)} trials\n")

    blocks: dict[str, list[dict]] = {}
    for r in rows:
        h = r.get("commanded_grasp_height_m")
        # An interleaved block carries two conditions under one label, so the
        # condition -- not the block -- is the unit of comparison.
        r["condition"] = (f"{r['label']}@{h*1000:.1f}mm" if h is not None
                          else r["label"])
        blocks.setdefault(r["condition"], []).append(r)
    summaries = {k: block_summary(v) for k, v in sorted(blocks.items())}

    hdr = (f"{'block':26s} {'n':>3s} {'held':>5s} {'height':>7s} {'offset':>8s} "
           f"{'engaged':>8s} {'twist med':>10s} {'twist max':>10s} "
           f"{'slip med':>9s} {'place med':>10s} {'carry':>7s} {'q stall':>8s} {'tip':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for name, s in summaries.items():
        print(f"{name:26s} {s['n']:3d} {s['held']:>2d}/{s['n']:<2d} "
              f"{(s['height_m'] or 0)*1000:6.1f}m {s['pad_offset_median_mm']:+7.2f} "
              f"{s['engaged_median_mm']:7.2f} {s['twist_median']:9.2f}° "
              f"{(s['twist_max'] or 0):9.2f}° {s['slip_median']:8.2f} "
              f"{(s['place_err_median_mm'] or 0):9.2f} {s['carry_median_s']:6.2f}s "
              f"{s['q_stall_median']:7.4f} {(s['tip_clearance_min_mm'] or 0):5.1f}")

    print("\n--- guards (G) ---")
    for name, s in summaries.items():
        problems = []
        if s["held"] != s["n"]:
            problems.append(f"holding {s['held']}/{s['n']}")
        if s["picked"] != s["n"]:
            problems.append(f"pick SUCCESS {s['picked']}/{s['n']}")
        if s["tip_clearance_min_mm"] is not None and s["tip_clearance_min_mm"] <= 2.0:
            problems.append(f"tip clearance {s['tip_clearance_min_mm']:.1f} mm")
        if s["lift_min_m"] is not None and s["lift_min_m"] <= 0.05:
            problems.append(f"lift {s['lift_min_m']:.3f} m")
        print(f"  {name:26s} {'OK' if not problems else 'CHECK: ' + '; '.join(problems)}")

    def compare(a: str, b: str, tag: str):
        if a not in summaries or b not in summaries:
            return
        sa, sb = summaries[a], summaries[b]
        print(f"\n--- {tag}: {b} vs {a} ---")
        ratio = sb["twist_median"] / sa["twist_median"] if sa["twist_median"] else float("nan")
        print(f"  twist median {sa['twist_median']:.2f}° -> {sb['twist_median']:.2f}°"
              f"  ({ratio*100:.1f}% of uncorrected)")
        print(f"  twist range  [{sa['twist_min']:.2f}, {sa['twist_max']:.2f}]° -> "
              f"[{sb['twist_min']:.2f}, {sb['twist_max']:.2f}]°"
              f"   {'DISJOINT' if sb['twist_max'] < sa['twist_min'] else 'OVERLAPPING'}")
        print(f"  permutation p (medians, {PERMUTATIONS} perms, seed {SEED}) = "
              f"{permutation_p(sa['twist'], sb['twist']):.5f}")
        u, eff, pmw = mann_whitney(sa["twist"], sb["twist"])
        print(f"  Mann-Whitney U={u:.1f}  rank-biserial={eff:+.3f}  p={pmw:.5f}"
              f"   (positive effect = the FIRST condition twists more)")
        na, nb = len(sa["twist"]), len(sb["twist"])
        hi_a = sum(1 for x in sa["twist"] if x > HIGH_TWIST_DEG)
        hi_b = sum(1 for x in sb["twist"] if x > HIGH_TWIST_DEG)
        wa, wb = wilson(hi_a, na), wilson(hi_b, nb)
        print(f"  high-twist mode (>{HIGH_TWIST_DEG:.0f} deg, post-hoc descriptor): "
              f"{hi_a}/{na} [{wa[0]:.2f}, {wa[1]:.2f}] vs "
              f"{hi_b}/{nb} [{wb[0]:.2f}, {wb[1]:.2f}]  "
              f"Fisher p={fisher_exact(hi_a, na - hi_a, hi_b, nb - hi_b):.4f}")
        (rlo, rhi), (dlo, dhi) = bootstrap_median_ratio(sa["twist"], sb["twist"])
        print(f"  bootstrap 95% CI on the median ratio  [{rlo:.2f}, {rhi:.2f}]"
              f"   (H1 'removed' needs the whole interval below 0.20)")
        print(f"  bootstrap 95% CI on the median change [{dlo:+.2f}, {dhi:+.2f}]°")
        sratio = sb["slip_median"] / sa["slip_median"] if sa["slip_median"] else float("nan")
        print(f"  slip median  {sa['slip_median']:.2f} -> {sb['slip_median']:.2f} mm"
              f"  ({sratio*100:.1f}%)")
        print(f"  q at stall   {sa['q_stall_median']:.4f} -> {sb['q_stall_median']:.4f} rad"
              f"  (delta {abs(sb['q_stall_median']-sa['q_stall_median']):.4f}, allowed 0.02)")
        print(f"  pad sep      {sa['pad_separation_mean_mm']:.2f} -> "
              f"{sb['pad_separation_mean_mm']:.2f} mm")
        print(f"  carry        {sa['carry_median_s']:.2f} -> {sb['carry_median_s']:.2f} s"
              f"  ({abs(sb['carry_median_s']-sa['carry_median_s'])/sa['carry_median_s']*100:.1f}%,"
              f" allowed 15%)")

    # ------------------------------------------------------------------
    # Pooled comparisons. The unit is the CONDITION, and blocks are pooled only
    # within a design: the two interleaved blocks each carry both conditions, so
    # pooling them cannot confound a bring-up with a treatment, while pooling an
    # interleaved block with a separate one can and is reported separately.
    # ------------------------------------------------------------------
    def pool(labels: list[str], height_mm: str) -> list[dict]:
        out: list[dict] = []
        for label in labels:
            out.extend(blocks.get(f"{label}@{height_mm}", []))
        return out

    def compare_pooled(labels: list[str], tag: str, design: str) -> None:
        a = [r for r in pool(labels, "30.0mm") if r.get("usable")]
        b = [r for r in pool(labels, "5.8mm") if r.get("usable")]
        if len(a) < 4 or len(b) < 4:
            return
        sa, sb = block_summary(a), block_summary(b)
        print(f"\n=== {tag} ===")
        print(f"    design: {design}")
        print(f"    blocks: {', '.join(labels)}")
        na, nb = len(sa["twist"]), len(sb["twist"])
        hi_a = sum(1 for x in sa["twist"] if x > HIGH_TWIST_DEG)
        hi_b = sum(1 for x in sb["twist"] if x > HIGH_TWIST_DEG)
        wa, wb = wilson(hi_a, na), wilson(hi_b, nb)
        pf = fisher_exact(hi_a, na - hi_a, hi_b, nb - hi_b)
        print(f"  RATE of entering the high-twist mode (>{HIGH_TWIST_DEG:.0f} deg) "
              f"-- the primary statistic, because the process is two-state:")
        print(f"    uncorrected  {hi_a:2d}/{na:2d} = {hi_a/na*100:5.1f}%  "
              f"Wilson 95% [{wa[0]*100:4.1f}%, {wa[1]*100:5.1f}%]")
        print(f"    corrected    {hi_b:2d}/{nb:2d} = {hi_b/nb*100:5.1f}%  "
              f"Wilson 95% [{wb[0]*100:4.1f}%, {wb[1]*100:5.1f}%]")
        print(f"    Fisher exact p = {pf:.4f}"
              f"    intervals {'DO NOT overlap' if wa[0] > wb[1] or wb[0] > wa[1] else 'OVERLAP'}")
        # The 10 deg cut is post-hoc, so show that the answer does not live on it.
        print("  threshold sensitivity (the cut is post-hoc, so vary it):")
        for cut in (5.0, 10.0, 15.0, 20.0):
            ka = sum(1 for x in sa["twist"] if x > cut)
            kb = sum(1 for x in sb["twist"] if x > cut)
            print(f"    >{cut:4.0f} deg: {ka:2d}/{na:2d} vs {kb:2d}/{nb:2d}"
                  f"   Fisher p={fisher_exact(ka, na - ka, kb, nb - kb):.4f}")
        u, eff, pmw = mann_whitney(sa["twist"], sb["twist"])
        print(f"  Rank test on the whole distribution (no threshold at all): "
              f"rank-biserial {eff:+.3f}, p={pmw:.5f}")
        print(f"  full distributions, sorted:")
        print(f"    uncorrected {[round(x, 1) for x in sorted(sa['twist'])]}")
        print(f"    corrected   {[round(x, 1) for x in sorted(sb['twist'])]}")
        print(f"  twist median {sa['twist_median']:6.2f} -> {sb['twist_median']:6.2f} deg"
              f"   max {sa['twist_max']:6.2f} -> {sb['twist_max']:6.2f} deg")
        (rlo, rhi), (dlo, dhi) = bootstrap_median_ratio(sa["twist"], sb["twist"])
        print(f"    bootstrap 95% CI on the median change [{dlo:+.2f}, {dhi:+.2f}] deg")
        print(f"  slip median  {sa['slip_median']:6.2f} -> {sb['slip_median']:6.2f} mm"
              f"   place err median {sa['place_err_median_mm']:5.2f} -> "
              f"{sb['place_err_median_mm']:5.2f} mm")
        print(f"  GUARDS  holding {sa['held']}/{sa['n']} vs {sb['held']}/{sb['n']}"
              f" | q_stall {sa['q_stall_median']:.4f} vs {sb['q_stall_median']:.4f}"
              f" | pad sep {sa['pad_separation_mean_mm']:.2f} vs "
              f"{sb['pad_separation_mean_mm']:.2f} mm"
              f" | carry {sa['carry_median_s']:.2f} vs {sb['carry_median_s']:.2f} s")
        print(f"  MEASURED offset {sa['pad_offset_median_mm']:+.2f} vs "
              f"{sb['pad_offset_median_mm']:+.2f} mm"
              f" | engaged {sa['engaged_median_mm']:.2f} vs {sb['engaged_median_mm']:.2f} mm"
              f" | tip clearance min {sa['tip_clearance_min_mm']:.1f} vs "
              f"{sb['tip_clearance_min_mm']:.1f} mm")
        # What this n can and cannot separate, stated whichever way the result fell.
        base = hi_a / na if na else 0.0
        detectable = []
        for target in (0.10, 0.20, 0.30, 0.40):
            k = round(target * nb)
            if fisher_exact(hi_a, na - hi_a, k, nb - k) < 0.05:
                detectable.append(f"{target*100:.0f}%")
        print(f"  POWER at this n: against an uncorrected rate of {base*100:.0f}%, a "
              f"corrected rate of {{{', '.join(detectable) if detectable else 'nothing'}}} "
              f"would reach p<0.05. Anything closer than that is not separable here.")

    compare_pooled(["paired", "paired2"],
                   "H1 at max_step_size 0.001 (shipped) - PRIMARY",
                   "interleaved: both heights alternated against one cell")
    compare_pooled(["uncorrected", "corrected"],
                   "H1 at max_step_size 0.001 - separate blocks (secondary)",
                   "separate blocks: condition is confounded with bring-up")
    compare_pooled(["paired", "paired2", "uncorrected", "corrected"],
                   "H1 at max_step_size 0.001 - all trials pooled (secondary)",
                   "mixed designs pooled; read the interleaved result first")
    compare_pooled(["paired_fine"],
                   "At max_step_size 0.0005 - PRIMARY for the timestep question",
                   "interleaved: both heights alternated against one cell")

    print("\n--- H6: does the carry's horizontal acceleration drive the twist? ---")
    print("  PAD columns are the test. The pad is driven by the arm and is upstream")
    print("  of the grasp. The PART columns are shown only to expose the trap: the")
    print("  part's own twisting IS relative motion, so it lands in the part's own")
    print("  second derivative and correlating twist against it is close to an")
    print("  identity. Read the spread as well as rho -- a predictor that barely")
    print("  varies cannot explain an outcome that varies by a factor of eighty.")
    for name, block in sorted(blocks.items()):
        ok = [r for r in block if r.get("usable")
              and r.get("a_pad_rms_mps2") is not None
              and r.get("twist_max_deg") is not None]
        if len(ok) < 6:
            continue
        tw = [r["twist_max_deg"] for r in ok]
        pad_rms = [r["a_pad_rms_mps2"] for r in ok]
        spread = (max(pad_rms) - min(pad_rms)) / median(pad_rms) * 100.0
        print(f"  {name:26s} n={len(ok):2d}  "
              f"PAD rho(rms)={spearman(tw, pad_rms):+.3f} "
              f"rho(peak)={spearman(tw, [r['a_pad_peak_mps2'] for r in ok]):+.3f} "
              f"spread={spread:4.1f}%   |   "
              f"PART rho(rms)={spearman(tw, [r['a_rms_mps2'] for r in ok]):+.3f}")

    (raw / "summary.json").write_text(json.dumps(
        {k: {kk: vv for kk, vv in v.items() if kk not in ("twist", "slip")}
         for k, v in summaries.items()}, indent=2, default=str))
    print("\nwrote raw/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
