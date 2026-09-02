#!/usr/bin/env python3
"""The shipped cell, as the three arms that bring one up address it.

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fn.py`,
copied at commit `eeaf903` -- the driver, the contact recorder and the spawn/remove/pose
probes are that file's, restructured into a module because this campaign has three arms
against one cell instead of one. That directory is FROZEN
(`docs/measurements/README.md`) and nothing in it is edited from here.

TWO CHANGES THAT ARE NOT RESTRUCTURING, and both are `criteria.md` requirements:

  * every Gazebo-transport subprocess call goes through `cite_bringup.gz.run`, the single
    door ADR-0042 names. The frozen rig built the environment itself and passed it to
    `subprocess.run`, which was correct at the time and is a second construction of the
    value that module exists to state once (CLAUDE.md section 10, P1). An unpartitioned
    `gz model --list` reaches no world and EXITS 0, so the failure this prevents is
    silence.
  * a pose recorder exists. I5 samples the part's yaw AT THE STALL and not only at the
    spawn, because the conveyor-yaw campaign found the jaws square the part up as they
    close, and a subprocess probe cannot be taken at an instant the harness only learns
    about afterwards.

The partition has to be in this process's environment BEFORE `gz.transport13` builds a
node, so the import order below is load-bearing and is not tidied.
"""

from __future__ import annotations

import math
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from common import ARM, DRIVE_JOINT, ZONE

from cite_bringup.gz import gz_environment, plan_for
from cite_bringup.gz import run as gz_run

os.environ.update(gz_environment(plan_for(ZONE)))

import rclpy  # noqa: E402
import tf2_ros  # noqa: E402
from cite_interfaces.action import Grasp, MoveTo, Pick  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402

PICK_FRAME = "cell_a__table_pick__surface"

#: `criteria.md` section 5.3 -- the work-piece, and the hull-grasp campaign's approach,
#: retreat and grasp heights taken verbatim.
WORKPIECE_SIZE_M = 0.05
WORKPIECE_MASS_KG = 0.2
WORKPIECE_MU = 1.0
SPAWN_DROP_M = 0.005
GRASP_HEIGHT_M = 0.03
APPROACH_M = 0.10
RETREAT_M = 0.12

#: The L0 effort, held fixed (section 5.1). ADR-0052 section 5: `effort` is the commanded
#: maximum echoed back and is not a measurement.
MAX_EFFORT_N = 60.0

BRING_UP_CEILING_S = 420.0
STEP_CEILING_S = 420.0
ACCEPT_CEILING_S = 90.0

_NUMBER = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_TRIPLE = re.compile(rf"\[\s*({_NUMBER})\s*[|\s]\s*({_NUMBER})\s*[|\s]\s*({_NUMBER})\s*\]")


# ---------------------------------------------------------------------------
# Gazebo transport, through the one door
# ---------------------------------------------------------------------------
def workpiece_sdf(name: str, mu: float = WORKPIECE_MU) -> str:
    """A 50 mm cube with one passive contact sensor.

    The sensor is I4 and it is PASSIVE: ADR-0029 removed the only consumer of contact
    data in this cell, so nothing acts on it and its presence changes no grasp.
    """
    inertia = WORKPIECE_MASS_KG * (WORKPIECE_SIZE_M**2 + WORKPIECE_SIZE_M**2) / 12.0
    s = WORKPIECE_SIZE_M
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <link name="link">
      <inertial>
        <mass>{WORKPIECE_MASS_KG}</mass>
        <inertia>
          <ixx>{inertia}</ixx><iyy>{inertia}</iyy><izz>{inertia}</izz>
          <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry><box><size>{s} {s} {s}</size></box></geometry>
        <surface><friction><ode><mu>{mu}</mu><mu2>{mu}</mu2></ode></friction></surface>
      </collision>
      <visual name="visual">
        <geometry><box><size>{s} {s} {s}</size></box></geometry>
        <material><ambient>0.8 0.3 0.1 1</ambient><diffuse>0.9 0.4 0.1 1</diffuse></material>
      </visual>
      <sensor name="contact" type="contact">
        <contact><collision>collision</collision></contact>
        <always_on>true</always_on>
        <update_rate>200</update_rate>
      </sensor>
    </link>
  </model>
