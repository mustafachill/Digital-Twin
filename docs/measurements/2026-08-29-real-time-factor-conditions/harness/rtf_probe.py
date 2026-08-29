#!/usr/bin/env python3
"""Sample one simulated cell's real-time factor continuously, from launch to teardown.

Runs INSIDE the container. One invocation produces one JSON record in the output
directory, and every figure this campaign reports comes from one of those records.

The difference from the second-world campaign's `cell_run.py`, which this borrows its
statistics parser's shape from: sampling starts at launch rather than after readiness, and
the whole series is kept. That is what lets the bring-up interval and a CPU-limited
interval be cut out of a run that was going to happen anyway, instead of costing a trial
each. `criteria.md` section 2 fixes the window and the warm-up; this script records enough
that any other window can be cut later without re-running.

Real-time factor is `delta(sim_time) / delta(real_time)` across a window, both fields from
Gazebo's own WorldStatistics. The `real_time_factor` field is a smoothed instantaneous
estimate and is recorded beside it, never as the headline -- whether the two disagree is
one of this campaign's questions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ZONE = "cell_a"
ARMS = ("arm_1", "arm_2", "arm_3")
WORLD_STATS_TOPIC = "/world/" + ZONE + "/stats"

# The rate L0 configures for every arm, generated into the controller configs. Quoted as
# the value samples are compared against, never as a source of truth.
EXPECTED_CONTROL_HZ = 150.0

READY_CEILING_S = 900.0
READY_POLL_S = 5.0
HERE = Path(__file__).resolve().parent


def sh(cmd, timeout=30.0):
    """Run a command and return (returncode, combined output). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout.decode("utf-8", "replace") if exc.stdout else "TIMEOUT")
    except Exception as exc:  # noqa: BLE001 - a probe must not die on its own instrument
        return 125, "ERROR " + str(exc)


def active_controllers(arm):
    """The set of controllers this arm's manager reports as active."""
    manager = "/cite/" + ZONE + "/" + arm + "/controller_manager"
    rc, out = sh(["ros2", "control", "list_controllers", "-c", manager], timeout=20.0)
    if rc != 0:
        return set()
    return {p[0] for p in (line.split() for line in out.splitlines())
            if len(p) >= 3 and p[2] == "active"}


# ---------------------------------------------------------------------------
# WorldStatistics streaming
#
# `gz topic -e` prints text-format protobuf. Parsed with a small state machine rather
# than by importing the Python bindings, so reproducing this does not depend on those
# bindings being present in whatever image it runs in. A message boundary is a blank
# line OR the reappearance of `sim_time` in a block that already has one, because a
# truncated block at a restart must not swallow the next message.
# ---------------------------------------------------------------------------
RE_SEC = re.compile(r"^\s*sec:\s*(-?\d+)")
RE_NSEC = re.compile(r"^\s*nsec:\s*(-?\d+)")
RE_RTF = re.compile(r"^real_time_factor:\s*([0-9.eE+-]+)")
RE_ITER = re.compile(r"^iterations:\s*(\d+)")


class StatsStream(threading.Thread):
    """Stream /world/<zone>/stats for the life of the run, restarting if it drops."""

    def __init__(self):
        super().__init__(daemon=True)
        self.samples = []
        self.restarts = 0
        self._stop = threading.Event()
        self._proc = None

    def run(self):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self._proc = subprocess.Popen(
                    ["gz", "topic", "-e", "-t", WORLD_STATS_TOPIC],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=1,
                )
            except Exception:  # noqa: BLE001
                time.sleep(2.0)
                continue
            self._consume(self._proc)
            if self._stop.is_set():
                return
            # The topic does not exist until gz sim advertises it; a fast exit here is
            # the normal state during the first seconds of a run, not an error.
            self.restarts += 1
            if time.monotonic() - started < 2.0:
                time.sleep(2.0)

    def _consume(self, proc):
        block, field = {}, None
        for line in proc.stdout:
            if self._stop.is_set():
                break
            line = line.rstrip("\n")
            if line.startswith("sim_time"):
                if "sim_sec" in block:
                    self._emit(block)
                    block = {}
                field = "sim"
                continue
            if line.startswith("real_time") and not line.startswith("real_time_factor"):
                field = "real"
                continue
            m = RE_SEC.match(line)
            if m and field:
                block[field + "_sec"] = int(m.group(1))
                continue
            m = RE_NSEC.match(line)
            if m and field:
                block[field + "_nsec"] = int(m.group(1))
                field = None
                continue
            m = RE_RTF.match(line)
            if m:
                block["rtf_reported"] = float(m.group(1))
                continue
            m = RE_ITER.match(line)
            if m:
                block["iterations"] = int(m.group(1))
                continue
            if line.strip() == "" and block:
                self._emit(block)
                block, field = {}, None

    def _emit(self, block):
        if "sim_sec" in block and "real_sec" in block:
            block["wall"] = time.time()
            self.samples.append(block)

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def t_of(sample, key):
    return sample[key + "_sec"] + float(sample.get(key + "_nsec", 0)) / 1e9


