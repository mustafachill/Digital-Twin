#!/usr/bin/env python3
"""Apply criteria.md 7's validity rules to raw/, and produce the tables in ANALYSIS.md.

The rules it applies were committed before the first trial and are applied literally,
including where they refuse a figure the campaign was run to produce.

ADAPTED from `2026-08-31-capacity-and-clock-deficit/harness/analyse.py`. **One rule moved,
and criteria.md 7 registered the move before the first trial.**

V6 is evaluated on the **macOS host's** 1-minute load average, read by `run_condition.sh`
either side of each trial into `raw/<LABEL>.host.json`. The extended campaign evaluated it
on `os.getloadavg()` **inside the container**, which is the Docker Desktop Linux VM's
`/proc/loadavg` and invisible to the macOS-side contention that dominates this machine --
its own Deviation 1, recorded after its data was collected. `trial.py` still records the
container figure, unchanged, and this analyser computes **both** exclusion sets and reports
them side by side. The registered reading is the host one; where they disagree, both are
published.

Everything else -- V1 through V5, the pooled medians, the block-paired ratios -- is the
extended campaign's code, so that the two campaigns' figures are produced by the same
arithmetic and can be read against each other.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

GEOMETRIES = ("VENDOR", "HULL")
THROTTLES = ("THROTTLED", "FREE")
TOPOLOGIES = ("PAIR", "SOLO")

V1_SPREAD = 0.20
V2_OVERLAP = 0.90
V4_MIN_SAMPLES = 100
V4_MAX_GAP_S = 10.0
V6_LOAD_DRIFT = 0.50


def load(raw: Path) -> list[dict]:
    # `.host.json` is this campaign's addition and matches `*.json` too. Excluded here
    # rather than renamed, because the sidecars are already committed and a rename would
    # rewrite collected data. Found after the last trial: the ghost records were all
    # `valid=False` under V3, so no pooled median, ratio or exclusion set moved -- the
    # bug inflated `n_records` from 24 to 48 and duplicated the per-trial listing. Both
    # summaries are compared in ANALYSIS.md's deviations.
    return [
        json.loads(p.read_text())
        for p in sorted(raw.glob("*.json"))
        if p.name != "summary.json" and not p.name.endswith(".host.json")
    ]


def condition_of(label: str) -> tuple[str, str, str, int]:
    topo, geom, thr, block = label.rsplit("_", 3)[0], *label.split("_")[1:]
    parts = label.split("_")
    return parts[0], parts[1], parts[2], int(parts[3])


def host_record(raw: Path, label: str) -> dict:
    """The host-side sidecar for one trial. criteria.md 7, V6."""
    p = raw / f"{label}.host.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def validate(rec: dict, median_load: float | None, host_load: float | None = None,
             median_host_load: float | None = None) -> list[str]:
    """Every rule that this record breaks, by name. Empty means valid."""
    broken = []
    if rec.get("verdict") != "COLLECTED":
        broken.append("V3:" + str(rec.get("discard_reason", "not collected")))
        return broken
    sides = rec.get("sides") or {}
    if set(sides) != set(rec["expected_sides"]):
        broken.append("V3:a side produced no record")
    for name, side in sides.items():
        st = side.get("stats")
        if not st:
            broken.append(f"V4:{name} produced no parsable window")
            continue
        if st["n_samples"] < V4_MIN_SAMPLES:
            broken.append(f"V4:{name} only {st['n_samples']} samples")
        if (st.get("wall_gap_max_s") or 0) > V4_MAX_GAP_S:
            broken.append(f"V4:{name} gap {st['wall_gap_max_s']:.1f} s")
    if rec["topology"] == "pair" and len(sides) == 2:
        (a, b) = list(sides.values())
        lo = max(a["window_started_wall"], b["window_started_wall"])
        hi = min(a["window_ended_wall"], b["window_ended_wall"])
        shorter = min(a["window_ended_wall"] - a["window_started_wall"],
                      b["window_ended_wall"] - b["window_started_wall"])
        overlap = max(0.0, hi - lo) / shorter if shorter > 0 else 0.0
        rec["_overlap"] = overlap
        if overlap < V2_OVERLAP:
            broken.append(f"V2:windows overlap {overlap:.2%}")
    cfg = rec.get("configuration", {})
    parts = rec["label"].split("_")
    want_rtf = "1" if parts[2] == "THROTTLED" else "0"
    want_geom = "vendor_meshes" if parts[1] == "VENDOR" else "convex_hull"
    if str(cfg.get("real_time_factor")) != want_rtf:
        broken.append(f"V5:world declares real_time_factor={cfg.get('real_time_factor')!r}")
    if cfg.get("collision_geometry") != want_geom:
        broken.append(f"V5:description bound {cfg.get('collision_geometry')!r}")
    if str(len(rec.get("expected_sides", []))) != ("2" if parts[0] == "PAIR" else "1"):
        broken.append("V5:topology does not match the label")
    # V6, on the HOST's load average. Two-sided exactly as written: a trial on a machine
    # quieter than the campaign median by more than 50 % is excluded too. Applied as
    # written, not as intended.
    if median_host_load is not None and host_load is not None:
        if abs(host_load - median_host_load) > V6_LOAD_DRIFT * median_host_load:
            broken.append(
                f"V6:pre-trial HOST load {host_load:.2f} against median {median_host_load:.2f}"
            )
    return broken


def v6_container_only(rec: dict, median_load: float | None) -> str | None:
    """The extended campaign's V6, computed for comparison and NOT applied.

    criteria.md 7 registers the host reading as this campaign's V6. This function exists so
    that ANALYSIS.md can report whether the two instruments would have excluded the same
    trials, which is the one thing the extended campaign could not report about its own.
    """
    if median_load is None or not rec.get("load_before"):
        return None
    load1 = rec["load_before"][0]
    if abs(load1 - median_load) > V6_LOAD_DRIFT * median_load:
        return f"V6(container):pre-trial load {load1:.2f} against median {median_load:.2f}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()
    raw = Path(args.raw)
    records = load(raw)

    loads = [r["load_before"][0] for r in records if r.get("load_before")]
    median_load = statistics.median(loads) if loads else None

    hosts = {r["label"]: host_record(raw, r["label"]) for r in records}
    host_loads = [h["host_load1_before"] for h in hosts.values() if h.get("host_load1_before")]
    median_host_load = statistics.median(host_loads) if host_loads else None

    rows = []
    for rec in records:
        parts = rec["label"].split("_")
        h = hosts.get(rec["label"], {})
        broken = validate(rec, median_load, h.get("host_load1_before"), median_host_load)
        container_v6 = v6_container_only(rec, median_load)
        sides = rec.get("sides") or {}
        row = dict(
            label=rec["label"], topology=parts[0], geometry=parts[1],
            throttle=parts[2], block=int(parts[3]),
            broken=broken, valid=not broken,
            load_before=(rec.get("load_before") or [None])[0],
            host_load_before=h.get("host_load1_before"),
            host_load_after=h.get("host_load1_after"),
            host_elapsed_s=(
                h["host_ended_epoch"] - h["host_started_epoch"]
                if h.get("host_ended_epoch") and h.get("host_started_epoch") else None
            ),
            base_commit=h.get("base_commit"),
            worktree_dirty_outside_campaign=h.get("worktree_clean_outside_campaign"),
            v6_container_would_exclude=container_v6,
            ready_after_s=rec.get("ready_after_s"),
            overlap=rec.get("_overlap"),
            sides={n: s.get("stats") for n, s in sides.items() if s.get("stats")},
        )
        rows.append(row)

    def figures(row, key):
        return [st[key] for st in row["sides"].values() if st and st.get(key) is not None]

    for row in rows:
        rtfs = figures(row, "rtf_window")
        row["rtf_min"] = min(rtfs) if rtfs else None
        row["rtf_max"] = max(rtfs) if rtfs else None
        deficits = figures(row, "deficit_total_s")
        row["deficit_max_s"] = max(deficits) if deficits else None
        rates = figures(row, "deficit_rate_s_per_s")
        row["deficit_rate_max"] = max(rates) if rates else None
        reported = figures(row, "rtf_reported_median")
        row["reported_over_window"] = (
            statistics.median([r / w for r, w in zip(reported, rtfs)]) if reported and rtfs else None
        )

    # Pooled per condition, with V1 applied literally.
    pooled = {}
    for topo in TOPOLOGIES:
        for geom in GEOMETRIES:
            for thr in THROTTLES:
                key = f"{topo}_{geom}_{thr}"
                sel = [r for r in rows if r["valid"] and r["label"].startswith(key + "_")]
                vals = sorted(v for r in sel for v in figures(r, "rtf_window"))
                if not vals:
                    pooled[key] = dict(n=0, refused=None)
                    continue
                med = statistics.median(vals)
                spread = (max(vals) - min(vals)) / med if med else None
                pooled[key] = dict(
                    n_trials=len(sel), n_side_windows=len(vals),
                    rtf_median=med, rtf_min=min(vals), rtf_max=max(vals),
                    spread_frac=spread,
                    refused_by_V1=bool(spread is not None and spread > V1_SPREAD),
                    capacity_min_median=(
                        statistics.median([r["rtf_min"] for r in sel if r["rtf_min"]])
                    ),
                    deficit_total_s_median=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_total_s")])
                    ),
                    deficit_rate_median=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_rate_s_per_s")])
                    ),
                    top1pct_median=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_top1pct_share")])
                        if [v for r in sel for v in figures(r, "deficit_top1pct_share")] else None
                    ),
                    top5pct_median=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_top5pct_share")])
                        if [v for r in sel for v in figures(r, "deficit_top5pct_share")] else None
                    ),
                    interval_median_s=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_interval_median_s")])
                        if [v for r in sel for v in figures(r, "deficit_interval_median_s")] else None
                    ),
                    interval_p99_s=(
                        statistics.median([v for r in sel for v in figures(r, "deficit_interval_p99_s")])
                        if [v for r in sel for v in figures(r, "deficit_interval_p99_s")] else None
                    ),
                    interval_max_s=(
                        max([v for r in sel for v in figures(r, "deficit_interval_max_s")])
                        if [v for r in sel for v in figures(r, "deficit_interval_max_s")] else None
                    ),
                    negative_intervals=sum(
                        int(v) for r in sel for v in figures(r, "n_intervals_negative_deficit")
                    ),
                    total_intervals=sum(int(v) for r in sel for v in figures(r, "n_intervals")),
                )

    # Block-paired ratios (criteria.md 6). Computed within a block, never across.
    blocks = sorted({r["block"] for r in rows})
    block_rows = []
    for b in blocks:
        def med_of(topo, geom, thr):
            sel = [r for r in rows if r["valid"] and r["block"] == b
                   and r["topology"] == topo and r["geometry"] == geom and r["throttle"] == thr]
            vals = [v for r in sel for v in figures(r, "rtf_window")]
            return statistics.median(vals) if vals else None
        e = dict(block=b)
        for topo in TOPOLOGIES:
            for thr in THROTTLES:
                v, h = med_of(topo, "VENDOR", thr), med_of(topo, "HULL", thr)
                if v and h:
                    e[f"G_{topo}_{thr}"] = h / v
            for geom in GEOMETRIES:
                t, f = med_of(topo, geom, "THROTTLED"), med_of(topo, geom, "FREE")
                if t and f:
                    e[f"throttle_cost_{topo}_{geom}"] = t / f
        for geom in GEOMETRIES:
            for thr in THROTTLES:
                s, p = med_of("SOLO", geom, thr), med_of("PAIR", geom, thr)
                if s and p:
                    e[f"pairing_penalty_{geom}_{thr}"] = s / p
                    e[f"aggregate_throughput_{geom}_{thr}"] = 2 * p / s
        block_rows.append(e)

    def block_med(key):
        vals = [e[key] for e in block_rows if key in e]
        return dict(median=statistics.median(vals), values=vals) if vals else None

    ratios = {}
    for e in block_rows:
        for k in e:
            if k != "block" and k not in ratios:
                ratios[k] = block_med(k)

    out = dict(
        n_records=len(records),
        median_pre_trial_load1=median_load,
        median_pre_trial_host_load1=median_host_load,
        v6_host_excluded=[r["label"] for r in rows
                          if any(b.startswith("V6:") for b in r["broken"])],
        v6_container_would_have_excluded=[r["label"] for r in rows
                                          if r.get("v6_container_would_exclude")],
        trials=[{k: v for k, v in r.items() if k != "sides"} | {
            "rtf_by_side": {n: (st or {}).get("rtf_window") for n, st in r["sides"].items()}
        } for r in rows],
        pooled=pooled,
        block_ratios=ratios,
        blocks=block_rows,
    )
    raw.joinpath("summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in (
        "n_records", "median_pre_trial_load1", "median_pre_trial_host_load1",
        "v6_host_excluded", "v6_container_would_have_excluded", "pooled")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
