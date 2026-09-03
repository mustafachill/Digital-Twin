#!/usr/bin/env python3
"""One block of `criteria.md` section 6's design: a stop grid, swept, one launch per trial.

`criteria.md` section 1's question, sections 4 and 5's instruments and levers, and section
10's validity rules as they are evaluated WHERE THE BLOCK IS TAKEN.

DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/measure_arm_b.py`,
copied at commit `ac11d84`, for the description surgery, the relaunch loop, the `Launch`
and `Driver` shapes and the "a failed trial is a recorded trial" handling; and from
`workspace/src/cite_bringup/test/test_grasp_predicate_launch.py` (read at `HEAD` on
2026-09-03) for the node set and for the stop orientation. That directory is FROZEN
(`docs/measurements/README.md`) and nothing in it is edited from here.

WHAT IS DIFFERENT FROM THE ANCESTOR, and each difference is a criteria clause:

  * **The stroke CLOSES.** Section 5.1 registers three reasons and the third decides it:
    the command stays the shipped default. `stop_upper_rad` is the jam and
    `stop_lower_rad` is an inert -1.0 rad, which is the orientation the shipped launch
    test uses. **The joint starts open at q = 0, its default, so no `initial_value`
    injection is needed at all** -- the ancestor's reversed opening-stroke rig needed one
    and this does not.
  * **The stop grid is registered and the refinement interval is located.** `common.py`'s
    `coarse_grid` and `fine_grid` are what enforce that, and `fine_grid` REFUSES an
    interval that is not an adjacent pair of the arm's own coarse grid. Section 5.1: no
    stop outside the two coarse spans is run, whatever the coarse grid shows.
  * **I4 is spent.** V14 is evaluated per trial from I2's booleans, I4's booleans and the
    two widths -- the rule that makes an unread log line distinguishable from a measured
    `false`.
  * **The stop's serialisation is checked, not assumed.** Section 7.0 registers that a
    harness writing `%.3f` radians would quantise every stop by ten times I7's tolerance
    and V5 would then reject the whole campaign for a defect in the harness's own output
    format. The description is written with `repr()` and READ BACK, and the round trip is a
    field on every record.
  * **V1 is a conjunction of two readings.** One snapshot at each end of every cycle, and
    the cycle index is the block index that travels on every record.

WHAT THIS RIG IS NOT. A synthetic stop at a position this harness chose, not a fouled
finger (`criteria.md` section 8, ADR-0052 section A.9.2). There is no simulator here at
all, so V3's "nothing was between the pads" is STRUCTURALLY ABSENT rather than silent, and
that is recorded per trial as a stated fact about the rig rather than left to be inferred
from a missing field.

Runs INSIDE the container; `run_block.sh` is the door.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
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

STARTUP_CEILING_S = 240.0
GOAL_CEILING_S = 120.0

#: The shakedown's one stop, and it is deliberately **on neither campaign grid**.
#: `criteria.md` section 10 permits one shakedown run per harness and it is not data; a
#: shakedown taken at a campaign stop would produce a record that looks exactly like a
#: trial, and the safest way to keep it out of a figure is for its lever to be a value the
#: campaign never sweeps. 50.00 mm is inside the window, so the chain is exercised to a
#: `holding_F` of `true` rather than only to a rejection.
SHAKEDOWN_STOP_MM = 50.00

#: `criteria.md` section 2's table, QUOTED from the frozen criteria so that the shipped
#: code can be checked against it before any trial. These are not inputs to anything: the
#: window, the grid and every reported figure are derived from the plan through the
#: compiled front end. A disagreement is RECORDED on the block header and the block still
#: runs -- rule D's shape, one level down: the arithmetic and the code are allowed to
#: disagree, and the disagreement is the finding.
CRITERIA_SECTION_2 = {
    "open_width_mm": 88.930,
    "closed_width_mm": 1.646,
    "edge_lo_mm": 47.6150,
    "edge_hi_mm": 52.3850,
    "edge_lo_position_rad": 0.428191,
    "edge_hi_position_rad": 0.382862,
    "margin_at_45mm_mm": 2.137972,
    "validator_ceiling_mm": 47.862,
    "floor_mm": 47.121519,
}
CROSS_CHECK_WIDTH_TOLERANCE_MM = 0.001
CROSS_CHECK_POSITION_TOLERANCE_RAD = 1e-5


# ---------------------------------------------------------------------------
# The rig description
# ---------------------------------------------------------------------------
def rig_description(manager, stop_q_rad: float | None) -> tuple[str, dict]:
    """Expand the production description and put the fixture on the gripper's block.

    `stop_q_rad` is the jam, as `stop_upper_rad`. `None` is arm CTL: the gripper's block
    goes on plain `mock_components/GenericSystem` with **no stop at all**
    (`criteria.md` section 5.3).

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
        "stop_applied": stop_q_rad is not None,
        "stop_upper_rad": stop_q_rad,
        "stop_lower_rad": common.STOP_LOWER_RAD if stop_q_rad is not None else None,
        "v13_ok": True,
        "stop_repr_round_trip_exact": None,
    }
    substituted = 0
    for block in blocks:
        hardware = block.find("hardware")
        plugin = hardware.find("plugin")
        declared = plugin.text.strip()
        # V13, asserted BEFORE substitution. A launch that finds anything else is
        # discarded: the L0 backend has changed and the rig is no longer substituting what
        # it thinks it is.
        if declared != common.PRODUCTION_PLUGIN:
            facts["v13_ok"] = False
            raise AssertionError(
                f'{block.get("name")} declares {declared!r}, not '
                f"{common.PRODUCTION_PLUGIN!r}. criteria.md V13 discards this launch: the "
                "L0 backend has changed and this rig is no longer substituting what it "
                "thinks it is."
            )
        names = {joint.get("name") for joint in block.findall("joint")}
        if DRIVE_JOINT not in names:
            # Everything that is not the gripper -- here, the arm -- gets the vendor's own
            # mock, unmodified. Only the component under test is replaced.
            plugin.text = common.MOCK_PLUGIN
            facts["blocks"].append(
                {"name": block.get("name"), "was": declared, "now": common.MOCK_PLUGIN})
            continue
        if stop_q_rad is None:
            plugin.text = common.MOCK_PLUGIN
            facts["blocks"].append(
                {"name": block.get("name"), "was": declared, "now": common.MOCK_PLUGIN,
                 "role": "the gripper, on plain mock with no stop (arm CTL)"})
            substituted += 1
            continue
        plugin.text = common.FIXTURE_PLUGIN
        for key, value in (
            ("stop_joint", DRIVE_JOINT),
            ("stop_lower_rad", repr(common.STOP_LOWER_RAD)),
            # `repr()`, and section 7.0 registers why: it round-trips a Python float
            # exactly, so a 0.005 mm rest tolerance is reachable. A `%.3f` here would
            # quantise every stop by up to 0.0005 rad -- 0.053 mm of width at `edge_lo`,
            # ten times the tolerance -- and V5 would reject every trial in the campaign
            # for a defect in this line rather than in the rig.
            ("stop_upper_rad", repr(stop_q_rad)),
        ):
            parameter = ElementTree.SubElement(hardware, "param")
            parameter.set("name", key)
            parameter.text = value
        facts["blocks"].append(
            {"name": block.get("name"), "was": declared, "now": common.FIXTURE_PLUGIN,
             "role": "the gripper, with a declared stop"})
        substituted += 1

    assert substituted == 1, (
        f"expected exactly one <ros2_control> block to declare {DRIVE_JOINT}, "
        f"found {substituted}"
    )
    text = ElementTree.tostring(robot, encoding="unicode")

    # The round trip, READ BACK out of the text that will be written to disk. Section 7.0
    # makes I7's whole tolerance depend on this holding, so it is measured rather than
    # asserted in a comment.
    if stop_q_rad is not None:
        written = ElementTree.fromstring(text)
        found = [
            parameter.text
            for element in written.findall("ros2_control")
            for parameter in element.find("hardware").findall("param")
            if parameter.get("name") == "stop_upper_rad"
        ]
        facts["stop_upper_rad_as_written"] = found[0] if found else None
        facts["stop_repr_round_trip_exact"] = bool(
            found and float(found[0]) == stop_q_rad)

    # V2's question, asked of the text the rig is about to publish. The block also reads it
    # back off the RUNNING node once the rig is up, which is the reading V2 is stated
    # against; this one is kept beside it so that a trial whose read-back failed still says
    # what was substituted.
    facts["hull_collision_refs_in_text"] = text.count(common.HULL_COLLISION_REFERENCE)
    return text, facts


