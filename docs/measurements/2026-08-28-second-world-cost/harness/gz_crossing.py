#!/usr/bin/env python3
"""Q1.4 -- does anything actually keep two Gazebo transports apart?

ROS_DOMAIN_ID is a DDS concept. `gz sim`, the belt plugin and the break-beam
plugin speak Gazebo transport, which has its own discovery and its own
partitioning. This asks, in one container -- one hostname, one user, one network
namespace -- what happens when two servers run the same generated world:

    shared      two servers, no GZ_PARTITION set: are both publishing the same
                world's topics into one namespace?
    partitioned the same two servers with a distinct GZ_PARTITION each

The evidence is publisher counts on the world's own topics, read with
`gz topic --info`. Two publishers of one world's clock in one namespace is the
Gazebo-transport form of the defect this project already knows by name.

Nothing here launches ROS. The question is deliberately below the bridge: if
Gazebo transport crosses, it crosses whatever the ROS side is doing.
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

WORLD = "/workspace/workspace/src/cite_generated/worlds/cell_a.sdf"
PLUGIN_PATH = "/opt/ros/jazzy/lib"
PROBES = (
    "/world/cell_a/stats",
    "/world/cell_a/clock",
    "/cite/cell_a/conveyor_1/command",
    "/cite/cell_a/beam_pick/detection",
)


def start(partition, log_path):
    env = dict(os.environ)
    existing = env.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
    env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = (
        PLUGIN_PATH + (os.pathsep + existing if existing else "")
    )
    if partition is None:
        env.pop("GZ_PARTITION", None)
    else:
        env["GZ_PARTITION"] = partition
    log = open(log_path, "w")
    proc = subprocess.Popen(
        ["gz", "sim", "-s", "-r", "-v", "2", WORLD],
        stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid,
    )
    return proc, env


def probe(env):
    result = dict()
    listing = subprocess.run(
        ["gz", "topic", "--list"], capture_output=True, text=True, env=env, timeout=30
    )
    result["topics"] = sorted(
        t for t in (listing.stdout or "").splitlines() if t.startswith("/")
    )
    for topic in PROBES:
        info = subprocess.run(
            ["gz", "topic", "--info", "-t", topic],
            capture_output=True, text=True, env=env, timeout=30,
        )
        text = info.stdout or ""
        result[topic] = dict(
            publisher_lines=[ln.strip() for ln in text.splitlines() if "gz.msgs" in ln],
            raw=text.strip()[:4000],
        )
    return result


def wait_for(env, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        listing = subprocess.run(
            ["gz", "topic", "--list"], capture_output=True, text=True, env=env
        )
        if "/world/cell_a/stats" in (listing.stdout or ""):
            return True
        time.sleep(1.0)
    return False


def stop(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
        proc.wait(timeout=45)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def arm(name, partition_1, partition_2, out):
    p1, env1 = start(partition_1, str(out.joinpath(name + "_1.log")))
    ready1 = wait_for(env1)
    p2, env2 = start(partition_2, str(out.joinpath(name + "_2.log")))
    ready2 = wait_for(env2)
    time.sleep(5.0)
    observed = dict(
        arm=name,
        partition_1=partition_1,
        partition_2=partition_2,
        first_ready=ready1,
        second_ready=ready2,
        seen_from_first=probe(env1),
        seen_from_second=probe(env2),
    )
    stop(p2)
    stop(p1)
    return observed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    results = [
        arm("shared_partition", None, None, out),
        arm("distinct_partition", "cite_plant", "cite_virtual", out),
    ]
    out.joinpath("gz_crossing.json").write_text(json.dumps(results, indent=2))

    for r in results:
        for side in ("seen_from_first", "seen_from_second"):
            stats = r[side]["/world/cell_a/stats"]["publisher_lines"]
            print(r["arm"], side, "publishers of /world/cell_a/stats:", len(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
