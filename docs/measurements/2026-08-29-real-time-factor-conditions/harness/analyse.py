#!/usr/bin/env python3
"""Turn raw/ into the tables the write-up quotes. Runs on the host; no ROS needed.

Every window in the write-up is cut here, from the continuous series each trial recorded,
by the definition `criteria.md` section 2 fixed before the data existed:
`delta(sim_time) / delta(real_time)` between the first and last WorldStatistics sample of
the interval. The smoothed `real_time_factor` field is carried alongside and never used as
the headline.

    python3 harness/analyse.py            # every table
    python3 harness/analyse.py --json     # the same figures, machine-readable
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "raw"
SETTLE_AFTER_LIMIT_CHANGE_S = 60.0


def t_of(sample, key):
    return sample[key + "_sec"] + float(sample.get(key + "_nsec", 0)) / 1e9


def rtf(series, t0=None, t1=None):
    use = [s for s in series
           if (t0 is None or s["wall"] >= t0) and (t1 is None or s["wall"] <= t1)]
    if len(use) < 2:
        return None
    d_sim = t_of(use[-1], "sim") - t_of(use[0], "sim")
    d_real = t_of(use[-1], "real") - t_of(use[0], "real")
    if d_real <= 0:
        return None
    rep = sorted(s["rtf_reported"] for s in use if "rtf_reported" in s)
    return dict(
        rtf_window=d_sim / d_real,
        sim_s=d_sim, real_s=d_real,
        wall_s=use[-1]["wall"] - use[0]["wall"],
        n=len(use),
        reported_median=statistics.median(rep) if rep else None,
        reported_min=rep[0] if rep else None,
        reported_max=rep[-1] if rep else None,
    )


def mark(record, name):
    for m in record.get("marks", []):
        if m["name"] == name:
            return m["wall"]
    return None


def load():
    trials = []
    for path in sorted(RAW.glob("*.json")):
        if path.name.endswith(".series.json") or path.name.endswith(".limits.json"):
            continue
        record = json.loads(path.read_text())
        series_path = RAW / (record["label"] + ".series.json")
        series = json.loads(series_path.read_text()) if series_path.exists() else []
        trials.append((record, series))
    return trials


def spread(values):
    if not values:
        return None
    med = statistics.median(values)
    lo, hi = min(values), max(values)
    return dict(n=len(values), median=med, min=lo, max=hi,
                range_pct_of_median=(hi - lo) / med * 100.0 if med else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    per_trial, by_condition = [], {}
    for record, series in load():
        label = record["label"]
        condition = label.rsplit("_", 1)[0]
        ready_at = mark(record, "ready")
        first = series[0]["wall"] if series else None
        row = dict(
            label=label, condition=condition, mode=record.get("mode"),
            ready=record.get("ready"),
            ready_after_s=(ready_at - mark(record, "launch_start")) if ready_at else None,
            window=record.get("window"),
            bringup=rtf(series, first, ready_at) if (ready_at and first) else None,
            whole_run=rtf(series),
            cores=(record.get("cpu") or {}).get("cores_used"),
            rss_gib=((record.get("cpu") or {}).get("rss_total_b") or 0) / 2**30,
            launch_rc=record.get("launch_returncode"),
            stats_samples=record.get("n_stats_samples"),
            joint_state_rates=record.get("joint_state_rates"),
        )
        limits_path = RAW / (label + ".limits.json")
        if limits_path.exists():
            events = json.loads(limits_path.read_text())
            segments = []
            for i, ev in enumerate(events):
                t0 = ev["wall"] + SETTLE_AFTER_LIMIT_CHANGE_S
                t1 = events[i + 1]["wall"] if i + 1 < len(events) else None
                if t1 is not None and t1 - t0 < 30:
                    continue
                segments.append(dict(cpus=ev["cpus"], rtf=rtf(series, t0, t1)))
            row["cpu_segments"] = segments
        per_trial.append(row)
        if row["window"] and record.get("ready"):
            by_condition.setdefault(condition, []).append(row["window"]["rtf_window"])

    summary = {c: spread(v) for c, v in by_condition.items()}
    bringup_by_condition = {}
    for row in per_trial:
        if row["bringup"]:
            bringup_by_condition.setdefault(row["condition"], []).append(
                row["bringup"]["rtf_window"])
    summary_bringup = {c: spread(v) for c, v in bringup_by_condition.items()}

    if args.json:
        print(json.dumps(dict(per_trial=per_trial, summary=summary,
                              summary_bringup=summary_bringup), indent=2))
        return

    print("## Per trial\n")
    head = ("| label | ready | ready after | window RTF | reported RTF (med) | "
            "bring-up RTF | cores | RSS GiB | rc |")
    print(head)
    print("|---" * 9 + "|")
    for r in per_trial:
        w = r["window"] or {}
        b = r["bringup"] or {}
        print("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["label"], r["ready"],
            f"{r['ready_after_s']:.0f} s" if r["ready_after_s"] else "-",
            f"{w.get('rtf_window'):.3f}" if w.get("rtf_window") else "-",
            f"{w.get('rtf_reported_median'):.3f}"
            if w.get("rtf_reported_median") is not None else "-",
            f"{b.get('rtf_window'):.3f}" if b.get("rtf_window") else "-",
            f"{r['cores']:.2f}" if r["cores"] else "-",
            f"{r['rss_gib']:.2f}", r["launch_rc"]))

    print("\n## By condition — window RTF\n")
    print("| condition | n | median | min | max | range as % of median |")
    print("|---|---|---|---|---|---|")
    for c, s in sorted(summary.items()):
        if not s:
            continue
        print(f"| {c} | {s['n']} | {s['median']:.3f} | {s['min']:.3f} | "
              f"{s['max']:.3f} | {s['range_pct_of_median']:.1f} % |")

    print("\n## By condition — bring-up interval RTF\n")
    print("| condition | n | median | min | max | range as % of median |")
    print("|---|---|---|---|---|---|")
    for c, s in sorted(summary_bringup.items()):
        if not s:
            continue
        print(f"| {c} | {s['n']} | {s['median']:.3f} | {s['min']:.3f} | "
              f"{s['max']:.3f} | {s['range_pct_of_median']:.1f} % |")

    for r in per_trial:
        if r.get("cpu_segments"):
            print(f"\n## CPU allocation segments — {r['label']}\n")
            print("| --cpus | window RTF | reported RTF (med) | sim s | real s | samples |")
            print("|---|---|---|---|---|---|")
            for seg in r["cpu_segments"]:
                s = seg["rtf"]
                if not s:
                    print(f"| {seg['cpus']:.0f} | - | - | - | - | - |")
                    continue
                print(f"| {seg['cpus']:.0f} | {s['rtf_window']:.3f} | "
                      f"{s['reported_median']:.3f} | {s['sim_s']:.1f} | "
                      f"{s['real_s']:.1f} | {s['n']} |")

    print("\n## joint_states rates, by trial and arm\n")
    print("| label | arm | ros2 topic hz | counted Hz | count | RTF x 150 |")
    print("|---|---|---|---|---|---|")
    for r in per_trial:
        rates = r.get("joint_state_rates") or {}
        predicted = (r["window"] or {}).get("rtf_window")
        for arm, v in rates.items():
            counted = v.get("counted") or {}
            print("| {} | {} | {} | {} | {} | {} |".format(
                r["label"], arm,
                f"{v.get('topic_hz_last'):.1f}" if v.get("topic_hz_last") else "-",
                f"{counted.get('hz'):.1f}" if counted.get("hz") else "-",
                counted.get("count", "-"),
                f"{predicted * 150:.1f}" if predicted else "-"))


if __name__ == "__main__":
    main()
