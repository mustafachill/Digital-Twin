#!/usr/bin/env python3
"""Hull-vs-vendor grasp harness for cell_a — ADR-0028 promotion gate, clause 2.

Repeats the trial protocol of `docs/measurements/2026-08-25-friction-grasp/`
against BOTH collision geometries, and adds the three quantities ADR-0028's
correction of 2026-08-31 names, none of which that campaign measured:

  M1  translation of the part along each gripper axis, between FIRST CONTACT
      and the SETTLED HOLD;
  M2  rotation of the part about the finger-pivot axis over the same window
      (a "pitch"), reported beside the two axes the earlier campaigns published;
  M3  contact-patch length along the pad, against the 37 -> 44 mm prediction;
  M4  the contact NORMAL's component along the approach axis, which is the
      mechanism ADR-0028 predicts and the only metric here that reads it
      directly.

Structure, the action-boundary driver, the Gazebo pose feed and the slip/twist
metrics are taken from that campaign's `harness/measure_grasp.py` and are
deliberately UNCHANGED where they are unchanged, so that a control figure here
is the same computation as the figure it is compared against. That file is
frozen (docs/measurements/README.md) and is therefore copied rather than
imported or edited.

WHY THE POSE FEED AND NOT TF: TF would give the pad pose through forward
kinematics on the commanded joint state, which is a servo's opinion of where the
finger is. The question here is where the part sits between two collision
surfaces, so the simulator's own pose feed is the instrument.

WHY A CONTACT SENSOR: M3 and M4 cannot be inferred from poses at all. The world
loads `gz::sim::systems::Contact` already, and `gz.msgs.Contact` carries
`position`, `normal`, `depth` and `wrench` per contact point. The sensor is on
the work-piece, is passive, and consumes no simulation state -- ADR-0029 removed
the attachment plugin that used to read contact data, so nothing acts on it.

Run inside the container, against a cell already brought up.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ZONE = "cell_a"
ARM = "arm_1"

# The partition must be in this process's environment BEFORE gz.transport13
# builds a node, and every `gz` subprocess needs it too (ADR-0042). One door.
from cite_bringup.gz import gz_environment, plan_for  # noqa: E402

os.environ.update(gz_environment(plan_for(ZONE)))

import rclpy  # noqa: E402
import tf2_ros  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402

from cite_interfaces.action import MoveTo, Pick, Place  # noqa: E402

PICK_FRAME = f"{ZONE}__table_pick__surface"
PLACE_FRAME = f"{ZONE}__conveyor_1__infeed"

WORKPIECE_SIZE = 0.05
WORKPIECE_MASS = 0.2
SPAWN_DROP_M = 0.005

#: Geometry the behaviour tree uses, restated from the friction campaign so that
#: the commanded grasp is the shipped one.
GRASP_HEIGHT_M = 0.03
RELEASE_HEIGHT_M = 0.04
APPROACH_M = 0.10
RETREAT_M = 0.12
GRASP_WIDTH_M = 0.045

PAD_LINK = f"{ARM}_left_finger"
PAD_LINK_R = f"{ARM}_right_finger"
#: The gripper base is lumped into `link5` by the vendor description, so `link5`
#: is the rigid body the gripper hangs off. Every displacement below is measured
#: RELATIVE TO IT, which removes any residual arm motion during closure exactly
#: rather than assuming the arm is still.
GRIPPER_BODY = f"{ARM}_link5"
ARM_MODEL = ARM
DRIVE_JOINT = f"{ARM}_drive_joint"

BRING_UP_CEILING_S = 420.0
STEP_CEILING_S = 420.0

OUT_OF_JAWS_MM = 25.0


def _workpiece_sdf(name: str, mu: float) -> str:
    inertia = WORKPIECE_MASS * (WORKPIECE_SIZE**2 + WORKPIECE_SIZE**2) / 12.0
    s = WORKPIECE_SIZE
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <link name="link">
      <inertial>
        <mass>{WORKPIECE_MASS}</mass>
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
      <!-- The instrument for M3 and M4. Passive: ADR-0029 removed the only
           consumer of contact data in this cell, so nothing acts on it. -->
      <sensor name="contact" type="contact">
        <contact><collision>collision</collision></contact>
        <always_on>true</always_on>
        <update_rate>200</update_rate>
      </sensor>
    </link>
  </model>
</sdf>
"""


# -----------------------------------------------------------------------------
# Pose and contact recording, straight from the simulator
# -----------------------------------------------------------------------------


@dataclass
class Sample:
    t: float
    p: tuple[float, float, float]
    q: tuple[float, float, float, float]   # x, y, z, w


@dataclass
class ContactSample:
    t: float
    #: (collision1, collision2, position, normal, depth) with position/normal in
    #: the world frame, exactly as the sensor reports them.
    points: list[tuple[str, str, tuple[float, float, float],
                       tuple[float, float, float], float]]


