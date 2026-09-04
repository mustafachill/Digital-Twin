#!/usr/bin/env python3
"""The shipped cell, as this campaign addresses it: L3 goals in, `controller_state` out.

DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/cell.py`, copied at
commit `ac11d84` -- the `Driver` node, `spin_until`, `send_goal`, `resolve`,
`move_to_frame_offset`, `do_pick`, the work-piece SDF and the spawn/remove probes, and the
load-bearing import order that puts `GZ_PARTITION` into this process's environment BEFORE
anything builds a Gazebo transport node. That directory is FROZEN
(`docs/measurements/README.md` rule 2) and nothing in it is edited from here.

WHAT IS THIS CAMPAIGN'S OWN, and why each had to be added:

  * `ControllerStateRecorder` -- I1 and I2, and the whole decision quantity. The frozen rig
    had no such subscriber; the only `JointTrajectoryControllerState` subscription anywhere
    in this repository is
    `workspace/src/cite_bringup/test/test_trajectory_constraints_launch.py`, and this one
    declares the explicit profile that file declares at `:110-115` for the reason
    `criteria.md` section 4.1 gives.
  * `JointStateRecorder` -- I4, the joint positions from a SECOND publisher, spent by V5's
    second clause and never a reported decision quantity.
  * `do_place`, and `MoveTo`'s two scaling fields reaching the goal -- CARRY and FAST.
  * A `MoveTo` client per LOAD ARM -- CONC. The load arms are load and no verdict is stated
    about them (rule T).

THE RECORDER LIVES IN THIS PROCESS, WHICH LIVES IN THE LAUNCH'S CONTAINER. Discovery from a
second container is partial in this checkout and has already produced a topic that existed
and could not be seen (`docs/operations/troubleshooting.md`); that is why the frozen
ancestor subscribes from inside `run_cell_block.sh`'s own container and why this does too.
`criteria.md` section 8 records it as the reason this campaign drives L3 directly instead of
sampling the two scenarios ADR-0036's revisit bullet names.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from common import ARM, PICK_FRAME, ZONE, controller_state_topic, joint_states_topic

from cite_bringup.gz import gz_environment, plan_for
from cite_bringup.gz import run as gz_run

# V12 and ADR-0042. The partition has to be in this process's environment BEFORE anything
# builds a Gazebo transport node, so this import order is load-bearing and is not tidied. An
# unpartitioned `gz model --list` reaches no world and EXITS 0, so what this prevents is
# plausible silence -- on a campaign whose whole hazard is silence.
os.environ.update(gz_environment(plan_for(ZONE)))

import rclpy  # noqa: E402
import tf2_ros  # noqa: E402
from cite_interfaces.action import MoveTo, Pick, Place  # noqa: E402
from control_msgs.msg import JointTrajectoryControllerState  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.callback_groups import ReentrantCallbackGroup  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import (  # noqa: E402
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import JointState  # noqa: E402

#: `criteria.md` section 4.1. The controller creates its publisher with
#: `rclcpp::SystemDefaultsQoS()`, EVERY policy of which is `*_SYSTEM_DEFAULT` and resolves in
#: the RMW rather than in the controller's source. The subscription therefore declares the
#: explicit profile
#: `workspace/src/cite_bringup/test/test_trajectory_constraints_launch.py:110-115` declares,
#: because two endpoints both leaving reliability to the system are two unknowns rather than
#: one -- and a RELIABLE subscriber is incompatible with a BEST_EFFORT publisher, which
#: subscribes silently and delivers nothing (CLAUDE.md section 10). What is not argued is
#: MEASURED: V4 records the publisher's RESOLVED endpoint QoS and requires a matched
#: publisher and a received message before the block's first goal.
CONTROLLER_STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.VOLATILE,
)

#: `criteria.md` section 5.2 -- the work-piece and the approach, retreat and grasp heights
#: taken verbatim from the frozen 2026-09-02 harness at `ac11d84`. Nothing about the part is
#: a lever here; CARRY carries it because that is what a production motion does.
WORKPIECE_SIZE_M = 0.05
WORKPIECE_MASS_KG = 0.2
WORKPIECE_MU = 1.0
SPAWN_DROP_M = 0.005
GRASP_HEIGHT_M = 0.03
APPROACH_M = 0.10
RETREAT_M = 0.12

#: The width and the release height the SHIPPED line uses, copied from
#: `workspace/src/cite_orchestration/include/cite_orchestration/skill_nodes.hpp` -- `PickAt`'s
#: `grasp_width_m` default of 0.045 and `PlaceAt`'s `release_height_m` default of 0.04, with
#: `require_holding` true. CARRY is registered as "whatever `Pick` and `Place` apply
#: themselves", and what the line applies is these. **This campaign takes no position on the
#: grasp predicate** (`criteria.md` section 0): a `Pick` reporting an empty grasp is an
#: excluded trial and nothing more.
GRASP_WIDTH_M = 0.045
RELEASE_HEIGHT_M = 0.04
PLACE_REQUIRE_HOLDING = True

BRING_UP_CEILING_S = 420.0
STEP_CEILING_S = 420.0
ACCEPT_CEILING_S = 90.0

_NUMBER = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_TRIPLE = re.compile(rf"\[\s*({_NUMBER})\s*[|\s]\s*({_NUMBER})\s*[|\s]\s*({_NUMBER})\s*\]")


# ---------------------------------------------------------------------------
# Gazebo transport, through the one door (V12, ADR-0042)
# ---------------------------------------------------------------------------
def workpiece_sdf(name: str, mu: float = WORKPIECE_MU) -> str:
    """The 50 mm cube the frozen 2026-09-02 harness spawns, copied at `ac11d84`.

    ITS CONTACT SENSOR IS DELIBERATELY ABSENT. That sensor was the 2026-09-01 and 2026-09-02
    campaigns' grasp witness; this campaign measures following error and takes no position on
    the grasp predicate (`criteria.md` section 0), so an instrument nothing here reads would
    be a cost with no reading behind it.
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
    </link>
  </model>
