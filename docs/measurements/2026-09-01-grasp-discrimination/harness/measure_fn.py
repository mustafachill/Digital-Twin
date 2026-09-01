#!/usr/bin/env python3
"""FN arm — a real grasp, and what the shipped predicate says about it.

`criteria.md` Q1, Q4, D1, D2, D3, D6. The false-negative direction: the band
`(w_cmd, w_cmd + 2*tolerance(q_reached))` inside which a genuine grasp is reported empty.
ADR-0052 extracts a first sample of this from the hull-grasp campaign's committed raw,
n = 47, taken for another question with no threshold registered for this one. This is the
first-class measurement.

THE ONE LEVER IS `Pick.Goal.grasp_width_m`, cycled over the four registered commands
within a single bring-up (`criteria.md` 6.1). `docs/measurements/README.md` requires
interleaving rather than blocking, and unlike the hull-grasp campaign's lever this one is
a field on a goal message rather than a rebuild, so it can actually be interleaved.

FIVE INSTRUMENTS, and the reason there are five rather than one is that the value the
predicate consumes is not directly observable from outside the skill server:

  I1  the server's own report line, scraped from the block log      (0.1 mm)
  I2  `q_at_stall_rad` off /joint_states, through the shipped map   (full precision)
  I3  `Pick.Result` -- code, holding, and the detail string         (full on failure)
  I4  a `Grasp` at the same command against the jaws as they stand  (full, typed)
  I5  the work-piece's own contact sensor -- was a part in the jaws  (V2)

I4 is a DIFFERENT EVENT from the close I1-I3 report and is never substituted for them.
It exists because `Grasp.Result.reached_width_m` IS `gripper_width_for(result->position)`
and `Grasp.Result.holding` IS `gripper_is_holding(...)` -- the only typed, full-precision
read of the predicate's own inputs and output that this system offers.

Derived from `../../2026-09-01-hull-grasp/harness/measure_hull_grasp.py`. That harness is
frozen (`../../README.md`), so it is copied rather than imported or edited.

Runs INSIDE the container, against a cell `run_fn_block.sh` has already brought up.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ZONE = "cell_a"
ARM = "arm_1"

# The partition must be in this process's environment BEFORE gz.transport13 builds a node,
# and every `gz` subprocess needs it too (ADR-0042). One door.
from cite_bringup.gz import gz_environment, plan_for  # noqa: E402

os.environ.update(gz_environment(plan_for(ZONE)))

import rclpy  # noqa: E402
import tf2_ros  # noqa: E402
from cite_interfaces.action import Grasp, MoveTo, Pick  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402

from cite_bringup import plan as bringup_plan  # noqa: E402

DRIVE_JOINT = f"{ARM}_drive_joint"
PICK_FRAME = "cell_a__table_pick__surface"

#: `criteria.md` 5.1, in metres, in the order they are cycled.
COMMANDS_M = (0.042, 0.045, 0.047, 0.048)

WORKPIECE_SIZE = 0.05
WORKPIECE_MASS = 0.2
SPAWN_DROP_M = 0.005
GRASP_HEIGHT_M = 0.03
APPROACH_M = 0.10
RETREAT_M = 0.12
RELEASE_WIDTH_M = 0.080
MAX_EFFORT_N = 60.0

BRING_UP_CEILING_S = 420.0
STEP_CEILING_S = 420.0

#: I1. The format string is `skill_server.cpp:2141-2149` and is matched verbatim, so a
#: change to it breaks this harness loudly instead of returning silence.
REPORT = re.compile(
    r"gripper: commanded ([-+0-9.]+) mm, reached ([-+0-9.]+) mm, "
    r"stalled=(true|false), reached_goal=(true|false), effort=([-+0-9.]+) -> (holding|empty)"
)


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
      <!-- I5, and it is the instrument criteria.md V2 turns on. Passive: ADR-0029
           removed the only consumer of contact data in this cell, so nothing acts on
           it and its presence changes no grasp. -->
      <sensor name="contact" type="contact">
        <contact><collision>collision</collision></contact>
        <always_on>true</always_on>
        <update_rate>200</update_rate>
      </sensor>
    </link>
  </model>
</sdf>
"""


def _gz_env() -> dict:
    return dict(os.environ)


