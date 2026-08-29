#!/usr/bin/env python3
"""Bring one simulated cell up headless, sample it, and tear it down.

Runs INSIDE the container. One invocation produces one JSON record in the output
directory, and every figure this campaign reports about a running cell comes from
one of those records.

Real-time factor is computed from Gazebo's own WorldStatistics -- the (sim_time,
real_time) pair at the two ends of the sampling window -- rather than from the
real_time_factor field, which is a smoothed instantaneous estimate. Both are
recorded; the window figure is the one the write-up uses, because it is the
definition rather than a filter's output.

CPU and memory come from /proc inside the container's own PID namespace, so a
second cell running in a second container cannot leak into this one's accounting.
That isolation is the reason each cell gets its own container rather than its own
shell in a shared one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ZONE = "cell_a"
ARMS = ("arm_1", "arm_2", "arm_3")
WORLD_STATS_TOPIC = "/world/cell_a/stats"

# The rate L0 configures for every arm, generated into the controller configs.
# Quoted here as the value the sample is compared against, not as a source of truth.
EXPECTED_CONTROL_HZ = 150.0

READY_CEILING_S = 900.0
POLL_PERIOD_S = 5.0
SIM_COMMAND = ["/workspace/scripts/sim", "--headless"]


def sh(cmd, timeout=30.0):
    """Run a command and return (returncode, combined output). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        text = exc.stdout.decode("utf-8", "replace") if exc.stdout else "TIMEOUT"
        return 124, text
    except Exception as exc:
        return 125, "ERROR " + str(exc)


def active_controllers(arm):
    """The set of controllers this arm's manager reports as active."""
    manager = "/cite/" + ZONE + "/" + arm + "/controller_manager"
    rc, out = sh(["ros2", "control", "list_controllers", "-c", manager], timeout=20.0)
    if rc != 0:
        return set()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "active":
            names.add(parts[0])
    return names


def proc_snapshot():
    """Per-pid CPU seconds and resident bytes, read from this PID namespace."""
    ticks = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    out = dict()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = entry.joinpath("stat").read_text()
            close = stat.rindex(")")
            comm = stat[stat.index("(") + 1:close]
            fields = stat[close + 2:].split()
            cpu_s = float(int(fields[11]) + int(fields[12])) / ticks
            rss_b = int(entry.joinpath("statm").read_text().split()[1]) * page
            raw = entry.joinpath("cmdline").read_bytes().replace(b"\0", b" ")
            cmdline = raw.decode("utf-8", "replace").strip()
        except (OSError, ValueError, IndexError):
            continue
        out[entry.name] = dict(
            comm=comm, cpu_s=cpu_s, rss_b=rss_b, cmd=cmdline[:240]
        )
    return out


# `gz topic -e` prints text-format protobuf. Parsed with a small state machine
# rather than by importing the Python bindings, so that reproducing this campaign
# does not depend on those bindings being present in whatever image it is run in.
STAT_SEC = re.compile(r"^\s*sec:\s*(-?\d+)")
STAT_NSEC = re.compile(r"^\s*nsec:\s*(-?\d+)")
STAT_RTF = re.compile(r"^real_time_factor:\s*([0-9.eE+-]+)")
STAT_ITER = re.compile(r"^iterations:\s*(\d+)")


