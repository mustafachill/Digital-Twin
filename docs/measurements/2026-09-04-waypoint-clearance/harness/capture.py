#!/usr/bin/env python3
"""The capture stage: one block, three scenarios, one recorder alive across all three.

`criteria.md` section 6. A block is one container session; within it the three captures run
in the fixed order BRINGUP, PICKPLACE, LINE with **one recorder alive across all three**, so
no capture owns a recorder start-up and every capture is sampled by the same instrument in
the same session.

DERIVED IN SHAPE FROM `docs/measurements/2026-09-04-following-error/harness/measure.py`,
copied at commit `0712272` -- the block header, the V1 opening reading taken before
`rclpy.init()`, the pre-first-goal refusal, and the `try` / `except BaseException` / `finally`
abort path whose FIRST act is `writer.seal(...)`. That directory is FROZEN
(`docs/measurements/README.md` rule 2) and nothing in it is edited from here.

**ONE STRUCTURAL DIFFERENCE FROM THAT ANCESTOR, AND IT CHANGES THE WHOLE SHAPE.** That rig
brought one cell up per block with `simulation.launch.py` and drove goals into it. This one
brings up **no cell at all**: `criteria.md` rule C-i records that each scenario starts its own
`move_group` through `IncludeLaunchDescription` inside its own process
(`tests/scenarios/bringup.py:110`) and **every run owns its own cell**. So this module
launches `./scripts/scenario <name>` three times, and the graph it is subscribed to appears
and disappears three times underneath it. Two consequences, both registered:

  * There is no `CITE_SIDE_READY` gate here and no readiness wait before a scenario, because
    there is nothing to wait for -- the scenario is what creates the cell. What is waited on
    is the DOOR (rule C-i), and it is waited on *while* the scenario runs.
  * V2, V3, V4 and V5 are read **per capture**, off the cell that produced that capture's
    trajectories, and they travel on every row that cell produced. A block-level reading
    would be a reading of whichever cell happened to be up when it was taken.

V12 IS SATISFIED BY CONSTRUCTION AND IS RECORDED AS A POSITIVE FINDING. This harness
constructs no Gazebo environment and makes no `gz` call at all: it is a ROS subscriber and a
subprocess launcher. The scenarios start their own Gazebo processes through the shipped
launch, which carries the partition (ADR-0042). `v12_gz_calls` is `0` on every record so that
a reader checks the claim rather than trusting it -- an unpartitioned `gz model --list`
reaches no world and **exits 0**, so a raw call would produce plausible silence.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import rclpy
from moveit_msgs.msg import DisplayTrajectory, PlanningSceneComponents
from moveit_msgs.srv import GetPlanningScene
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

SHAKEDOWN_LABEL = "SHAKEDOWN"

#: A block refused before its first capture writes no record and returns this. Distinct from
#: every exit code `run_cell_block.sh` produces, so the campaign log says which layer refused.
BLOCK_REFUSED_EXIT = 6

#: How often the graph is polled for a matched publisher and for the arrival of a scene. **It
#: sequences nothing** (V13, P4): the scenario is already running, and this only observes.
POLL_S = 0.05

#: How often I4 is re-read while a capture's scene is still empty. It sequences nothing: the
#: scenario is already running and this only observes. The shakedown established that bring-up
#: applies the generated planning scene AFTER `move_group` starts answering.
SCENE_REREAD_S = 5.0

#: A bound on one scenario. `continuous_line` is the longest capture this campaign takes and
#: the tree's own ceilings live inside the scenario; this is the outer bound on the SUBPROCESS
#: and is deliberately far above any of them, so that it is the scenario's ceilings that fire
#: and never this one. It is not registered in `criteria.md` and decides no quantity.
SCENARIO_WALL_CEILING_S = 3600.0


class Recorder(Node):
    """I1 and V4: every `DisplayTrajectory` on every arm's `display_planned_path`.

    THE QoS IS DECLARED EXPLICITLY AND MATCHED DELIBERATELY (CLAUDE.md section 10).
    `criteria.md` section 2.1: `DisplayMotionPath` publishes with `rclcpp::SystemDefaultsQoS()`
    -- every policy `*_SYSTEM_DEFAULT`, resolved in the RMW and **not latched**. A subscriber
    must therefore be compatible with whatever the RMW resolves and must be alive before the
    publication, which is why this node is created once and outlives all three scenarios.

    `KEEP_ALL` rather than a depth: a depth would make this subscriber's own queue a source of
    the loss rule C-ii measures, and the whole point of C-ii is to attribute a shortfall to the
    publisher's side rather than to the instrument. **Every matched publisher's resolved
    endpoint QoS is recorded** (V4), and section 2.1 registers that TWO are expected per arm --
    one per pipeline, each pipeline loading its own `DisplayMotionPath` instance.
    """

    def __init__(self) -> None:
        super().__init__("cite_waypoint_clearance_recorder")
        self.callbacks = ReentrantCallbackGroup()
        self.profile = QoSProfile(
            history=HistoryPolicy.KEEP_ALL,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.lock = threading.Lock()
        self.capture: str | None = None
        self.received: list[dict] = []
        self.counts = {arm: 0 for arm in common.ARMS}
        self.topics = {arm: common.display_topic(arm) for arm in common.ARMS}
        self.subscriptions_by_arm = {
            arm: self.create_subscription(
                DisplayTrajectory,
                topic,
                self._make_callback(arm),
                self.profile,
                callback_group=self.callbacks,
            )
            for arm, topic in self.topics.items()
        }
        self.scene_clients = {
            arm: self.create_client(
                GetPlanningScene,
                f"{common.arm_namespace(arm)}/get_planning_scene",
                callback_group=self.callbacks,
            )
            for arm in common.ARMS
        }

    # -- I1 ----------------------------------------------------------------
    def _make_callback(self, arm: str):
        def handle(message: DisplayTrajectory) -> None:
            received_at = time.time()
            with self.lock:
                capture = self.capture
                self.counts[arm] += 1
                index = self.counts[arm]
                self.received.append(_trajectory_record(arm, capture, index, received_at,
                                                        message))
        return handle

    # -- V4 and rule C-i ---------------------------------------------------
    def publishers_on(self, arm: str) -> list[dict]:
        """Every matched publisher's resolved endpoint QoS, from the running graph.

        A POSITIVE reading: an empty list is an empty list and is never read as "no
        disagreement found". Section 2.1's expectation of two per arm is recorded against what
        is actually found, and a mismatch is reported rather than corrected.
        """
        found = []
        for info in self.get_publishers_info_by_topic(self.topics[arm]):
            profile = info.qos_profile
            found.append(
                {
                    "node": info.node_name,
                    "namespace": info.node_namespace,
                    "endpoint_type": str(info.endpoint_type),
                    "topic_type": info.topic_type,
                    "reliability": str(profile.reliability),
                    "durability": str(profile.durability),
                    "history": str(profile.history),
                    "depth": profile.depth,
                    "liveliness": str(profile.liveliness),
                }
            )
        return found

    def resolved_topics(self) -> dict:
        """The name resolution of section 2.1, checked against the RUNNING graph.

        Section 2.1 registers the expected name as a resolution argument and NOT as a reading
        off a running cell -- no cell was up when `criteria.md` was written. This records
        every `display_planned_path` the graph actually carries, so a mismatch is reported and
        never silently corrected.
        """
        graph = {
            name: types
            for name, types in self.get_topic_names_and_types()
            if name.endswith("/" + common.DISPLAY_TOPIC)
        }
        # A TOPIC NAME ON THE GRAPH IS NOT A PUBLISHER, and this node's own three
        # subscriptions put all three expected names there whether or not a cell exists. The
        # shakedown printed `expected_all_present: true` before any scenario had started, off
        # a graph holding nothing but this recorder. The publisher count is the reading that
        # means something, and it is recorded beside the names rather than instead of them.
        return {
            "expected": dict(self.topics),
            "found_on_graph": graph,
            "expected_all_present": all(topic in graph for topic in self.topics.values()),
            "unexpected": sorted(set(graph) - set(self.topics.values())),
            "publisher_count_by_topic": {
                name: len(self.get_publishers_info_by_topic(name)) for name in graph
            },
            "note": "this node's own subscriptions put every expected name on the graph, so "
                    "`expected_all_present` is not evidence that a cell is up; "
                    "`publisher_count_by_topic` is",
        }

    # -- I4 ----------------------------------------------------------------
    def planning_scene(self, arm: str, timeout_s: float) -> dict:
        """I4 -- the scene the planner actually held, in the frame `move_group` reports.

        **The object poses the compute stage uses are these**, not the generated file's, so no
        frame convention of that file has to be trusted (section 2.2). `link_padding` and
        `link_scale` are recorded because the compute stage is UNPADDED: a non-zero padding
        makes MoveIt's verdict and this campaign's distance two different quantities, and
        section 7.6's VALID1 and rule E both need the value stated rather than assumed.
        """
        client = self.scene_clients[arm]
        if not client.wait_for_service(timeout_sec=timeout_s):
            return {"read_ok": False, "why": "get_planning_scene was never advertised"}
        request = GetPlanningScene.Request()
        request.components.components = (
            PlanningSceneComponents.WORLD_OBJECT_GEOMETRY
            | PlanningSceneComponents.TRANSFORMS
            | PlanningSceneComponents.ALLOWED_COLLISION_MATRIX
            | PlanningSceneComponents.LINK_PADDING_AND_SCALING
        )
        future = client.call_async(request)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not future.done():
            time.sleep(POLL_S)
        if not future.done():
            return {"read_ok": False, "why": f"get_planning_scene never answered in {timeout_s}s"}
        response = future.result()
        scene = response.scene
        objects = {}
        for obj in scene.world.collision_objects:
            entry = {
                "frame_id": obj.header.frame_id,
                "primitives": [
                    {"type": int(primitive.type), "dimensions": list(primitive.dimensions)}
                    for primitive in obj.primitives
                ],
                "primitive_poses": [
                    {
                        "xyz": [pose.position.x, pose.position.y, pose.position.z],
                        "quaternion_xyzw": [
                            pose.orientation.x, pose.orientation.y,
                            pose.orientation.z, pose.orientation.w,
                        ],
                    }
                    for pose in obj.primitive_poses
                ],
                "pose": {
                    "xyz": [obj.pose.position.x, obj.pose.position.y, obj.pose.position.z],
                    "quaternion_xyzw": [
                        obj.pose.orientation.x, obj.pose.orientation.y,
                        obj.pose.orientation.z, obj.pose.orientation.w,
                    ],
                },
                "meshes": len(obj.meshes),
            }
            objects[obj.id] = entry
        return {
            "read_ok": True,
            "planning_frame": scene.world.collision_objects[0].header.frame_id
            if scene.world.collision_objects else scene.robot_model_name,
            "robot_model_name": scene.robot_model_name,
            "object_count": len(objects),
            "objects": objects,
            "link_padding": [
                {"link_name": entry.link_name, "padding": entry.padding}
                for entry in scene.link_padding
            ],
            "link_scale": [
                {"link_name": entry.link_name, "scale": entry.scale}
                for entry in scene.link_scale
            ],
            "allowed_collision_entries": len(scene.allowed_collision_matrix.entry_names),
        }


def _trajectory_record(arm: str, capture: str | None, index: int, received_at: float,
                       message: DisplayTrajectory) -> dict:
    """One captured trajectory, recorded WHOLE (I1).

    `trajectory_start.joint_state` is recorded in full because section 5.4's completion
    depends on it: it is a full MoveIt `RobotState` with every `<mimic>` already enforced by
    MoveIt's own `RobotModel` (`display_motion_path.cpp:89`), and it is what gives the
    gripper's six moving links a configuration at all.

    V15: the receive time and the header stamp are both recorded and **both are labels**. No
    verdict in section 7 depends on a clock.
    """
    start = message.trajectory_start.joint_state
    points = []
    if message.trajectory:
        joint = message.trajectory[0].joint_trajectory
        names = list(joint.joint_names)
        for point in joint.points:
            points.append(
                {
                    "positions": [float(value) for value in point.positions],
                    "time_from_start": point.time_from_start.sec
                    + point.time_from_start.nanosec * 1e-9,
                }
            )
        header_stamp = joint.header.stamp.sec + joint.header.stamp.nanosec * 1e-9
        multi_dof = len(message.trajectory[0].multi_dof_joint_trajectory.points)
    else:
        names = []
        header_stamp = None
        multi_dof = 0
    return {
        "arm": arm,
        "capture": capture,
        "receive_index_in_arm": index,
        "received_at_wall": received_at,
        "received_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(received_at)),
        "model_id": message.model_id,
        "trajectory_count_in_message": len(message.trajectory),
        "joint_names": names,
        "points": points,
        "waypoints": len(points),
        "header_stamp_s": header_stamp,
        "multi_dof_points": multi_dof,
        "trajectory_start": {
            "name": list(start.name),
            "position": [float(value) for value in start.position],
        },
    }


def run_capture(recorder: Recorder, name: str, scenario: str, logs: Path,
                tag: str, timeout_s: float) -> dict:
    """One capture: start the scenario, watch the door, read the cell, wait for the exit.

    THE DOOR IS WATCHED WHILE THE SCENARIO RUNS AND NOT BEFORE IT (rule C-i). The publisher
    is created by `DisplayMotionPath::initialize` on a `move_group` the scenario itself
    starts, so a wait before the scenario would be a wait for something that does not exist --
    which is the dead clause rule C-i was restated to remove.
    """
    log_path = logs / f"{tag}_{name}.log"
    started_wall = time.time()
    started = time.monotonic()
    with recorder.lock:
        recorder.capture = name
        first_index = {arm: recorder.counts[arm] for arm in common.ARMS}

    print(f"== {name}: ./scripts/scenario {scenario} -> {log_path.name} ==", flush=True)
    with log_path.open("w") as handle:
        process = subprocess.Popen(
            [str(common.repo_root() / "scripts" / "scenario"), scenario],
            stdout=handle,
            stderr=subprocess.STDOUT,
            cwd=str(common.repo_root()),
        )

        door: dict[str, dict] = {}
        geometry: dict[str, dict] = {}
        scene: dict[str, dict] = {}
        scene_attempts: dict[str, int] = {arm: 0 for arm in common.ARMS}
        next_scene_read = started
        deadline = started + timeout_s
        while process.poll() is None and time.monotonic() < deadline:
            for arm in common.ARMS:
                if arm not in door:
                    publishers = recorder.publishers_on(arm)
                    if publishers:
                        waited = time.monotonic() - started
                        door[arm] = {
                            "matched_publisher_count": len(publishers),
                            "matched_publishers": publishers,
                            "waited_s": waited,
                            "matched_at_wall": time.time(),
                            "ceiling_s": common.DOOR_CEILING_S,
                            "within_ceiling": waited <= common.DOOR_CEILING_S,
                            "subscription_qos": {
                                "history": "KEEP_ALL",
                                "reliability": "RELIABLE",
                                "durability": "VOLATILE",
                            },
                            "topic": recorder.topics[arm],
                        }
                        print(f"   door open on {arm} after {waited:.1f}s, "
                              f"{len(publishers)} matched publisher(s)", flush=True)
                elif arm not in geometry:
                    # I3, V2 and V3, read off the cell THIS capture is running. Taken once the
                    # door is open, because that is the first instant the arm's own nodes are
                    # provably on the graph.
                    geometry[arm] = common.running_geometry(common.arm_namespace(arm),
                                                            timeout_s=60.0)
                    print(f"   V2/V3 on {arm}: chars={geometry[arm]['description_chars']} "
                          f"hulls={geometry[arm]['hull_collision_refs']} "
                          f"v2={geometry[arm]['v2_ok']} v3={geometry[arm]['v3_ok']}",
                          flush=True)
                elif not scene.get(arm, {}).get("object_count"):
                    # I4 IS RE-READ UNTIL THE SCENE IS NON-EMPTY, and the shakedown is why.
                    # Read once at the instant the door opened, the scene came back with ZERO
                    # objects on all three arms: bring-up applies the generated planning scene
                    # after `move_group` starts answering, so a single early read records an
                    # empty world -- and the compute stage's every distance would then be a
                    # distance to nothing. V5 discards a block whose read-back is empty, so a
                    # harness that reads too early would discard every block for a defect of
                    # its own. The LAST non-empty read is what travels; the attempt count and
                    # the first non-empty instant travel with it.
                    if time.monotonic() >= next_scene_read:
                        next_scene_read = time.monotonic() + SCENE_REREAD_S
                        scene_attempts[arm] += 1
                        reading = recorder.planning_scene(arm, timeout_s=30.0)
                        reading["attempts"] = scene_attempts[arm]
                        reading["read_at_s_into_capture"] = time.monotonic() - started
                        previous = scene.get(arm)
                        if reading.get("object_count") or previous is None:
                            scene[arm] = reading
                        if reading.get("object_count"):
                            print(f"   I4 on {arm}: read_ok={reading.get('read_ok')} "
                                  f"objects={reading.get('object_count')} after "
                                  f"{scene_attempts[arm]} attempt(s), "
                                  f"{reading['read_at_s_into_capture']:.0f}s into the capture",
                                  flush=True)
            time.sleep(POLL_S)

        # A SETTLED publisher reading, taken while the cell is still up. The first-match
        # reading is a snapshot of a graph mid-discovery -- the shakedown caught arm_1 with
        # ONE publisher at 2.4 s and arm_2 and arm_3 with THREE at 5.8 s -- and V4's
        # expectation of two per arm is a statement about a settled graph, not about the
        # instant a subscription first matched. BOTH readings travel; neither replaces the
        # other, and V4 is stated over the settled one with the first-match count beside it.
        settled = {arm: recorder.publishers_on(arm) for arm in common.ARMS}

        timed_out = process.poll() is None
        if timed_out:
            process.kill()
        exit_code = process.wait()

    text = log_path.read_text(errors="replace")
    scrape = common.scrape_capture_log(text)
    with recorder.lock:
        recorder.capture = None
        gained = {arm: recorder.counts[arm] - first_index[arm] for arm in common.ARMS}

    record = {
        "capture": name,
        "scenario": scenario,
        "log": str(log_path),
        "log_sha256": common.sha256(log_path),
        "started_at_wall": started_wall,
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_wall)),
        "duration_s": time.monotonic() - started,
        "subprocess_exit_code": exit_code,
        "subprocess_timed_out": timed_out,
        "subprocess_wall_ceiling_s": timeout_s,
        "received_by_arm": gained,
        "received_total": sum(gained.values()),
        "door": door,
        # Rule C-i, per arm: an arm that never matched within the ceiling fails C-i for this
        # capture. Recorded as a POSITIVE finding per arm, so a missing arm is a missing arm.
        "door_by_arm": {
            arm: {
                **door.get(arm, {"matched_publisher_count": 0, "within_ceiling": False,
                                 "waited_s": None, "matched_publishers": []}),
                "settled_publisher_count": len(settled.get(arm, [])),
                "settled_publishers": settled.get(arm, []),
            }
            for arm in common.ARMS
        },
        "i4_scene_attempts": scene_attempts,
        "v2": {arm: {key: value for key, value in reading.items() if key != "urdf"}
               for arm, reading in geometry.items()},
        "v3": {arm: {key: reading[key] for key in
                     ("production_plugin_refs", "fixture_plugin_refs", "mock_plugin_refs",
                      "v3_ok")}
               for arm, reading in geometry.items()},
        "i4_scene": scene,
        **scrape,
    }
    return record, geometry


def v14(root: Path) -> dict:
    """V14 -- the recorder is on the graph the cell is on.

    The failure this rule exists for produces a complete, empty, PLAUSIBLE capture: a recorder
    on another domain matches nothing, receives nothing, and reports a quiet cell. The domain
    the generated plan resolves for the plant side is asked of `cite_bringup.plan`, which is
    the one place a base and an offset are added (CLAUDE.md section 2), rather than
    recomputed here.
    """
    environment = os.environ.get("ROS_DOMAIN_ID")
    reading = {
        "ros_domain_id_env": environment,
        "cite_domain_base_env": os.environ.get("CITE_DOMAIN_BASE"),
        "resolved_from_plan": None,
        "resolver": None,
        "v14_ok": None,
    }
    try:
        from ament_index_python.packages import get_package_share_directory  # noqa: PLC0415
        from cite_bringup.plan import (  # noqa: PLC0415
            PLANT_SIDE,
            domain_base,
            load,
            resolve_domain_id,
        )

        # The plan is loaded from the INSTALLED share directory, which is what the launch
        # itself reads, and `domain_base` and `resolve_domain_id` are asked for the answer
        # rather than `base + offset` being added here -- that addition is written in exactly
        # one place on purpose (ADR-0044 clause 4), and a second copy is a value in two places.
        share = Path(get_package_share_directory("cite_generated"))
        plan = load(share / "bringup" / f"{common.ZONE}_plan.yaml")
        resolved = resolve_domain_id(plan, PLANT_SIDE, domain_base(os.environ))
        reading["resolved_from_plan"] = int(resolved)
        reading["resolver"] = (
            "cite_bringup.plan.resolve_domain_id(plan, PLANT_SIDE, domain_base(environ))"
        )
        reading["v14_ok"] = environment is not None and int(environment) == int(resolved)
    except BaseException as error:  # noqa: BLE001 - a failure to resolve is a THIRD state
        reading["resolver"] = f"unavailable: {error!r}"
        reading["v14_ok"] = None
    del root
    return reading


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="the raw/ directory to write into")
    parser.add_argument("--block", required=True, help="B1, B2, B3 -- or SHAKEDOWN")
    parser.add_argument(
        "--captures",
        default=",".join(common.CAPTURE_NAMES),
        help="the captures to take, in order. criteria.md section 6 registers all three for "
             "a campaign block; a shakedown may take fewer and is not data either way",
    )
    parser.add_argument(
        "--shakedown",
        action="store_true",
        help="criteria.md section 10 -- ONE run per harness, published under raw/shakedown/, "
             "excluded from every figure in section 7, and it may not set or adjust any "
             "threshold",
    )
    arguments = parser.parse_args()

    label = SHAKEDOWN_LABEL if arguments.shakedown else arguments.block
    out = Path(arguments.out)
    logs = out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    wanted = [name.strip() for name in arguments.captures.split(",") if name.strip()]
    schedule = [(name, scenario) for name, scenario in common.CAPTURES if name in wanted]
    unknown = sorted(set(wanted) - set(common.CAPTURE_NAMES))
    if unknown:
        print(f"ABORT: {unknown} are not registered captures. criteria.md section 3 "
              f"registers {list(common.CAPTURE_NAMES)}", file=sys.stderr)
        return 2

    start_snapshot = common.snapshot()
    start_load = common.host_load()
    print(f"== {label}: V1 opening reading, clean={start_snapshot['clean']} ==", flush=True)
    print(f"   vendor pin: {json.dumps(start_snapshot['vendor_pin'])}", flush=True)
    print(f"   load: {start_load['load_1m']:.2f} {start_load['load_5m']:.2f} "
          f"{start_load['load_15m']:.2f}", flush=True)

    rclpy.init()
    recorder = Recorder()
    executor = MultiThreadedExecutor()
    executor.add_node(recorder)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    writer = None
    try:
        domain = v14(common.repo_root())
        print(f"== V14: {json.dumps(domain)} ==", flush=True)

        header = {
            "label": label,
            "block": arguments.block,
            "is_shakedown": bool(arguments.shakedown),
            "captures_scheduled": [name for name, _ in schedule],
            "criteria_sha256": start_snapshot["criteria_sha256"],
            "base_commit": common.BASE_COMMIT,
            "v1_start": start_snapshot,
            "load_start": start_load,
            "v7_start": common.v7(start_load),
            "v14": domain,
            # V12, as a POSITIVE assertion rather than an absence. This process makes no
            # Gazebo-transport call of any kind; the scenarios carry the partition themselves.
            "v12_gz_calls": 0,
            "v12_note": "the harness constructs no Gazebo environment and makes no gz call "
                        "(criteria.md V12); the scenarios start their own Gazebo processes "
                        "through the shipped launch, which carries GZ_PARTITION (ADR-0042)",
            # V13: nothing here sleeps to sequence a bring-up. The scenarios' own gates are
            # the event, and the recorder waits for a matched publisher and for nothing else.
            "v13": {
                "sleeps_to_sequence_bringup": False,
                "note": "the recorder waits for a matched publisher (V4, rule C-i) and for "
                        "nothing else; the scenario is started first and the door is watched "
                        "while it runs",
            },
            "model_hash": start_snapshot["model_hash"],
            "host": common.host_facts(),
            "topics": recorder.resolved_topics(),
            "generated": {
                "planning_scene": common.planning_scene_file(),
                "static_transforms": common.static_transforms(),
                "arms": {arm: common.plan_arm(arm) for arm in common.ARMS},
            },
            "registered_sizes": {
                "close_band_m": common.CLOSE_BAND_M,
                "step_high_m": common.STEP_HIGH_M,
                "step_mid_m": common.STEP_MID_M,
                "diff_floor_m": common.DIFF_FLOOR_M,
                "sub_step_m": common.SUB_STEP_M,
                "sub_ceiling": common.SUB_CEILING,
                "censor_m": common.CENSOR_M,
                "door_ceiling_s": common.DOOR_CEILING_S,
                "loss_ceiling_share": common.LOSS_CEILING_SHARE,
            },
        }
        writer = common.RecordWriter(out, label, header)
        print(f"== topics: {json.dumps(header['topics'])} ==", flush=True)

        for name, scenario in schedule:
            record, geometry = run_capture(
                recorder, name, scenario, logs, label, SCENARIO_WALL_CEILING_S
            )
            for arm, reading in geometry.items():
                urdf = reading.get("urdf") or ""
                if urdf:
                    # The description that actually ran, kept beside the record rather than
                    # inside it: I11's forward kinematics is computed from THIS text, and a
                    # 300 kB string in every row would make the trajectory file unreadable.
                    path = out / f"{label}_{name}_{arm}.urdf"
                    if not path.exists() or path.read_text() != urdf:
                        path.write_text(urdf)
                    record["v2"][arm]["urdf_file"] = path.name
            writer.add_capture(record)
            print(f"== {name}: exit={record['subprocess_exit_code']} "
                  f"received={record['received_total']} i5={record['i5_published']} "
                  f"i6={record['i6_refusals']} in {record['duration_s']:.0f}s ==", flush=True)
            for line in record["i9_verdict_lines"]:
                print(f"   I9: Scenario '{line['scenario']}' {line['rest']}", flush=True)

            # Drain the captured trajectories into the record stream, each carrying its own
            # capture's validity readings (see `RecordWriter.add`).
            with recorder.lock:
                pending = [row for row in recorder.received if row["capture"] == name]
                recorder.received = [row for row in recorder.received if row["capture"] != name]
            for row in pending:
                arm = row["arm"]
                writer.add(
                    {
                        **row,
                        "v2": record["v2"].get(arm),
                        "v3": record["v3"].get(arm),
                        "v4": record["door_by_arm"].get(arm),
                        "v5": None,   # computed by `compute.py` against I4's read-back
                        "i4_scene_read_ok": record["i4_scene"].get(arm, {}).get("read_ok"),
                        "urdf_file": record["v2"].get(arm, {}).get("urdf_file"),
                        "capture_scenario": scenario,
                        "v12_gz_calls": 0,
                        "v13": header["v13"],
                        "v14": domain,
                    }
                )
            print(f"== {name}: {len(pending)} trajectory record(s) written ==", flush=True)

        # Anything that arrived outside a capture window -- between two scenarios, or after
        # the last one -- is recorded rather than dropped, with `capture = None`. It enters no
        # capture's figures (rule T states every verdict per capture) and its existence is a
        # finding about the instrument.
        with recorder.lock:
            stragglers = list(recorder.received)
            recorder.received = []
        for row in stragglers:
            writer.add({**row, "capture": None, "straggler": True})
        if stragglers:
            print(f"== {len(stragglers)} trajectory record(s) arrived OUTSIDE any capture "
                  f"window and carry capture=None ==", flush=True)

        end_snapshot = common.snapshot()
        end_load = common.host_load()
        flags = writer.seal(end_snapshot, end_load,
                            "the block ran to the end of its schedule")
        writer.complete(len(schedule), {"load_end": end_load})
        print(f"== V1 closing reading: v1_clean={flags['v1_clean']} "
              f"disagreed_mid_block={flags['disagreed_mid_block']} ==", flush=True)
        print(f"== {label}: {len(writer.rows)} trajectory record(s) over "
              f"{len(writer.captures)} capture(s) ==", flush=True)

    except BaseException as error:  # noqa: BLE001 -- the abort path must run for anything
        print(f"\n## {label} ABORTED: {error!r}", file=sys.stderr)
        if writer is not None:
            # V1's own sentence: the closing reading is taken AT THE ABORT, as the FIRST act
            # of the abort path, so that V8's promise -- a block ending early is reported with
            # the n it reached -- does not silently lose every row it had.
            try:
                flags = writer.seal(
                    common.snapshot(), common.host_load(), f"the block aborted: {error!r}"
                )
                print(f"## V1 closing reading taken at the abort: "
                      f"v1_clean={flags['v1_clean']}", file=sys.stderr)
            except BaseException as sealing:  # noqa: BLE001
                print(f"## the closing reading itself failed: {sealing!r}", file=sys.stderr)
        raise
    finally:
        try:
            executor.shutdown(timeout_sec=5.0)
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            recorder.destroy_node()
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            rclpy.shutdown()
        except BaseException:  # noqa: BLE001, S110
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
