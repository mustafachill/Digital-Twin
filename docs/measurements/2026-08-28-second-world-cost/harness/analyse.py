#!/usr/bin/env python3
"""Reduce raw/ to the figures criteria.md pre-registered, and nothing else.

Every band and rule this prints is quoted from criteria.md rather than decided
here, so that the analysis cannot quietly choose a threshold the data suits. Where
a rule fires -- V2's variance refusal in particular -- it fires before the number
it would qualify is interpreted.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def load(raw, prefix):
    records = []
    for path in sorted(raw.glob(prefix + "*.json")):
        if path.name.endswith(".stats.json"):
            continue
        try:
            rec = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("ready") and rec.get("stats"):
            records.append(rec)
    return records


def rtfs(records):
    return [r["stats"]["rtf_window"] for r in records]


def med(values):
    return statistics.median(values) if values else None


def spread(values):
    if not values:
        return None
    return (max(values) - min(values)) / statistics.median(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()
    raw = Path(args.raw)

    solo = load(raw, "SOLO_")
    pair_a = load(raw, "PAIR_") 
    pair_a = [r for r in pair_a if r["label"].endswith("_A")]
    pair_b = [r for r in load(raw, "PAIR_") if r["label"].endswith("_B")]
    hull = load(raw, "HULL_")

    out = dict()
    out["n"] = dict(solo=len(solo), pair_a=len(pair_a), pair_b=len(pair_b), hull=len(hull))
    out["rtf"] = dict(
        solo=rtfs(solo), pair_a=rtfs(pair_a), pair_b=rtfs(pair_b), hull=rtfs(hull)
    )
    out["median_rtf"] = dict(
        (k, med(v)) for k, v in out["rtf"].items()
    )
    out["solo_spread_fraction"] = spread(rtfs(solo))
    out["V2_fires"] = (out["solo_spread_fraction"] or 0) > 0.25

    if med(rtfs(solo)) and med(rtfs(pair_a)):
        out["R_per_world"] = med(rtfs(solo)) / med(rtfs(pair_a))
        both = rtfs(pair_a) + rtfs(pair_b)
        out["R_aggregate_per_world"] = med(rtfs(solo)) / med(both)
        out["aggregate_throughput_ratio"] = med(both) * 2 / med(rtfs(solo))
    if med(rtfs(solo)) and med(rtfs(hull)):
        out["G_hull_gain"] = med(rtfs(hull)) / med(rtfs(solo))

    out["cpu_cores"] = dict(
        solo=[r.get("cpu_cores_used") for r in solo],
        pair_a=[r.get("cpu_cores_used") for r in pair_a],
        pair_b=[r.get("cpu_cores_used") for r in pair_b],
        hull=[r.get("cpu_cores_used") for r in hull],
    )
    out["joint_state_hz"] = dict(
        solo=[r.get("joint_state_hz") for r in solo],
        hull=[r.get("joint_state_hz") for r in hull],
    )
    out["rss_total_b"] = dict(
        solo=[r.get("rss_total_b") for r in solo],
        pair_a=[r.get("rss_total_b") for r in pair_a],
        hull=[r.get("rss_total_b") for r in hull],
    )
    print(json.dumps(out, indent=2))
    raw.joinpath("summary.json").write_text(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