</sdf>
"""


def spawn(name: str, xyz, yaw_rad: float = 0.0, mu: float = WORKPIECE_MU):
    """Create the work-piece at a pose and a YAW ABOUT THE WORLD VERTICAL.

    The yaw is the lever of Arm C and it is named with its axis every time it appears
    (`criteria.md` section 5.3): an angle without an axis is not a measurement of
    anything, and this repository has already put a roll where only a yaw could belong.
    """
    path = Path(f"/tmp/{name}.sdf")
    path.write_text(workpiece_sdf(name, mu))
    return gz_run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
         "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2]), "-Y", str(yaw_rad)],
        zone=ZONE, timeout=180,
    )


def remove(world: str, name: str):
    return gz_run(
        ["gz", "service", "-s", f"/world/{world}/remove",
         "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
         "--timeout", "5000", "--req", f'name: "{name}" type: MODEL'],
        zone=ZONE, timeout=60,
    )


def model_pose(name: str) -> dict | None:
    """One model's pose, as XYZ and RPY, by subprocess probe.

    The slow instrument, kept for the spawn reading and as a cross-check on the pose
    stream. `raw` is retained so that a later reader can re-parse the text rather than
    trust this regular expression.
    """
    out = gz_run(["gz", "model", "-m", name, "-p"], zone=ZONE, timeout=30).stdout
    triples = _TRIPLE.findall(out)
    if not triples:
        return None
    xyz = tuple(float(v) for v in triples[0])
    rpy = tuple(float(v) for v in triples[1]) if len(triples) > 1 else None
    return {"xyz": xyz, "rpy": rpy, "yaw_rad": rpy[2] if rpy else None, "raw": out}


def models_in_world() -> list[str]:
    """Every model the world holds, for V3's "no work-piece exists in the world at all".

    Through the one door, because an unpartitioned `gz model --list` returns an EMPTY
    list having reached no world and exits 0 -- which would read here as "no work-piece",
    the exact answer V3 is asking for, arrived at by not looking.
    """
    out = gz_run(["gz", "model", "--list"], zone=ZONE, timeout=60).stdout
    names = []
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            names.append(stripped[2:].strip())
    return names


def gz_topics() -> list[str]:
    out = gz_run(["gz", "topic", "-l"], zone=ZONE, timeout=60).stdout
    return [line.strip() for line in out.splitlines() if line.strip().startswith("/")]


# ---------------------------------------------------------------------------
# I4 -- the contact witness
# ---------------------------------------------------------------------------
@dataclass
class ContactSample:
    t: float
    finger_points: int
    total_points: int


class ContactRecorder:
    """I4 -- the work-piece's own contact sensor. Built per trial and dies with the part.

    Copied from the frozen `measure_fn.py` at `eeaf903`. It answers one question, which
    is V3's: was anything of the gripper touching the part while the jaws stalled?
    Without it, "a real grasp reported empty" would be asserted from the reached width
    alone, which is the quantity under measurement. A witness that is not the thing being
    measured is the point.

    IT CANNOT EXIST WHERE THERE IS NO WORK-PIECE. Arm A spawns none, so nothing carries
    this sensor there and I4's inverted job -- witness NO contact -- is discharged by
    `models_in_world()` instead. That is recorded as a limit of the instrument in the
    write-up rather than presented as a witness that happened to see nothing.
    """

    def __init__(self, world: str, model: str) -> None:
        from gz.msgs10.contacts_pb2 import Contacts
        from gz.transport13 import Node as GzNode

        self._lock = threading.Lock()
        self.samples: list[ContactSample] = []
        self.message_count = 0
        self._node = GzNode()
        self.topic = f"/world/{world}/model/{model}/link/link/sensor/contact/contact"

        def on_contacts(msg: Contacts) -> None:
            stamp = msg.header.stamp
            t = stamp.sec + stamp.nsec * 1e-9
            finger = 0
            total = 0
            for contact in msg.contact:
                names = f"{contact.collision1.name} {contact.collision2.name}"
                points = len(contact.position)
                total += points
                if "finger" in names:
                    finger += points
            with self._lock:
                self.message_count += 1
                self.samples.append(
                    ContactSample(t=t, finger_points=finger, total_points=total))

        self.subscribed = self._node.subscribe(Contacts, self.topic, on_contacts)

    def snapshot(self) -> list[ContactSample]:
        with self._lock:
            return list(self.samples)

    def first_finger_contact_time(self) -> float | None:
        for sample in self.snapshot():
            if sample.finger_points:
                return sample.t
        return None

    def summarise(self, since: float | None = None) -> dict:
        samples = self.snapshot()
        window = [s for s in samples if since is None or s.t >= since]
        return {
            "contact_topic": self.topic,
            "contact_subscribed": bool(self.subscribed),
            "contact_messages": self.message_count,
            "contact_messages_in_window": len(window),
            "finger_contact_points_max": max((s.finger_points for s in window), default=0),
            "finger_contact_messages": sum(1 for s in window if s.finger_points),
            "first_finger_contact_t": self.first_finger_contact_time(),
        }


# ---------------------------------------------------------------------------
# I5 -- the pose stream
# ---------------------------------------------------------------------------
@dataclass
class PoseSample:
    t: float
    x: float
    y: float
    z: float
    yaw_rad: float


class PoseRecorder:
    """I5 -- the part's pose and yaw through the close, sampled continuously.

    Subscribed rather than probed, because "the yaw AT THE STALL" is an instant the
    harness only learns about once the result arrives; a subprocess probe issued then is
    a reading of where the part is afterwards. The probe in `model_pose` is kept as the
    spawn reading and as a cross-check, and both go into the record.

    A yaw about the WORLD VERTICAL, out of the quaternion, and never any other rotation.
    """

    def __init__(self, world: str, model: str) -> None:
        from gz.msgs10.pose_v_pb2 import Pose_V
        from gz.transport13 import Node as GzNode

        self._lock = threading.Lock()
        self.samples: list[PoseSample] = []
        self.model = model
        self._node = GzNode()
        self.topics = [
            f"/world/{world}/dynamic_pose/info",
            f"/world/{world}/pose/info",
        ]

        def on_poses(msg: Pose_V) -> None:
            for pose in msg.pose:
                if pose.name != self.model:
                    continue
                stamp = msg.header.stamp
                t = stamp.sec + stamp.nsec * 1e-9
                q = pose.orientation
                yaw = math.atan2(
                    2.0 * (q.w * q.z + q.x * q.y),
                    1.0 - 2.0 * (q.y * q.y + q.z * q.z),
                )
                with self._lock:
                    self.samples.append(
                        PoseSample(t=t, x=pose.position.x, y=pose.position.y,
                                   z=pose.position.z, yaw_rad=yaw))

        self.subscribed = {
            topic: bool(self._node.subscribe(Pose_V, topic, on_poses))
            for topic in self.topics
        }

    def snapshot(self) -> list[PoseSample]:
        with self._lock:
            return list(self.samples)

    def at_or_before(self, t: float | None) -> PoseSample | None:
        samples = self.snapshot()
        if not samples:
            return None
        if t is None:
            return samples[-1]
        earlier = [s for s in samples if s.t <= t]
        return earlier[-1] if earlier else samples[0]

    def summarise(self) -> dict:
        samples = self.snapshot()
        return {
            "pose_topics": self.topics,
            "pose_subscribed": self.subscribed,
            "pose_samples": len(samples),
        }


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------
class Driver(Node):
    """One node against the running cell's L3 action servers.

    QoS on `/joint_states` is the default sensor-side profile the broadcaster publishes
    with; it is declared by `create_subscription`'s depth argument here exactly as the
    frozen rig declared it, and a mismatch would deliver nothing rather than fail
    (CLAUDE.md section 10).
    """

    def __init__(self, name: str = "option_f_regions_harness") -> None:
        super().__init__(name)
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        base = f"/cite/{ZONE}/{ARM}"
        self.namespace_ = base
        self.move_to = ActionClient(self, MoveTo, f"{base}/move_to")
        self.pick = ActionClient(self, Pick, f"{base}/pick")
        self.grasp = ActionClient(self, Grasp, f"{base}/grasp")
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer, self)
        self.drive_q: list[tuple[float, float]] = []
        self.last_joint_state: dict | None = None
        self.create_subscription(JointState, f"{base}/joint_states", self._on_joints, 20)
        self.closing_time: float | None = None
        self.grasp_time: float | None = None

    def _on_joints(self, message: JointState) -> None:
        t = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        # The whole vector, kept for the one question the drive joint cannot answer: did
        # the arm move at all? Arm D's refusal trials assert that it did not, and an
        # assertion about the arm cannot be made from the gripper's joint alone.
        self.last_joint_state = {
            "t": t,
            "name": list(message.name),
            "position": [float(value) for value in message.position],
        }
        if DRIVE_JOINT not in message.name:
            return
        index = message.name.index(DRIVE_JOINT)
        self.drive_q.append((t, message.position[index]))

    def sim_now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def start_spinning(self) -> None:
        self._executor = MultiThreadedExecutor(num_threads=4)
        self._executor.add_node(self)
        self._spin = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin.start()

    def spin_until(self, predicate, ceiling_s: float, what: str):
        end = time.monotonic() + ceiling_s
        result = predicate()
        while result is None and time.monotonic() < end:
            time.sleep(0.05)
            result = predicate()
        if result is None:
            raise TimeoutError(f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def await_stack(self, settle_s: float = 8.0) -> None:
        for client, label in ((self.move_to, "move_to"), (self.pick, "pick"),
                              (self.grasp, "grasp")):
            self.spin_until(
                lambda c=client: c.wait_for_server(timeout_sec=1.0) or None,
                BRING_UP_CEILING_S, f"the {label} action server",
            )
        time.sleep(settle_s)

    def resolve(self, frame: str):
        tf = self.spin_until(
            lambda: (
                self.buffer.lookup_transform("cite_world", frame, rclpy.time.Time())
                if self.buffer.can_transform("cite_world", frame, rclpy.time.Time())
                else None
            ),
            BRING_UP_CEILING_S, f"a transform from cite_world to {frame}",
        )
        t = tf.transform.translation
        return (t.x, t.y, t.z)

    def send_goal(self, client, goal, ceiling_s: float, feedback_cb=None):
        if not client.wait_for_server(timeout_sec=60.0):
            raise TimeoutError(f"no server for {client._action_name}")
        send = client.send_goal_async(goal, feedback_callback=feedback_cb)
        try:
            handle = self.spin_until(
                lambda: send.result() if send.done() else None,
                ACCEPT_CEILING_S, "goal acceptance")
        except TimeoutError:
            raise TimeoutError(
                f"no acceptance response from {client._action_name} within "
                f"{ACCEPT_CEILING_S:.0f}s") from None
        if not handle.accepted:
            return None
        future = handle.get_result_async()
        try:
            wrapped = self.spin_until(
                lambda: future.result() if future.done() else None, ceiling_s,
                "the goal to finish")
        except TimeoutError:
            handle.cancel_goal_async()
            time.sleep(5.0)
            raise
        return wrapped.result

    # -- the three doors -----------------------------------------------------
    def go_home(self) -> bool:
        goal = MoveTo.Goal()
        goal.named_configuration = "home"
        result = self.send_goal(self.move_to, goal, STEP_CEILING_S)
        return result is not None and result.result.code == 0

    def move_to_frame_offset(self, frame: str, z_m: float):
        """Send the tool to a pose stated IN `frame`, tool axis pointing down.

        The orientation is `Pick`'s own convention -- a half turn about x, which puts the
        tool z along the frame's -z -- so a pose built here and a pose `Pick` builds
        differ only in the offset applied to it. Arms C and D use this to reach the part
        through the shipped `MoveTo` when the width they want is one `Pick` refuses.
        """
        goal = MoveTo.Goal()
        goal.target.header.frame_id = frame
        goal.target.pose.position.z = z_m
        goal.target.pose.orientation.x = 1.0
        goal.target.pose.orientation.w = 0.0
        return self.send_goal(self.move_to, goal, STEP_CEILING_S)

    def do_pick(self, workpiece: str, width_m: float):
        goal = Pick.Goal()
        goal.object_pose.header.frame_id = PICK_FRAME
        goal.object_pose.pose.position.z = GRASP_HEIGHT_M
        goal.object_pose.pose.orientation.x = 1.0
        goal.object_pose.pose.orientation.w = 0.0
        goal.workpiece_id = workpiece
        goal.approach_distance_m = APPROACH_M
        goal.retreat_distance_m = RETREAT_M
        goal.grasp_width_m = width_m

        def on_feedback(message):
            phase = message.feedback.phase
            if phase == Pick.Feedback.PHASE_GRASPING and self.closing_time is None:
                self.closing_time = self.sim_now()
            if phase == Pick.Feedback.PHASE_RETREATING and self.grasp_time is None:
                self.grasp_time = self.sim_now()

        return self.send_goal(self.pick, goal, STEP_CEILING_S, on_feedback)

    def do_grasp(self, width_m: float, expect_object: bool):
        goal = Grasp.Goal()
        goal.width_m = width_m
        goal.max_effort_n = MAX_EFFORT_N
        goal.expect_object = expect_object
        return self.send_goal(self.grasp, goal, STEP_CEILING_S)


def grasp_result_fields(result, prefix: str) -> dict:
    """`Grasp.Result` as I1 reports it: the verdict and the widths, typed and full."""
    if result is None:
        return {f"{prefix}_answered": False}
    return {
        f"{prefix}_answered": True,
        f"{prefix}_result_code": int(result.result.code),
        f"{prefix}_detail": result.result.detail,
        f"{prefix}_reached_width_m": float(result.reached_width_m),
        f"{prefix}_measured_effort_n": float(result.measured_effort_n),
        f"{prefix}_holding": bool(result.holding),
    }


def q_at(driver: Driver, boundary: float | None) -> float | None:
    """I3 -- the last drive-joint sample at or before `boundary`, in the joint's own units.

    `criteria.md` I3, taken literally: "the last `arm_1_drive_joint` sample on
    `/joint_states` at or before the result arrives". `boundary` is that arrival, in
    simulation time, read as soon as the result future completes.
    """
    if boundary is None:
        boundary = driver.sim_now()
    before = [q for t, q in driver.drive_q if t <= boundary]
    if before:
        return before[-1]
    return driver.drive_q[-1][1] if driver.drive_q else None


#: How many drive-joint samples of the closing window a record carries. Enough for the
#: whole of a close at this cell's publication rate, and bounded so that one long trial
#: cannot make a block's raw file unreadable.
TRACE_CAP = 600


def window_trace(driver: Driver, start: float | None, end: float | None) -> list[list[float]]:
    """The drive joint through the close, so that a V4 exclusion can be explained.

    Published on every record because V4 is expected to fire across Arm A for a
    structural reason -- I1 reads a joint the controller has just released while it is
    still moving, I3 reads it a little later -- and a rule that excludes trials has to
    leave behind the evidence for WHY, or the exclusion becomes an assertion.
    """
    if start is None or end is None:
        return []
    inside = [[t, q] for t, q in driver.drive_q if start <= t <= end]
    if len(inside) <= TRACE_CAP:
        return inside
    step = len(inside) / TRACE_CAP
    return [inside[int(index * step)] for index in range(TRACE_CAP)]