def sample_world_stats(seconds):
    """Stream WorldStatistics for `seconds` and return the parsed series."""
    proc = subprocess.Popen(
        ["gz", "topic", "-e", "-t", WORLD_STATS_TOPIC],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    samples = []
    block = dict()
    field = None
    deadline = time.monotonic() + seconds
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.startswith("sim_time"):
                field = "sim"
                continue
            if line.startswith("real_time") and not line.startswith("real_time_factor"):
                field = "real"
                continue
            m = STAT_SEC.match(line)
            if m and field:
                block[field + "_sec"] = int(m.group(1))
                continue
            m = STAT_NSEC.match(line)
            if m and field:
                block[field + "_nsec"] = int(m.group(1))
                field = None
                continue
            m = STAT_RTF.match(line)
            if m:
                block["rtf_reported"] = float(m.group(1))
                continue
            m = STAT_ITER.match(line)
            if m:
                block["iterations"] = int(m.group(1))
                continue
            if line.strip() == "" and block:
                block["wall"] = time.time()
                samples.append(block)
                block = dict()
                if time.monotonic() > deadline:
                    break
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return dict(samples=samples)


def window_rtf(samples):
    """Delta(sim) / Delta(real) across the window, plus the reported RTF spread."""
    usable = [s for s in samples if "sim_sec" in s and "real_sec" in s]
    if len(usable) < 2:
        return None
    first = usable[0]
    last = usable[-1]

    def t(s, k):
        return s[k + "_sec"] + float(s.get(k + "_nsec", 0)) / 1e9

    d_sim = t(last, "sim") - t(first, "sim")
    d_real = t(last, "real") - t(first, "real")
    if d_real <= 0:
        return None
    reported = sorted(s["rtf_reported"] for s in usable if "rtf_reported" in s)
    gaps = [usable[i + 1]["wall"] - usable[i]["wall"] for i in range(len(usable) - 1)]
    return dict(
        window_sim_s=d_sim,
        window_real_s=d_real,
        rtf_window=d_sim / d_real,
        n_samples=len(usable),
        rtf_reported_median=reported[len(reported) // 2] if reported else None,
        rtf_reported_min=reported[0] if reported else None,
        rtf_reported_max=reported[-1] if reported else None,
        wall_gap_max_s=max(gaps) if gaps else None,
    )


def joint_state_hz(arm, seconds=25.0):
    """Measured publication rate, against the EXPECTED_CONTROL_HZ the model sets."""
    topic = "/cite/" + ZONE + "/" + arm + "/joint_states"
    rc, out = sh(["ros2", "topic", "hz", topic, "--window", "200"], timeout=seconds)
    del rc
    rates = [float(m) for m in re.findall(r"average rate:\s*([0-9.]+)", out)]
    return rates[-1] if rates else None


def graph_snapshot():
    """Everything Q1 needs to say whether one cell can see the other."""
    _, nodes = sh(["ros2", "node", "list"], timeout=60.0)
    _, topics = sh(["ros2", "topic", "list"], timeout=60.0)
    _, clock = sh(["ros2", "topic", "info", "/clock", "--verbose"], timeout=60.0)
    _, gz_topics = sh(["gz", "topic", "--list"], timeout=60.0)
    return dict(
        ros_nodes=sorted(n for n in nodes.splitlines() if n.startswith("/")),
        ros_topics=sorted(t for t in topics.splitlines() if t.startswith("/")),
        clock_info=clock,
        gz_topics=sorted(t for t in gz_topics.splitlines() if t.startswith("/")),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-seconds", type=float, default=120.0)
    ap.add_argument("--ready-file", default=None,
                    help="written once this cell is fully active")
    ap.add_argument("--start-gate", default=None,
                    help="wait for this file before sampling, so a PAIR samples "
                         "the same window from both cells")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    record = dict(
        label=args.label,
        started_wall=time.time(),
        domain_id=os.environ.get("ROS_DOMAIN_ID"),
        gz_partition=os.environ.get("GZ_PARTITION"),
        sample_seconds=args.sample_seconds,
    )

    log = out.joinpath(args.label + ".launch.log").open("w")
    launch = subprocess.Popen(
        SIM_COMMAND, stdout=log, stderr=subprocess.STDOUT, preexec_fn=os.setsid
    )

    # Readiness is an observed state, not an elapsed time: every arm's controller
    # manager reporting active controllers. P4 applies to a measurement harness
    # too -- a fixed sleep here would sample a different part of the bring-up on
    # a loaded host than on an idle one, which is exactly the comparison at stake.
    deadline = time.monotonic() + READY_CEILING_S
    ready = False
    per_arm = dict()
    while time.monotonic() < deadline:
        per_arm = dict((arm, len(active_controllers(arm))) for arm in ARMS)
        if all(v >= 3 for v in per_arm.values()):
            ready = True
            break
        if launch.poll() is not None:
            break
        time.sleep(POLL_PERIOD_S)
    record["ready"] = ready
    record["active_controllers_per_arm"] = per_arm
    record["ready_after_s"] = time.time() - record["started_wall"]

    if ready:
        if args.ready_file:
            Path(args.ready_file).write_text(str(time.time()))
        if args.start_gate:
            gate_deadline = time.monotonic() + 900
            while time.monotonic() < gate_deadline:
                if Path(args.start_gate).exists():
                    break
                time.sleep(1.0)

        record["graph"] = graph_snapshot()
        before = proc_snapshot()
        t0 = time.time()
        stats = sample_world_stats(args.sample_seconds)
        t1 = time.time()
        after = proc_snapshot()

        record["stats"] = window_rtf(stats["samples"])
        record["wall_elapsed_s"] = t1 - t0
        record["joint_state_hz"] = dict((a, joint_state_hz(a)) for a in ARMS)
        record["expected_control_hz"] = EXPECTED_CONTROL_HZ

        cpu = dict()
        for pid, aft in after.items():
            bef = before.get(pid)
            if bef is None or bef["comm"] != aft["comm"]:
                continue
            delta = aft["cpu_s"] - bef["cpu_s"]
            if delta > 0.05:
                cpu[pid] = dict(comm=aft["comm"], cpu_s=delta, cmd=aft["cmd"])
        record["cpu_by_pid"] = cpu
        record["cpu_total_s"] = sum(v["cpu_s"] for v in cpu.values())
        record["cpu_cores_used"] = record["cpu_total_s"] / max(t1 - t0, 1e-9)
        record["rss_total_b"] = sum(v["rss_b"] for v in after.values())
        by_comm = dict()
        for v in after.values():
            by_comm[v["comm"]] = by_comm.get(v["comm"], 0) + v["rss_b"]
        record["rss_by_comm"] = by_comm
        out.joinpath(args.label + ".stats.json").write_text(json.dumps(stats))

    try:
        os.killpg(os.getpgid(launch.pid), signal.SIGINT)
        launch.wait(timeout=180)
    except Exception:
        try:
            os.killpg(os.getpgid(launch.pid), signal.SIGKILL)
        except Exception:
            pass
    record["launch_returncode"] = launch.returncode
    record["finished_wall"] = time.time()
    out.joinpath(args.label + ".json").write_text(json.dumps(record, indent=2))
    keys = ("label", "ready", "stats", "cpu_cores_used")
    print(json.dumps(dict((k, record.get(k)) for k in keys)))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
