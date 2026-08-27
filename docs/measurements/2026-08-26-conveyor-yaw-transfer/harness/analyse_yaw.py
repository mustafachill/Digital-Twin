"""Read this campaign's raw/ against the thresholds in criteria.md.

Every statistic is the published campaigns' own, imported from
`../../2026-08-25-grasp-plane-offset/harness/analyse.py` rather than reimplemented:
Wilson intervals, two-sided Fisher exact, the permutation test on the difference
of medians and the bootstrap CI, at the same seed and the same permutation count.
Reimplementing them would produce numbers that mean almost the same thing, which
is worse than either reusing them or not reporting them.

Gates are evaluated and printed BEFORE any effect, in the pattern
`analyse.py` established: a block that is not a valid comparison is reported as
not a comparison, rather than as a result that happens to be uninteresting.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OFFSET = HERE.parent.parent / "2026-08-25-grasp-plane-offset" / "harness"
sys.path.insert(0, str(OFFSET))
sys.path.insert(0, str(HERE))

import analyse as A  # noqa: E402  (the published statistics, unchanged)
import yaw as yawlib  # noqa: E402

RAW = HERE.parent / "raw"

TRAVELLED_GATE_M = 0.900
CONTROL_GATE_M = 0.050
FLAT_DEG = 5.0
SET_TOLERANCE_DEG = 2.0
PRESERVE_MEDIAN_DEG = 2.0
PRESERVE_P95_DEG = 5.0
WIDEN_MEDIAN_DEG = 5.0
SPIN_DEG_S = 1.0


def load(*names: str) -> list[dict]:
    """Load one or more blocks, tagging each row with the block it came from.

    Arm C ran as two blocks against two separate cells rather than one, because
    the first was interrupted. They are pooled, and every row carries `block` so
    that the pooling can be undone by anyone who doubts it.
    """
    rows = []
    for name in names:
        path = RAW / f"{name}_trials.json"
        if not path.exists():
            continue
        for r in json.loads(path.read_text()):
            if "trial" in r:
                r["block"] = name
                rows.append(r)
    return rows


def bootstrap_median_ci(xs, reps: int = 20000):
    """Percentile bootstrap CI on a median, at the published campaign's seed.

    Reported so that a null result states what it EXCLUDES rather than merely
    failing to reject — the pattern `analyse.py` uses for the same reason.
    """
    import random
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(A.SEED + 3)
    meds = []
    for _ in range(reps):
        meds.append(A.median([xs[rng.randrange(len(xs))] for _ in xs]))
    meds.sort()
    q = lambda v, f: v[max(0, min(len(v) - 1, int(f * len(v))))]
    return (q(meds, 0.025), q(meds, 0.975))


def pct(xs, q):
    if not xs:
        return float("nan")
    ordered = sorted(xs)
    k = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[k]


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return "n/a"
    return f"{x:.{nd}f}"


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def arm_a(rows, control):
    section("ARM A — the belt's yaw transfer function")
    scored = [r for r in rows if r.get("ok")]
    print(f"trials recorded {len(rows)}, ok {len(scored)}")

    # ---- Gates, first and separately.
    section("G — gates (evaluated before any effect)")
    not_carried = [r for r in scored if not r.get("carried")]
    print(f"G1 travelled >= {TRAVELLED_GATE_M} m : "
          f"{len(scored) - len(not_carried)}/{len(scored)} pass")
    if scored:
        tr = [r["travelled_m"] for r in scored]
        print(f"   travelled_m  min {fmt(min(tr),3)}  median {fmt(A.median(tr),3)}  "
              f"max {fmt(max(tr),3)}")

    if control:
        ctl = [r for r in control if "travelled_m" in r]
        moved = [r for r in ctl if r["travelled_m"] >= CONTROL_GATE_M]
        print(f"G2 negative control (name outside the <carry> list): n={len(ctl)}, "
              f"travelled_m max {fmt(max((r['travelled_m'] for r in ctl), default=float('nan')),4)}")
        print(f"   -> {'PASS - the gate discriminates' if not moved else 'FAIL - an uncarried part moved anyway'}")
    else:
        print("G2 negative control: NOT RUN")

    tilted = [r for r in scored if r.get("tilt_at_read_deg", 0) > FLAT_DEG]
    print(f"G3 tilt <= {FLAT_DEG} deg at the read : "
          f"{len(scored)-len(tilted)}/{len(scored)} pass")
    off = [r for r in scored
           if not (0.450 <= r.get("x_at_read", -1) <= 1.650 and abs(r.get("y_last", 0)) <= 0.200)]
    print(f"G4 still on the belt at the read : {len(scored)-len(off)}/{len(scored)} pass")

    print(f"G5 the input was actually set (|settled - commanded| <= {SET_TOLERANCE_DEG} deg):")
    ok_g5 = True
    for level in sorted({r["commanded_yaw_deg"] for r in scored}):
        at = [r for r in scored if r["commanded_yaw_deg"] == level]
        err = [abs(r["yaw_settled_deg"] - level) for r in at]
        bad = A.median(err) > SET_TOLERANCE_DEG
        ok_g5 &= not bad
        print(f"   {level:5.1f} deg : n={len(at):2d}  median |err| {fmt(A.median(err),4)} deg"
              f"  max {fmt(max(err),4)}  {'FAIL' if bad else 'ok'}")
    print(f"   -> {'PASS' if ok_g5 else 'FAIL'}")

    valid = [r for r in scored if r.get("carried") and r.get("flat_at_read")]
    print(f"\nvalid trials for the effect: {len(valid)}")

    # ---- H1
    section("H1 — does a conveyor ride change the yaw?")
    print(f"{'level':>7} {'mode':>9} {'n':>3} {'settled':>9} {'at read':>9} "
          f"{'med |d|':>8} {'p95 |d|':>8} {'presented':>10}")
    pooled = []
    for level in sorted({r["commanded_yaw_deg"] for r in valid}):
        for mode in sorted({r["mode"] for r in valid}):
            at = [r for r in valid if r["commanded_yaw_deg"] == level and r["mode"] == mode]
            if not at:
                continue
            d = [abs(r["delta_yaw_deg"]) for r in at]
            pooled.extend(d)
            print(f"{level:7.1f} {mode:>9} {len(at):3d} "
                  f"{fmt(A.median([r['yaw_settled_deg'] for r in at]),3):>9} "
                  f"{fmt(A.median([r['yaw_at_read_deg'] for r in at]),3):>9} "
                  f"{fmt(A.median(d),4):>8} {fmt(pct(d,0.95),4):>8} "
                  f"{fmt(A.median([r['presented_at_read_mm'] for r in at]),2):>10}")
    if pooled:
        med, p95 = A.median(pooled), pct(pooled, 0.95)
        print(f"\npooled |delta|: n={len(pooled)}  median {fmt(med,4)} deg  "
              f"p95 {fmt(p95,4)} deg  max {fmt(max(pooled),4)} deg")
        signed = [r["delta_yaw_deg"] for r in valid]
        lo, hi = bootstrap_median_ci(signed)
        print(f"signed delta: median {fmt(A.median(signed),4)} deg  "
              f"bootstrap 95% CI [{fmt(lo,5)}, {fmt(hi,5)}] deg")
        verdict = ("PRESERVES" if med <= PRESERVE_MEDIAN_DEG and p95 <= PRESERVE_P95_DEG
                   else "WIDENS" if med > WIDEN_MEDIAN_DEG else "INTERMEDIATE")
        print(f"-> H1 verdict: the belt {verdict} the yaw "
              f"(thresholds: preserve median<={PRESERVE_MEDIAN_DEG}, p95<={PRESERVE_P95_DEG})")

    # ---- H2
    section("H2 — is the part still turning when it arrives?")
    rates = [abs(r["yaw_rate_at_read_deg_s"]) for r in valid
             if not math.isnan(r.get("yaw_rate_at_read_deg_s", float("nan")))]
    if rates:
        spinning = [x for x in rates if x > SPIN_DEG_S]
        k, n = len(spinning), len(rates)
        lo, hi = A.wilson(k, n)
        print(f"|yaw rate| at the read: n={n}  median {fmt(A.median(rates),4)} deg/s  "
              f"max {fmt(max(rates),4)} deg/s")
        print(f"turning faster than {SPIN_DEG_S} deg/s: {k}/{n}  "
              f"Wilson 95% [{fmt(lo,3)}, {fmt(hi,3)}]")
        print(f"-> H2 verdict: {'STILL TURNING' if k/n > 0.25 else 'SETTLED'}")

    # ---- H3
    section("H3 — does stopping the belt change the answer?")
    paired = [(r["yaw_at_read_deg"], r["yaw_settled_after_stop_deg"]) for r in valid
              if "yaw_settled_after_stop_deg" in r]
    if paired:
        diffs = [abs(a - b) for a, b in paired]
        print(f"paired |read - after stop|: n={len(diffs)}  median {fmt(A.median(diffs),4)} deg"
              f"  max {fmt(max(diffs),4)} deg")
    run = [r["yaw_at_read_deg"] - r["yaw_settled_deg"] for r in valid if r["mode"] == "running"]
    idx = [r["yaw_at_read_deg"] - r["yaw_settled_deg"] for r in valid if r["mode"] == "indexed"]
    if run and idx:
        p = A.permutation_p(run, idx)
        print(f"running delta  n={len(run):2d} median {fmt(A.median(run),4)} deg")
        print(f"indexed delta  n={len(idx):2d} median {fmt(A.median(idx),4)} deg")
        print(f"two-sided permutation p = {p:.4f} (100 000 perms, seed {A.SEED})")
        changed = (paired and A.median([abs(a - b) for a, b in paired]) > 2.0) or p < 0.01
        print(f"-> H3 verdict: stopping the belt "
              f"{'CHANGES the answer' if changed else 'does NOT change the answer'}")


def arm_c(rows):
    section("ARM C — where does the grasp boundary fall?")
    scored = [r for r in rows if r.get("ok") is not False and "commanded_yaw_deg" in r]
    if not scored:
        print("no trials")
        return
    blocks = {}
    for r in scored:
        blocks[r.get("block", "?")] = blocks.get(r.get("block", "?"), 0) + 1
    print(f"trials {len(scored)}  (blocks: {blocks})")

    section("G6 — did the arm get a grasp to measure?")
    reached = [r for r in scored if r.get("pick_succeeded")]
    print(f"Pick returned SUCCESS: {len(reached)}/{len(scored)}")
    for level in sorted({r["commanded_yaw_deg"] for r in scored}):
        at = [r for r in scored if r["commanded_yaw_deg"] == level]
        ok = [r for r in at if r.get("pick_succeeded")]
        print(f"   {level:5.1f} deg : {len(ok)}/{len(at)} reached a grasp")

    section("H4 — physical grasp success by spawn yaw")
    print("`grasp_ok` = lift>0.05 m AND held_through_transport AND place_err<=0.05 m.")
    print("NOT `pick_reported_holding`, which is true by construction at every yaw.\n")
    print(f"{'yaw':>6} {'presented':>10} {'n':>3} {'holding':>8} {'grasp_ok':>9} "
          f"{'rate':>6} {'Wilson 95%':>18}")
    base = None
    table = []
    for level in sorted({r["commanded_yaw_deg"] for r in scored}):
        at = [r for r in scored if r["commanded_yaw_deg"] == level]
        ok = [r for r in at if grasp_ok(r)]
        holding = [r for r in at if r.get("pick_reported_holding")]
        lo, hi = A.wilson(len(ok), len(at))
        table.append((level, len(ok), len(at), lo, hi))
        if base is None:
            base = (len(ok), len(at))
        print(f"{level:6.1f} {yawlib.presented_mm(level):10.2f} {len(at):3d} "
              f"{len(holding):>3}/{len(at):<4} {len(ok):>3}/{len(at):<5} "
              f"{len(ok)/len(at):6.2f} [{fmt(lo,3)}, {fmt(hi,3)}]")

    print("\nFisher exact against the 0 deg cell:")
    for level, k, n, _, _ in table:
        if level == 0.0:
            continue
        p = A.fisher_exact(base[0], base[1] - base[0], k, n - k)
        print(f"   {level:5.1f} deg : p = {p:.5f}")

    safe = [lv for lv, k, n, lo, hi in table if lo >= 0.80]
    fail = [lv for lv, k, n, lo, hi in table if hi <= 0.50]
    print(f"\ntheta_safe (largest level with Wilson lower bound >= 0.80): "
          f"{max(safe) if safe else 'NONE OF THE TESTED LEVELS'}")
    print(f"theta_fail (smallest level with Wilson upper bound <= 0.50): "
          f"{min(fail) if fail else 'none of the tested levels'}")

    # WHAT THIS n CAN AND CANNOT SEPARATE, printed whichever way the result fell —
    # the pattern analyse.py uses. With every trial a success, the Wilson lower
    # bound is n/(n + 1.96^2), so it is a statement about the SAMPLE SIZE and not
    # about the yaw. No per-level block here is large enough to clear 0.80, and
    # that is a property of the budget rather than a finding about the gripper.
    need = math.ceil(3.8416 * 0.80 / 0.20)
    print(f"\nPOWER. With k = n, the Wilson lower bound is n/(n+3.8416). Clearing "
          f"0.80 needs n >= {need}\nin a single cell; the largest cell here is "
          f"{max(n for _, _, n, _, _ in table)}. The per-level rule is therefore "
          f"UNDERPOWERED,\nand theta_safe is reported above as undetermined rather "
          f"than as a failure of the gripper.")

    # Pooled, which the uniform mechanism licenses and which is stated as a
    # pooled claim rather than smuggled in as a per-level one.
    for name, levels in (("0-30 deg (all levels)", None), ("5-30 deg (yawed only)", 5.0)):
        sel = [r for r in scored
               if levels is None or r["commanded_yaw_deg"] >= levels]
        k = len([r for r in sel if grasp_ok(r)])
        lo, hi = A.wilson(k, len(sel))
        print(f"pooled {name:>22}: {k}/{len(sel)}  "
              f"Wilson 95% [{fmt(lo,3)}, {fmt(hi,3)}]")


def grasp_ok(r) -> bool:
    return bool(
        (r.get("lift_m") or 0) > 0.05
        and r.get("held_through_transport")
        and (r.get("place_err_m") is not None and r["place_err_m"] <= 0.05)
    )


def arm_d(rows):
    section("ARM D — the shipped path, end to end")
    scored = [r for r in rows if r.get("ok")]
    print(f"trials recorded {len(rows)}, ok {len(scored)}")
    if not scored:
        for r in rows:
            print("   ", {k: r.get(k) for k in ("trial", "note", "pick_succeeded",
                                                "on_belt_after_place")})
        return

    dep = [r["yaw_deposited_deg"] for r in scored]
    arr = [r["yaw_at_read_deg"] for r in scored]
    delta = [r["delta_yaw_deg"] for r in scored]
    pres = [r["presented_at_read_mm"] for r in scored]

    section("H5 — what the shipped path delivers")
    print(f"yaw as DEPOSITED on the belt : n={len(dep)} median {fmt(A.median(dep),3)} deg  "
          f"p95 {fmt(pct(dep,0.95),3)}  max {fmt(max(dep),3)} deg")
    print(f"yaw AT THE OUTFEED           : n={len(arr)} median {fmt(A.median(arr),3)} deg  "
          f"p95 {fmt(pct(arr,0.95),3)}  max {fmt(max(arr),3)} deg")
    print(f"presented at the outfeed     : median {fmt(A.median(pres),2)} mm  "
          f"max {fmt(max(pres),2)} mm")
    print(f"ride contribution |delta|    : median {fmt(A.median([abs(d) for d in delta]),4)} deg  "
          f"max {fmt(max(abs(d) for d in delta),4)} deg")

    dep_rate = [abs(r["yaw_rate_deposited_deg_s"]) for r in scored
                if not math.isnan(r.get("yaw_rate_deposited_deg_s", float("nan")))]
    read_rate = [abs(r["yaw_rate_at_read_deg_s"]) for r in scored
                 if not math.isnan(r.get("yaw_rate_at_read_deg_s", float("nan")))]
    if dep_rate:
        k = len([x for x in dep_rate if x > SPIN_DEG_S])
        lo, hi = A.wilson(k, len(dep_rate))
        print(f"\nspin as deposited: median {fmt(A.median(dep_rate),4)} deg/s  "
              f"max {fmt(max(dep_rate),4)}  >{SPIN_DEG_S} deg/s in {k}/{len(dep_rate)} "
              f"Wilson [{fmt(lo,3)}, {fmt(hi,3)}]")
    if read_rate:
        k = len([x for x in read_rate if x > SPIN_DEG_S])
        print(f"spin at the outfeed: median {fmt(A.median(read_rate),4)} deg/s  "
              f"max {fmt(max(read_rate),4)}  >{SPIN_DEG_S} deg/s in {k}/{len(read_rate)}")

    print(f"\nleft the belt before being picked: "
          f"{len([r for r in scored if r.get('left_belt')])}/{len(scored)}")
    print("\nper trial:")
    print(f"{'trial':>5} {'mode':>9} {'deposited':>10} {'at read':>9} {'delta':>8} "
          f"{'presented':>10} {'placed':>7}")
    for r in scored:
        print(f"{r['trial']:5d} {r['mode']:>9} {fmt(r['yaw_deposited_deg'],3):>10} "
              f"{fmt(r['yaw_at_read_deg'],3):>9} {fmt(r['delta_yaw_deg'],3):>8} "
              f"{fmt(r['presented_at_read_mm'],2):>10} "
              f"{str(r.get('place_succeeded')):>7}")
    print("\n`pick_reported_holding` is NOT reported for this arm: the block was run "
          "with a\nharness that read it from the wrong field. See deviation 3. "
          "That the gripper was\nholding is evidenced instead by `Place` succeeding "
          "with require_holding=True, and by\nthe part physically arriving on the belt.")


def main() -> int:
    belt = load("belt")
    control = load("nocarry")
    grasp = load("graspyaw", "graspyaw2")
    endtoend = load("endtoend")
    if belt:
        arm_a(belt, control)
    if endtoend:
        arm_d(endtoend)
    if grasp:
        arm_c(grasp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
