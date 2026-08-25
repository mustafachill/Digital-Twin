"""The five named QoS profiles, in Python (ADR-0025).

Incompatible QoS between a publisher and a subscriber **connects silently and
delivers nothing**. ``ros2 topic list`` shows the topic, ``ros2 topic info``
shows both endpoints, and no error is produced anywhere. It is the
most-misdiagnosed failure in ROS 2, and v1's handoff protocol died of exactly it.

The defence is to never improvise a profile. Use one of these, every time. A
``QoSProfile`` constructed anywhere outside this module is a review finding.

See ``docs/interfaces/qos-profiles.md``; a test asserts that this module, the C++
header beside it, and that document all state the same numbers.
"""

from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

__all__ = ["SENSOR", "STATE", "COMMAND", "LATCHED", "EVENT", "sensor", "state",
           "command", "latched", "event"]


def _profile(
    reliability: ReliabilityPolicy,
    durability: DurabilityPolicy,
    history: HistoryPolicy,
    depth: int,
) -> QoSProfile:
    return QoSProfile(
        reliability=reliability, durability=durability, history=history, depth=depth
    )


#: High-rate sensor streams where only the newest value matters.
SENSOR = _profile(
    ReliabilityPolicy.BEST_EFFORT, DurabilityPolicy.VOLATILE, HistoryPolicy.KEEP_LAST, 5
)

#: Periodic state — joint state, line state, divergence metrics.
STATE = _profile(
    ReliabilityPolicy.RELIABLE, DurabilityPolicy.VOLATILE, HistoryPolicy.KEEP_LAST, 10
)

#: Commands that must arrive.
COMMAND = _profile(
    ReliabilityPolicy.RELIABLE, DurabilityPolicy.VOLATILE, HistoryPolicy.KEEP_LAST, 10
)

#: Configuration a late joiner must receive immediately.
LATCHED = _profile(
    ReliabilityPolicy.RELIABLE, DurabilityPolicy.TRANSIENT_LOCAL, HistoryPolicy.KEEP_LAST, 1
)

#: Discrete events that must not be dropped.
EVENT = _profile(
    ReliabilityPolicy.RELIABLE, DurabilityPolicy.VOLATILE, HistoryPolicy.KEEP_ALL, 100
)


def sensor() -> QoSProfile:
    return SENSOR


def state() -> QoSProfile:
    return STATE


def command() -> QoSProfile:
    return COMMAND


def latched() -> QoSProfile:
    return LATCHED


def event() -> QoSProfile:
    return EVENT
