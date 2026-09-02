#!/usr/bin/env python3
"""Arm B -- a drive joint jammed part-way through an OPENING stroke.

`criteria.md` Q-B, section 5.2, threshold B1, rule N-B. This is the region the term
option F removed used to cover: `reached_width > commanded_width`.

WHY THE STROKE HAS TO OPEN, and it is registered in the criteria before any trial ran. A
CLOSING stroke satisfies the removed term structurally -- the jaws stop short of a
narrower command, so the reached width is always the larger -- and commanding a close to
52 mm against a 50 mm part is not a counter-example either, because the jaws pass 52 mm
before they meet the part, the goal is reached, and F rejects on `reached_goal`. The only
way into the region is an OPENING stroke that jams part-way, where the joint is held MORE
CLOSED than commanded and `w_reached < w_cmd`.

SO THE STOPS ARE REVERSED FROM EVERY OTHER RIG IN THIS REPOSITORY. `stop_lower_rad` sits
at the jam and `stop_upper_rad` at +1.0 rad, inert; the drive joint starts CLOSED and
opens into the lower stop. `JointStopSystem` refuses to run if the joint starts outside
its stops -- "a stop that has to move the arm to take effect manufactures the fault it is
supposed to detect" -- so the joint's initial position is set through
`mock_components::GenericSystem`'s `initial_value` state-interface parameter.

**IF THAT DOES NOT WORK, THIS ARM CANNOT RUN, AND THAT IS A RESULT.** A rig that cannot
start closed cannot produce an opening jam, and `criteria.md` section 5.2 says in as many
words that this is a rig failure to report and never a reason to relax the stop. Every
trial therefore records what the joint actually started at, whether the fixture announced
its stop (I7) and whether it refused the start (I8), so a null in this arm can be told
apart from an arm that never ran.

WHAT THIS RIG IS NOT. A synthetic stop at a position this harness chose, not a fouled
finger (`criteria.md` section 8, ADR-0052 section A.9.2). And there is no simulator here
at all, so I4 -- the contact witness -- is STRUCTURALLY ABSENT rather than silent: nothing
can touch anything, and V3's "no contact at all" is discharged by the rig's construction.
That is recorded per trial rather than left to be inferred.

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fp.py`
(commit `eeaf903`) for the description surgery and the relaunch loop, and from
`workspace/src/cite_bringup/test/test_grasp_predicate_launch.py` (commit `d3eeac4`) for
the node set. The 2026-09-01 directory is frozen and nothing in it is edited from here.

Runs INSIDE the container; `run_arm_b.sh` is the door.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
from common import DRIVE_JOINT  # noqa: E402

import rclpy  # noqa: E402
from cite_interfaces.action import Grasp  # noqa: E402
from control_msgs.action import GripperCommand  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.node import Node  # noqa: E402
from sensor_msgs.msg import JointState  # noqa: E402

#: `criteria.md` V7. Asserted rather than substituted for blindly: if the L0 backend has
#: changed, this rig is no longer substituting what it thinks it is.
PRODUCTION_PLUGIN = "gz_ros2_control/GazeboSimSystem"
FIXTURE_PLUGIN = "cite_test_hardware/JointStopSystem"
MOCK_PLUGIN = "mock_components/GenericSystem"

#: `criteria.md` section 5.2, in mm, in the order they are cycled. Two of them are
#: CONTROLS -- 46.0 below the window's narrow edge and 54.0 above its wide edge -- and
#: they are the only trials in this arm the window itself is expected to reject.
JAM_WIDTHS_MM = (46.0, 48.0, 50.0, 52.0, 54.0)
CONTROL_JAMS_MM = (46.0, 54.0)

#: The criteria's own table of drive positions, kept only as a CROSS-CHECK. The value the
#: rig uses comes from the shipped `gripper_position_for` through `predicate_eval`; a
#: disagreement is recorded per trial rather than resolved in favour of either.
JAM_POSITIONS_FROM_CRITERIA_RAD = {
    46.0: 0.443404,
    48.0: 0.424555,
    50.0: 0.405605,
    52.0: 0.386545,
    54.0: 0.367366,
}
JAM_POSITION_AGREEMENT_RAD = 1e-4

#: Held fixed for every Arm B trial (`criteria.md` section 5.2). Wider than every jam, so
#: the stroke opens in all of them and `w_reached < w_cmd` throughout. Under F the command
#: does not enter the verdict, and holding it fixed is what makes that checkable rather
#: than assumed.
COMMANDED_WIDTH_M = 0.056

#: The inert stop. Literal, as the criteria states it: +1.0 rad is above the whole travel
#: (`closed_position` is 0.85), so the joint can never meet it.
STOP_UPPER_RAD = 1.0

REPEATS = 3
MAX_EFFORT_N = 60.0
STARTUP_CEILING_S = 240.0
GOAL_CEILING_S = 120.0

#: I7 and I8 -- the fixture's own two lines, matched verbatim
#: (`joint_stop_system.cpp:186-191` and `:171-182`).
STOP_ANNOUNCE = re.compile(r"has reached a declared stop at ([-+0-9.eE]+)")
START_REFUSAL = re.compile(
    r"starts at ([-+0-9.eE]+), outside its declared stops \[([-+0-9.eE]+), ([-+0-9.eE]+)\]")

#: I7's second half: the drive joint must rest AT the declared stop, not merely somewhere
#: short of its command. 0.001 rad is `criteria.md` section 7.0's drive-position MIS, and
#: it is 0.100 mm of width through this linkage.
STOP_REST_TOLERANCE_RAD = 0.001


# ---------------------------------------------------------------------------
# The rig description
# ---------------------------------------------------------------------------
def rig_description(manager, jam_q_rad: float, initial_q_rad: float) -> tuple[str, dict]:
    """Expand the production description and reverse the stops on the gripper's block.

    Returns the description and a dictionary of what was actually substituted, so that a
    trial record says what it ran rather than what it intended to run.
    """
    expanded = subprocess.run(
        ["xacro", str(manager.description)], capture_output=True, text=True, check=True
    ).stdout
    robot = ElementTree.fromstring(expanded)

    for gazebo in robot.findall("gazebo"):
        robot.remove(gazebo)

    blocks = robot.findall("ros2_control")
    assert blocks, f"{manager.description} expanded to no <ros2_control> block"

    facts: dict = {
        "blocks": [],
        "stop_lower_rad": jam_q_rad,
        "stop_upper_rad": STOP_UPPER_RAD,
        "initial_value_rad": initial_q_rad,
        "initial_value_injected": False,
    }
    stopped = 0
    for block in blocks:
        hardware = block.find("hardware")
        plugin = hardware.find("plugin")
        declared = plugin.text.strip()
        # V7. A rig that substitutes for something other than the production backend is
        # measuring a system nobody ships.
        assert declared == PRODUCTION_PLUGIN, (
            f'{block.get("name")} declares {declared!r}, not {PRODUCTION_PLUGIN!r}. '
            "The L0 backend has changed and this rig is no longer substituting what it "
            "thinks it is."
        )
        names = {joint.get("name") for joint in block.findall("joint")}
        if DRIVE_JOINT not in names:
            plugin.text = MOCK_PLUGIN
            facts["blocks"].append({"name": block.get("name"), "was": declared,
                                    "now": MOCK_PLUGIN})
            continue
        plugin.text = FIXTURE_PLUGIN
        for key, value in (
            ("stop_joint", DRIVE_JOINT),
            # REVERSED. The jam is the LOWER stop, because the stroke opens into it.
            ("stop_lower_rad", repr(jam_q_rad)),
            ("stop_upper_rad", repr(STOP_UPPER_RAD)),
        ):
            parameter = ElementTree.SubElement(hardware, "param")
            parameter.set("name", key)
            parameter.text = value

        # The jaws must start CLOSED, or the fixture refuses on its first read. Only the
        # drive joint is set: the five followers are mimic joints and `GenericSystem`
        # drives them from the leader on the first read, so a second statement of their
        # position here would be the same fact in six places (P1).
        for joint in block.findall("joint"):
            if joint.get("name") != DRIVE_JOINT:
                continue
            for interface in joint.findall("state_interface"):
                if interface.get("name") != "position":
                    continue
                parameter = ElementTree.SubElement(interface, "param")
                parameter.set("name", "initial_value")
                parameter.text = repr(initial_q_rad)
                facts["initial_value_injected"] = True
        facts["blocks"].append({"name": block.get("name"), "was": declared,
                                "now": FIXTURE_PLUGIN})
        stopped += 1

    assert stopped == 1, (
        f"expected exactly one <ros2_control> block to declare {DRIVE_JOINT}, found {stopped}"
    )
    text = ElementTree.tostring(robot, encoding="unicode")
    # V2's question, asked of the description this rig will actually publish. This arm
    # brings no cell up, so there is no running node to read it off -- but the rig is
    # built from the same generated xacro, and a rig that had silently stopped carrying
    # the shipped collision geometry would be a rig measuring a different arm.
    facts["hull_collision_refs"] = text.count(common.HULL_COLLISION_REFERENCE)
    facts["v2_ok"] = (
        facts["hull_collision_refs"] == common.HULL_COLLISION_REFERENCES_EXPECTED)
    assert facts["initial_value_injected"], (
        f"{DRIVE_JOINT} declares no <state_interface name=\"position\">, so its initial "
        "position cannot be set and the fixture would refuse the start. This arm cannot "
        "run against this description."
    )
    return ElementTree.tostring(robot, encoding="unicode"), facts


# ---------------------------------------------------------------------------
# The rig, as one launch
# ---------------------------------------------------------------------------
class Launch:
    """`arm_b.launch.py`, started per jam position.

    A jam position is a description change and therefore a relaunch (`criteria.md`
    section 6), so the interleaving in this arm is over the RELAUNCH ORDER.
    """

    def __init__(self, description: str, log: Path) -> None:
        self.log = log
        self.handle = log.open("w")
        self.file = Path(tempfile.mkstemp(suffix=".urdf", prefix="arm_b_rig_")[1])
        self.file.write_text(description)
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            ["ros2", "launch", str(Path(__file__).resolve().parent / "arm_b.launch.py"),
             f"description_file:={self.file}"],
            stdout=self.handle, stderr=subprocess.STDOUT, env=dict(os.environ),
            preexec_fn=os.setsid,
        )

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if self.process is not None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                self.process.wait(timeout=60)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait(timeout=20)
                except ProcessLookupError:
                    pass
        self.handle.close()
        self.file.unlink(missing_ok=True)


class Driver(Node):
    """One node against the rig: the L3 `Grasp` action, and the controller's own action.

    The `Grasp` client is I1 and the verdict. The `GripperCommand` client is a SECOND
    EVENT and is recorded as one: it re-commands the same position against a joint that
    is already resting on the stop, which is what makes `stalled`, `reached_goal` and
    `position` readable at full precision from the controller itself rather than only
    through the server's 0.1 mm log line.
    """

    def __init__(self, manager) -> None:
        super().__init__("option_f_arm_b_harness")
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=False)])
        self.namespace = manager.node.rsplit("/", 1)[0]
        self.grasp = ActionClient(self, Grasp, manager.skills.grasp)
        self.gripper = ActionClient(self, GripperCommand, manager.gripper_action)
        self.samples: list[tuple[float, float]] = []
        self.create_subscription(
            JointState, f"{self.namespace}/joint_states", self._record, 50)

    def _record(self, message: JointState) -> None:
        if DRIVE_JOINT not in message.name:
            return
        index = message.name.index(DRIVE_JOINT)
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        self.samples.append((stamp, message.position[index]))

    def _spin(self, future, ceiling_s: float):
        rclpy.spin_until_future_complete(self, future, timeout_sec=ceiling_s)
        return future.result()

    def await_servers(self, launch: Launch) -> None:
        deadline = time.monotonic() + STARTUP_CEILING_S
        for client, label in ((self.gripper, "the gripper controller's action"),
                              (self.grasp, "the skill server's Grasp action")):
            while time.monotonic() < deadline:
                if client.wait_for_server(timeout_sec=2.0):
                    break
                if not launch.alive():
                    raise RuntimeError(f"the launch exited before {label} appeared")
            else:
                raise RuntimeError(f"{label} never appeared within {STARTUP_CEILING_S:.0f}s")

    def await_joint_states(self, launch: Launch) -> None:
        deadline = time.monotonic() + STARTUP_CEILING_S
        while not self.samples and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
            if not launch.alive():
                raise RuntimeError("the launch exited before any /joint_states arrived")
        if not self.samples:
            raise RuntimeError("no /joint_states carrying the drive joint")

    def send_grasp(self, width_m: float):
        goal = Grasp.Goal()
        goal.width_m = width_m
        goal.max_effort_n = MAX_EFFORT_N
        # False, so that the fields are reported rather than converted into an
        # EXECUTION_FAILED (`criteria.md` I1). The verdict this arm reads is `holding`.
        goal.expect_object = False
        handle = self._spin(self.grasp.send_goal_async(goal), GOAL_CEILING_S)
        if handle is None or not handle.accepted:
            return None
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        return outcome.result if outcome is not None else None

    def send_gripper(self, q_cmd: float):
        goal = GripperCommand.Goal()
        goal.command.position = q_cmd
        goal.command.max_effort = MAX_EFFORT_N
        handle = self._spin(self.gripper.send_goal_async(goal), GOAL_CEILING_S)
        if handle is None or not handle.accepted:
            return None
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        return outcome.result if outcome is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default="B")
    parser.add_argument("--repeats", type=int, default=REPEATS)
    # The one shakedown `criteria.md` section 10 permits, and NOTHING ELSE. It runs a
    # single jam so that a rig defect is found before the campaign rather than during it.
    # Deliberately not a `--jams` flag: an option that could select the sweep would be an
    # option that could move it after seeing data.
    parser.add_argument("--shakedown", action="store_true")
    parser.add_argument(
        "--eval", default=str(Path(__file__).resolve().parent / "predicate_eval"))
    parser.add_argument(
        "--eval-superseded",
        default=str(Path(__file__).resolve().parent / "predicate_eval_superseded"))
    arguments = parser.parse_args()

    out = Path(arguments.out)
    logs = out / "logs"
    document, manager = common.load_plan()
    travel = common.travel_from_plan(manager)
    parts = common.parts_from_plan(document)
    edge_lo, edge_hi = common.window_m(travel, parts)

    predicate = common.Predicate(Path(arguments.eval), travel, parts)
    superseded_path = Path(arguments.eval_superseded)
    superseded = (
        common.SupersededPredicate(superseded_path, travel)
        if superseded_path.exists() else None
    )

    q_cmd = predicate.position(COMMANDED_WIDTH_M)
    initial_q = travel["closed_position"]

    header = {
        "arm": "B",
        "question": "criteria.md Q-B -- a jammed OPENING stroke, inside the window",
        "provenance": common.provenance(),
        "host": common.host_facts(),
        "travel": travel,
        "parts": parts,
        "window_m": {"edge_lo": edge_lo, "edge_hi": edge_hi},
        "commanded_width_m": COMMANDED_WIDTH_M,
        "q_cmd_rad": q_cmd,
        "initial_position_rad": initial_q,
        "stop_upper_rad": STOP_UPPER_RAD,
        "predicate_eval": predicate.describe(),
        "superseded": common.superseded_provenance(),
        # I4 in this arm, stated once in the header and again on every record.
        "contact_witness": "structurally absent -- this rig has no simulator, so nothing "
                           "can touch anything and V3's 'no contact at all' is discharged "
                           "by construction rather than by a sensor",
    }
    writer = common.TrialWriter(out, arguments.label, header)

    if not header["provenance"]["v1_clean"]:
        print("WARNING: V1 is NOT clean for this block. Every record carries the diff; "
              "criteria.md V1 discards the block rather than relabelling it.")

    schedule: list[tuple[int, float]] = []
    if arguments.shakedown:
        schedule = [(0, 50.0)]
    else:
        for cycle in range(arguments.repeats):
            for width_mm in JAM_WIDTHS_MM:
                schedule.append((cycle, width_mm))

    rclpy.init()
    for index, (cycle, jam_mm) in enumerate(schedule, start=1):
        jam_q = predicate.position(jam_mm / 1000.0)
        tabulated = JAM_POSITIONS_FROM_CRITERIA_RAD.get(jam_mm)
        log = logs / f"{arguments.label}_{index:03d}_{jam_mm:.2f}.log"
        print(f"[{index}/{len(schedule)}] jam {jam_mm:.2f} mm -> q {jam_q!r} rad")

        row: dict = {
            "trial": index,
            "cycle": cycle,
            "arm": "B",
            "condition": "control" if jam_mm in CONTROL_JAMS_MM else "window",
            "jam_width_mm": jam_mm,
            "jam_position_rad": jam_q,
            "jam_position_from_criteria_rad": tabulated,
            "jam_position_agrees_with_criteria": (
                tabulated is not None and abs(jam_q - tabulated) <= JAM_POSITION_AGREEMENT_RAD
            ),
            "commanded_width_m": COMMANDED_WIDTH_M,
            "q_cmd_rad": q_cmd,
            "stroke": "opening",
            "initial_position_rad": initial_q,
            "stop_lower_rad": jam_q,
            "stop_upper_rad": STOP_UPPER_RAD,
            "contact_witness": header["contact_witness"],
            "finger_contact_points_max": 0,
            "log": log.name,
        }

        description, facts = rig_description(manager, jam_q, initial_q)
        row["rig"] = facts
        launch = Launch(description, log)
        driver = None
        try:
            launch.start()
            driver = Driver(manager)
            driver.await_servers(launch)
            driver.await_joint_states(launch)
            row["joint_state_first_rad"] = driver.samples[0][1]

            # I1 and the verdict.
            result = driver.send_grasp(COMMANDED_WIDTH_M)
            if result is None:
                raise RuntimeError("the skill server never answered the Grasp goal")
            row.update(
                {
                    "ok": True,
                    "holding_F": bool(result.holding),
                    "i1_reached_width_m": float(result.reached_width_m),
                    "i1_measured_effort_n": float(result.measured_effort_n),
                    "i1_result_code": int(result.result.code),
                    "i1_detail": result.result.detail,
                }
            )

            # I3 -- the drive joint's own last sample, at full precision.
            q_reached = driver.samples[-1][1] if driver.samples else None
            row["i3_q_at_stall_rad"] = q_reached
            row["i3_joint_state_samples"] = len(driver.samples)
            if q_reached is not None:
                row["i3_reached_width_m"] = predicate.width(q_reached)
                row["d_narrow_m"] = row["i3_reached_width_m"] - edge_lo
                row["d_wide_m"] = edge_hi - row["i3_reached_width_m"]
                # I7's second half: the joint must be RESTING at the declared stop.
                row["rests_at_stop"] = abs(q_reached - jam_q) <= STOP_REST_TOLERANCE_RAD
                row["rest_error_rad"] = q_reached - jam_q

            # A SECOND EVENT, and recorded as one: the controller's own typed answer,
            # which is the only full-precision source of `stalled` and `reached_goal`.
            controller = driver.send_gripper(q_cmd)
            if controller is not None:
                row.update(
                    {
                        "gc_position_rad": float(controller.position),
                        "gc_stalled": bool(controller.stalled),
                        "gc_reached_goal": bool(controller.reached_goal),
                        "gc_effort_n": float(controller.effort),
                        "gc_width_m": predicate.width(float(controller.position)),
                    }
                )
        except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    trial {index} failed: {exc}")
        finally:
            if driver is not None:
                driver.destroy_node()
            launch.stop()

        # I2, I7 and I8, read out of the block log after the launch has gone.
        text = log.read_text(errors="replace") if log.exists() else ""
        reports = [
            {
                "commanded_mm": float(m.group(1)),
                "reached_mm": float(m.group(2)),
                "stalled": m.group(3) == "true",
                "reached_goal": m.group(4) == "true",
                "effort_n": float(m.group(5)),
                "verdict": m.group(6),
            }
            for m in common.REPORT.finditer(text)
        ]
        announced = STOP_ANNOUNCE.search(text)
        refused = START_REFUSAL.search(text)
        row.update(
            {
                "i2_reports": reports,
                "stalled": reports[0]["stalled"] if reports else None,
                "reached_goal": reports[0]["reached_goal"] if reports else None,
                "i7_stop_announced": bool(announced),
                "i7_stop_announced_at_rad": float(announced.group(1)) if announced else None,
                "i8_start_refused": bool(refused),
                "i8_start_position_rad": float(refused.group(1)) if refused else None,
                "fixture_named_itself": "ADR-0040 TEST FIXTURE" in text,
            }
        )
        # V4, both halves. It sits here rather than in the trial above because its
        # second clause needs the I2 log line, which is only readable once the launch
        # this trial ran under has gone.
        row.update(common.v4(
            row.get("i1_reached_width_m"), row.get("i3_reached_width_m"), reports))

        # V5, evaluated here rather than left to the write-up.
        row["v5_valid"] = bool(
            row.get("i7_stop_announced")
            and row.get("rests_at_stop")
            and not row.get("i8_start_refused")
        )

        # holding_S -- the comparison quantity, from a BUILD of `4ef2d7c` (V10). It
        # enters no verdict; it is reported so a reader can see which regions the change
        # opened and which it closed.
        if superseded is not None and row.get("i3_q_at_stall_rad") is not None \
                and row.get("stalled") is not None:
            row["holding_S"] = superseded.holding(
                COMMANDED_WIDTH_M, row["i3_q_at_stall_rad"],
                bool(row["stalled"]), bool(row["reached_goal"]))
            row["holding_S_provenance"] = header["superseded"]
        else:
            row["holding_S"] = None
            row["holding_S_provenance"] = {"available": False}

        writer.add(row)
        print(
            f"    holding_F={row.get('holding_F')} holding_S={row.get('holding_S')} "
            f"w_reached={row.get('i3_reached_width_m')} v5={row.get('v5_valid')}"
        )

    rclpy.shutdown()
    predicate.close()
    if superseded is not None:
        superseded.close()
    print(f"wrote {writer.path}: {len(writer.rows)} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