class PoseRecorder:
    def __init__(self, world: str, wanted, topic_suffix: str = "dynamic_pose/info"):
        from gz.transport13 import Node as GzNode
        from gz.msgs10.pose_v_pb2 import Pose_V

        self._wanted = wanted if callable(wanted) else (lambda n, s=set(wanted): n in s)
        self._lock = threading.Lock()
        self.tracks: dict[str, list[Sample]] = {}
        self.latest: dict[str, Sample] = {}
        self.seen_names: set[str] = set()
        self.recording = False

        self._node = GzNode()
        topic = f"/world/{world}/{topic_suffix}"

        def on_pose(msg: Pose_V) -> None:
            stamp = msg.header.stamp
            t = stamp.sec + stamp.nsec * 1e-9
            with self._lock:
                for pose in msg.pose:
                    self.seen_names.add(pose.name)
                    if not self._wanted(pose.name):
                        continue
                    sample = Sample(
                        t=t,
                        p=(pose.position.x, pose.position.y, pose.position.z),
                        q=(pose.orientation.x, pose.orientation.y,
                           pose.orientation.z, pose.orientation.w),
                    )
                    self.latest[pose.name] = sample
                    if not self.recording:
                        continue
                    self.tracks.setdefault(pose.name, []).append(sample)

        if not self._node.subscribe(Pose_V, topic, on_pose):
            raise RuntimeError(f"could not subscribe to {topic}")
        self.topic = topic

    def start(self) -> None:
        with self._lock:
            self.tracks = {}
            self.recording = True

    def stop(self) -> None:
        with self._lock:
            self.recording = False

    def snapshot(self) -> dict[str, list[Sample]]:
        with self._lock:
            return {k: list(v) for k, v in self.tracks.items()}

    def names(self) -> set[str]:
        with self._lock:
            return set(self.seen_names)


class ContactRecorder:
    """Subscribe to one spawned work-piece's contact sensor.

    The topic is created when the model is spawned and destroyed with it, so a
    recorder is built per trial and torn down with the part.
    """

    def __init__(self, world: str, model: str, link: str = "link",
                 sensor: str = "contact"):
        from gz.transport13 import Node as GzNode
        from gz.msgs10.contacts_pb2 import Contacts

        self._lock = threading.Lock()
        self.samples: list[ContactSample] = []
        self.recording = False
        self.message_count = 0
        self._node = GzNode()
        self.topic = (f"/world/{world}/model/{model}/link/{link}"
                      f"/sensor/{sensor}/contact")

        def on_contacts(msg: Contacts) -> None:
            stamp = msg.header.stamp
            t = stamp.sec + stamp.nsec * 1e-9
            points = []
            for c in msg.contact:
                n = len(c.position)
                for i in range(n):
                    pos = c.position[i]
                    nrm = c.normal[i] if i < len(c.normal) else None
                    depth = c.depth[i] if i < len(c.depth) else float("nan")
                    points.append((
                        c.collision1.name, c.collision2.name,
                        (pos.x, pos.y, pos.z),
                        (nrm.x, nrm.y, nrm.z) if nrm is not None else (
                            float("nan"),) * 3,
                        depth,
                    ))
            with self._lock:
                self.message_count += 1
                if self.recording:
                    self.samples.append(ContactSample(t=t, points=points))

        self.subscribed = self._node.subscribe(Contacts, self.topic, on_contacts)

    def start(self) -> None:
        with self._lock:
            self.samples = []
            self.recording = True

    def stop(self) -> None:
        with self._lock:
            self.recording = False

    def snapshot(self) -> list[ContactSample]:
        with self._lock:
            return list(self.samples)


# -----------------------------------------------------------------------------
# Small vector / quaternion helpers (copied from the friction harness)
# -----------------------------------------------------------------------------


def quat_rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def quat_inv(q):
    return (-q[0], -q[1], -q[2], q[3])


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def compose(parent: Sample, child: Sample) -> Sample:
    p = quat_rotate(parent.q, child.p)
    return Sample(t=child.t,
                  p=(parent.p[0] + p[0], parent.p[1] + p[1], parent.p[2] + p[2]),
                  q=quat_mul(parent.q, child.q))


