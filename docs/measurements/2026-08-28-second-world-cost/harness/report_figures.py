#!/usr/bin/env python3
"""Every figure the write-up quotes, printed from raw/ in one place.

Written so that each number in ANALYSIS.md can be traced to one line here and
one file in raw/, rather than to a shell pipeline that no longer exists.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def rec(raw, label):
    path = raw.joinpath(label + ".json")
    if not path.exists():
        return None
    return json.loads(path.read_text())


def cpu_split(record):
    groups = dict()
    for v in record.get("cpu_by_pid", dict()).values():
        cmd = v["cmd"]
        if "gz sim" in cmd:
            key = "gz sim (physics + gz_ros2_control)"
        elif "move_group" in cmd:
            key = "move_group"
        elif "parameter_bridge" in cmd:
            key = "parameter_bridge"
        elif "skill_server" in cmd:
            key = "skill_server"
        elif "robot_state_publisher" in cmd:
            key = "robot_state_publisher"
        else:
            key = "other"
        groups[key] = groups.get(key, 0.0) + v["cpu_s"]
    total = sum(groups.values())
    return groups, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()
    raw = Path(args.raw)

    labels_solo = ["SOLO_1", "SOLO_2", "SOLO_3", "SOLO_4", "SOLO_5"]
    labels_hull = ["HULL_1", "HULL_2", "HULL_3", "HULL_4", "HULL_5"]

    print("=== per-run real-time factor, from Gazebo WorldStatistics ===")
    for group in (labels_solo, labels_hull):
        for label in group:
            r = rec(raw, label)
            if r and r.get("stats"):
                hz = r.get("joint_state_hz") or dict()
                hzs = [v for v in hz.values() if v]
                print(
                    label,
                    "rtf", round(r["stats"]["rtf_window"], 4),
                    "cores", round(r["cpu_cores_used"], 2),
                    "rss_GiB", round(r["rss_total_b"] / 2 ** 30, 2),
                    "joint_states_hz_median",
                    round(statistics.median(hzs), 1) if hzs else None,
                )
    print()
    print("=== per-step cost, milliseconds of real time per simulated second ===")
    world = json.loads(raw.joinpath("world_only.json").read_text())
    w_rtf = world[0]["stats"]["rtf_window"]
    solo_rtf = statistics.median(
        [rec(raw, x)["stats"]["rtf_window"] for x in labels_solo if rec(raw, x)]
    )
    hull_rtf = statistics.median(
        [rec(raw, x)["stats"]["rtf_window"] for x in labels_hull if rec(raw, x)]
    )
    def inv(v):
        return 1.0 / v

    print("world only  rtf", round(w_rtf, 3), "real_s_per_sim_s", round(inv(w_rtf), 4))
    print("full vendor rtf", round(solo_rtf, 3), "real_s_per_sim_s", round(inv(solo_rtf), 4))
    print("full hull   rtf", round(hull_rtf, 3), "real_s_per_sim_s", round(inv(hull_rtf), 4))
    arms_vendor = inv(solo_rtf) - inv(w_rtf)
    arms_hull = inv(hull_rtf) - inv(w_rtf)
    print("arms share of vendor step", round(arms_vendor / inv(solo_rtf), 4))
    print("collision share of arm cost", round((arms_vendor - arms_hull) / arms_vendor, 4))
    print("collision share of whole step", round((arms_vendor - arms_hull) / inv(solo_rtf), 4))
    print("world paused cores", world[1]["cpu_cores"])
    print("world only cores", round(world[0]["cpu_cores"], 3))
    print()
    print("=== CPU split within one full cell ===")
    for label in ("SOLO_4", "HULL_4"):
        r = rec(raw, label)
        if not r:
            continue
        groups, total = cpu_split(r)
        print(label, "total_cpu_s", round(total, 1))
        for k in sorted(groups, key=lambda x: -groups[x]):
            print("   ", k, round(groups[k], 1), "s", round(100 * groups[k] / total, 1), "%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
