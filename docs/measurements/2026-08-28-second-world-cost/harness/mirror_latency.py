#!/usr/bin/env python3
"""What it costs to carry joint state across a ROS domain boundary.

Q5. L5's failure-mode table names "mirroring lag treated as divergence" -- the
model blamed for a network problem -- and DivergenceMetrics has no latency field
today. This measures the floor: what the transport costs on one host when nothing
is wrong.

Three nodes in one process, so that publish and receive instants are read from one
wall clock and a one-way latency is meaningful without any clock synchronisation:

    source   (domain A)  publishes JointState at the cell's configured rate
    relay    (domain A -> domain B)  forwards it, one hop across the boundary
    mirror   (domain B)  receives it and records now - stamp

A same-domain subscriber on domain A records the same quantity over one hop, so the
DOMAIN-CROSSING cost can be separated from the cost of publishing at all. The
ratio of the two is what transfers; the absolute is this laptop's.

Stamps are WALL CLOCK, deliberately, not sim time. The quantity is transport delay;
a sim-time stamp would measure the simulator instead.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

TOPIC = "/cite/cell_a/arm_1/joint_states"
MIRROR_TOPIC = TOPIC

# joint_state_broadcaster publishes on the default reliable profile; the rig
# matches it rather than choosing a friendlier one, because an easier QoS would
# measure a transport this project does not use.
QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10
)

JOINT_NAMES = [
    "arm_1_joint1", "arm_1_joint2", "arm_1_joint3", "arm_1_joint4", "arm_1_joint5",
    "arm_1_drive_joint",
]


def cpu_seconds():
    ticks = os.sysconf("SC_CLK_TCK")
    with open("/proc/self/stat") as fh:
        stat = fh.read()
    fields = stat[stat.rindex(")") + 2:].split()
    return float(int(fields[11]) + int(fields[12])) / ticks


def stamp_now(msg):
    now = time.time()
    msg.header.stamp.sec = int(now)
    msg.header.stamp.nanosec = int((now - int(now)) * 1e9)


def stamp_age(msg):
    sent = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
    return time.time() - sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-a", type=int, required=True)
    ap.add_argument("--domain-b", type=int, required=True)
    ap.add_argument("--rate-hz", type=float, default=150.0)
    ap.add_argument("--samples", type=int, default=20000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ctx_a = rclpy.context.Context()
    rclpy.init(context=ctx_a, domain_id=args.domain_a)
    ctx_b = rclpy.context.Context()
    rclpy.init(context=ctx_b, domain_id=args.domain_b)

    source = Node("mirror_source", context=ctx_a)
    relay_in = Node("mirror_relay_in", context=ctx_a)
    local = Node("mirror_local", context=ctx_a)
    relay_out = Node("mirror_relay_out", context=ctx_b)
    mirror = Node("mirror_sink", context=ctx_b)

    pub_a = source.create_publisher(JointState, TOPIC, QOS)
    pub_b = relay_out.create_publisher(JointState, MIRROR_TOPIC, QOS)

    crossed = []
    same_domain = []

    def on_relay(msg):
        pub_b.publish(msg)

    def on_local(msg):
        same_domain.append(stamp_age(msg))

    def on_mirror(msg):
        crossed.append(stamp_age(msg))

    relay_in.create_subscription(JointState, TOPIC, on_relay, QOS)
    local.create_subscription(JointState, TOPIC, on_local, QOS)
    mirror.create_subscription(JointState, MIRROR_TOPIC, on_mirror, QOS)

    exec_a = SingleThreadedExecutor(context=ctx_a)
    exec_a.add_node(relay_in)
    exec_a.add_node(local)
    exec_b = SingleThreadedExecutor(context=ctx_b)
    exec_b.add_node(mirror)

    stop = threading.Event()
    threading.Thread(target=lambda: spin(exec_a, stop), daemon=True).start()
    threading.Thread(target=lambda: spin(exec_b, stop), daemon=True).start()

    # Discovery is an event, not a duration: wait for both hops to have a matched
    # subscriber before the first sample. Publishing before a match is publishing
    # into nothing -- the defect CLAUDE.md section 10 records as having cost this
    # project a belt setpoint that was never once delivered.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if pub_a.get_subscription_count() >= 2 and pub_b.get_subscription_count() >= 1:
            break
        time.sleep(0.05)
    matched = dict(
        pub_a_subscribers=pub_a.get_subscription_count(),
        pub_b_subscribers=pub_b.get_subscription_count(),
    )

    msg = JointState()
    msg.name = JOINT_NAMES
    msg.position = [0.0] * len(JOINT_NAMES)
    msg.velocity = [0.0] * len(JOINT_NAMES)
    msg.effort = [0.0] * len(JOINT_NAMES)

    period = 1.0 / args.rate_hz
    cpu0 = cpu_seconds()
    t0 = time.time()
    next_at = time.monotonic()
    for _ in range(args.samples):
        next_at += period
        stamp_now(msg)
        pub_a.publish(msg)
        sleep_for = next_at - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)
    time.sleep(1.0)
    t1 = time.time()
    cpu1 = cpu_seconds()
    stop.set()

    result = dict(
        domain_a=args.domain_a,
        domain_b=args.domain_b,
        rate_hz=args.rate_hz,
        published=args.samples,
        matched_at_start=matched,
        wall_s=t1 - t0,
        rig_cpu_s=cpu1 - cpu0,
        rig_cpu_cores=(cpu1 - cpu0) / max(t1 - t0, 1e-9),
        crossed=summarise(crossed),
        same_domain=summarise(same_domain),
    )
    if result["crossed"] and result["same_domain"]:
        result["crossing_overhead_ms"] = (
            result["crossed"]["p50_ms"] - result["same_domain"]["p50_ms"]
        )
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps(dict(
        crossed=result["crossed"], same_domain=result["same_domain"],
        rig_cpu_cores=result["rig_cpu_cores"],
    )))

    rclpy.shutdown(context=ctx_a)
    rclpy.shutdown(context=ctx_b)
    return 0


def spin(executor, stop):
    while not stop.is_set():
        executor.spin_once(timeout_sec=0.05)


def summarise(values):
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)

    def pct(p):
        return ordered[min(n - 1, int(p * n))] * 1000.0

    return dict(
        n=n,
        p50_ms=pct(0.50),
        p95_ms=pct(0.95),
        p99_ms=pct(0.99),
        max_ms=ordered[-1] * 1000.0,
        mean_ms=statistics.fmean(ordered) * 1000.0,
    )


if __name__ == "__main__":
    sys.exit(main())