def quat_conj_rotate(q, v):
    x, y, z, w = q
    x, y, z = -x, -y, -z
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def rotvec(q) -> tuple[float, float, float]:
    """Axis-angle vector of `q`, in radians, with the angle in [0, pi]."""
    x, y, z, w = q
    if w < 0.0:
        x, y, z, w = -x, -y, -z, -w
    s = math.sqrt(max(0.0, x * x + y * y + z * z))
    if s < 1e-12:
        return (0.0, 0.0, 0.0)
    angle = 2.0 * math.atan2(s, w)
    return (angle * x / s, angle * y / s, angle * z / s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def norm(a):
    return math.sqrt(dot(a, a))


def interpolate(track: list[Sample], t: float) -> Sample | None:
    if not track:
        return None
    best = None
    for s in track:
        if s.t <= t:
            best = s
        else:
            break
    return best or track[0]


def gripper_axes(pad_l: Sample, pad_r: Sample):
    """The three named axes, in world coordinates, at one instant.

    The vendor's gripper joints all have `rpy="0 0 0"` origins and rotate about
    the gripper base frame's x; the parallel linkage cancels the finger link's
    own net rotation, which the friction campaign measured at 0.14 deg over a
    whole carry. So the LEFT FINGER LINK's frame is the gripper base frame's
    orientation to within that, and:

        ex  the finger-pivot axis      (M2's axis)
        ey  the jaw / closing axis,    left pad -> right pad; the axis the
                                       published 18.7 deg roll is about
        ez  the approach axis          (M1's predicted axis, and M4's)

    `pad_to_pad_angle_deg` is returned with them as a check on that claim rather
    than an assertion of it: it is the angle between `ey` as taken from the
    finger's own frame and the measured pad-to-pad direction. A frame that has
    come apart says so in the data instead of quietly relabelling two axes.
    """
    ex = quat_rotate(pad_l.q, (1.0, 0.0, 0.0))
    ey = quat_rotate(pad_l.q, (0.0, 1.0, 0.0))
    ez = quat_rotate(pad_l.q, (0.0, 0.0, 1.0))
    d = sub(pad_r.p, pad_l.p)
    dn = norm(d)
    # SIGN, MEASURED RATHER THAN ASSUMED. The shakedown showed the finger frame's
    # +y running from the RIGHT pad to the LEFT one, so `ey` is oriented against
    # the measured pad-to-pad vector here and the reported angle is the residual
    # of that alignment, not 180 minus it. Direction matters because `d_close` is
    # a signed number that has to mean the same thing in both arms of the A/B.
    if dn > 1e-9 and dot(d, ey) < 0.0:
        ey = (-ey[0], -ey[1], -ey[2])
    angle = float("nan")
    if dn > 1e-9:
        c = max(-1.0, min(1.0, dot(d, ey) / dn))
        angle = math.degrees(math.acos(c))
    return ex, ey, ez, angle


# -----------------------------------------------------------------------------
# The driver
# -----------------------------------------------------------------------------


class Driver(Node):
    def __init__(self, world: str):
        super().__init__("hull_grasp_harness")
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.world = world
        base = f"/cite/{ZONE}/{ARM}"
        self.move_to = ActionClient(self, MoveTo, f"{base}/move_to")
        self.pick = ActionClient(self, Pick, f"{base}/pick")
        self.place = ActionClient(self, Place, f"{base}/place")
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer, self)
        self.drive_q: list[tuple[float, float]] = []
        self.recording_joints = False
        self.create_subscription(JointState, f"{base}/joint_states", self._on_joints, 20)
        self.grasp_time: float | None = None
        self.closing_time: float | None = None
        self.release_time: float | None = None

    def _on_joints(self, msg: JointState) -> None:
        if not self.recording_joints or DRIVE_JOINT not in msg.name:
            return
        i = msg.name.index(DRIVE_JOINT)
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.drive_q.append((t, msg.position[i]))

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
                              (self.place, "place")):
            self.spin_until(
                lambda c=client: c.wait_for_server(timeout_sec=1.0) or None,
                BRING_UP_CEILING_S, f"the {label} action server",
            )
        time.sleep(settle_s)

    def resolve(self, frame: str) -> tuple[float, float, float]:
        tf = self.spin_until(
            lambda: (self.buffer.lookup_transform("cite_world", frame, rclpy.time.Time())
                     if self.buffer.can_transform("cite_world", frame, rclpy.time.Time())
                     else None),
            BRING_UP_CEILING_S, f"a transform from cite_world to {frame}")
        t = tf.transform.translation
        return (t.x, t.y, t.z)

    def send_goal(self, client, goal, ceiling_s: float, feedback_cb=None):
        if not client.wait_for_server(timeout_sec=60.0):
            raise TimeoutError(f"no server for {client._action_name}")
        send = client.send_goal_async(goal, feedback_callback=feedback_cb)
        try:
            handle = self.spin_until(
                lambda: send.result() if send.done() else None, 90.0, "goal acceptance")
        except TimeoutError:
            raise TimeoutError(
                f"no acceptance response from {client._action_name} within 90s"
            ) from None
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

    def go_home(self) -> bool:
        goal = MoveTo.Goal()
        goal.named_configuration = "home"
        result = self.send_goal(self.move_to, goal, STEP_CEILING_S)
        return result is not None and result.result.code == 0

    def do_pick(self, workpiece: str):
        goal = Pick.Goal()
        goal.object_pose.header.frame_id = PICK_FRAME
        goal.object_pose.pose.position.z = GRASP_HEIGHT_M
        goal.object_pose.pose.orientation.x = 1.0
        goal.object_pose.pose.orientation.w = 0.0
        goal.workpiece_id = workpiece
        goal.approach_distance_m = APPROACH_M
        goal.retreat_distance_m = RETREAT_M
        goal.grasp_width_m = GRASP_WIDTH_M

        def on_feedback(msg):
            fb = msg.feedback
            if fb.phase == Pick.Feedback.PHASE_GRASPING and self.closing_time is None:
                self.closing_time = self.sim_now()
            if fb.phase == Pick.Feedback.PHASE_RETREATING and self.grasp_time is None:
                self.grasp_time = self.sim_now()

        return self.send_goal(self.pick, goal, STEP_CEILING_S, on_feedback)

    def do_place(self):
        goal = Place.Goal()
        goal.target_pose.header.frame_id = PLACE_FRAME
        goal.target_pose.pose.position.z = RELEASE_HEIGHT_M
        goal.target_pose.pose.orientation.x = 1.0
        goal.target_pose.pose.orientation.w = 0.0
        goal.approach_distance_m = APPROACH_M
        goal.retreat_distance_m = RETREAT_M
        goal.require_holding = True

        def on_feedback(msg):
            fb = msg.feedback
            if fb.phase == Place.Feedback.PHASE_RELEASING and self.release_time is None:
                self.release_time = self.sim_now()

        return self.send_goal(self.place, goal, STEP_CEILING_S, on_feedback)