</sdf>
"""


def spawn(name: str, xyz, yaw_rad: float = 0.0, mu: float = WORKPIECE_MU):
    """Create the work-piece at a pose, through `cite_bringup.gz.run` and nothing else."""
    path = Path(f"/tmp/{name}.sdf")
    path.write_text(workpiece_sdf(name, mu))
    return gz_run(
        [
            "ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
            "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2]), "-Y", str(yaw_rad),
        ],
        zone=ZONE,
        timeout=180,
    )


def remove(world: str, name: str):
    return gz_run(
        [
            "gz", "service", "-s", f"/world/{world}/remove",
            "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
            "--timeout", "5000", "--req", f'name: "{name}" type: MODEL',
        ],
        zone=ZONE,
        timeout=60,
    )


def model_pose(name: str) -> dict | None:
    """One model's pose, by subprocess probe. Used to confirm the part appeared."""
    out = gz_run(["gz", "model", "-m", name, "-p"], zone=ZONE, timeout=30).stdout
    triples = _TRIPLE.findall(out)
    if not triples:
        return None
    xyz = tuple(float(v) for v in triples[0])
    rpy = tuple(float(v) for v in triples[1]) if len(triples) > 1 else None
    return {"xyz": xyz, "rpy": rpy, "yaw_rad": rpy[2] if rpy else None, "raw": out}


def gz_topics() -> list[str]:
    """The world's own topic list, through the one door.

    Recorded once per block as a POSITIVE reading that the harness process reached a world at
    all. An unpartitioned probe returns an empty list and exits 0, so an empty answer here is
    itself the V12 finding rather than a fact about the world.
    """
    out = gz_run(["gz", "topic", "-l"], zone=ZONE, timeout=60).stdout
    return [line.strip() for line in out.splitlines() if line.strip().startswith("/")]


# ---------------------------------------------------------------------------
# I1 and I2 -- the decision quantity
# ---------------------------------------------------------------------------
@dataclass
class StateSample:
    """One `controller_state` message, kept whole.

    `t` is the message's OWN `header.stamp`, on the controller's simulated clock (V14). The
    only place a wall clock appears anywhere in this campaign is I9's ratio.
    """

    t: float
    error_positions: list[float] = field(default_factory=list)
    reference_positions: list[float] = field(default_factory=list)
    reference_velocities: list[float] = field(default_factory=list)
    feedback_positions: list[float] = field(default_factory=list)
    feedback_velocities: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "t": self.t,
            "error_positions": self.error_positions,
            "reference_positions": self.reference_positions,
            "reference_velocities": self.reference_velocities,
            "feedback_positions": self.feedback_positions,
            "feedback_velocities": self.feedback_velocities,
        }


