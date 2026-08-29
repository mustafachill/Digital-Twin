#!/usr/bin/env python3
"""Count arrivals of a topic over wall time. The second of criteria.md section 2's two rates.

`ros2 topic hz` reports what its own subscriber received, which on a saturated host is a
lower bound on what was published. This counts the same thing with a deliberately deep
queue (keep-last 1000) so that the two readings differ by queue policy and by nothing
else. Wall time, not sim time: the question is how fast messages arrive at a consumer.
"""

from __future__ import annotations

import json
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState


def main():
    topic, seconds = sys.argv[1], float(sys.argv[2])
    rclpy.init()
    node = Node("cite_rtf_counter")
    qos = QoSProfile(depth=1000, history=QoSHistoryPolicy.KEEP_LAST,
                     reliability=QoSReliabilityPolicy.RELIABLE)
    state = dict(n=0, first=None, last=None)

    def on_msg(_msg):
        now = time.time()
        if state["first"] is None:
            state["first"] = now
        state["last"] = now
        state["n"] += 1

    node.create_subscription(JointState, topic, on_msg, qos)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    rclpy.shutdown()

    span = (state["last"] - state["first"]) if state["n"] > 1 else None
    print(json.dumps(dict(
        topic=topic, count=state["n"], span_s=span,
        hz=(state["n"] - 1) / span if span and span > 0 else None,
        wall_seconds=seconds,
        hz_over_requested_window=state["n"] / seconds,
    )))


if __name__ == "__main__":
    main()