# -----------------------------------------------------------------------------
# Simulator side-channel
# -----------------------------------------------------------------------------


def _gz_env() -> dict:
    return dict(os.environ)


def spawn(name: str, xyz, mu: float) -> subprocess.CompletedProcess:
    path = Path(f"/tmp/{name}.sdf")
    path.write_text(_workpiece_sdf(name, mu))
    return subprocess.run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
         "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2])],
        capture_output=True, text=True, timeout=180, env=_gz_env())


def remove(world: str, name: str) -> None:
    subprocess.run(
        ["gz", "service", "-s", f"/world/{world}/remove",
         "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
         "--timeout", "5000", "--req", f'name: "{name}" type: MODEL'],
        capture_output=True, text=True, timeout=60, env=_gz_env())


def model_pose(name: str):
    import re
    out = subprocess.run(["gz", "model", "-m", name, "-p"],
                         capture_output=True, text=True, timeout=30,
                         env=_gz_env()).stdout
    number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    triples = re.findall(rf"\[\s*({number})\s+({number})\s+({number})\s*\]", out)
    if not triples:
        return None
    return tuple(float(v) for v in triples[0])


def verify_geometry(declared: str) -> dict:
    """Read the description the RUNNING cell publishes and say what it collides with.

    criteria.md V2. The flip happens in L0 on the host, three build steps and a
    launch away from the physics that is measured; nothing between them checks
    that the geometry which arrived is the geometry that was asked for. A block
    that silently ran the other arm of the A/B is not a wrong number, it is a
    number attributed to the wrong condition, and no later analysis can see it.
    """
    proc = subprocess.run(
        ["ros2", "param", "get", f"/cite/{ZONE}/{ARM}/description_publisher",
         "robot_description"],
        capture_output=True, text=True, timeout=180)
    text = proc.stdout
    hull = text.count("cite_description/meshes/collision/xarm5/convex_hull")
    vendor_visual = text.count("xarm_description/meshes/xarm5/visual")
    result = {
        "declared_geometry": declared,
        "hull_collision_refs": hull,
        "vendor_visual_refs": vendor_visual,
        "description_chars": len(text),
    }
    expected_hull = 13 if declared == "convex_hull" else 0
    result["geometry_verified"] = (hull == expected_hull)
    return result


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


def _is_finger(collision_name: str) -> str | None:
    """Which pad a collision name belongs to, or None."""
    if "left_finger" in collision_name:
        return "left"
    if "right_finger" in collision_name:
        return "right"
    return None