class ControllerStateRecorder:
    """I1 and I2 -- the controller's own `state_error_`, as it publishes it.

    THE CENTRAL HAZARD OF THIS CAMPAIGN LIVES HERE. An unmatched subscription, a topic that
    does not exist, a QoS mismatch, a controller that never activated and a rig that ran on
    mock hardware all produce the same empty or zero set, and every one of them reads as "the
    tolerance stayed quiet". So this class counts what it received, reports what it matched,
    and reads the PUBLISHER's resolved QoS off the graph rather than asserting it. Rule L is
    what refuses a trial that this instrument did not observe; V4 is what refuses a block
    whose subscription had not matched before its first goal.

    The buffer is CLEARED at each trial boundary. A block is fourteen trials over many
    minutes at 150 Hz, and keeping every sample of a whole block in memory buys nothing: the
    trial is the domain of every statistic section 7 defines, and the block-level readings
    this class keeps -- `received`, and the first and last stamp for I9 -- survive the clear.
    """

    def __init__(self, node: Node, arm: str, group) -> None:
        self.node = node
        self.arm = arm
        self.topic = controller_state_topic(arm)
        self._lock = threading.Lock()
        self._samples: list[StateSample] = []
        self.received = 0
        self.first_stamp: float | None = None
        self.last_stamp: float | None = None
        self.first_received_wall: float | None = None
        self.last_received_wall: float | None = None
        self.subscription = node.create_subscription(
            JointTrajectoryControllerState,
            self.topic,
            self._on_state,
            CONTROLLER_STATE_QOS,
            callback_group=group,
        )

    def _on_state(self, message: JointTrajectoryControllerState) -> None:
        stamp = message.header.stamp
        t = stamp.sec + stamp.nanosec * 1e-9
        sample = StateSample(
            t=t,
            error_positions=[float(v) for v in message.error.positions],
            reference_positions=[float(v) for v in message.reference.positions],
            reference_velocities=[float(v) for v in message.reference.velocities],
            feedback_positions=[float(v) for v in message.feedback.positions],
            feedback_velocities=[float(v) for v in message.feedback.velocities],
        )
        wall = time.monotonic()
        with self._lock:
            self.received += 1
            if self.first_stamp is None:
                self.first_stamp = t
                self.first_received_wall = wall
            self.last_stamp = t
            self.last_received_wall = wall
            self._samples.append(sample)

    def mark(self) -> int:
        with self._lock:
            return len(self._samples)

    def take(self, first_index: int) -> list[dict]:
        """The trial's samples, and then the buffer is emptied.

        `criteria.md` section 7.1: a trial's samples are the messages received between the
        goal handle reporting accepted and the result arriving. `first_index` is the count at
        acceptance; everything after it, at the moment the result arrived, is the trial.
        """
        with self._lock:
            taken = [sample.as_dict() for sample in self._samples[first_index:]]
            self._samples.clear()
            return taken

    def matched_publishers(self) -> list[dict]:
        """V4 -- the publisher's RESOLVED endpoint QoS, read off the graph.

        Section 4.1 shows the controller offers `SystemDefaultsQoS`, every policy of which
        resolves in the RMW, so the profile this campaign subscribes with is a compatibility
        bet. This is what settles it per block instead of inheriting a sentence from another
        file.
        """
        endpoints = self.node.get_publishers_info_by_topic(self.topic)
        out = []
        for endpoint in endpoints:
            qos = endpoint.qos_profile
            out.append(
                {
                    "node": endpoint.node_name,
                    "namespace": endpoint.node_namespace,
                    "type": endpoint.topic_type,
                    "history": str(qos.history),
                    "depth": qos.depth,
                    "reliability": str(qos.reliability),
                    "durability": str(qos.durability),
                    "liveliness": str(qos.liveliness),
                }
            )
        return out

    def summarise(self) -> dict:
        with self._lock:
            return {
                "topic": self.topic,
                "subscription_qos": {
                    "history": "KEEP_LAST",
                    "depth": 10,
                    "reliability": "RELIABLE",
                    "durability": "VOLATILE",
                    "declared_because": "criteria.md section 4.1 -- the publisher leaves "
                                        "every policy to the RMW, so the subscriber states "
                                        "one rather than adding a second unknown",
                },
                "messages_received": self.received,
                "first_sim_stamp": self.first_stamp,
                "last_sim_stamp": self.last_stamp,
                "first_received_monotonic": self.first_received_wall,
                "last_received_monotonic": self.last_received_wall,
            }


