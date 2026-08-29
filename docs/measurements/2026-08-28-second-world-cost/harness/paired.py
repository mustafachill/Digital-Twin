#!/usr/bin/env python3
"""Deviation 1's arithmetic: the same ratios, computed within a block.

criteria.md registered R and G as ratios of MEDIANS across all repeats, and
registered validity rule V2 to refuse them if the SOLO repeats' own range exceeds
25 % of their median. V2 fired. This computes the same two ratios block by block
instead -- SOLO_n against PAIR_n and HULL_n, each measured within minutes of the
other -- so that a drift in the host's state between blocks cancels rather than
landing on one condition.

It is NOT a replacement for the pre-registered figure and does not overturn V2.
It is reported beside it, labelled as the deviation it is.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def read(raw, label):
    path = raw.joinpath(label + ".json")
    if not path.exists():
        return None
    rec = json.loads(path.read_text())
    if not rec.get("ready") or not rec.get("stats"):
        return None
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--blocks", type=int, default=5)
    args = ap.parse_args()
    raw = Path(args.raw)

    rows = []
    for i in range(1, args.blocks + 1):
        solo = read(raw, "SOLO_" + str(i))
        pair_a = read(raw, "PAIR_" + str(i) + "_A")
        pair_b = read(raw, "PAIR_" + str(i) + "_B")
        hull = read(raw, "HULL_" + str(i))
        if solo is None:
            continue
        s = solo["stats"]["rtf_window"]
        row = dict(block=i, solo=s)
        if pair_a and pair_b:
            a = pair_a["stats"]["rtf_window"]
            b = pair_b["stats"]["rtf_window"]
            row["pair_a"] = a
            row["pair_b"] = b
            row["R_block"] = s / a
            row["R_block_mean_pair"] = s / ((a + b) / 2.0)
            row["aggregate_throughput"] = (a + b) / s
        if hull:
            h = hull["stats"]["rtf_window"]
            row["hull"] = h
            row["G_block"] = h / s
        rows.append(row)

    def med(key):
        vals = [r[key] for r in rows if key in r]
        return statistics.median(vals) if vals else None

    def rng(key):
        vals = [r[key] for r in rows if key in r]
        return [min(vals), max(vals)] if vals else None

    out = dict(
        blocks=rows,
        R_block_median=med("R_block"),
        R_block_range=rng("R_block"),
        R_block_mean_pair_median=med("R_block_mean_pair"),
        aggregate_throughput_median=med("aggregate_throughput"),
        aggregate_throughput_range=rng("aggregate_throughput"),
        G_block_median=med("G_block"),
        G_block_range=rng("G_block"),
    )
    raw.joinpath("paired.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