def closure_metrics(wp: list[Sample], pad_l: list[Sample], pad_r: list[Sample],
                    body: list[Sample], arm: Sample | None,
                    contacts: list[ContactSample],
                    t_close: float | None, t_settled: float | None) -> dict:
    """M1, M2, M3, M4 — everything measured between first contact and the hold.

    Every displacement is expressed relative to `GRIPPER_BODY`, so residual arm
    motion during closure cancels rather than being assumed absent.
    """
    out: dict = {}
    if arm is None or not wp or not pad_l or not pad_r or t_settled is None:
        out["closure_error"] = "missing track"
        return out

    def pad_world(track, t):
        s = interpolate(track, t)
        return compose(arm, s) if s is not None else None

    # --- first contact, from the sensor -------------------------------------
    first = None
    for c in contacts:
        if t_close is not None and c.t < t_close - 1.0:
            continue
        if any(_is_finger(a) or _is_finger(b) for a, b, *_ in c.points):
            first = c.t
            break
    out["t_first_contact_sim"] = first
    out["n_contact_messages"] = len(contacts)
    out["contact_points_seen"] = sum(len(c.points) for c in contacts)
    if first is None:
        out["closure_error"] = "no finger contact reported"
        return out

    t0, t1 = first, t_settled
    out["closure_window_s"] = t1 - t0
    if t1 <= t0:
        out["closure_error"] = f"non-positive window {t1 - t0:.4f}s"
        return out

    pl0, pr0 = pad_world(pad_l, t0), pad_world(pad_r, t0)
    b0, b1 = interpolate(body, t0), interpolate(body, t1)
    w0, w1 = interpolate(wp, t0), interpolate(wp, t1)
    if None in (pl0, pr0, b0, b1, w0, w1):
        out["closure_error"] = "missing sample at a window edge"
        return out
    b0w, b1w = compose(arm, b0), compose(arm, b1)

    ex, ey, ez, pad_angle = gripper_axes(pl0, pr0)
    out["pad_to_pad_axis_angle_deg"] = pad_angle

    # --- M1: translation, per axis, relative to the gripper body -------------
    def in_frame(wsample: Sample, bsample: Sample):
        d = sub(wsample.p, bsample.p)
        return (dot(d, ex), dot(d, ey), dot(d, ez))

    r0 = in_frame(w0, b0w)
    r1 = in_frame(w1, b1w)
    out["d_pivot_mm"] = (r1[0] - r0[0]) * 1000.0
    out["d_close_mm"] = (r1[1] - r0[1]) * 1000.0
    out["d_approach_mm"] = (r1[2] - r0[2]) * 1000.0
    out["d_total_mm"] = math.dist(r1, r0) * 1000.0
    #: How far the gripper body itself moved over the window. If this is large
    #: the arm was not still and M1 is a difference of two moving things -- the
    #: reason the measurement is taken relative to the body at all.
    out["body_move_mm"] = math.dist(b1w.p, b0w.p) * 1000.0

    # --- M2: rotation, decomposed on the same triad --------------------------
    dq = quat_mul(quat_inv(quat_mul(quat_inv(b0w.q), w0.q)),
                  quat_mul(quat_inv(b1w.q), w1.q))
    # Express the body-frame rotation vector back on the world triad by
    # rotating it with the body orientation at t0.
    rv_body = rotvec(dq)
    rv = quat_rotate(b0w.q, rv_body)
    out["pitch_pivot_deg"] = math.degrees(dot(rv, ex))
    out["roll_close_deg"] = math.degrees(dot(rv, ey))
    out["yaw_approach_deg"] = math.degrees(dot(rv, ez))
    out["rot_total_deg"] = math.degrees(norm(rv))

    # --- M3 / M4: the contact patch and the contact normal -------------------
    # Sampled over the HOLD: the last 25% of the closure window plus everything
    # up to the settle, which is where the jaws are stalled on the part.
    hold_start = t0 + 0.75 * (t1 - t0)
    per_msg_len_l, per_msg_len_r, per_msg_len_any = [], [], []
    per_msg_count = []
    normal_z, normal_y, depths = [], [], []
    patch_rows = []
    for c in contacts:
        if c.t < hold_start or c.t > t1 + 1e-9:
            continue
        b = interpolate(body, c.t)
        if b is None:
            continue
        bw = compose(arm, b)
        zs_l, zs_r, zs_any = [], [], []
        for a, bn, pos, nrm, depth in c.points:
            side = _is_finger(a) or _is_finger(bn)
            if side is None:
                continue
            d = sub(pos, bw.p)
            z = dot(d, ez) * 1000.0
            y = dot(d, ey) * 1000.0
            zs_any.append(z)
            (zs_l if side == "left" else zs_r).append(z)
            if not math.isnan(nrm[0]):
                normal_z.append(abs(dot(nrm, ez)))
                normal_y.append(abs(dot(nrm, ey)))
            if not math.isnan(depth):
                depths.append(depth * 1000.0)
            patch_rows.append((c.t, side, z, y, dot(nrm, ex), dot(nrm, ey),
                               dot(nrm, ez), depth))
        if zs_l:
            per_msg_len_l.append(max(zs_l) - min(zs_l))
        if zs_r:
            per_msg_len_r.append(max(zs_r) - min(zs_r))
        if zs_any:
            per_msg_len_any.append(max(zs_any) - min(zs_any))
            per_msg_count.append(len(zs_any))

    def med(v):
        if not v:
            return None
        s = sorted(v)
        n = len(s)
        return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

    out["patch_len_left_mm_median"] = med(per_msg_len_l)
    out["patch_len_right_mm_median"] = med(per_msg_len_r)
    out["patch_len_max_mm"] = max(per_msg_len_any, default=None)
    out["contact_points_per_msg_median"] = med(per_msg_count)
    out["normal_approach_component_median"] = med(normal_z)
    out["normal_closing_component_median"] = med(normal_y)
    out["normal_approach_component_max"] = max(normal_z, default=None)
    out["penetration_depth_mm_median"] = med(depths)
    out["_patch_rows"] = patch_rows
    return out


