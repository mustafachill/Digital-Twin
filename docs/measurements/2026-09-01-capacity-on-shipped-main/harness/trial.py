#!/usr/bin/env python3
"""Run one trial: bring a cell or a pair up, sample every side concurrently, tear it down.

Runs INSIDE the container. One invocation produces one JSON record in the output
directory, and every figure this campaign reports comes from one of those records.

**The instrument is `Delta sim_time / Delta real_time` over the window**, taken from each
side's `/world/<name>/stats`. Gazebo's own `real_time_factor` field is recorded and is
NEVER the figure: ADR-0049 decision 5 forbids it, on a prior campaign's measurement that
it over-reports by up to 4.15x under starvation. Recording it anyway is how this campaign
answers Q7.

**Every Gazebo-transport process is started through `cite_bringup.gz`**, carrying that
side's `GZ_PARTITION` (ADR-0042), with the side addressed BY NAME and never by position
(ADR-0044, ADR-0047 -- and `gz.py`'s own docstring, which records what a positional
lookup cost). That module is the only door this harness uses.

Readiness is a token on the supervisor's pipe, not an interval: `CITE_SIDE_READY` per
side. There is no sleep anywhere in the bring-up path (P4). The settle after readiness
and the sampling window are stated durations of a measurement, which is a different thing
from sequencing a start-up on a guess.
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

sys.path.insert(0, "/workspace/workspace/src/cite_bringup")

from cite_bringup import gz  # noqa: E402
from cite_bringup.plan import PLANT_SIDE  # noqa: E402
from cite_bringup.readiness import announced_side  # noqa: E402

ZONE = "cell_a"
WORLD_STATS_TOPIC = "/world/cell_a/stats"

#: The supervisor's own ceiling. Not widened here and not this harness's to widen
#: (`cite_bringup/pair.py`: "It must never be widened to absorb a slow host").
READY_CEILING_S = 900.0
STOP_GRACE_S = 120.0

STAT_SEC = re.compile(r"^\s*sec:\s*(-?\d+)")
STAT_NSEC = re.compile(r"^\s*nsec:\s*(-?\d+)")
STAT_RTF = re.compile(r"^real_time_factor:\s*([0-9.eE+-]+)")
STAT_ITER = re.compile(r"^iterations:\s*(\d+)")


def load_average() -> list[float]:
    try:
        return list(os.getloadavg())
    except OSError:
        return []


def installed_configuration() -> dict:
    """V5: read the configuration under test off the INSTALLED artifacts.

    Not off `model/` and not off `workspace/src/`. The question this answers is what the
    running cell loaded, and this repository has twice published figures produced by a
    build that was not the build being described.
    """
    out: dict = {}
    try:
        prefix = subprocess.run(
            ["ros2", "pkg", "prefix", "cite_generated"],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        share = Path(prefix) / "share" / "cite_generated"
        world = (share / "worlds" / f"{ZONE}.sdf").read_text()
        m = re.search(r"<real_time_factor>([^<]+)</real_time_factor>", world)
        out["real_time_factor"] = m.group(1).strip() if m else None
        m = re.search(r"<max_step_size>([^<]+)</max_step_size>", world)
        out["max_step_size"] = m.group(1).strip() if m else None
        arm = (share / "description" / f"{ZONE}_arm_1.urdf.xacro").read_text()
        m = re.search(r'collision_mesh_path="([^"]*)"', arm)
        root = m.group(1) if m else None
        out["collision_mesh_path"] = root
        out["collision_geometry"] = "convex_hull" if (root and "convex_hull" in root) else "vendor_meshes"
        out["world_sha_head"] = world[:0]  # placeholder, replaced below
    except Exception as exc:  # noqa: BLE001 - provenance, never control flow
        out["error"] = f"{type(exc).__name__}: {exc}"
    out.pop("world_sha_head", None)
    return out


def sides_of(topology: str) -> list[str]:
    plan = gz.plan_for(ZONE)
    names = [s.name for s in plan.sides]
    if topology == "solo":
        # By name. `plan.sides[0]` would be the positional lookup ADR-0044 refuses,
        # and gz.py's docstring records what it cost the last time it was used.
        return [PLANT_SIDE]
    return names


def sample_side(side: str, seconds: float, result: dict) -> None:
    """Stream WorldStatistics for one side, in that side's partition, for `seconds`."""
    env = gz.process_environment(gz.plan_for(ZONE), side=side)
    proc = subprocess.Popen(
        ["gz", "topic", "-e", "-t", WORLD_STATS_TOPIC],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1, env=env,
    )
    samples: list[dict] = []
    block: dict = {}
    field = None
    started = time.time()
    deadline = time.monotonic() + seconds
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
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
                block = {}
                if time.monotonic() > deadline:
                    break
    except Exception as exc:  # noqa: BLE001
        result["stream_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["side"] = side
    result["gz_partition"] = env.get("GZ_PARTITION")
    result["window_started_wall"] = started
    result["window_ended_wall"] = time.time()
    result["samples"] = samples
    result["stats"] = analyse(samples)


def analyse(samples: list[dict]) -> dict | None:
    """The whole instrument, in one place: rate, deficit, and the deficit's shape."""
    usable = [s for s in samples if "sim_sec" in s and "real_sec" in s]
    if len(usable) < 2:
        return None

    def t(s, k):
        return s[k + "_sec"] + float(s.get(k + "_nsec", 0)) / 1e9

    d_sim = t(usable[-1], "sim") - t(usable[0], "sim")
    d_real = t(usable[-1], "real") - t(usable[0], "real")
    if d_real <= 0:
        return None

    # Per-interval deficit. One interval is ~200 ms of wall time and therefore
    # ~200 physics steps: a SINGLE step's overrun is below this resolution, and
    # criteria.md 4 registers that limit rather than implying step-level detail.
    increments = []
    for a, b in zip(usable, usable[1:]):
        di_sim = t(b, "sim") - t(a, "sim")
        di_real = t(b, "real") - t(a, "real")
        if di_real <= 0:
            continue
        increments.append(dict(d_sim=di_sim, d_real=di_real, deficit=di_real - di_sim))

    deficits = sorted(x["deficit"] for x in increments)
    total_deficit = d_real - d_sim
    positive_total = sum(x for x in deficits if x > 0)

    def q(p):
        if not deficits:
            return None
        idx = min(len(deficits) - 1, max(0, int(round(p * (len(deficits) - 1)))))
        return deficits[idx]

    def top_share(frac):
        if not deficits or positive_total <= 0:
            return None
        n = max(1, int(round(frac * len(deficits))))
        return sum(deficits[-n:]) / positive_total

    reported = sorted(s["rtf_reported"] for s in usable if "rtf_reported" in s)
    gaps = [usable[i + 1]["wall"] - usable[i]["wall"] for i in range(len(usable) - 1)]
    iters = [s["iterations"] for s in usable if "iterations" in s]

    return dict(
        n_samples=len(usable),
        window_sim_s=d_sim,
        window_real_s=d_real,
        rtf_window=d_sim / d_real,
        deficit_total_s=total_deficit,
        deficit_rate_s_per_s=total_deficit / d_real,
        n_intervals=len(increments),
        deficit_interval_median_s=q(0.5),
        deficit_interval_p95_s=q(0.95),
        deficit_interval_p99_s=q(0.99),
        deficit_interval_max_s=deficits[-1] if deficits else None,
        deficit_interval_min_s=deficits[0] if deficits else None,
        deficit_positive_total_s=positive_total,
        deficit_top1pct_share=top_share(0.01),
        deficit_top5pct_share=top_share(0.05),
        deficit_top10pct_share=top_share(0.10),
        n_intervals_negative_deficit=sum(1 for x in deficits if x < 0),
        rtf_reported_median=reported[len(reported) // 2] if reported else None,
        rtf_reported_min=reported[0] if reported else None,
        rtf_reported_max=reported[-1] if reported else None,
        iterations_first=iters[0] if iters else None,
        iterations_last=iters[-1] if iters else None,
        wall_gap_max_s=max(gaps) if gaps else None,
        deficit_intervals=[round(x, 9) for x in deficits],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--topology", choices=("pair", "solo"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--settle", type=float, default=30.0)
    ap.add_argument("--window", type=float, default=120.0)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    console = out_dir.joinpath(args.label + ".console").open("w")

    expected = sides_of(args.topology)
    record: dict = dict(
        label=args.label,
        topology=args.topology,
        expected_sides=expected,
        settle_s=args.settle,
        window_s=args.window,
        configuration=installed_configuration(),
        load_before=load_average(),
        started_wall=time.time(),
    )

    argv = ["/workspace/scripts/sim", "--pair"] if args.topology == "pair" else \
           ["/workspace/scripts/sim", "--headless"]
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, start_new_session=True,
    )

    ready: set[str] = set()
    ready_at: dict[str, float] = {}
    exited_early = threading.Event()

    def pump():
        assert proc.stdout is not None
        for raw in proc.stdout:
            console.write(raw)
            console.flush()
            name = announced_side(raw.rstrip("\n"))
            if name is not None:
                ready.add(name)
                ready_at.setdefault(name, time.time())
        exited_early.set()

    threading.Thread(target=pump, daemon=True).start()

    deadline = time.monotonic() + READY_CEILING_S
    while not set(expected).issubset(ready):
        if exited_early.is_set():
            record["verdict"] = "DISCARDED"
            record["discard_reason"] = "a side exited before every side announced readiness (V3)"
            break
        if time.monotonic() > deadline:
            record["verdict"] = "DISCARDED"
            record["discard_reason"] = f"ready ceiling {READY_CEILING_S:g} s expired (V3)"
            break
        time.sleep(0.2)

    record["ready_sides"] = sorted(ready)
    record["ready_at"] = ready_at

    if set(expected).issubset(ready):
        record["ready_after_s"] = max(ready_at.values()) - record["started_wall"]
        time.sleep(args.settle)
        results: dict[str, dict] = {name: {} for name in expected}
        threads = [
            threading.Thread(target=sample_side, args=(name, args.window, results[name]))
            for name in expected
        ]
        # Started together, joined together. Two sequential samples are not
        # "both sides in the same window" (criteria.md V2).
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=args.window + 120.0)
        record["sides"] = results
        record["exited_during_window"] = exited_early.is_set()
        record["verdict"] = "DISCARDED" if exited_early.is_set() else "COLLECTED"
        if exited_early.is_set():
            record["discard_reason"] = "a side exited during the sampling window (V3)"

    record["load_after"] = load_average()

    # Teardown. SIGINT to the supervisor or the launch, which owns its own stop.
    if proc.poll() is None:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=STOP_GRACE_S)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    record["sim_exit_status"] = proc.poll()
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    record["ended_wall"] = time.time()

    out_dir.joinpath(args.label + ".json").write_text(json.dumps(record, indent=1))
    console.close()
    summary = {
        name: (record.get("sides", {}).get(name, {}).get("stats") or {}).get("rtf_window")
        for name in expected
    }
    print(f"{args.label}: {record.get('verdict')} {summary}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
