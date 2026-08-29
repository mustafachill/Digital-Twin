#!/usr/bin/env python3
"""Q3.2 -- the generated world with no arms in it, and the same world paused.

Two ablations against the same instrument the full-cell runs use, so the three
numbers are commensurable:

    world      the generated cell_a world running alone: ground plane, three belt
               plugins, four break-beam plugins, no arms, no controllers, no ROS
    paused     the same server with physics stopped through Gazebo's own world
               control service -- everything still loaded, nothing stepping

The point is not the absolute figures. It is the share: how much of a full cell's
step is the arms, and whether the part of the server that is not physics is a
rounding error or not.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cell_run import proc_snapshot, sample_world_stats, window_rtf

WORLD = "/workspace/workspace/src/cite_generated/worlds/cell_a.sdf"
PLUGIN_PATH = "/opt/ros/jazzy/lib"
CONTROL_SERVICE = "/world/cell_a/control"
CONTROL_TYPE = "gz.msgs.WorldControl"
REPLY_TYPE = "gz.msgs.Boolean"


def measure(label, seconds):
    before = proc_snapshot()
    t0 = time.time()
    stats = sample_world_stats(seconds)
    t1 = time.time()
    after = proc_snapshot()
    cpu = 0.0
    for pid, aft in after.items():
        bef = before.get(pid)
        if bef is not None and bef["comm"] == aft["comm"]:
            cpu += max(0.0, aft["cpu_s"] - bef["cpu_s"])
    return dict(
        label=label,
        stats=window_rtf(stats["samples"]),
        wall_s=t1 - t0,
        cpu_cores=cpu / max(t1 - t0, 1e-9),
        rss_total_b=sum(v["rss_b"] for v in after.values()),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-seconds", type=float, default=120.0)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    existing = env.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
    env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = (
        PLUGIN_PATH + (os.pathsep + existing if existing else "")
    )

    log = out.joinpath("world_only.log").open("w")
    proc = subprocess.Popen(
        ["gz", "sim", "-s", "-r", "-v", "2", WORLD],
        stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid,
    )

    # Readiness is the stats topic appearing, not a sleep.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        listing = subprocess.run(
            ["gz", "topic", "--list"], capture_output=True, text=True, env=env
        )
        if "/world/cell_a/stats" in (listing.stdout or ""):
            break
        time.sleep(1.0)

    results = [measure("world_only", args.sample_seconds)]

    subprocess.run(
        ["gz", "service", "-s", CONTROL_SERVICE, "--reqtype", CONTROL_TYPE,
         "--reptype", REPLY_TYPE, "--timeout", "3000", "--req", "pause: true"],
        capture_output=True, text=True, env=env,
    )
    results.append(measure("world_paused", args.sample_seconds))

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
        proc.wait(timeout=60)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass

    out.joinpath("world_only.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