def carry_metrics(wp: list[Sample], pad: list[Sample], z_rest: float,
                  t_grasp: float | None, t_release: float | None,
                  place_xy, arm: Sample | None, pad_r: list[Sample] | None) -> dict:
    """The friction campaign's own metrics, unchanged, as controls."""
    out: dict = {}
    if not wp:
        return {"error": "no work-piece samples"}
    z_max = max(s.p[2] for s in wp)
    out["z_rest"] = z_rest
    out["z_max"] = z_max
    out["lift_m"] = z_max - z_rest
    out["n_samples_wp"] = len(wp)

    v_max = 0.0
    for a, b in zip(wp, wp[1:]):
        dt = b.t - a.t
        if dt <= 1e-9:
            continue
        v_max = max(v_max, math.dist(a.p, b.p) / dt)
    out["v_max_mps"] = v_max

    carry = [s for s in wp if (t_grasp is None or s.t >= t_grasp)
             and (t_release is None or s.t <= t_release)]
    out["carry_samples"] = len(carry)
    out["carry_duration_s"] = (carry[-1].t - carry[0].t) if len(carry) > 1 else 0.0

    slips: list[tuple[float, float]] = []
    if pad and arm is not None and t_grasp is not None:
        ref = None
        for s in carry:
            pad_s = interpolate(pad, s.t)
            if pad_s is None:
                continue
            pad_w = compose(arm, pad_s)
            rel = quat_conj_rotate(pad_w.q, sub(s.p, pad_w.p))
            if ref is None:
                ref = rel
                continue
            slips.append((s.t - carry[0].t, math.dist(rel, ref) * 1000.0))

    twists: list[tuple[float, float]] = []
    axis_terms: list[tuple[float, float, float, float]] = []
    if pad and arm is not None and t_grasp is not None:
        qref = None
        for s in carry:
            pad_s = interpolate(pad, s.t)
            if pad_s is None:
                continue
            pad_w = compose(arm, pad_s)
            rel_q = quat_mul(quat_inv(pad_w.q), s.q)
            if qref is None:
                qref = rel_q
                continue
            delta = quat_mul(quat_inv(qref), rel_q)
            w = max(-1.0, min(1.0, abs(delta[3])))
            ang = math.degrees(2.0 * math.acos(w))
            twists.append((s.t - carry[0].t, ang))
            rv = quat_rotate(pad_w.q, rotvec(delta))
            axis_terms.append((ang, rv[0], rv[1], rv[2]))
    out["twist_max_deg"] = max((v for _, v in twists), default=None)
    out["twist_final_deg"] = twists[-1][1] if twists else None
    #: The vertical component of the net carry rotation -- the quantity the
    #: conveyor-yaw campaign calls a YAW, and the one the 18.7 deg roll is not.
    if axis_terms:
        ang, rx, ry, rz = max(axis_terms, key=lambda r: r[0])
        out["carry_rot_world_vertical_deg"] = abs(math.degrees(rz))
    else:
        out["carry_rot_world_vertical_deg"] = None

    if slips:
        out["slip_max_mm"] = max(v for _, v in slips)
        out["slip_final_mm"] = slips[-1][1]
        n = len(slips)
        mt = sum(t for t, _ in slips) / n
        mv = sum(v for _, v in slips) / n
        den = sum((t - mt) ** 2 for t, _ in slips)
        out["slip_rate_mm_per_s"] = (
            sum((t - mt) * (v - mv) for t, v in slips) / den if den > 1e-12 else 0.0)
    else:
        out["slip_max_mm"] = out["slip_final_mm"] = out["slip_rate_mm_per_s"] = None

    out["held_through_transport"] = (
        out["slip_max_mm"] is not None and out["slip_max_mm"] < OUT_OF_JAWS_MM)

    if pad and pad_r and arm is not None and t_grasp is not None:
        widths = []
        for s in pad:
            if s.t < t_grasp or (t_release is not None and s.t > t_release):
                continue
            r = interpolate(pad_r, s.t)
            if r is None:
                continue
            widths.append(math.dist(s.p, r.p) * 1000.0)
        if widths:
            out["pad_separation_mm_min"] = min(widths)
            out["pad_separation_mm_max"] = max(widths)
            out["pad_separation_mm_mean"] = sum(widths) / len(widths)

    final = wp[-1].p
    out["final_xyz"] = final
    out["place_err_m"] = math.hypot(final[0] - place_xy[0], final[1] - place_xy[1])
    return out