class JointStateRecorder:
    """I4 -- the joint positions from a SECOND publisher, `joint_state_broadcaster`.

    Spent by V5's second clause and NEVER a reported decision quantity. It is bounded: only
    the most recent samples are kept, because the only question asked of it is what it read
    nearest the instant of one trial's peak.
    """

    CAP = 4000

    def __init__(self, node: Node, arm: str, group) -> None:
        self.topic = joint_states_topic(arm)
        self._lock = threading.Lock()
        self.samples: list[tuple[float, list[str], list[float]]] = []
        self.received = 0
        self.subscription = node.create_subscription(
            JointState, self.topic, self._on_joints, 20, callback_group=group
        )

    def _on_joints(self, message: JointState) -> None:
        t = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        with self._lock:
            self.received += 1
            self.samples.append(
                (t, list(message.name), [float(v) for v in message.position])
            )
            if len(self.samples) > self.CAP:
                del self.samples[: len(self.samples) - self.CAP]

    def nearest(self, t: float | None, joints: list[str]) -> dict | None:
        """The `/joint_states` sample nearest `t`, projected onto the controller's joints.

        `criteria.md` V5's second clause: the difference is REPORTED and EXCLUDES NOTHING,
        because the two publishers are sampled independently and are not obliged to coincide
        in time.
        """
        if t is None:
            return None
        with self._lock:
            samples = list(self.samples)
        if not samples:
            return None
        stamp, names, positions = min(samples, key=lambda s: abs(s[0] - t))
        projected = []
        for joint in joints:
            projected.append(positions[names.index(joint)] if joint in names else None)
        return {
            "topic": self.topic,
            "sim_t": stamp,
            "dt_from_peak_s": stamp - t,
            "positions": projected,
        }

    def summarise(self) -> dict:
        return {"topic": self.topic, "messages_received": self.received}


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------
class Driver(Node):
    """One node against the running cell's L3 action servers and its controller state.

    EVERY CLIENT AND EVERY SUBSCRIPTION IS IN ONE REENTRANT CALLBACK GROUP. CONC runs three
    arms at once, so a mutually exclusive group -- the node default -- would serialise the
    three arms' goal and result callbacks against each other and against the recorder's, and
    the load arms would stop being load (CLAUDE.md section 10). Nothing in this class blocks
    inside a callback: every wait is a poll from a harness thread on a future the executor is
    completing.
    """

    def __init__(self, load_arms: tuple[str, ...], name: str = "following_error_harness"):
        super().__init__(name)
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.group = ReentrantCallbackGroup()
        base = f"/cite/{ZONE}/{ARM}"
        self.namespace_ = base
        self.move_to = ActionClient(self, MoveTo, f"{base}/move_to", callback_group=self.group)
        self.pick = ActionClient(self, Pick, f"{base}/pick", callback_group=self.group)
        self.place = ActionClient(self, Place, f"{base}/place", callback_group=self.group)
        self.load_move_to = {
            arm: ActionClient(
                self,
                MoveTo,
                f"/cite/{ZONE}/{arm}/move_to",
                callback_group=self.group,
            )
            for arm in load_arms
        }
        self.states = ControllerStateRecorder(self, ARM, self.group)
        self.joints = JointStateRecorder(self, ARM, self.group)
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer, self)

    # -- plumbing ------------------------------------------------------------
    def sim_now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def start_spinning(self) -> None:
        # Four arms' action callbacks, two subscriptions and a TF listener. Sized so that a
        # load arm's result callback cannot be waiting behind arm_1's.
        self._executor = MultiThreadedExecutor(num_threads=8)
        self._executor.add_node(self)
        self._spin = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin.start()

    def spin_until(self, predicate, ceiling_s: float, what: str):
        end = time.monotonic() + ceiling_s
        result = predicate()
        while result is None and time.monotonic() < end:
            time.sleep(0.02)
            result = predicate()
        if result is None:
            raise TimeoutError(f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def await_stack(self, ceiling_s: float = BRING_UP_CEILING_S) -> dict:
        """V13's second clause -- no arm's L3 server was waited on past the rig's ceiling.

        The cell's readiness EVENT is `run_cell_block.sh`'s business (I5, ADR-0047, P4);
        this is the harness's own check that the servers it is about to address are the ones
        that announced. It records the wait, so that a block which only just made the ceiling
        is visible rather than indistinguishable from one that was ready at once.
        """
        waits = {}
        clients = [("move_to", self.move_to), ("pick", self.pick), ("place", self.place)]
        clients += [(f"{arm}/move_to", client) for arm, client in self.load_move_to.items()]
        for label, client in clients:
            started = time.monotonic()
            self.spin_until(
                lambda c=client: c.wait_for_server(timeout_sec=1.0) or None,
                ceiling_s,
                f"the {label} action server",
            )
            waits[label] = time.monotonic() - started
        return {
            "server_wait_s": waits,
            "ceiling_s": ceiling_s,
            "within_ceiling": all(value < ceiling_s for value in waits.values()),
        }

    def resolve(self, frame: str):
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

    # -- one goal, with its samples ------------------------------------------
    def run_goal(
        self, client, goal, ceiling_s: float = STEP_CEILING_S, record_samples: bool = True
    ) -> dict:
        """Send one L3 goal and return everything section 5.3 needs to judge it.

        A TRIAL IS ONE L3 GOAL. The sample window opens when the handle reports ACCEPTED and
        closes when the result arrives -- section 7.1's own definition, implemented as the
        recorder's count at those two instants.

        BOTH SYMBOLS THE RESULT CARRIES ARE RETURNED, and neither is derived from the other:
        the `action_msgs/GoalStatus` value and the `ResultCode` payload. Section 5.3 requires
        both to say SUCCESS for a trial to be healthy, and requires a DISAGREEMENT between
        them to be reported in full and never resolved by reading one of the two.

        `record_samples=False` IS WHAT KEEPS THE LOAD ARMS OUT OF arm_1'S RECORD, and it is
        not an optimisation. The recorder holds ONE buffer -- arm_1's, because arm_1 is the
        only decision quantity (rule T) -- and `take` empties it. A load arm driving its own
        goals through this method with sampling on would mark and drain that buffer under
        arm_1's feet, and arm_1's CONC trials would silently record a fraction of their
        samples: rule L would report an instrument loss caused by the harness, at exactly the
        condition CONC exists to measure.
        """
        record: dict = {
            "action": client._action_name,
            "accepted": None,
            "status": None,
            "result_code": None,
            "detail": None,
            "timed_out": False,
            "error": None,
            "accept_sim_t": None,
            "result_sim_t": None,
            "accept_wall": time.monotonic(),
        }
        samples: list[dict] = []
        if not client.wait_for_server(timeout_sec=60.0):
            record["error"] = f"no server for {client._action_name}"
            return {"goal": record, "samples": samples}

        send = client.send_goal_async(goal)
        try:
            handle = self.spin_until(
                lambda: send.result() if send.done() else None,
                ACCEPT_CEILING_S,
                "goal acceptance",
            )
        except TimeoutError:
            record["error"] = (
                f"no acceptance response from {client._action_name} within "
                f"{ACCEPT_CEILING_S:.0f}s"
            )
            record["timed_out"] = True
            return {"goal": record, "samples": samples}

        record["accepted"] = bool(handle.accepted)
        if not handle.accepted:
            record["error"] = "the goal was refused"
            return {"goal": record, "samples": samples}

        first_index = self.states.mark() if record_samples else None
        record["accept_sim_t"] = self.sim_now()
        future = handle.get_result_async()
        try:
            wrapped = self.spin_until(
                lambda: future.result() if future.done() else None,
                ceiling_s,
                "the goal to finish",
            )
        except TimeoutError:
            record["result_sim_t"] = self.sim_now()
            record["timed_out"] = True
            record["error"] = f"no result within {ceiling_s:.0f}s"
            if record_samples:
                samples = self.states.take(first_index)
            handle.cancel_goal_async()
            return {"goal": record, "samples": samples}

        record["result_sim_t"] = self.sim_now()
        if record_samples:
            samples = self.states.take(first_index)
        record["status"] = int(wrapped.status)
        payload = wrapped.result
        record["result_code"] = int(payload.result.code)
        record["detail"] = str(payload.result.detail)
        record["result_wall"] = time.monotonic()
        record["duration_wall_s"] = record["result_wall"] - record["accept_wall"]
        if hasattr(payload, "position_error_m"):
            record["position_error_m"] = float(payload.position_error_m)
        if hasattr(payload, "holding"):
            record["holding"] = bool(payload.holding)
        return {"goal": record, "samples": samples}

    # -- the goals this campaign sends ---------------------------------------
    def home_goal(self, velocity_scaling: float, acceleration_scaling: float):
        goal = MoveTo.Goal()
        goal.named_configuration = "home"
        goal.velocity_scaling = velocity_scaling
        goal.acceleration_scaling = acceleration_scaling
        return goal

    def frame_goal(self, frame: str, z_m: float, velocity_scaling: float,
                   acceleration_scaling: float):
        """A pose stated IN `frame`, tool axis pointing down.

        The orientation is `Pick`'s own convention -- a half turn about x, which puts the
        tool z along the frame's -z -- copied from the frozen 2026-09-02 harness at
        `ac11d84`, so a pose built here and a pose `Pick` builds differ only in the offset.
        """
        goal = MoveTo.Goal()
        goal.target.header.frame_id = frame
        goal.target.pose.position.z = z_m
        goal.target.pose.orientation.x = 1.0
        goal.target.pose.orientation.w = 0.0
        goal.velocity_scaling = velocity_scaling
        goal.acceleration_scaling = acceleration_scaling
        return goal

    def pick_goal(self, workpiece: str):
        goal = Pick.Goal()
        goal.object_pose.header.frame_id = PICK_FRAME
        goal.object_pose.pose.position.z = GRASP_HEIGHT_M
        goal.object_pose.pose.orientation.x = 1.0
        goal.object_pose.pose.orientation.w = 0.0
        goal.workpiece_id = workpiece
        goal.approach_distance_m = APPROACH_M
        goal.retreat_distance_m = RETREAT_M
        goal.grasp_width_m = GRASP_WIDTH_M
        return goal

    def place_goal(self, frame: str):
        goal = Place.Goal()
        goal.target_pose.header.frame_id = frame
        goal.target_pose.pose.position.z = RELEASE_HEIGHT_M
        goal.target_pose.pose.orientation.x = 1.0
        goal.target_pose.pose.orientation.w = 0.0
        goal.approach_distance_m = APPROACH_M
        goal.retreat_distance_m = RETREAT_M
        goal.require_holding = PLACE_REQUIRE_HOLDING
        return goal


# ---------------------------------------------------------------------------
# CONC -- the load arms
# ---------------------------------------------------------------------------
class LoadArm:
    """One load arm, shuttling CRUISE's shape on its OWN station frames, continuously.

    `criteria.md` section 3's amendment. The frames come from the generated topology, so
    their reachability is evidenced by `continuous_line` rather than assumed here -- AND IF A
    LOAD ARM'S GOAL FAILS ANYWAY, THAT IS REPORTED AND IS NOT A FINDING ABOUT arm_1
    (rule T).

    What it publishes for arm_1's record is the set of intervals, in the CONTROLLER'S OWN
    SIMULATED CLOCK, over which it held an accepted and unfinished `MoveTo` goal. `measure.py`
    intersects those with arm_1's moving window to decide `load_active`.
    """

    def __init__(self, driver: Driver, arm: str, frames: dict) -> None:
        self.driver = driver
        self.arm = arm
        self.client = driver.load_move_to[arm]
        self.pick_frame = frames["pick_frame"]
        self.place_frame = frames["place_frame"]
        self._lock = threading.Lock()
        self.intervals: list[tuple[float, float]] = []
        self.goals_sent = 0
        self.goals_accepted = 0
        #: Whether this arm has ever had a goal ACCEPTED. `measure.py` waits on it before
        #: arm_1's first CONC goal, because the 2026-09-04 shakedown showed arm_2 still
        #: PLANNING its first goal while arm_1's first CONC window ran -- `sent 1, accepted 0`,
        #: and `load_active` false for a reason that was the harness's starting order rather
        #: than the load condition. Waited on as an EVENT, with a ceiling, never slept for.
        self.goals_succeeded = 0
        self.failures: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sequence(self):
        return [
            self.driver.home_goal(0.0, 0.0),
            self.driver.frame_goal(self.pick_frame, APPROACH_M, 0.0, 0.0),
            self.driver.frame_goal(self.place_frame, APPROACH_M, 0.0, 0.0),
            self.driver.home_goal(0.0, 0.0),
        ]

    def _run(self) -> None:
        while not self._stop.is_set():
            for goal in self._sequence():
                if self._stop.is_set():
                    return
                started = self.driver.sim_now()
                with self._lock:
                    self.goals_sent += 1
                try:
                    outcome = self.driver.run_goal(
                        self.client, goal, STEP_CEILING_S, record_samples=False
                    )
                except Exception as error:  # a load arm never fails arm_1's trial
                    with self._lock:
                        self.failures.append({"arm": self.arm, "error": repr(error)})
                    continue
                record = outcome["goal"]
                ended = self.driver.sim_now()
                with self._lock:
                    if record.get("accepted"):
                        self.goals_accepted += 1
                        self.intervals.append((started, ended))
                    if record.get("result_code") == 0:
                        self.goals_succeeded += 1
                    else:
                        self.failures.append(
                            {
                                "arm": self.arm,
                                "accepted": record.get("accepted"),
                                "status": record.get("status"),
                                "result_code": record.get("result_code"),
                                "detail": record.get("detail"),
                                "error": record.get("error"),
                            }
                        )

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, join_s: float = 60.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=join_s)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "arm": self.arm,
                "pick_frame": self.pick_frame,
                "place_frame": self.place_frame,
                "goals_sent": self.goals_sent,
                "goals_accepted": self.goals_accepted,
                "goals_succeeded": self.goals_succeeded,
                "failures": list(self.failures),
                "intervals": list(self.intervals),
            }