def spawn(name: str, xyz, mu: float) -> subprocess.CompletedProcess:
    path = Path(f"/tmp/{name}.sdf")
    path.write_text(_workpiece_sdf(name, mu))
    return subprocess.run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
         "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2])],
        capture_output=True, text=True, timeout=180, env=_gz_env(),
    )


def remove(world: str, name: str) -> None:
    subprocess.run(
        ["gz", "service", "-s", f"/world/{world}/remove",
         "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
         "--timeout", "5000", "--req", f'name: "{name}" type: MODEL'],
        capture_output=True, text=True, timeout=60, env=_gz_env(),
    )


def model_pose(name: str):
    out = subprocess.run(
        ["gz", "model", "-m", name, "-p"], capture_output=True, text=True,
        timeout=30, env=_gz_env(),
    ).stdout
    number = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    triples = re.findall(rf"\[\s*({number})\s+({number})\s+({number})\s*\]", out)
    if not triples:
        return None
    return tuple(float(v) for v in triples[0])


@dataclass
class ContactSample:
    t: float
    finger_points: int
    total_points: int


class ContactRecorder:
    """I5 — the work-piece's own contact sensor. Built per trial and dies with the part.

    It answers exactly one question, which is `criteria.md` V2's: was anything of the
    gripper touching the part while the jaws stalled? Without it, "a real grasp reported
    empty" would be asserted from the reached width alone, which is the quantity under
    measurement. A witness that is not the thing being measured is the point.
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
                self.samples.append(ContactSample(t=t, finger_points=finger, total_points=total))

        self.subscribed = self._node.subscribe(Contacts, self.topic, on_contacts)

    def snapshot(self) -> list[ContactSample]:
        with self._lock:
            return list(self.samples)


class Driver(Node):
    def __init__(self) -> None:
        super().__init__("fn_grasp_discrimination_harness")
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        base = f"/cite/{ZONE}/{ARM}"
        self.move_to = ActionClient(self, MoveTo, f"{base}/move_to")
        self.pick = ActionClient(self, Pick, f"{base}/pick")
        self.grasp = ActionClient(self, Grasp, f"{base}/grasp")
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer, self)
        self.drive_q: list[tuple[float, float]] = []
        self.create_subscription(JointState, f"{base}/joint_states", self._on_joints, 20)
        self.closing_time: float | None = None
        self.grasp_time: float | None = None

    def _on_joints(self, message: JointState) -> None:
        if DRIVE_JOINT not in message.name:
            return
        index = message.name.index(DRIVE_JOINT)
        t = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
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
                lambda: send.result() if send.done() else None, 90.0, "goal acceptance")
        except TimeoutError:
            raise TimeoutError(
                f"no acceptance response from {client._action_name} within 90s") from None
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


class Predicate:
    """The shipped predicate, through `predicate_eval`. Identical to the FP arm's."""

    def __init__(self, executable: Path, travel: dict) -> None:
        self.command = [str(executable)] + [f"--{k}={v!r}" for k, v in travel.items()]
        self.process = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def _ask(self, request: str) -> str:
        self.process.stdin.write(request + "\n")
        self.process.stdin.flush()
        answer = self.process.stdout.readline()
        if not answer:
            raise RuntimeError(f"predicate_eval died answering {request!r}")
        return answer.strip()

    def width(self, q: float) -> float:
        return float(self._ask(f"width {q!r}"))

    def position(self, width_m: float) -> float:
        return float(self._ask(f"position {width_m!r}"))

    def tolerance(self, q: float) -> float:
        return float(self._ask(f"tolerance {q!r}"))

    def holding(self, commanded_m: float, q: float, stalled: bool, goal: bool) -> bool:
        return self._ask(f"holding {commanded_m!r} {q!r} {int(stalled)} {int(goal)}") == "1"

    def close(self) -> None:
        self.process.stdin.close()
        self.process.wait(timeout=30)