# -----------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=ZONE)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--label", required=True)
    ap.add_argument("--geometry", required=True,
                    choices=("vendor_meshes", "convex_hull"))
    ap.add_argument("--out", default="/workspace/docs/measurements/"
                                     "2026-09-01-hull-grasp/raw")
    ap.add_argument("--mu", type=float, default=1.0)
    args = ap.parse_args()

    rclpy.init()
    driver = Driver(args.world)
    driver.start_spinning()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    pick_xyz = driver.resolve(PICK_FRAME)
    place_xyz = driver.resolve(PLACE_FRAME)
    print(f"pick frame  {PICK_FRAME} at {pick_xyz}", flush=True)
    print(f"place frame {PLACE_FRAME} at {place_xyz}", flush=True)

    print("waiting for the whole stack to be up and matched...", flush=True)
    driver.await_stack()
    print("stack ready", flush=True)

    geometry_check = verify_geometry(args.geometry)
    print(f"geometry check: {geometry_check}", flush=True)
    (outdir / f"{args.label}_geometry.json").write_text(
        json.dumps(geometry_check, indent=2))
    if not geometry_check["geometry_verified"]:
        print("ABORT: the running description does not carry the declared "
              "collision geometry.", flush=True)
        driver.destroy_node()
        rclpy.shutdown()
        return 3

    tracked = (ARM_MODEL, PAD_LINK, PAD_LINK_R, GRIPPER_BODY)
    recorder = PoseRecorder(
        args.world,
        lambda n: n in tracked or n.startswith("probe_part_"))
    print(f"recording from {recorder.topic}", flush=True)
    for _ in range(20):
        time.sleep(0.25)

    arm_p = model_pose(ARM_MODEL)
    arm_world_pose = Sample(t=0.0, p=arm_p, q=(0.0, 0.0, 0.0, 1.0)) if arm_p else None
    print(f"arm model {ARM_MODEL} world position {arm_p}", flush=True)

    rows = []
    for i in range(1, args.trials + 1):
        name = f"probe_part_{args.label}_{i:03d}"
        print(f"\n=== trial {i}/{args.trials}  model={name} "
              f"geometry={args.geometry} ===", flush=True)
        driver.grasp_time = None
        driver.closing_time = None
        driver.release_time = None
        driver.drive_q = []

        remove(args.world, name)
        spawn_xyz = (pick_xyz[0], pick_xyz[1],
                     pick_xyz[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M)
        created = spawn(name, spawn_xyz, args.mu)
        if created.returncode != 0:
            rows.append({"trial": i, "ok": False,
                         "note": f"spawn failed: {created.stderr[-300:]}"})
            continue

        settled = None
        for _ in range(60):
            time.sleep(0.5)
            settled = model_pose(name)
            if settled is not None:
                break
        if settled is None:
            rows.append({"trial": i, "ok": False, "note": "work-piece never appeared"})
            continue
        for _ in range(10):
            time.sleep(0.5)
        settled = model_pose(name) or settled
        z_rest = settled[2]
        print(f"  settled at {settled}", flush=True)

        contacts = ContactRecorder(args.world, name)
        print(f"  contact topic {contacts.topic} subscribed={contacts.subscribed}",
              flush=True)
        time.sleep(1.0)

        recorder.start()
        contacts.start()
        driver.recording_joints = True
        t0 = time.monotonic()
        note = ""
        aborted = False
        try:
            homed = driver.go_home()
            pick_result = driver.do_pick(name)
            picked = pick_result is not None and pick_result.result.code == 0
            holding = bool(pick_result.holding) if pick_result is not None else False
            pick_code = pick_result.result.code if pick_result is not None else None
            place_result = driver.do_place() if picked else None
            placed_ok = place_result is not None and place_result.result.code == 0
            place_code = place_result.result.code if place_result is not None else None
            driver.go_home()
        except TimeoutError as exc:
            note = f"timeout: {exc}"
            homed = picked = holding = placed_ok = False
            pick_result = place_result = None
            pick_code = place_code = None
            aborted = "no acceptance response" in str(exc)
        wall = time.monotonic() - t0
        driver.recording_joints = False
        for _ in range(10):
            time.sleep(0.5)
        recorder.stop()
        contacts.stop()

        tracks = recorder.snapshot()
        contact_samples = contacts.snapshot()
        if i == 1:
            seen = sorted(recorder.names())
            (outdir / f"{args.label}_entities.txt").write_text("\n".join(seen))
        wp_track = tracks.get(name, [])
        pad_track = tracks.get(PAD_LINK, [])
        pad_r_track = tracks.get(PAD_LINK_R, [])
        body_track = tracks.get(GRIPPER_BODY, [])
        arm_pose = recorder.latest.get(ARM_MODEL) or arm_world_pose

        try:
            metrics = carry_metrics(wp_track, pad_track, z_rest, driver.grasp_time,
                                    driver.release_time,
                                    (place_xyz[0], place_xyz[1]), arm_pose, pad_r_track)
        except Exception as exc:
            metrics = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            closure = closure_metrics(wp_track, pad_track, pad_r_track, body_track,
                                      arm_pose, contact_samples,
                                      driver.closing_time, driver.grasp_time)
        except Exception as exc:
            closure = {"closure_error": f"{type(exc).__name__}: {exc}"}
        patch_rows = closure.pop("_patch_rows", [])

        raw = outdir / f"{args.label}_trial{i:03d}_samples.csv"
        with raw.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "sim_t", "x", "y", "z", "qx", "qy", "qz", "qw"])
            for entity, track in tracks.items():
                for s in track:
                    w.writerow([entity, f"{s.t:.6f}", *[f"{v:.9f}" for v in s.p],
                                *[f"{v:.9f}" for v in s.q]])
        # FINGER CONTACTS, IN THE CLOSURE WINDOW, AND NOTHING ELSE. Unfiltered
        # this file is 131 MB per trial and almost all of it is the work-piece
        # resting on the pick surface -- 48 trials of table contacts nobody will
        # read, at the cost of the campaign being publishable at all. The window
        # is the one every closure metric is computed over, widened by a second
        # at each end so that the edges can be checked rather than trusted.
        t_c = closure.get("t_first_contact_sim")
        lo = (t_c - 1.0) if t_c is not None else float("-inf")
        hi = (driver.grasp_time + 1.0) if driver.grasp_time is not None else float("inf")
        rawc = outdir / f"{args.label}_trial{i:03d}_contacts.csv"
        with rawc.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sim_t", "collision1", "collision2", "px", "py", "pz",
                        "nx", "ny", "nz", "depth"])
            for c in contact_samples:
                if c.t < lo or c.t > hi:
                    continue
                for a, b, pos, nrm, depth in c.points:
                    if _is_finger(a) is None and _is_finger(b) is None:
                        continue
                    w.writerow([f"{c.t:.6f}", a, b, *[f"{v:.9f}" for v in pos],
                                *[f"{v:.9f}" for v in nrm], f"{depth:.9f}"])
        rawp = outdir / f"{args.label}_trial{i:03d}_patch.csv"
        with rawp.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sim_t", "pad", "z_mm", "y_mm", "n_pivot", "n_close",
                        "n_approach", "depth_m"])
            for r in patch_rows:
                w.writerow(r)
        rawq = outdir / f"{args.label}_trial{i:03d}_drive_joint.csv"
        with rawq.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sim_t", "drive_joint_rad"])
            for t, q in driver.drive_q:
                w.writerow([f"{t:.6f}", f"{q:.6f}"])

        q_at_stall = None
        if driver.grasp_time is not None and driver.drive_q:
            before = [q for t, q in driver.drive_q if t <= driver.grasp_time]
            q_at_stall = before[-1] if before else None

        row = {
            "trial": i,
            "label": args.label,
            "geometry": args.geometry,
            "model": name,
            "mu": args.mu,
            "homed": homed,
            "pick_succeeded": picked,
            "pick_result_code": pick_code,
            "pick_reported_holding": holding,
            "place_succeeded": placed_ok,
            "place_result_code": place_code,
            "wall_s": round(wall, 1),
            "t_closing_sim": driver.closing_time,
            "t_grasp_sim": driver.grasp_time,
            "t_release_sim": driver.release_time,
            "q_at_stall_rad": q_at_stall,
            "note": note,
            **metrics,
            **closure,
        }
        rows.append(row)
        print("  " + json.dumps({k: v for k, v in row.items()
                                 if k not in ("final_xyz",)}, default=str), flush=True)

        contacts.stop()
        remove(args.world, name)
        for _ in range(6):
            time.sleep(0.5)
        summary = outdir / f"{args.label}_trials.json"
        summary.write_text(json.dumps(rows, indent=2, default=str))
        if aborted:
            print("ABORTING the block: the arm is wedged behind an undelivered "
                  "goal response.", flush=True)
            break

    summary = outdir / f"{args.label}_trials.json"
    summary.write_text(json.dumps(rows, indent=2, default=str))
    print(f"\nwrote {summary}", flush=True)

    driver.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
