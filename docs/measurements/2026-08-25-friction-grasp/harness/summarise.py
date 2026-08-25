#!/usr/bin/env python3
"""Apply the pre-registered verdicts to a block's trials and print the table."""
import json, math, statistics, sys
from pathlib import Path

LIFTED_M, PLACE_TOL_M, FLING_MPS = 0.05, 0.10, 1.0
SLIP_MM, TWIST_DEG, OUT_OF_JAWS_MM = 5.0, 5.0, 25.0


def verdicts(r):
    v = {}
    v["grasp_acquired"] = bool(r.get("pick_reported_holding"))
    v["lift_achieved"] = (r.get("lift_m") or 0.0) > LIFTED_M
    v["held"] = bool(r.get("held_through_transport"))
    v["flung"] = ((r.get("v_max_mps") or 0.0) > FLING_MPS
                  or (r.get("place_err_m") or 9.9) > 0.5)
    v["placed"] = (r.get("place_err_m") or 9.9) < PLACE_TOL_M
    v["success"] = (v["grasp_acquired"] and v["lift_achieved"] and v["held"]
                    and v["placed"] and not v["flung"])
    return v


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d)


def block(path):
    rows = json.loads(Path(path).read_text())
    rows = [r for r in rows if "trial" in r]
    label = rows[0].get("label", path)
    print(f"\n=== {label}  (n={len(rows)}) ===")
    print(f"{'t':>3} {'grasp':>6} {'lift':>7} {'slip':>7} {'twist':>7} {'drift':>7} "
          f"{'vmax':>6} {'perr':>7} {'q_stall':>8} {'OK':>6}")
    succ = 0
    slips, twists, drifts, lifts, qs = [], [], [], [], []
    for r in rows:
        v = verdicts(r)
        succ += v["success"]
        f = lambda k, d=0.0: (r.get(k) if r.get(k) is not None else d)
        if r.get("slip_max_mm") is not None:
            slips.append(r["slip_max_mm"]); twists.append(r["twist_max_deg"])
            drifts.append(r["pad_distance_drift_mm_max"]); lifts.append(r["lift_m"])
        if r.get("q_at_stall_rad"):
            qs.append(r["q_at_stall_rad"])
        print(f"{r['trial']:>3} {str(v['grasp_acquired']):>6} {f('lift_m'):7.3f} "
              f"{f('slip_max_mm',-1):7.2f} {f('twist_max_deg',-1):7.2f} "
              f"{f('pad_distance_drift_mm_max',-1):7.2f} {f('v_max_mps',-1):6.2f} "
              f"{f('place_err_m',-1):7.3f} {f('q_at_stall_rad',-1):8.4f} "
              f"{str(v['success']):>6}"
              + ("  <-- " + r["note"][:60] if r.get("note") else ""))
    n = len(rows)
    print(f"  success {succ}/{n}   Wilson 95% lower bound on the rate: {wilson(succ, n):.3f}")
    for name, xs, unit in (("slip_max", slips, "mm"), ("twist_max", twists, "deg"),
                           ("pad_dist_drift", drifts, "mm"), ("lift", lifts, "m"),
                           ("q_at_stall", qs, "rad")):
        if xs:
            print(f"  {name:>15}: median {statistics.median(xs):8.3f} {unit:>3}  "
                  f"min {min(xs):8.3f}  max {max(xs):8.3f}")
    over_slip = sum(1 for s in slips if s > SLIP_MM)
    over_twist = sum(1 for s in twists if s > TWIST_DEG)
    print(f"  T2: slip_max > {SLIP_MM} mm in {over_slip}/{len(slips)}; "
          f"twist_max > {TWIST_DEG} deg in {over_twist}/{len(twists)}")
    return dict(label=label, n=n, success=succ, slips=slips, twists=twists)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        block(p)
