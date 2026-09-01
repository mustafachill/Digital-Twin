#!/usr/bin/env python3
"""Post-hoc diagnostic for criteria.md 7.4 (rule S) and for the M3 asymmetry.

WRITTEN AFTER THE DATA, and labelled as such. It sets no threshold and changes no
verdict: `analyse.py` decides those against `criteria.md`. What this answers is the
question rule S obliges the write-up to answer if the mechanism does not show —
**were the hull's wedges ever within reach of the part at all?** — plus the one the
data raised that nothing had asked: the two pads do not contact over the same length.

Reads `raw/*_patch.csv.gz`, which is every finger contact point in the hold window.

    .venv/bin/python docs/measurements/2026-09-01-hull-grasp/harness/mechanism.py
"""

from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import statistics
from pathlib import Path

import numpy as np

RAW = Path(__file__).resolve().parent.parent / "raw"

#: ADR-0028's audit, in the same frame this harness measures z in. Cited, not
#: re-derived: the wedges are the hull's ramps across the vendor's 2.0 mm relief
#: steps, at these z, and the numbers beside them are (vendor aperture, hull
#: aperture) in mm at the shipped 45 mm command.
WEDGES = {132.0: (48.99, 46.28), 134.0: (48.99, 45.40), 173.0: (48.99, 47.66)}
PAD_APERTURE_MM = 44.99


def per_trial(path: Path) -> dict | None:
    # `raw/` publishes the patch files gzipped: uncompressed they are 25 MB per
    # condition and the campaign directory would be four times the largest one
    # already published here. Nothing else changed.
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return None
    by_msg = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        by_msg[r["sim_t"]][r["pad"]].append((float(r["z_mm"]), float(r["y_mm"]),
                                             abs(float(r["n_approach"]))))
    out: dict = {"file": path.name}
    for pad in ("left", "right"):
        lens, ys, zmins, zmaxs = [], [], [], []
        for msg in by_msg.values():
            pts = msg.get(pad)
            if not pts:
                continue
            zs = [p[0] for p in pts]
            lens.append(max(zs) - min(zs))
            zmins.append(min(zs))
            zmaxs.append(max(zs))
            ys.extend(p[1] for p in pts)
        if not lens:
            continue
        out[f"{pad}_len_median"] = statistics.median(lens)
        out[f"{pad}_z_min_median"] = statistics.median(zmins)
        out[f"{pad}_z_max_median"] = statistics.median(zmaxs)
        out[f"{pad}_y_median"] = statistics.median(ys)
    if "left_y_median" in out and "right_y_median" in out:
        out["face_separation_mm"] = out["right_y_median"] - out["left_y_median"]
    if "left_len_median" in out and "right_len_median" in out:
        out["len_asymmetry_mm"] = abs(out["left_len_median"] - out["right_len_median"])
        out["len_min_mm"] = min(out["left_len_median"], out["right_len_median"])
        out["len_max_mm"] = max(out["left_len_median"], out["right_len_median"])
    na = [abs(float(r["n_approach"])) for r in rows]
    out["n_approach_max"] = max(na)
    out["n_approach_p99"] = float(np.percentile(na, 99))
    return out


def main() -> int:
    groups = collections.defaultdict(list)
    for f in sorted(glob.glob(str(RAW / "*_patch.csv.gz"))):
        p = Path(f)
        cond = "HULL" if p.name.startswith("HULL") else "VENDOR"
        t = per_trial(p)
        if t:
            groups[cond].append(t)

    print("=" * 74)
    print("Where the contact patch sits, per condition (median over trials)")
    keys = ["left_len_median", "right_len_median", "len_min_mm", "len_max_mm",
            "len_asymmetry_mm", "left_z_min_median", "left_z_max_median",
            "right_z_min_median", "right_z_max_median", "face_separation_mm",
            "n_approach_max", "n_approach_p99"]
    print(f"{'quantity':<26}{'VENDOR':>14}{'HULL':>14}{'delta':>12}")
    summary = {}
    for k in keys:
        v = [t[k] for t in groups["VENDOR"] if k in t]
        h = [t[k] for t in groups["HULL"] if k in t]
        if not v or not h:
            continue
        mv, mh = statistics.median(v), statistics.median(h)
        summary[k] = {"vendor": mv, "hull": mh, "delta": mh - mv,
                      "n_vendor": len(v), "n_hull": len(h)}
        print(f"{k:<26}{mv:>14.4f}{mh:>14.4f}{mh - mv:>12.4f}")

    print("\n" + "=" * 74)
    print("Rule S diagnostic — were the wedges within reach of the part?")
    for cond in ("VENDOR", "HULL"):
        sep = statistics.median([t["face_separation_mm"] for t in groups[cond]
                                 if "face_separation_mm" in t])
        # The pads stall wider than the 45 mm command; every relief feature moves
        # out with them, because it is the same rigid link.
        stall_excess = sep - PAD_APERTURE_MM
        print(f"\n  {cond}: pad-face separation at the hold = {sep:.3f} mm, "
              f"which is {stall_excess:+.3f} mm wider than the commanded pad aperture")
        for z, (vend, hull) in sorted(WEDGES.items()):
            aperture = (vend if cond == "VENDOR" else hull) + stall_excess
            gap = aperture - 50.0
            verdict = "TOUCHES the part" if gap <= 0 else f"clear by {gap:.3f} mm"
            print(f"    z = {z:5.1f} mm: surface aperture {aperture:7.3f} mm "
                  f"vs the 50 mm part -> {verdict}")
        zmin = statistics.median([t["left_z_min_median"] for t in groups[cond]])
        zmax = statistics.median([t["left_z_max_median"] for t in groups[cond]])
        print(f"    contact reaches z = {zmin:.2f} .. {zmax:.2f} mm "
              f"(left pad, median over {len(groups[cond])} trials)")

    (RAW / "mechanism.json").write_text(json.dumps(
        {"summary": summary,
         "per_trial": {k: v for k, v in groups.items()}}, indent=2, default=str))
    print(f"\nwrote {RAW / 'mechanism.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
