#!/usr/bin/env python3
"""Q4 -- what a virtual side costs when it has no physics in it.

In SHADOW the virtual counterpart only has to DISPLAY mirrored joint state. That
needs robot_state_publisher and no simulator at all. This builds exactly that and
nothing more, on its own ROS domain, fed from a running plant cell:

    one robot_state_publisher per arm, on the virtual domain, holding the same
    generated description the plant's arms are spawned from
    one relay carrying each arm's joint_states across the domain boundary

and reports the CPU and resident memory the whole virtual side consumes over the
same 120 s window a full second cell is measured over. The comparison is a ratio,
so it survives the move to another machine; the absolute does not.

The relay is in-process with two rclpy contexts, which is the cheapest honest way
to cross a domain boundary. A heavier transport would measure the transport.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cell_run import proc_snapshot

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

ARMS = ("arm_1", "arm_2", "arm_3")
DESCRIPTION_DIR = "/workspace/workspace/src/cite_generated/description"
QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10
)


def urdf_for(arm):
    xacro = os.path.join(DESCRIPTION_DIR, "cell_a_" + arm + ".urdf.xacro")
    done = subprocess.run(["xacro", xacro], capture_output=True, text=True, timeout=180)
    if done.returncode != 0:
        raise SystemExit("xacro failed for " + arm + ": " + done.stderr[-500:])
    return done.stdout


def start_state_publishers(out):
    procs = []
    for arm in ARMS:
        urdf = urdf_for(arm)
        log = out.joinpath("rsp_" + arm + ".log").open("w")
        proc = subprocess.Popen(
            ["ros2", "run", "robot_state_publisher", "robot_state_publisher",
             "--ros-args", "-r", "__ns:=/cite/cell_a/" + arm,
             "-p", "robot_description:=" + urdf],
            stdout=log, stderr=subprocess.STDOUT, preexec_fn=os.setsid,
        )
        procs.append(proc)
    return procs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plant-domain", type=int, required=True)
    ap.add_argument("--sample-seconds", type=float, default=120.0)
    ap.add_argument("--gate", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    virtual_domain = int(os.environ["ROS_DOMAIN_ID"])

    procs = start_state_publishers(out)

    ctx_plant = rclpy.context.Context()
    rclpy.init(context=ctx_plant, domain_id=args.plant_domain)
    ctx_virtual = rclpy.context.Context()
    rclpy.init(context=ctx_virtual, domain_id=virtual_domain)

    relay_in = Node("shadow_relay_in", context=ctx_plant)
    relay_out = Node("shadow_relay_out", context=ctx_virtual)
    counts = dict((a, 0) for a in ARMS)
    publishers = dict()
    for arm in ARMS:
        topic = "/cite/cell_a/" + arm + "/joint_states"
        publishers[arm] = relay_out.create_publisher(JointState, topic, QOS)

    def make_cb(arm):
        def cb(msg):
            counts[arm] += 1
            publishers[arm].publish(msg)
        return cb

    for arm in ARMS:
        topic = "/cite/cell_a/" + arm + "/joint_states"
        relay_in.create_subscription(JointState, topic, make_cb(arm), QOS)

    exec_plant = SingleThreadedExecutor(context=ctx_plant)
    exec_plant.add_node(relay_in)
    stop = threading.Event()

    def spin():
        while not stop.is_set():
            exec_plant.spin_once(timeout_sec=0.05)

    threading.Thread(target=spin, daemon=True).start()

    # The relay is up when it is receiving from the plant, which is an event.
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if all(v > 0 for v in counts.values()):
            break
        time.sleep(0.5)
    receiving = dict(counts)

    Path(args.gate).write_text(str(time.time()))

    before = proc_snapshot()
    n0 = dict(counts)
    t0 = time.time()
    time.sleep(args.sample_seconds)
    t1 = time.time()
    n1 = dict(counts)
    after = proc_snapshot()

    cpu = dict()
    for pid, aft in after.items():
        bef = before.get(pid)
        if bef is None or bef["comm"] != aft["comm"]:
            continue
        delta = aft["cpu_s"] - bef["cpu_s"]
        if delta > 0.01:
            cpu[pid] = dict(comm=aft["comm"], cpu_s=delta, cmd=aft["cmd"])
    total_cpu = sum(v["cpu_s"] for v in cpu.values())

    record = dict(
        label=args.label,
        virtual_domain=virtual_domain,
        plant_domain=args.plant_domain,
        receiving_at_start=receiving,
        messages_relayed=dict((a, n1[a] - n0[a]) for a in ARMS),
        wall_s=t1 - t0,
        cpu_by_pid=cpu,
        cpu_total_s=total_cpu,
        cpu_cores_used=total_cpu / max(t1 - t0, 1e-9),
        rss_total_b=sum(v["rss_b"] for v in after.values()),
    )
    out.joinpath(args.label + ".json").write_text(json.dumps(record, indent=2))
    print(json.dumps(dict(
        cpu_cores_used=record["cpu_cores_used"],
        rss_total_b=record["rss_total_b"],
        messages_relayed=record["messages_relayed"],
    )))

    stop.set()
    for proc in procs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            proc.wait(timeout=30)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
