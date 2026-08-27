#!/usr/bin/env python3
"""Friction-grasp repeatability harness for cell_a.

Drives arm_1 through repeated pick-carry-place trials at the L3 action boundary —
the same `Pick` and `Place` actions the behaviour tree calls — while recording the
work-piece's pose from the simulator at full physics-publication rate.

The single lever that makes this a measurement of FRICTION: the work-piece is
spawned under a model name that is not in the grasp plugin's `<graspable>` list,
so the plugin loads, runs and never fires. Nothing else about the cell is altered.

Poses are read from Gazebo's own pose feed rather than from TF. TF would give the
pad pose through forward kinematics on the commanded joint state, which is a
software servo's opinion of where the finger is; the simulator's pose feed is
where the finger actually is. That distinction is the whole point when the
question is whether a part slides between the pads.

Run inside the container, against a cell already brought up by ./scripts/sim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import rclpy
import tf2_ros
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState

from cite_interfaces.action import MoveTo, Pick, Place

ZONE = "cell_a"
ARM = "arm_1"
PICK_FRAME = f"{ZONE}__table_pick__surface"
PLACE_FRAME = f"{ZONE}__conveyor_1__infeed"

WORKPIECE_SIZE = 0.05
WORKPIECE_MASS = 0.2
SPAWN_DROP_M = 0.005

#: Geometry the behaviour tree uses. Restated here rather than invented: the
#: trials must exercise the same commanded grasp the shipped cycle does.
GRASP_HEIGHT_M = 0.03
RELEASE_HEIGHT_M = 0.04
APPROACH_M = 0.10
RETREAT_M = 0.12
GRASP_WIDTH_M = 0.045

PAD_LINK = f"{ARM}_left_finger"
PAD_LINK_R = f"{ARM}_right_finger"
#: The pose feed reports a top-level MODEL in the world frame and a LINK in
#: its own model's frame. Verified on the smoke run: arm_1_left_finger sits at
#: (0.207, -0.070, 0.011) at rest, which is nowhere near the cell. Composing
#: through the arm's (constant, bolted) model pose is what makes a pad pose
#: and a work-piece pose comparable at all.
ARM_MODEL = ARM
DRIVE_JOINT = f"{ARM}_drive_joint"

BRING_UP_CEILING_S = 420.0
STEP_CEILING_S = 420.0


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
      <!-- The ONLY contact sensor in the cell, exactly as
           tests/scenarios/pick_and_place.py spawns it. It is passive and changes
           no dynamics, but the grasp plugin's FindGraspable iterates
           ContactSensorData in the world and no pad link carries a sensor -- so
           without this element there is no contact data anywhere and the plugin
           cannot fire whatever the model is called. A control block spawned
           without it measures friction while believing it measures the plugin. -->
      <sensor name="contact" type="contact">
        <contact><collision>collision</collision></contact>
        <always_on>true</always_on>
        <update_rate>100</update_rate>
      </sensor>
    </link>
  </model>
</sdf>
"""


# -----------------------------------------------------------------------------
# Pose recording, straight from the simulator
# -----------------------------------------------------------------------------


@dataclass
class Sample:
    t: float                     # simulation time, seconds
    p: tuple[float, float, float]
    q: tuple[float, float, float, float]   # x, y, z, w


class PoseRecorder:
    """Subscribes to Gazebo's pose feed and keeps the entities we asked for.

    Entity naming in the feed is not something to assume — `--probe` dumps it.
    """

    def __init__(self, world: str, wanted, topic_suffix: str = "dynamic_pose/info"):
        from gz.transport13 import Node as GzNode
        from gz.msgs10.pose_v_pb2 import Pose_V

        self._wanted = wanted if callable(wanted) else (lambda n, s=set(wanted): n in s)
        self._lock = threading.Lock()
        self.tracks: dict[str, list[Sample]] = {}
        #: Latest pose per wanted entity, kept whether or not a trial is
        #: recording. A bolted arm may publish its model pose only at start-up,
        #: and that pose is what every pad measurement is composed through.
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
                    # A repeated header entry can carry the stamp instead; fall
                    # back to the per-pose one when the outer stamp is zero.
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


def quat_rotate(q: tuple[float, float, float, float], v: tuple[float, float, float]):
    """Rotate `v` by `q`."""
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def quat_inv(q):
    return (-q[0], -q[1], -q[2], q[3])


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def compose(parent: Sample, child: Sample) -> Sample:
    """Express a link pose, given in its model's frame, in the world frame."""
    p = quat_rotate(parent.q, child.p)
    return Sample(
        t=child.t,
        p=(parent.p[0] + p[0], parent.p[1] + p[1], parent.p[2] + p[2]),
        q=quat_mul(parent.q, child.q),
    )