# ---------------------------------------------------------------------------
# The rig, as one launch
# ---------------------------------------------------------------------------
class Launch:
    """`rig.launch.py`, started per stop.

    A stop position is a description change and therefore a RELAUNCH (`criteria.md`
    section 6), so the interleaving in this campaign is over the relaunch order: one cycle
    visits every stop of a block once, and the repeats are successive cycles.
    """

    def __init__(self, description: str, log: Path) -> None:
        self.log = log
        self.handle = log.open("w")
        self.file = Path(tempfile.mkstemp(suffix=".urdf", prefix="stall_band_rig_")[1])
        self.file.write_text(description)
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            ["ros2", "launch", str(Path(__file__).resolve().parent / "rig.launch.py"),
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

    The `Grasp` client is I1 and the verdict. The `GripperCommand` client is **I4, a SECOND
    EVENT**, and is recorded as one: it re-commands the same position against a joint that
    is already resting on the stop, which is what makes `stalled`, `reached_goal` and
    `position` readable at full precision from the controller itself rather than only
    through the server's 0.1 mm log line. V14 is what spends it.
    """

    def __init__(self, manager) -> None:
        super().__init__("stall_band_flip_harness")
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
        goal.max_effort_n = common.MAX_EFFORT_N
        # False, so that the fields are reported rather than converted into an
        # EXECUTION_FAILED (`criteria.md` I1). The verdict this campaign reads is `holding`.
        goal.expect_object = False
        handle = self._spin(self.grasp.send_goal_async(goal), GOAL_CEILING_S)
        if handle is None or not handle.accepted:
            return None
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        return outcome.result if outcome is not None else None

    def send_gripper(self, q_cmd: float):
        goal = GripperCommand.Goal()
        goal.command.position = q_cmd
        goal.command.max_effort = common.MAX_EFFORT_N
        handle = self._spin(self.gripper.send_goal_async(goal), GOAL_CEILING_S)
        if handle is None or not handle.accepted:
            return None
        outcome = self._spin(handle.get_result_async(), GOAL_CEILING_S)
        return outcome.result if outcome is not None else None


# ---------------------------------------------------------------------------
# The section 2 cross-check, before any trial of the block
# ---------------------------------------------------------------------------
def section_2_cross_check(predicate: common.Predicate, floor_m: float,
                          edges: tuple[float, float], margin_m: float) -> dict:
    """The section 2 cross-check, as a dictionary the block header carries.

    Every left-hand value is the SHIPPED program's answer; every right-hand value is quoted
    from the frozen `criteria.md`. A disagreement is recorded and the block still runs.
    """
    edge_lo, edge_hi = edges
    rows = (
        ("open_width_mm", predicate.max_width() * 1000.0,
         CRITERIA_SECTION_2["open_width_mm"], CROSS_CHECK_WIDTH_TOLERANCE_MM),
        ("closed_width_mm", predicate.min_width() * 1000.0,
         CRITERIA_SECTION_2["closed_width_mm"], CROSS_CHECK_WIDTH_TOLERANCE_MM),
        ("edge_lo_mm", edge_lo * 1000.0,
         CRITERIA_SECTION_2["edge_lo_mm"], CROSS_CHECK_WIDTH_TOLERANCE_MM),
        ("edge_hi_mm", edge_hi * 1000.0,
         CRITERIA_SECTION_2["edge_hi_mm"], CROSS_CHECK_WIDTH_TOLERANCE_MM),
        ("edge_lo_position_rad", predicate.position(edge_lo),
         CRITERIA_SECTION_2["edge_lo_position_rad"], CROSS_CHECK_POSITION_TOLERANCE_RAD),
        ("edge_hi_position_rad", predicate.position(edge_hi),
         CRITERIA_SECTION_2["edge_hi_position_rad"], CROSS_CHECK_POSITION_TOLERANCE_RAD),
        ("margin_at_45mm_mm", margin_m * 1000.0,
         CRITERIA_SECTION_2["margin_at_45mm_mm"], 1e-5),
        ("validator_ceiling_mm", (0.050 - margin_m) * 1000.0,
         CRITERIA_SECTION_2["validator_ceiling_mm"], 0.001),
        ("floor_mm", floor_m * 1000.0, CRITERIA_SECTION_2["floor_mm"], 1e-4),
    )
    result = {
        name: {
            "shipped": shipped,
            "criteria": stated,
            "tolerance": tolerance,
            "agrees": abs(shipped - stated) <= tolerance,
        }
        for name, shipped, stated, tolerance in rows
    }
    result["all_agree"] = all(entry["agrees"] for entry in result.values())
    return result


# ---------------------------------------------------------------------------
# One trial
# ---------------------------------------------------------------------------
def run_trial(manager, predicate, superseded, row: dict, log: Path,
              command_m: float, stop_q: float | None, q_cmd: float,
              edges: tuple[float, float], namespace: str) -> dict:
    """One launch, one `Grasp`, one `GripperCommand`, and every instrument read off it."""
    edge_lo, edge_hi = edges
    description, facts = rig_description(manager, stop_q)
    row["rig"] = facts
    row["v13_ok"] = facts["v13_ok"]
    launch = Launch(description, log)
    cursor = common.LogCursor(log)
    driver = None
    controller = None
    reports: list[dict] = []
    try:
        launch.start()
        driver = Driver(manager)
        driver.await_servers(launch)
        driver.await_joint_states(launch)
        row["joint_state_first_rad"] = driver.samples[0][1]

        # V2 and V13, off the description the RUNNING rig publishes. Taken once the rig is
        # up, which is the only instant at which the question "what did this rig publish"
        # has an answer.
        row["geometry"] = common.running_geometry(namespace)
        row["v2_ok"] = row["geometry"]["v2_ok"]

        # I1 and the verdict.
        cursor.mark()
        result = driver.send_grasp(command_m)
        if result is None:
            raise RuntimeError("the skill server never answered the Grasp goal")
        row.update({
            "ok": True,
            "holding_F": bool(result.holding),
            "i1_reached_width_m": float(result.reached_width_m),
            "i1_measured_effort_n": float(result.measured_effort_n),
            "i1_result_code": int(result.result.code),
            "i1_detail": result.result.detail,
        })

        # I2 -- waited for, bounded, and recorded as MISSING if it never came (V14).
        reports = cursor.await_report()
        row["i2_read_before_teardown"] = bool(reports)

        # I3 -- the drive joint's own last sample, at full precision, mapped through the
        # shipped closed form. The CROSS-CHECK V4 is the rule over, never a reported
        # decision quantity: section 2.1 defines `w_reached` as `Grasp.Result.reached_width_m`.
        q_reached = driver.samples[-1][1] if driver.samples else None
        row["i3_q_at_rest_rad"] = q_reached
        row["i3_joint_state_samples"] = len(driver.samples)
        if q_reached is not None:
            row["i3_reached_width_m"] = predicate.width(q_reached)

        # I4 -- A SECOND EVENT, and recorded as one.
        controller = driver.send_gripper(q_cmd)
        if controller is not None:
            row.update({
                "i4_position_rad": float(controller.position),
                "i4_stalled": bool(controller.stalled),
                "i4_reached_goal": bool(controller.reached_goal),
                "i4_effort_n": float(controller.effort),
                "i4_width_m": predicate.width(float(controller.position)),
            })
    except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
        row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        print(f"    trial failed: {exc}")
    finally:
        if driver is not None:
            driver.destroy_node()
        launch.stop()

    # I2, I5 and I6, read out of the block log after the launch has gone. The I2 segment is
    # the cursor's, so a line belonging to the second event cannot be read as the first's;
    # a segment that was empty before teardown is re-read here, because a line flushed at
    # teardown is still that grasp's line and V14 counts an absent one as a loss.
    if not reports:
        reports = cursor.collect()
        row["i2_read_after_teardown"] = bool(reports)
    text = log.read_text(errors="replace") if log.exists() else ""
    announced = common.STOP_ANNOUNCE.search(text)
    refused = common.START_REFUSAL.search(text)
    row.update({
        "i2_reports": reports,
        "stalled": reports[0]["stalled"] if reports else None,
        "reached_goal": reports[0]["reached_goal"] if reports else None,
        "i5_stop_announced": bool(announced),
        "i5_stop_announced_at_rad": float(announced.group(1)) if announced else None,
        "i6_start_refused": bool(refused),
        "i6_start_position_rad": float(refused.group(1)) if refused else None,
        "fixture_named_itself": "ADR-0040 TEST FIXTURE" in text,
    })

    # I7 -- the joint rests ON the stop and not merely near it, measured against
    # `gripper_width_for(stop_upper_rad)` **on the drive position the fixture actually
    # declared** and not on the nominal `w_stop` (section 7.0).
    if stop_q is not None:
        reference = predicate.width(stop_q)
        row["i7_reference_width_m"] = reference
        row["i7_tolerance_m"] = common.REST_TOLERANCE_M
        rest_q = row.get("i3_q_at_rest_rad")
        if rest_q is not None:
            row["i7_rest_width_m"] = predicate.width(rest_q)
            row["i7_rest_error_m"] = row["i7_rest_width_m"] - reference
            row["i7_rest_error_rad"] = rest_q - stop_q
            row["i7_rests_at_stop"] = abs(row["i7_rest_error_m"]) <= common.REST_TOLERANCE_M
        else:
            row["i7_rests_at_stop"] = None
        if row.get("i4_width_m") is not None:
            row["i7_rest_error_from_i4_m"] = row["i4_width_m"] - reference
    else:
        row["i7_reference_width_m"] = None
        row["i7_rests_at_stop"] = None

    # V4, both clauses. It sits here rather than in the trial above because its second
    # clause needs the I2 log line, which may only be readable once the launch has gone.
    row.update(common.v4(
        row.get("i1_reached_width_m"), row.get("i3_reached_width_m"), reports))

    # V14, evaluated here rather than left to the write-up.
    row.update(common.v14(
        reports,
        None if controller is None else {
            "stalled": row.get("i4_stalled"), "reached_goal": row.get("i4_reached_goal")},
        row.get("i1_reached_width_m"), row.get("i4_width_m")))

    # V5 -- arms LO and HI only. CTL has no stop, so the rule has nothing to say about it
    # and `None` is recorded rather than a `False` that would read as a failed fixture.
    if stop_q is None:
        row["v5_valid"] = None
        row["v5_note"] = ("arm CTL declares no stop, so V5 does not apply; "
                          "criteria.md section 7.4 requires that no stop warning appear, "
                          "and `i5_stop_announced` is where that is read")
    else:
        row["v5_valid"] = bool(
            row.get("i5_stop_announced")
            and row.get("i7_rests_at_stop")
            and not row.get("i6_start_refused")
        )

    # The two distances section 7 reports, from the DECISION quantity (I1) and never from
    # the cross-check instrument.
    i1_reached = row.get("i1_reached_width_m")
    row["w_reached_source"] = "I1 (Grasp.Result.reached_width_m)"
    if i1_reached is not None:
        row["d_narrow_m"] = i1_reached - edge_lo
        row["d_wide_m"] = edge_hi - i1_reached

    # `holding_S` -- the comparison quantity, from a BUILD of `4ef2d7c` (V12). Its inputs
    # are section 2.1's, named there rather than left to this harness: the reached position
    # is I1's `reached_width_m` carried back through the shipped `gripper_position_for`,
    # the two booleans are I2's, and the command is this trial's. So `holding_F` and
    # `holding_S` are evaluated on ONE event, never on two.
    if superseded is not None and i1_reached is not None and row.get("stalled") is not None:
        q_for_s = predicate.position(i1_reached)
        row["holding_S_input_position_rad"] = q_for_s
        row["holding_S"] = superseded.holding(
            command_m, q_for_s, bool(row["stalled"]), bool(row["reached_goal"]))
    else:
        row["holding_S"] = None
        row["holding_S_unavailable_reason"] = (
            "V12: no superseded build, or no I1 width, or no I2 booleans on this trial")
    return row


# ---------------------------------------------------------------------------
# One block
# ---------------------------------------------------------------------------
def schedule_for(block: str, arguments) -> tuple[list[tuple[int, float | None]], dict]:
    """The stops this block runs, and how they were decided.

    `criteria.md` section 5.1: the STEP is registered and the INTERVAL is located by the
    coarse data. Every refusal below is that sentence made executable.
    """
    if arguments.shakedown:
        # Section 10's one shakedown, and it is not data. Two trials in one run: one
        # stopped, one on plain mock, because the two rig shapes substitute different
        # plugins and a defect in either would otherwise be found during the campaign.
        return [(0, SHAKEDOWN_STOP_MM), (0, None)], {
            "how": "criteria.md section 10's shakedown; the stop is on neither campaign "
                   "grid and the second trial is arm CTL's plugin substitution",
        }

    definition = common.BLOCKS[block]
    kind = definition["stops"]
    if kind == "coarse":
        stops = list(common.coarse_grid(definition["arm"]))
        how = {"how": f"criteria.md section 5.1 stage 1, arm {definition['arm']}'s "
                      f"registered {common.COARSE_STEP_MM} mm coarse grid"}
    elif kind == "fine":
        if arguments.low_mm is None or arguments.high_mm is None:
            raise SystemExit(
                f"block {block} is a refinement and needs --low-mm and --high-mm, the two "
                "endpoints of the coarse interval the coarse stage LOCATED"
            )
        stops = list(common.fine_grid(definition["arm"], arguments.low_mm, arguments.high_mm))
        how = {"how": f"criteria.md section 5.1 stage 2, {common.FINE_STEP_MM} mm across "
                      f"the located coarse interval [{arguments.low_mm}, "
                      f"{arguments.high_mm}] mm, inclusive of both endpoints",
               "located_interval_mm": [arguments.low_mm, arguments.high_mm],
               "refines": common.REFINED_PREDICATE[block]}
    elif kind == "given":
        if not arguments.stops_mm:
            raise SystemExit(
                "block INV needs --stops-mm, the four fine-grid stops straddling F's two "
                "verdict changes (criteria.md section 5.2's sub-condition INV)"
            )
        stops = [round(float(value), 2) for value in arguments.stops_mm.split(",")]
        if len(stops) != 4:
            raise SystemExit(
                f"INV runs FOUR straddling stops and {len(stops)} were given. "
                "criteria.md section 5.2 registers four and section 6 registers 12 trials."
            )
        for stop in stops:
            if not common.on_a_fine_grid(stop):
                raise SystemExit(
                    f"{stop} mm is not a point of either arm's fine grid, so it is not a "
                    "stop this campaign runs (criteria.md section 5.1)"
                )
        how = {"how": "criteria.md section 5.2 sub-condition INV: the four fine-grid stops "
                      "straddling F's two verdict changes, at the second command",
               "stops_mm": stops}
    elif kind == "none":
        stops = [None]
        how = {"how": "criteria.md section 5.3: no stop at all, the gripper's block on "
                      "plain mock_components/GenericSystem"}
    else:  # pragma: no cover - the table above has four kinds
        raise SystemExit(f"unknown stop kind {kind!r} for block {block}")

    for stop in stops:
        if stop is not None and common.arm_of_stop(stop) is None:
            raise SystemExit(
                f"{stop} mm lies outside both coarse spans {common.COARSE_SPANS_MM}. "
                "criteria.md section 5.1: no stop outside them is run, whatever the coarse "
                "grid shows."
            )

    schedule = [(cycle, stop)
                for cycle in range(definition["repeats"])
                for stop in stops]
    return schedule, how


def main() -> int:
    parser = argparse.ArgumentParser(
        description="one block of criteria.md section 6's design")
    parser.add_argument("--out", required=True)
    parser.add_argument("--block", required=True,
                        help=f"one of {', '.join(common.BLOCK_ORDER)}")
    parser.add_argument("--low-mm", type=float, default=None,
                        help="a refinement's located coarse interval, lower endpoint")
    parser.add_argument("--high-mm", type=float, default=None,
                        help="a refinement's located coarse interval, upper endpoint")
    parser.add_argument("--stops-mm", default=None,
                        help="INV's four straddling stops, comma separated, in mm")
    # The one shakedown `criteria.md` section 10 permits, and NOTHING ELSE. Deliberately
    # not a `--stops` flag on the campaign path: an option that could select the sweep
    # would be an option that could move it after seeing data.
    parser.add_argument("--shakedown", action="store_true")
    parser.add_argument(
        "--eval", default=str(Path(__file__).resolve().parent / "predicate_eval"))
    parser.add_argument(
        "--eval-superseded",
        default=str(Path(__file__).resolve().parent / "predicate_eval_superseded"))
    arguments = parser.parse_args()

    if not arguments.shakedown and arguments.block not in common.BLOCKS:
        raise SystemExit(
            f"unknown block {arguments.block!r}; criteria.md section 6 registers "
            f"{', '.join(common.BLOCK_ORDER)}"
        )
    definition = common.BLOCKS.get(arguments.block, common.BLOCKS["LO-C"])
    label = "SHAKEDOWN" if arguments.shakedown else arguments.block

    out = Path(arguments.out)
    logs = out / "logs"
    document, manager = common.load_plan()
    namespace = manager.node.rsplit("/", 1)[0]
    travel = common.travel_from_plan(manager)
    parts = common.parts_from_plan(document)
    edges = common.window_m(travel, parts)

    predicate = common.Predicate(Path(arguments.eval), travel, parts)
    superseded_path = Path(arguments.eval_superseded)
    superseded = (
        common.SupersededPredicate(superseded_path, travel)
        if superseded_path.exists() else None
    )

    command_m = definition["command_m"]
    # Section 5.2's command is L0's `default_grasp_width_m`, and it is ASSERTED against the
    # plan rather than trusted. A campaign commanding a width the model no longer declares
    # would be measuring the window at a command nobody sends.
    plan_default = common.plan_default_grasp_width_m(manager)
    if abs(plan_default - common.W_CMD_SHIPPED_M) > 1e-12:
        raise SystemExit(
            f"the plan delivers gripper_default_grasp_width_m = {plan_default!r} and "
            f"criteria.md section 5.2 registers {common.W_CMD_SHIPPED_M!r}. The command "
            "this campaign sends is the production command, and it is no longer that."
        )
    q_cmd = predicate.position(command_m)

    floor_m = None
    if superseded is not None:
        floor_m = common.superseded_flip_m(superseded, common.W_CMD_SHIPPED_M)

    # P6's registered outcome, computed HERE from L0 rather than imported. `criteria.md`
    # section 7.5: `stall_timeout` times `max_drive_rate_rad_s` is where the rate-limited
    # ramp has reached when the stall detector fires on a plugin whose velocity channel is
    # dead. That the 2026-09-01 campaign observed the same triple is AGREEMENT and is not
    # this campaign's data; nothing of its is differenced against anything here (rule H).
    settings = common.controller_settings(manager)
    p6_rest_rad = float(settings["stall_timeout_s"]) * float(settings["max_drive_rate_rad_s"])

    schedule, how = schedule_for(arguments.block, arguments)

    start_snapshot = common.snapshot()
    header = {
        "campaign": "2026-09-03-stall-band-flip",
        "block": label,
        "question": "criteria.md section 1 -- where the shipped predicate's verdict flips, "
                    "at each edge of its window, bracketed to 0.05 mm or finer",
        "arm": definition["arm"],
        "stops": how,
        "repeats": 1 if arguments.shakedown else definition["repeats"],
        "trials_scheduled": len(schedule),
        "commanded_width_m": command_m,
        "q_cmd_rad": q_cmd,
        "travel": travel,
        "parts": parts,
        "window_m": {"edge_lo": edges[0], "edge_hi": edges[1]},
        "floor_m": floor_m,
        "floor_note": "criteria.md section 2.2's closed-form floor, solved by bisection on "
                      "the SUPERSEDED BUILD's own answer at the shipped command. Rule H "
                      "admits it into FLOOR1 because it is COMPUTED here; ADR-0052 section "
                      "A.6's cited figure is named beside it and enters no arithmetic.",
        "section_2_cross_check": section_2_cross_check(
            predicate, floor_m if floor_m is not None else float("nan"), edges,
            predicate.margin(common.W_CMD_SHIPPED_M)),
        "predicate_eval": predicate.describe(),
        "superseded": common.superseded_provenance(),
        "controller_settings": settings,
        "p6": {
            "rest_position_rad": p6_rest_rad,
            "rest_width_m": predicate.width(p6_rest_rad),
            "two_width_tolerances_m": 2.0 * predicate.tolerance(p6_rest_rad),
            "derivation": "stall_timeout x max_drive_rate_rad_s, both read from the "
                          "generated configuration and the generated plan",
        },
        "host": common.host_facts(),
        "thresholds": {
            "mis_width_m": common.MIS_WIDTH_M,
            "bracket_step_mm": common.BRACKET_STEP_MM,
            "rest_tolerance_m": common.REST_TOLERANCE_M,
            "v4_tolerance_m": common.V4_TOLERANCE_M,
            "v14_tolerance_m": common.V14_TOLERANCE_M,
            "v7_load_threshold": common.V7_LOAD_THRESHOLD,
        },
        "v3_contact_witness": "structurally absent -- this rig has no simulator, so nothing "
                              "can touch anything and V3's 'nothing was between the pads' "
                              "is discharged by construction rather than by a sensor",
        "v1_start": start_snapshot,
        "is_shakedown": bool(arguments.shakedown),
    }
    writer = common.TrialWriter(out, label, header)

    if not header["section_2_cross_check"]["all_agree"]:
        print("NOTE: the shipped code and criteria.md section 2's table DISAGREE. The "
              "block still runs; the disagreement is on the header and analyse.py prints "
              "it either way.")

    rclpy.init()
    cycle_bounds: dict[int, dict] = {}
    current_cycle = None
    for index, (cycle, stop_mm) in enumerate(schedule, start=1):
        if cycle != current_cycle:
            if current_cycle is not None:
                cycle_bounds[current_cycle]["end"] = common.snapshot()
                cycle_bounds[current_cycle]["load_end"] = common.host_load()
                print(f"== cycle {current_cycle} closed ==")
                # Section 6's quiesce, between a teardown and the next launch. It is a
                # quiesce for an instrument and sequences no bring-up (P4).
                time.sleep(common.QUIESCE_S)
            cycle_bounds[cycle] = {
                "start": common.snapshot(), "load_start": common.host_load()}
            current_cycle = cycle
            print(f"== cycle {cycle} opened, load "
                  f"{cycle_bounds[cycle]['load_start']['load_1m']} ==")

        stop_q = None if stop_mm is None else predicate.position(stop_mm / 1000.0)
        name = "no_stop" if stop_mm is None else f"{stop_mm:.2f}"
        log = logs / f"{label}_{index:03d}_{name}.log"
        print(f"[{index}/{len(schedule)}] block {label} cycle {cycle} stop {name} mm"
              + ("" if stop_q is None else f" -> q {stop_q!r} rad"))

        # The shakedown runs one stopped trial and one on plain mock, so its arm is a
        # property of the trial rather than of the block. On the campaign path the block's
        # arm is the block's, and this expression returns it.
        arm = definition["arm"] if not arguments.shakedown else (
            "LO" if stop_mm is not None else "CTL")
        row: dict = {
            "trial": index,
            "cycle": cycle,
            "arm": arm,
            "block_label": label,
            "w_stop_mm": stop_mm,
            "stop_position_rad": stop_q,
            "stop_lower_rad": None if stop_q is None else common.STOP_LOWER_RAD,
            "w_cmd_m": command_m,
            "q_cmd_rad": q_cmd,
            "stroke": "closing",
            "v3_contact_witness": header["v3_contact_witness"],
            "v3_ok": True,
            "log": log.name,
        }
        run_trial(manager, predicate, superseded, row, log, command_m, stop_q, q_cmd,
                  edges, namespace)
        row["v1"] = None  # filled in below, once the cycle's second reading exists
        writer.add(row)
        print(f"    holding_F={row.get('holding_F')} holding_S={row.get('holding_S')} "
              f"w_reached(I1)={row.get('i1_reached_width_m')} "
              f"v5={row.get('v5_valid')} v14={row.get('v14_ok')}")

    if current_cycle is not None:
        cycle_bounds[current_cycle]["end"] = common.snapshot()
        cycle_bounds[current_cycle]["load_end"] = common.host_load()

    # V1 and V7 travel ON the record and are computed here, where the block was taken. They
    # are written back over the rows once the cycle's second reading exists, which is the
    # earliest instant at which the CONJUNCTION has a value at all.
    for row in writer.rows:
        bounds = cycle_bounds[row["cycle"]]
        row["v1"] = common.v1(bounds["start"], bounds["end"])
        row["v1_clean"] = row["v1"]["v1_clean"]
        row["i9"] = {"start": bounds["load_start"], "end": bounds["load_end"]}
        row["v7_flagged"] = bool(
            common.v7(bounds["load_start"]) or common.v7(bounds["load_end"]))
    writer.flush()

    rclpy.shutdown()
    predicate.close()
    if superseded is not None:
        superseded.close()
    clean = sum(1 for row in writer.rows if row.get("v1_clean"))
    print(f"wrote {writer.path}: {len(writer.rows)} trials, {clean} with v1_clean")
    if clean != len(writer.rows):
        print("WARNING: V1 is NOT clean for every cycle of this block. Every record "
              "carries both readings; criteria.md V1 DISCARDS the block rather than "
              "relabelling it, and analyse.py is what applies that.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