def travel_from_plan(manager) -> dict:
    keys = manager.gripper
    return {
        "open_position": float(keys["gripper_open_position"]),
        "closed_position": float(keys["gripper_closed_position"]),
        "drive_pivot_y_m": float(keys["gripper_drive_pivot_y_m"]),
        "drive_pivot_z_m": float(keys["gripper_drive_pivot_z_m"]),
        "finger_offset_y_m": float(keys["gripper_finger_offset_y_m"]),
        "finger_offset_z_m": float(keys["gripper_finger_offset_z_m"]),
        "pad_inset_m": float(keys["gripper_pad_inset_m"]),
        "tip_link_z_m": float(keys["gripper_tip_link_z_m"]),
        "pad_face_centre_z_m": float(keys["gripper_pad_face_centre_z_m"]),
        "goal_tolerance": float(keys["gripper_goal_tolerance_rad"]),
    }


@dataclass
class LogCursor:
    """I1 — read the server's report lines for ONE action, not for the whole block.

    The block log accumulates a line per close, and a trial issues three closes (the
    Pick, the I4 re-close, the release). Attributing them by position in the file would
    break the first time a retry inserted one, so each action's segment is bracketed by
    the file's size before and after it.
    """

    path: Path
    offset: int = 0
    reports: list = field(default_factory=list)

    def mark(self) -> None:
        self.offset = self.path.stat().st_size if self.path.exists() else 0

    def collect(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", errors="replace") as handle:
            handle.seek(self.offset)
            text = handle.read()
        found = []
        for match in REPORT.finditer(text):
            found.append(
                {
                    "commanded_mm": float(match.group(1)),
                    "reached_mm": float(match.group(2)),
                    "stalled": match.group(3) == "true",
                    "reached_goal": match.group(4) == "true",
                    "effort_n": float(match.group(5)),
                    "verdict": match.group(6),
                }
            )
        return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--trials", type=int, default=16)
    parser.add_argument("--world", default=ZONE)
    parser.add_argument("--mu", type=float, default=1.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sim-log", required=True)
    parser.add_argument(
        "--eval", default=str(Path(__file__).resolve().parent / "predicate_eval"))
    arguments = parser.parse_args()

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)

    document = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
    manager = next(entry for entry in document.controller_managers if entry.asset == ARM)
    predicate = Predicate(Path(arguments.eval), travel_from_plan(manager))
    cursor = LogCursor(Path(arguments.sim_log))

    # V1 — the geometry that actually ran, read off the description the RUNNING cell
    # publishes rather than off the model file. `criteria.md` expects 13 hull references.
    running = subprocess.run(
        ["ros2", "param", "get", f"/cite/{ZONE}/{ARM}/description_publisher",
         "robot_description"],
        capture_output=True, text=True, timeout=300,
    ).stdout
    geometry = {
        "hull_collision_refs": running.count(
            "cite_description/meshes/collision/xarm5/convex_hull"),
        "vendor_visual_refs": running.count("xarm_description/meshes/xarm5/visual"),
        "description_chars": len(running),
    }
    geometry["geometry_verified"] = geometry["hull_collision_refs"] == 13
    (out / f"{arguments.label}_geometry.json").write_text(json.dumps(geometry, indent=2))
    print(f"V1: {geometry}")
    if not geometry["geometry_verified"]:
        print("ABORT: the running description does not carry the shipped hull geometry.")
        return 3

    rclpy.init()
    driver = Driver()
    driver.start_spinning()
    driver.await_stack()
    pick_xyz = driver.resolve(PICK_FRAME)
    print(f"pick frame at {pick_xyz}")

    rows = []
    aborted = False
    for index in range(1, arguments.trials + 1):
        width_m = COMMANDS_M[(index - 1) % len(COMMANDS_M)]
        name = f"gd_part_{arguments.label}_{index:03d}"
        driver.closing_time = None
        driver.grasp_time = None
        driver.drive_q = []
        started = time.monotonic()
        row: dict = {
            "trial": index,
            "label": arguments.label,
            "commanded_width_m": width_m,
            "model": name,
            "mu": arguments.mu,
        }
        recorder = None
        try:
            row["homed"] = driver.go_home()
            remove(arguments.world, name)
            spawn_xyz = (pick_xyz[0], pick_xyz[1],
                         pick_xyz[2] + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M)
            created = spawn(name, spawn_xyz, arguments.mu)
            if created.returncode != 0:
                raise RuntimeError(f"spawn failed: {created.stderr[-300:]}")
            appeared = None
            for _ in range(60):
                appeared = model_pose(name)
                if appeared is not None:
                    break
                time.sleep(0.5)
            if appeared is None:
                raise RuntimeError("the work-piece never appeared")
            time.sleep(5.0)
            recorder = ContactRecorder(arguments.world, name)
            time.sleep(1.0)

            cursor.mark()
            pick_result = driver.do_pick(name, width_m)
            row["pick_reports"] = cursor.collect()

            picked = pick_result is not None and pick_result.result.code == 0
            row.update(
                {
                    "pick_accepted": pick_result is not None,
                    "pick_result_code": pick_result.result.code if pick_result else None,
                    "pick_detail": pick_result.result.detail if pick_result else None,
                    "pick_reported_holding": bool(pick_result.holding) if pick_result else None,
                    "pick_succeeded": picked,
                    "reached_grasping_phase": driver.closing_time is not None,
                    "reached_retreating_phase": driver.grasp_time is not None,
                }
            )

            # I2. The stall is the last drive-joint sample at or before the moment the
            # close ended -- `PHASE_RETREATING` when the Pick got that far, and the end
            # of the closing window otherwise, which is the case a false negative
            # produces and which nothing has had to read before.
            boundary = driver.grasp_time
            if boundary is None:
                boundary = driver.sim_now()
            before = [q for t, q in driver.drive_q if t <= boundary]
            q_at_stall = before[-1] if before else None
            row["q_at_stall_rad"] = q_at_stall
            row["drive_samples"] = len(driver.drive_q)
            if q_at_stall is not None:
                reached = predicate.width(q_at_stall)
                threshold = 2.0 * predicate.tolerance(q_at_stall)
                margin = reached - width_m
                row.update(
                    {
                        "reached_width_m_i2": reached,
                        "threshold_m_i2": threshold,
                        "margin_m_i2": margin,
                        "ratio_i2": margin / threshold if threshold else None,
                        "predicate_i2": predicate.holding(width_m, q_at_stall, True, False),
                    }
                )

            # I4 — a typed, full-precision read of the predicate's own inputs and output,
            # on the jaws as they stand. A DIFFERENT EVENT from the close above.
            cursor.mark()
            confirm = driver.do_grasp(width_m, expect_object=False)
            row["i4_reports"] = cursor.collect()
            if confirm is not None:
                row.update(
                    {
                        "i4_result_code": confirm.result.code,
                        "i4_reached_width_m": float(confirm.reached_width_m),
                        "i4_holding": bool(confirm.holding),
                        "i4_effort_n": float(confirm.measured_effort_n),
                    }
                )

            # I5 (V2). The window is the closing phase; contacts are counted over every
            # message the sensor produced up to the end of the close.
            samples = recorder.snapshot()
            in_window = [
                s for s in samples
                if driver.closing_time is None or s.t >= driver.closing_time - 1.0
            ]
            row.update(
                {
                    "contact_messages": recorder.message_count,
                    "contact_messages_in_window": len(in_window),
                    "finger_contact_points_max": max((s.finger_points for s in in_window),
                                                     default=0),
                    "finger_contact_messages": sum(1 for s in in_window if s.finger_points),
                }
            )

            # Release, so the next trial starts from an open gripper whatever happened.
            cursor.mark()
            driver.do_grasp(RELEASE_WIDTH_M, expect_object=False)
            row["release_reports"] = cursor.collect()
            row["ok"] = True
        except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    trial {index} failed: {exc}")
            aborted = "no acceptance response" in str(exc)
        finally:
            try:
                remove(arguments.world, name)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2.0)

        row["wall_s"] = round(time.monotonic() - started, 1)
        rows.append(row)
        (out / f"{arguments.label}_trials.json").write_text(
            json.dumps(rows, indent=2, default=str))
        print(
            f"[{index}/{arguments.trials}] w_cmd={width_m*1000:.1f} mm "
            f"ratio={row.get('ratio_i2')} predicate={row.get('predicate_i2')} "
            f"pick_code={row.get('pick_result_code')} ({row['wall_s']}s)"
        )
        if aborted:
            print("ABORTING the block: the arm is wedged behind an undelivered goal response.")
            break

    try:
        driver.go_home()
    except Exception:  # noqa: BLE001
        pass
    driver.destroy_node()
    rclpy.shutdown()
    predicate.close()
    print(f"wrote {out / f'{arguments.label}_trials.json'}: {len(rows)} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