def window_rtf(samples, t0=None, t1=None):
    """delta(sim)/delta(real) across [t0, t1] of wall time, plus the reported spread."""
    use = [s for s in samples
           if (t0 is None or s["wall"] >= t0) and (t1 is None or s["wall"] <= t1)]
    if len(use) < 2:
        return None
    d_sim = t_of(use[-1], "sim") - t_of(use[0], "sim")
    d_real = t_of(use[-1], "real") - t_of(use[0], "real")
    if d_real <= 0:
        return None
    rep = sorted(s["rtf_reported"] for s in use if "rtf_reported" in s)
    gaps = [use[i + 1]["wall"] - use[i]["wall"] for i in range(len(use) - 1)]
    return dict(
        rtf_window=d_sim / d_real,
        window_sim_s=d_sim,
        window_real_s=d_real,
        wall_span_s=use[-1]["wall"] - use[0]["wall"],
        n_samples=len(use),
        rtf_reported_median=rep[len(rep) // 2] if rep else None,
        rtf_reported_min=rep[0] if rep else None,
        rtf_reported_max=rep[-1] if rep else None,
        wall_gap_max_s=max(gaps) if gaps else None,
    )


def proc_snapshot():
    """Per-pid CPU seconds and resident bytes, from this container's PID namespace."""
    ticks = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    out = {}
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
            cmd = entry.joinpath("cmdline").read_bytes().replace(b"\0", b" ")
        except (OSError, ValueError, IndexError):
            continue
        out[entry.name] = dict(comm=comm, cpu_s=cpu_s, rss_b=rss_b,
                               cmd=cmd.decode("utf-8", "replace").strip()[:240])
    return out


def joint_state_rates(arm, seconds):
    """Two independent readings of the same rate, per criteria.md section 2.

    `ros2 topic hz` is what the recorded 21 Hz figure was most plausibly taken with.
    The counted rate is a keep-last-1000 subscriber counting arrivals over wall time.
    Publishing both is the point: if they disagree, the instrument is the finding.
    """
    topic = "/cite/" + ZONE + "/" + arm + "/joint_states"
    out = {}
    rc, text = sh(["ros2", "topic", "hz", topic, "--window", "200"], timeout=seconds + 10)
    del rc
    rates = [float(m) for m in re.findall(r"average rate:\s*([0-9.]+)", text)]
    out["topic_hz_last"] = rates[-1] if rates else None
    out["topic_hz_all"] = rates
    rc, text = sh([sys.executable, str(HERE / "count_hz.py"), topic, str(seconds)],
                  timeout=seconds + 40)
    try:
        out["counted"] = json.loads(text.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out["counted"] = dict(error=text[-400:], rc=rc)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("sim", "scenario"), default="sim")
    ap.add_argument("--scenario", default="pick_and_place")
    ap.add_argument("--warmup-s", type=float, default=30.0)
    ap.add_argument("--window-s", type=float, default=120.0)
    ap.add_argument("--hz-seconds", type=float, default=20.0)
    ap.add_argument("--max-s", type=float, default=3600.0,
                    help="hard ceiling on a scenario run before it is torn down")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "sim":
        command = ["/workspace/scripts/sim", "--headless"]
    else:
        command = ["/workspace/scripts/scenario", args.scenario, "--teardown-advisory"]

    record = dict(label=args.label, mode=args.mode, command=command,
                  warmup_s=args.warmup_s, window_s=args.window_s,
                  expected_control_hz=EXPECTED_CONTROL_HZ,
                  started_wall=time.time(), marks=[])

    def mark(name):
        record["marks"].append(dict(name=name, wall=time.time()))

    stream = StatsStream()
    stream.start()

    log = out.joinpath(args.label + ".launch.log").open("w")
    launch = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                              preexec_fn=os.setsid, cwd="/workspace")
    mark("launch_start")

    # Readiness is an observed state, not an elapsed time (P4). A fixed sleep here
    # would sample a different part of bring-up on a loaded host than on an idle one,
    # which is exactly one of the comparisons at stake.
    deadline = time.monotonic() + READY_CEILING_S
    ready, per_arm = False, {}
    while time.monotonic() < deadline:
        per_arm = {a: len(active_controllers(a)) for a in ARMS}
        if all(v >= 3 for v in per_arm.values()):
            ready = True
            break
        if launch.poll() is not None:
            break
        time.sleep(READY_POLL_S)
    mark("ready" if ready else "ready_failed")
    record["ready"] = ready
    record["active_controllers_per_arm"] = per_arm

    if ready and args.mode == "sim":
        time.sleep(args.warmup_s)
        mark("window_open")
        before = proc_snapshot()
        t0 = time.time()
        record["joint_state_rates"] = {
            a: joint_state_rates(a, args.hz_seconds) for a in ARMS
        }
        remaining = args.window_s - (time.time() - t0)
        if remaining > 0:
            time.sleep(remaining)
        t1 = time.time()
        mark("window_close")
        after = proc_snapshot()
        record["window"] = window_rtf(stream.samples, t0, t1)
        record["cpu"] = cpu_delta(before, after, t1 - t0)
    elif ready and args.mode == "scenario":
        time.sleep(args.warmup_s)
        mark("window_open")
        before = proc_snapshot()
        t0 = time.time()
        record["joint_state_rates"] = {
            "arm_1": joint_state_rates("arm_1", args.hz_seconds)
        }
        launch.wait(timeout=max(args.max_s - (time.time() - t0), 60))
        t1 = time.time()
        mark("window_close")
        after = proc_snapshot()
        record["window"] = window_rtf(stream.samples, t0, t1)
        record["cpu"] = cpu_delta(before, after, t1 - t0)

    if launch.poll() is None:
        try:
            os.killpg(os.getpgid(launch.pid), signal.SIGINT)
            launch.wait(timeout=240)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(os.getpgid(launch.pid), signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass
    mark("torn_down")
    record["launch_returncode"] = launch.returncode
    stream.stop()
    record["stats_restarts"] = stream.restarts
    record["n_stats_samples"] = len(stream.samples)
    record["finished_wall"] = time.time()

    out.joinpath(args.label + ".series.json").write_text(json.dumps(stream.samples))
    out.joinpath(args.label + ".json").write_text(json.dumps(record, indent=2))
    print(json.dumps({k: record.get(k) for k in
                      ("label", "ready", "window", "launch_returncode")}))
    return 0 if ready else 1


def cpu_delta(before, after, elapsed):
    used = {}
    for pid, aft in after.items():
        bef = before.get(pid)
        if bef is None or bef["comm"] != aft["comm"]:
            continue
        d = aft["cpu_s"] - bef["cpu_s"]
        if d > 0.05:
            used[pid] = dict(comm=aft["comm"], cpu_s=d, cmd=aft["cmd"])
    total = sum(v["cpu_s"] for v in used.values())
    by_comm = {}
    for v in after.values():
        by_comm[v["comm"]] = by_comm.get(v["comm"], 0) + v["rss_b"]
    return dict(by_pid=used, total_s=total,
                cores_used=total / max(elapsed, 1e-9),
                rss_total_b=sum(v["rss_b"] for v in after.values()),
                rss_by_comm=by_comm)


if __name__ == "__main__":
    sys.exit(main())
