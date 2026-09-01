#!/usr/bin/env python3
"""FP arm — a stall on nothing, and what the shipped predicate says about it.

`criteria.md` Q2, D5, rule N. This is the direction ADR-0052 records as **never
measured**, and the one that ends with the line carrying a part it does not have.

WHY ORDINARY MOCK HARDWARE CANNOT PRODUCE IT, which is the whole reason this rig exists.
`mock_components/GenericSystem` mirrors the command into the state, so a close on empty
jaws ARRIVES where it was sent: `reached_goal` is true, `stalled` is false, and
`gripper_is_holding`'s FIRST condition rejects it before any threshold is consulted. The
producer of a false positive is a joint that stops SHORT of its command with nothing
between the pads, and `cite_test_hardware::JointStopSystem` (ADR-0040) is the fixture
that makes one on demand: it clamps a named joint's position STATE at a declared value
while the command runs on past it, and it differentiates the clamped position so the
controller sees the zero velocity its stall detector needs.

WHAT THIS RIG IS NOT. It is a synthetic stop at a position this harness chose, not a
fouled finger, and `criteria.md` section 8 records that. It answers what the predicate
does with such a stall. It does not say where a real jam stops.

Runs INSIDE the container; `run_fp.sh` is the door. No Gazebo, no work-piece, no physics.

    python3 measure_fp.py --out /workspace/docs/measurements/2026-09-01-grasp-discrimination/raw
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree

import rclpy
from control_msgs.action import GripperCommand
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState

from cite_bringup import plan as bringup_plan

ZONE = "cell_a"
ARM = "arm_1"
DRIVE_JOINT = f"{ARM}_drive_joint"

#: `criteria.md` 5.2. Asserted rather than substituted for the production plugin: if the
#: L0 backend has changed, this rig is no longer substituting what it thinks it is (V7).
PRODUCTION_PLUGIN = "gz_ros2_control/GazeboSimSystem"
FIXTURE_PLUGIN = "cite_test_hardware/JointStopSystem"
MOCK_PLUGIN = "mock_components/GenericSystem"

#: `criteria.md` 5.2, the twelve stop widths in mm, bracketing the section 2 band edge of
#: 47.1215 mm at +/- 0.02 mm. Written here in the order they are cycled.
STOP_WIDTHS_MM = (45.5, 46.0, 46.5, 47.0, 47.05, 47.10, 47.15, 47.20, 47.5, 48.0, 49.0, 50.0)
REPEATS = 3

#: The command is held fixed at the shipped default throughout; the stop is the lever.
COMMANDED_WIDTH_M = 0.045
MAX_EFFORT_N = 60.0

#: `stop_lower_rad`. The plugin refuses on its first read if the joint starts outside its
#: declared stops -- "a stop that has to move the arm to take effect manufactures the
#: fault it is supposed to detect" -- and the drive joint starts at `open_position`, 0.0.
#: -1.0 rad brackets that with room to spare and is never approached from below.
STOP_LOWER_RAD = -1.0

STARTUP_CEILING_S = 180.0
GOAL_CEILING_S = 90.0


# ---------------------------------------------------------------------------
# The shipped predicate, and the shipped linkage map
# ---------------------------------------------------------------------------
class Predicate:
    """A conversation with `predicate_eval`, which compiles the shipped `gripper.cpp`."""

    def __init__(self, executable: Path, travel: dict[str, float]) -> None:
        self.command = [str(executable)] + [f"--{k}={v!r}" for k, v in travel.items()]
        self.process = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1
        )

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

    def holding(self, commanded_m: float, q: float, stalled: bool, reached_goal: bool) -> bool:
        return self._ask(f"holding {commanded_m!r} {q!r} {int(stalled)} {int(reached_goal)}") == "1"

    def close(self) -> None:
        self.process.stdin.close()
        self.process.wait(timeout=30)


def travel_from_plan(manager) -> dict[str, float]:
    """The ten travel parameters as the SKILL SERVER receives them, from the plan."""
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


# ---------------------------------------------------------------------------
# The rig description
# ---------------------------------------------------------------------------
def rig_description(manager, stop_upper_rad: float | None) -> str:
    """Expand the production description and substitute the hardware backend.

    Derived from `cite_bringup/test/test_abort_classification_launch.py::_rig_description`,
    whose assertions are kept because they encode failures already paid for there. Two
    differences, both deliberate:

      * the STOPPED block is the GRIPPER's, not the arm's, and the stop joint is
        `arm_1_drive_joint`;
      * `stop_upper_rad` is a campaign lever rather than a multiple of a tolerance.

    `stop_upper_rad = None` builds the FP-C control: every block on plain mock hardware,
    no stop anywhere.
    """
    expanded = subprocess.run(
        ["xacro", str(manager.description)], capture_output=True, text=True, check=True
    ).stdout
    robot = ElementTree.fromstring(expanded)

    for gazebo in robot.findall("gazebo"):
        robot.remove(gazebo)

    blocks = robot.findall("ros2_control")
    assert blocks, f"{manager.description} expanded to no <ros2_control> block"

    stopped = 0
    for block in blocks:
        hardware = block.find("hardware")
        plugin = hardware.find("plugin")
        # V7. A rig that substitutes for something other than the production backend is
        # measuring a system nobody ships.
        assert plugin.text.strip() == PRODUCTION_PLUGIN, (
            f'{block.get("name")} declares {plugin.text.strip()!r}, not {PRODUCTION_PLUGIN!r}. '
            "The L0 backend has changed and this rig is no longer substituting what it "
            "thinks it is."
        )
        names = {joint.get("name") for joint in block.findall("joint")}
        if stop_upper_rad is None or DRIVE_JOINT not in names:
            plugin.text = MOCK_PLUGIN
            continue
        plugin.text = FIXTURE_PLUGIN
        for key, value in (
            ("stop_joint", DRIVE_JOINT),
            ("stop_lower_rad", repr(STOP_LOWER_RAD)),
            ("stop_upper_rad", repr(stop_upper_rad)),
        ):
            parameter = ElementTree.SubElement(hardware, "param")
            parameter.set("name", key)
            parameter.text = value
        stopped += 1

    expected = 0 if stop_upper_rad is None else 1
    assert stopped == expected, (
        f"expected exactly {expected} <ros2_control> block(s) to declare {DRIVE_JOINT}, "
        f"found {stopped}"
    )
    return ElementTree.tostring(robot, encoding="unicode")


# ---------------------------------------------------------------------------
# The rig, as processes
# ---------------------------------------------------------------------------
class Rig:
    """One `ros2_control_node` with two controllers, started and stopped per stop width.

    Started directly rather than through `ros2 launch`: a stop position is a description
    change and therefore a relaunch, and driving twelve of them from one process is
    simpler to reason about than twelve nested launch services. Nothing here sequences on
    a sleep -- the spawner's own service wait is the synchronisation point (P4), and the
    driver waits on the action server matching.
    """

    def __init__(self, manager, description: str, log: Path) -> None:
        self.manager = manager
        self.namespace = manager.node.rsplit("/", 1)[0]
        self.log = log
        self.processes: list[subprocess.Popen] = []
        self.handle = log.open("w")

        # A wildcard key so that both the description publisher and the controller
        # manager receive it from one file. The controller manager takes the description
        # off the TOPIC -- it logs "Waiting for data on 'robot_description' topic" until
        # it arrives -- so `robot_state_publisher` is a load-bearing part of this rig and
        # not scenery, which is also how `test_abort_classification_launch.py` feeds it.
        import yaml

        self.params = Path(tempfile.mkstemp(suffix=".yaml", prefix="fp_rig_")[1])
        self.params.write_text(
            yaml.safe_dump(
                {"/**": {"ros__parameters": {
                    "robot_description": description, "use_sim_time": False}}}
            )
        )

    def start(self) -> None:
        environment = dict(os.environ)
        self.processes.append(
            subprocess.Popen(
                [
                    "ros2", "run", "robot_state_publisher", "robot_state_publisher",
                    "--ros-args",
                    "-r", f"__ns:={self.namespace}",
                    "-r", "__node:=description_publisher",
                    "--params-file", str(self.params),
                ],
                stdout=self.handle, stderr=subprocess.STDOUT, env=environment,
                preexec_fn=os.setsid,
            )
        )
        self.processes.append(
            subprocess.Popen(
                [
                    "ros2", "run", "controller_manager", "ros2_control_node",
                    "--ros-args",
                    "-r", f"__ns:={self.namespace}",
                    "--params-file", str(bringup_plan.resolve_uri(self.manager.parameters)),
                    "--params-file", str(self.params),
                ],
                stdout=self.handle, stderr=subprocess.STDOUT, env=environment,
                preexec_fn=os.setsid,
            )
        )
        for controller in (f"{ARM}_joint_state_broadcaster", f"{ARM}_gripper_controller"):
            spawner = subprocess.run(
                [
                    "ros2", "run", "controller_manager", "spawner", controller,
                    "--controller-manager", self.manager.node,
                    "--controller-manager-timeout", str(STARTUP_CEILING_S),
                ],
                capture_output=True, text=True, timeout=STARTUP_CEILING_S + 60,
                env=environment,
            )
            self.handle.write(f"\n== spawner {controller} rc={spawner.returncode} ==\n")
            self.handle.write(spawner.stdout)
            self.handle.write(spawner.stderr)
            self.handle.flush()
            if spawner.returncode != 0:
                raise RuntimeError(f"spawner for {controller} exited {spawner.returncode}")

    def stop(self) -> None:
        for process in self.processes:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGINT)
            except ProcessLookupError:
                continue
        for process in self.processes:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=10)
        self.handle.close()
        self.params.unlink(missing_ok=True)


class Driver(Node):
    def __init__(self, manager) -> None:
        super().__init__("fp_grasp_discrimination_harness")
        self.namespace = manager.node.rsplit("/", 1)[0]
        self.client = ActionClient(self, GripperCommand, manager.gripper_action)
        self.samples: list[tuple[float, float]] = []
        self.create_subscription(
            JointState,
            f"{self.namespace}/joint_states",
            self._record,
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=200,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            ),
        )

    def _record(self, message: JointState) -> None:
        if DRIVE_JOINT not in message.name:
            return
        index = message.name.index(DRIVE_JOINT)
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        self.samples.append((stamp, message.position[index]))

    def _spin(self, future, ceiling_s: float):
        rclpy.spin_until_future_complete(self, future, timeout_sec=ceiling_s)
        return future.result()

    def await_server(self) -> bool:
        return self.client.wait_for_server(timeout_sec=STARTUP_CEILING_S)

    def await_joint_states(self) -> bool:
        deadline = time.monotonic() + STARTUP_CEILING_S
        while not self.samples and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        return bool(self.samples)

    def close_to(self, q_cmd: float):
        goal = GripperCommand.Goal()
        goal.command.position = q_cmd
        goal.command.max_effort = MAX_EFFORT_N
        handle = self._spin(self.client.send_goal_async(goal), GOAL_CEILING_S)
        if handle is None or not handle.accepted:
            return None, handle
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        return (outcome.result if outcome is not None else None), handle


STOP_ANNOUNCE = re.compile(r"has reached a declared stop at ([-+0-9.eE]+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default="FP")
    parser.add_argument("--repeats", type=int, default=REPEATS)
    # The rig-validation pass `criteria.md` section 10 permits, and NOTHING ELSE. It runs
    # one stop width and one control, so that a rig defect is found before the campaign
    # rather than during it. It is deliberately not a `--widths` flag: an option that
    # could select the sweep would be an option that could move it after seeing data.
    parser.add_argument("--shakedown", action="store_true")
    parser.add_argument(
        "--eval",
        default=str(Path(__file__).resolve().parent / "predicate_eval"),
    )
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    logs.mkdir(exist_ok=True)

    document = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
    manager = next(entry for entry in document.controller_managers if entry.asset == ARM)
    travel = travel_from_plan(manager)
    predicate = Predicate(Path(arguments.eval), travel)

    q_cmd = predicate.position(COMMANDED_WIDTH_M)
    print(f"commanded width {COMMANDED_WIDTH_M*1000:.1f} mm -> q_cmd {q_cmd!r} rad")

    # criteria.md 6.2: the twelve stop widths are cycled, `repeats` times, so the
    # relaunch order interleaves them rather than blocking each.
    schedule: list[tuple[int, float | None]] = []
    if arguments.shakedown:
        schedule = [(0, None), (0, 47.15)]
    else:
        for cycle in range(arguments.repeats):
            for width_mm in STOP_WIDTHS_MM:
                schedule.append((cycle, width_mm))
        # FP-C, the control: three trials with no stop at all, interleaved one per cycle.
        for cycle in range(3):
            schedule.insert(cycle * (len(STOP_WIDTHS_MM) + 1), (cycle, None))

    rclpy.init()
    rows = []
    for index, (cycle, width_mm) in enumerate(schedule, start=1):
        label = "FPC" if width_mm is None else f"{width_mm:.2f}"
        stop_q = None if width_mm is None else predicate.position(width_mm / 1000.0)
        log = logs / f"{arguments.label}_{index:03d}_{label}.log"
        print(f"[{index}/{len(schedule)}] stop {label} mm -> q {stop_q}")

        description = rig_description(manager, stop_q)
        rig = Rig(manager, description, log)
        row: dict = {
            "trial": index,
            "cycle": cycle,
            "condition": "FP-C" if width_mm is None else "FP",
            "stop_width_mm": width_mm,
            "stop_upper_rad": stop_q,
            "commanded_width_m": COMMANDED_WIDTH_M,
            "q_cmd_rad": q_cmd,
            "log": log.name,
        }
        driver = None
        try:
            rig.start()
            driver = Driver(manager)
            if not driver.await_server():
                raise RuntimeError(f"{manager.gripper_action} never appeared")
            if not driver.await_joint_states():
                raise RuntimeError("no /joint_states carrying the drive joint")
            result, _ = driver.close_to(q_cmd)
            if result is None:
                raise RuntimeError("the gripper controller never answered")
            reached_q = float(result.position)
            reached_width = predicate.width(reached_q)
            threshold = 2.0 * predicate.tolerance(reached_q)
            margin = reached_width - COMMANDED_WIDTH_M
            row.update(
                {
                    "ok": True,
                    "reached_position_rad": reached_q,
                    "reached_width_m": reached_width,
                    "stalled": bool(result.stalled),
                    "reached_goal": bool(result.reached_goal),
                    "effort_n": float(result.effort),
                    "margin_m": margin,
                    "threshold_m": threshold,
                    "ratio": margin / threshold if threshold else None,
                    "predicate_holding": predicate.holding(
                        COMMANDED_WIDTH_M, reached_q, bool(result.stalled),
                        bool(result.reached_goal),
                    ),
                    "joint_state_final_rad": driver.samples[-1][1] if driver.samples else None,
                    "joint_state_samples": len(driver.samples),
                }
            )
        except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    trial {index} failed: {exc}")
        finally:
            if driver is not None:
                driver.destroy_node()
            rig.stop()

        # I8 (V6): the plugin's own announcement, read out of the block log rather than
        # inferred from the position. A stop that never engaged is a trial about mock
        # hardware wearing the fixture's name.
        text = log.read_text(errors="replace") if log.exists() else ""
        announced = STOP_ANNOUNCE.search(text)
        row["stop_announced"] = bool(announced)
        row["stop_announced_at_rad"] = float(announced.group(1)) if announced else None
        row["fixture_named_itself"] = "ADR-0040 TEST FIXTURE" in text
        rows.append(row)
        (out / f"{arguments.label}_trials.json").write_text(json.dumps(rows, indent=2, default=str))

    rclpy.shutdown()
    predicate.close()
    print(f"wrote {out / f'{arguments.label}_trials.json'}: {len(rows)} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