def quat_conj_rotate(q: tuple[float, float, float, float], v: tuple[float, float, float]):
    """Rotate `v` by the inverse of quaternion `q` — i.e. express a world vector
    in the frame `q` describes."""
    x, y, z, w = q
    # inverse of a unit quaternion is its conjugate
    x, y, z = -x, -y, -z
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def interpolate(track: list[Sample], t: float) -> Sample | None:
    """Nearest sample at or before `t`. The feed is dense in simulation time, so
    nearest-before is well under a millisecond of error and avoids inventing a
    pose by blending quaternions."""
    if not track:
        return None
    best = None
    for s in track:
        if s.t <= t:
            best = s
        else:
            break
    return best or track[0]


# -----------------------------------------------------------------------------
# The driver
# -----------------------------------------------------------------------------


@dataclass
class TrialResult:
    trial: int
    ok: bool
    note: str = ""
    data: dict = field(default_factory=dict)


class Driver(Node):
    def __init__(self, world: str):
        super().__init__("friction_grasp_harness")
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
        self.release_time: float | None = None

    def _on_joints(self, msg: JointState) -> None:
        if not self.recording_joints or DRIVE_JOINT not in msg.name:
            return
        i = msg.name.index(DRIVE_JOINT)
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.drive_q.append((t, msg.position[i]))

    def sim_now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    # -- plumbing -------------------------------------------------------------

    def start_spinning(self) -> None:
        """Spin in the background for the whole run.

        THE DEFECT THIS EXISTS FOR. Spinning only inside a wait loop leaves the
        action client unserviced while the main thread sits in a `gz` or `ros2`
        subprocess, and — worse — it makes the very first goal race the server's
        discovery. `wait_for_server` returns the instant the server appears in the
        graph, which is before rmw_fastrtps has matched the reply path, and the
        server then logs

            Failed to send goal response ... (timeout): client will not receive
            response

        while going on to execute the goal. The client never learns the goal was
        accepted, abandons it, and the skill server holds the arm against every
        later goal — so one lost response turns a block of trials into a block of
        identical failures. Observed at 213 ms after 'skills are accepting goals'.
        """
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
        """Wait for the skill server, then let the reply path finish matching.

        The settle is a measurement-harness concession and is named as one: there
        is no ROS-level event for 'the action server's response writer has matched
        my response reader', which is the condition that actually has to hold.
        Nothing in the system under test is sequenced by it.
        """
        for client, label in ((self.move_to, "move_to"), (self.pick, "pick"),
                              (self.place, "place")):
            self.spin_until(
                lambda c=client: c.wait_for_server(timeout_sec=1.0) or None,
                BRING_UP_CEILING_S, f"the {label} action server",
            )
        time.sleep(settle_s)

    def resolve(self, frame: str) -> tuple[float, float, float]:
        tf = self.spin_until(
            lambda: (
                self.buffer.lookup_transform("cite_world", frame, rclpy.time.Time())
                if self.buffer.can_transform("cite_world", frame, rclpy.time.Time())
                else None
            ),
            BRING_UP_CEILING_S,
            f"a transform from cite_world to {frame}",
        )
        t = tf.transform.translation
        return (t.x, t.y, t.z)

    def send_goal(self, client, goal, ceiling_s: float, feedback_cb=None):
        """Send an action goal and block until it terminates. Returns the result
        or None if it was rejected."""
        if not client.wait_for_server(timeout_sec=60.0):
            raise TimeoutError(f"no server for {client._action_name}")
        send = client.send_goal_async(goal, feedback_callback=feedback_cb)
        try:
            handle = self.spin_until(
                lambda: send.result() if send.done() else None, 90.0, "goal acceptance"
            )
        except TimeoutError:
            raise TimeoutError(
                f"no acceptance response from {client._action_name} within 90s. "
                "The server may have accepted it and failed to deliver the response; "
                "every later goal on this arm will then be rejected."
            ) from None
        if not handle.accepted:
            return None
        future = handle.get_result_async()
        try:
            wrapped = self.spin_until(
                lambda: future.result() if future.done() else None, ceiling_s,
                "the goal to finish",
            )
        except TimeoutError:
            # Cancel what we abandon. The skill server runs one skill at a time
            # and holds the arm until the goal terminates; walking away from it
            # wedges every later trial. SkillNode::send does the same thing.
            handle.cancel_goal_async()
            time.sleep(5.0)
            raise
        return wrapped.result

    # -- the cycle ------------------------------------------------------------

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
            # PHASE_RETREATING at 0.8 is emitted immediately after the gripper
            # closed and reported holding: the instant the lift begins, which is
            # the reference the slip measurement is taken against.
            fb = msg.feedback
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
# Simulator side-channel: spawn and remove
# -----------------------------------------------------------------------------