def covers(intervals: list[tuple[float, float]], start: float, end: float) -> bool:
    """Whether the UNION of `intervals` covers every instant of `[start, end]`.

    `criteria.md` section 3: `load_active` is true iff both load arms "had an accepted,
    unfinished `MoveTo` goal for the whole of arm_1's moving window". That is a statement
    about every instant of the window, so it is the union that has to cover it and not any
    single goal -- a load arm's own goal is comparable in length to arm_1's, so requiring one
    goal to span the window would make the flag structurally false and CONC1 unevaluable by
    construction.
    """
    if end < start:
        return False
    ordered = sorted(intervals)
    reached = start
    for low, high in ordered:
        if low > reached:
            return False
        reached = max(reached, high)
        if reached >= end:
            return True
    return reached >= end


def covered_fraction(intervals: list[tuple[float, float]], start: float, end: float) -> float:
    """How much of `[start, end]` the union covers. Reported beside `load_active`.

    A flag that is false says nothing about how nearly it was true, and CONC1 has to report
    the count of trials that do not carry `load_active`; this is what lets the write-up say
    whether those were gaps of milliseconds or of the whole window.
    """
    span = end - start
    if span <= 0:
        return 0.0
    total = 0.0
    reached = start
    for low, high in sorted(intervals):
        if high <= reached:
            continue
        total += max(0.0, min(high, end) - max(low, reached))
        reached = max(reached, high)
        if reached >= end:
            break
    return max(0.0, min(1.0, total / span))


def spawn_pose(pick_xyz) -> tuple[float, float, float]:
    """CARRY's spawn pose, copied from the frozen 2026-09-02 harness at `ac11d84`."""
    return (
        pick_xyz[0],
        pick_xyz[1],
        pick_xyz[2] + WORKPIECE_SIZE_M / 2.0 + SPAWN_DROP_M,
    )