def spawn(world: str, name: str, xyz, mu: float) -> subprocess.CompletedProcess:
    path = Path(f"/tmp/{name}.sdf")
    path.write_text(_workpiece_sdf(name, mu))
    return subprocess.run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
         "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2])],
        capture_output=True, text=True, timeout=180,
    )


def remove(world: str, name: str) -> None:
    subprocess.run(
        ["gz", "service", "-s", f"/world/{world}/remove",
         "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
         "--timeout", "5000", "--req", f'name: "{name}" type: MODEL'],
        capture_output=True, text=True, timeout=60,
    )


def model_pose(name: str) -> tuple[float, float, float] | None:
    import re
    out = subprocess.run(["gz", "model", "-m", name, "-p"],
                         capture_output=True, text=True, timeout=30).stdout
    number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    triples = re.findall(rf"\[\s*({number})\s+({number})\s+({number})\s*\]", out)
    if not triples:
        return None
    return tuple(float(v) for v in triples[0])


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


#: A work-piece that has moved this far relative to the pad that holds it is
#: no longer between the jaws: half the 50 mm part's width. Used to decide
#: `held_through_transport` -- see the deviation note in results.md.
OUT_OF_JAWS_MM = 25.0


def compute_metrics(wp: list[Sample], pad: list[Sample], z_rest: float,
                    t_grasp: float | None, t_release: float | None,
                    place_xy: tuple[float, float],
                    arm: Sample | None = None,
                    pad_r: list[Sample] | None = None) -> dict:
    out: dict = {}
    if not wp:
        return {"error": "no work-piece samples"}

    z_max = max(s.p[2] for s in wp)
    out["z_rest"] = z_rest
    out["z_max"] = z_max
    out["lift_m"] = z_max - z_rest
    out["n_samples_wp"] = len(wp)
    out["n_samples_pad"] = len(pad)

    # Speed, from consecutive samples of the simulator's own feed.
    v_max = 0.0
    for a, b in zip(wp, wp[1:]):
        dt = b.t - a.t
        if dt <= 1e-9:
            continue
        d = math.dist(a.p, b.p)
        v_max = max(v_max, d / dt)
    out["v_max_mps"] = v_max

    # Carry window: from the grasp to the release.
    carry = [s for s in wp if (t_grasp is None or s.t >= t_grasp)
             and (t_release is None or s.t <= t_release)]
    out["carry_samples"] = len(carry)
    out["carry_duration_s"] = (carry[-1].t - carry[0].t) if len(carry) > 1 else 0.0

    lifted_seen = any(s.p[2] > z_rest + 0.05 for s in carry)
    out["lifted_during_carry"] = lifted_seen
    out["z_min_during_carry"] = min((s.p[2] for s in carry), default=float("nan"))

    # Slip: work-piece position in the pad frame, relative to the grasp instant.
    # The pad pose arrives in the arm model's frame and is composed into the world
    # here; without that the difference below mixes two frames and reports the
    # arm's own motion as slip.
    slips: list[tuple[float, float]] = []
    if pad and arm is not None and t_grasp is not None:
        ref = None
        for s in carry:
            pad_s = interpolate(pad, s.t)
            if pad_s is None:
                continue
            pad_w = compose(arm, pad_s)
            rel = quat_conj_rotate(
                pad_w.q,
                (s.p[0] - pad_w.p[0], s.p[1] - pad_w.p[1], s.p[2] - pad_w.p[2]),
            )
            if ref is None:
                ref = rel
                continue
            slips.append((s.t - carry[0].t, math.dist(rel, ref) * 1000.0))
    # Twist: how far the work-piece has turned RELATIVE TO THE PAD since the
    # grasp. Added after the smoke run, which showed the part rotating tens of
    # degrees between jaws that themselves barely moved -- a mode a translation
    # figure alone reports as a few millimetres and a cube-shaped scenario
    # assertion cannot see at all. Recorded as a measurement in its own right.
    twists: list[tuple[float, float]] = []
    dists: list[tuple[float, float]] = []
    if pad and arm is not None and t_grasp is not None:
        qref = None
        dref = None
        for s in carry:
            pad_s = interpolate(pad, s.t)
            if pad_s is None:
                continue
            pad_w = compose(arm, pad_s)
            rel_q = quat_mul(quat_inv(pad_w.q), s.q)
            # Rotation-invariant: a scalar distance between a point on the part
            # and a point on the pad. Constant under any rigid grasp, whatever
            # either body's orientation does.
            d = math.dist(s.p, pad_w.p) * 1000.0
            if qref is None:
                qref, dref = rel_q, d
                continue
            delta = quat_mul(quat_inv(qref), rel_q)
            w = max(-1.0, min(1.0, abs(delta[3])))
            twists.append((s.t - carry[0].t, math.degrees(2.0 * math.acos(w))))
            dists.append((s.t - carry[0].t, d - dref))
    out["twist_max_deg"] = max((v for _, v in twists), default=None)
    out["twist_final_deg"] = twists[-1][1] if twists else None
    out["pad_distance_drift_mm_max"] = (
        max((abs(v) for _, v in dists), default=None)
    )

    if slips:
        out["slip_max_mm"] = max(v for _, v in slips)
        out["slip_final_mm"] = slips[-1][1]
        n = len(slips)
        mt = sum(t for t, _ in slips) / n
        mv = sum(v for _, v in slips) / n
        den = sum((t - mt) ** 2 for t, _ in slips)
        out["slip_rate_mm_per_s"] = (
            sum((t - mt) * (v - mv) for t, v in slips) / den if den > 1e-12 else 0.0
        )
    else:
        out["slip_max_mm"] = None
        out["slip_final_mm"] = None
        out["slip_rate_mm_per_s"] = None

    # The part is held all the way to the release if it never leaves the jaws.
    # Stated as a slip bound rather than as a height, because the commanded
    # descent onto the belt takes the part back down to its spawn height and a
    # height test cannot tell that apart from a drop.
    out["held_through_transport"] = (
        out["slip_max_mm"] is not None and out["slip_max_mm"] < OUT_OF_JAWS_MM
    )

    # Jaw separation, measured between the two pads in the simulator rather than
    # inferred from the drive joint. A quantity a physical cell could also be
    # measured for, which the controller's reported position is not.
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
    ap.add_argument("--label", default="run")
    ap.add_argument("--out", default="/workspace/docs/measurements/2026-08-25-friction-grasp/raw")
    ap.add_argument("--mu", type=float, default=1.0)
    ap.add_argument("--graspable", action="store_true",
                    help="spawn as 'workpiece', which the plugin WILL attach — the control")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    rclpy.init()
    driver = Driver(args.world)
    driver.start_spinning()

    if args.probe:
        rec = PoseRecorder(args.world, set())
        for _ in range(40):
            time.sleep(0.25)
        names = sorted(rec.names())
        print(f"topic: {rec.topic}")
        print(f"entities ({len(names)}):")
        for n in names:
            print("  ", n)
        driver.destroy_node()
        rclpy.shutdown()
        return 0

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    pick_xyz = driver.resolve(PICK_FRAME)
    place_xyz = driver.resolve(PLACE_FRAME)
    print(f"pick frame  {PICK_FRAME} at {pick_xyz}", flush=True)
    print(f"place frame {PLACE_FRAME} at {place_xyz}", flush=True)

    print("waiting for the whole stack to be up and matched...", flush=True)
    driver.await_stack()
    print("stack ready", flush=True)

    tracked_prefixes = (ARM_MODEL, PAD_LINK, PAD_LINK_R)
    recorder = PoseRecorder(
        args.world,
        lambda n: n in tracked_prefixes or n == "workpiece" or n.startswith("probe_part_"),
    )
    print(f"recording from {recorder.topic}", flush=True)
    # Give the feed a moment to deliver the bolted arm's model pose, which is
    # published rarely and is what every pad measurement is composed through.
    for _ in range(20):
        time.sleep(0.25)

    arm_p = model_pose(ARM_MODEL)
    arm_world_pose = (
        Sample(t=0.0, p=arm_p, q=(0.0, 0.0, 0.0, 1.0)) if arm_p else None
    )
    print(f"arm model {ARM_MODEL} world position {arm_p}", flush=True)

    rows = []
    for i in range(1, args.trials + 1):
        name = "workpiece" if args.graspable else f"probe_part_{args.label}_{i:03d}"
        print(f"\n=== trial {i}/{args.trials}  model={name} ===", flush=True)
        driver.grasp_time = None
        driver.release_time = None
        driver.drive_q = []

        remove(args.world, name)
        spawn_xyz = (pick_xyz[0], pick_xyz[1],
                     pick_xyz[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M)
        created = spawn(args.world, name, spawn_xyz, args.mu)
        if created.returncode != 0:
            rows.append({"trial": i, "ok": False, "note": f"spawn failed: {created.stderr[-300:]}"})
            continue

        # Let it settle, and confirm from the simulator that it is there.
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

        recorder.start()
        driver.recording_joints = True
        t0 = time.monotonic()
        note = ""
        aborted = False
        try:
            homed = driver.go_home()
            pick_result = driver.do_pick(name)
            picked = pick_result is not None and pick_result.result.code == 0
            holding = bool(pick_result.holding) if pick_result is not None else False
            place_result = driver.do_place() if picked else None
            placed_ok = place_result is not None and place_result.result.code == 0
            driver.go_home()
        except TimeoutError as exc:
            note = f"timeout: {exc}"
            homed = picked = holding = placed_ok = False
            pick_result = place_result = None
            aborted = "no acceptance response" in str(exc)
        wall = time.monotonic() - t0
        driver.recording_joints = False
        # A short tail so the part's settling after release is in the record.
        for _ in range(10):
            time.sleep(0.5)
        recorder.stop()

        tracks = recorder.snapshot()
        if i == 1:
            seen = sorted(recorder.names())
            print(f"  [diag] pose feed carries {len(seen)} entities; "
                  f"matching: {[n for n in seen if 'finger' in n or 'probe_part' in n or 'workpiece' in n]}",
                  flush=True)
            (outdir / f"{args.label}_entities.txt").write_text("\n".join(seen))
        wp_track = tracks.get(name, [])
        pad_track = tracks.get(PAD_LINK, [])
        arm_pose = recorder.latest.get(ARM_MODEL) or arm_world_pose
        if i == 1 and arm_pose is not None and recorder.latest.get(PAD_LINK):
            check = compose(arm_pose, recorder.latest[PAD_LINK])
            print(f"  [diag] arm world pose p={arm_pose.p} q={arm_pose.q}", flush=True)
            print(f"  [diag] pad composed into world: {check.p} "
                  f"(gz model -m {ARM_MODEL} -p said {arm_p})", flush=True)
        try:
            metrics = compute_metrics(
                wp_track, pad_track, z_rest, driver.grasp_time, driver.release_time,
                (place_xyz[0], place_xyz[1]), arm_pose, tracks.get(PAD_LINK_R, []),
            )
        except Exception as exc:   # a broken metric must not cost the block
            metrics = {"error": f"{type(exc).__name__}: {exc}"}

        # Raw samples, so the numbers above can be re-derived rather than believed.
        raw = outdir / f"{args.label}_trial{i:03d}_samples.csv"
        with raw.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "sim_t", "x", "y", "z", "qx", "qy", "qz", "qw"])
            for entity, track in tracks.items():
                for s in track:
                    w.writerow([entity, f"{s.t:.6f}", *[f"{v:.6f}" for v in s.p],
                                *[f"{v:.6f}" for v in s.q]])
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
            "model": name,
            "plugin_can_fire": args.graspable,
            "mu": args.mu,
            "homed": homed,
            "pick_succeeded": picked,
            "pick_reported_holding": holding,
            "place_succeeded": placed_ok,
            "wall_s": round(wall, 1),
            "t_grasp_sim": driver.grasp_time,
            "t_release_sim": driver.release_time,
            "q_at_stall_rad": q_at_stall,
            "note": note,
            **metrics,
        }
        rows.append(row)
        print("  " + json.dumps({k: v for k, v in row.items()
                                 if k not in ("final_xyz",)}, default=str), flush=True)

        recorder.stop()
        remove(args.world, name)
        for _ in range(6):
            time.sleep(0.5)
        if locals().get("aborted"):
            print("ABORTING the block: the arm is wedged behind an undelivered "
                  "goal response, so every later trial would only restate it.",
                  flush=True)
            break

    summary = outdir / f"{args.label}_trials.json"
    summary.write_text(json.dumps(rows, indent=2, default=str))
    print(f"\nwrote {summary}", flush=True)

    driver.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
