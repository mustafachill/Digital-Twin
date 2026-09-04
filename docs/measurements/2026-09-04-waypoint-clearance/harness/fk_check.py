#!/usr/bin/env python3
"""I12, FK1 and VALID1 -- MoveIt's own `RobotModel`, checking the reimplementation.

`criteria.md` section 4.2. I11 is a reimplementation, and **a reimplementation that nothing
checks is where a silently wrong frame convention lives**. I12 is MoveIt's own model, which is
what the cell used. They are not averaged and neither corrects the other: FK1 states whether
they agree, and a disagreement is the result (rule D).

DERIVED IN SHAPE FROM `workspace/src/cite_skills/test/test_planning_pipeline.py`, read at
`HEAD` on 2026-09-04 -- the launch description (`robot_state_publisher` + `move_group`, no
simulator and no controllers), the five-entry parameter assembly with the joint-limits and
Cartesian-limits merge, the `/tf` remappings on BOTH nodes, the static-transform broadcast
before anything is applied, the joint-state publisher that stands in for the absent
`joint_state_broadcaster`, the `ApplyPlanningScene` diff plus the read-back that does not
trust it, and `validity_of`'s intersection of contacts with the scene's own object ids
(`test_planning_pipeline.py:418`). That file is production test code and is not edited from
here; this is a copy, and this header says so.

TWO DELIBERATE DIFFERENCES FROM IT.
  * It drives `arm_2`; this drives **whichever arms the sample contains**, one per
    subprocess, because a campaign sample spans every arm that planned. Its own comment
    records why it avoids `arm_1`: `./scripts/test` runs two launch tests concurrently on one
    domain and two `move_group` nodes in one namespace answer each other's service calls.
    **So this rig must not run while `./scripts/test` is running**, and README.md says so.
  * FK is requested in the **model root frame**, not in `base_link`, because that is the
    frame I11 computes in.

WHAT THIS RIG CANNOT DO, and it is registered here rather than discovered: it brings up no
simulator, so nothing here is evidence about motion, contact or the executed path. It answers
exactly two questions -- do the two forward kinematics agree, and does MoveIt's collision
predicate agree in sign with the compute stage's distance.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402


def _launch_description(arm: str):
    """Exactly the assembly `test_planning_pipeline.py:205-258` performs, for one arm."""
    import yaml
    from ament_index_python.packages import get_package_share_directory
    from launch import LaunchDescription
    from launch.substitutions import Command
    from launch_ros.actions import Node
    from launch_ros.parameter_descriptions import ParameterValue

    generated = Path(get_package_share_directory("cite_generated"))

    def resolve(uri: str) -> Path:
        prefix = "package://cite_generated/"
        assert uri.startswith(prefix), f"unexpected artifact reference: {uri}"
        return generated / uri[len(prefix):]

    def read(path: Path) -> dict:
        return yaml.safe_load(path.read_text()) or {}

    plan = common.plan_arm(arm)
    namespace = common.arm_namespace(arm)
    description = ParameterValue(
        Command(["xacro ", str(resolve(plan["description"]))]), value_type=str
    )
    semantic = ParameterValue(Command(["xacro ", str(resolve(plan["srdf"]))]), value_type=str)
    # The joint limits and the Cartesian limits are two files and ONE MoveIt parameter
    # namespace. Pilz's Cartesian parameter listener declares its four keys with no defaults,
    # so a run without the second file does not disable LIN -- it takes move_group down while
    # the pipeline initialises.
    planning = {
        **read(resolve(plan["joint_limits"])),
        **read(resolve(plan["cartesian_limits"])),
    }
    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                namespace=namespace,
                parameters=[{"robot_description": description, "use_sim_time": False}],
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="log",
            ),
            Node(
                package="moveit_ros_move_group",
                executable="move_group",
                name="move_group",
                namespace=namespace,
                parameters=[
                    {
                        "robot_description": description,
                        "robot_description_semantic": semantic,
                        "use_sim_time": False,
                        "publish_robot_description_semantic": True,
                    },
                    {"robot_description_kinematics": read(resolve(plan["kinematics"]))},
                    {"robot_description_planning": planning},
                    read(resolve(plan["planning_pipelines"])),
                    read(resolve(plan["controllers"])),
                ],
                # Without these a namespaced node subscribes inside its namespace and never
                # sees the arm it plans for (`simulation.launch.py:1157-1158`).
                remappings=[("/tf", "/tf"), ("/tf_static", "/tf_static")],
                output="log",
            ),
        ]
    )


class Rig:
    """The node side: joint states, static frames, the scene, FK and validity."""

    def __init__(self, arm: str) -> None:
        import rclpy
        from geometry_msgs.msg import Pose, TransformStamped
        from moveit_msgs.msg import CollisionObject, PlanningScene, PlanningSceneComponents
        from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene, GetPositionFK, \
            GetStateValidity
        from rclpy.callback_groups import ReentrantCallbackGroup
        from rclpy.node import Node as RclpyNode
        from sensor_msgs.msg import JointState
        from shape_msgs.msg import SolidPrimitive
        from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener

        self.rclpy = rclpy
        self.messages = {
            "TransformStamped": TransformStamped,
            "Pose": Pose,
            "CollisionObject": CollisionObject,
            "PlanningScene": PlanningScene,
            "PlanningSceneComponents": PlanningSceneComponents,
            "SolidPrimitive": SolidPrimitive,
            "JointState": JointState,
        }
        self.arm = arm
        self.plan = common.plan_arm(arm)
        self.namespace = common.arm_namespace(arm)
        self.node = RclpyNode(f"cite_waypoint_clearance_fk_{arm}")
        self.callbacks = ReentrantCallbackGroup()

        self.fk = self.node.create_client(
            GetPositionFK, f"{self.namespace}/compute_fk", callback_group=self.callbacks
        )
        self.validity = self.node.create_client(
            GetStateValidity, f"{self.namespace}/check_state_validity",
            callback_group=self.callbacks,
        )
        self.apply_scene = self.node.create_client(
            ApplyPlanningScene, f"{self.namespace}/apply_planning_scene",
            callback_group=self.callbacks,
        )
        self.get_scene = self.node.create_client(
            GetPlanningScene, f"{self.namespace}/get_planning_scene",
            callback_group=self.callbacks,
        )
        self.apply_type = ApplyPlanningScene
        self.get_type = GetPlanningScene
        self.fk_type = GetPositionFK
        self.validity_type = GetStateValidity

        self.frames = StaticTransformBroadcaster(self.node)
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self.node)

        self.scene = common.planning_scene_file()
        self.scene_ids = frozenset(self.scene["objects"])
        self.transforms = common.static_transforms()

        # With no controllers there is no `joint_state_broadcaster`, so this rig IS the state
        # source; without a complete state MoveIt's `CurrentStateMonitor` never converges and
        # `check_state_validity` blocks until the ceiling.
        self.state_names: list[str] = []
        self.state_positions: list[float] = []
        self.publisher = self.node.create_publisher(
            JointState, f"{self.namespace}/joint_states", 10
        )
        self.node.create_timer(0.05, self._publish, callback_group=self.callbacks)

    def _publish(self) -> None:
        if not self.state_names:
            return
        message = self.messages["JointState"]()
        message.header.stamp = self.node.get_clock().now().to_msg()
        message.name = list(self.state_names)
        message.position = [float(value) for value in self.state_positions]
        self.publisher.publish(message)

    def call(self, client, request, timeout: float = 120.0):
        future = client.call_async(request)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.02)
        return None

    def publish_frames(self) -> None:
        """The generated static transforms; without them move_group ACCEPTS the scene diff
        and then silently drops every object, which is a scene that reports success and holds
        nothing."""
        messages = []
        for entry in self.transforms.values():
            message = self.messages["TransformStamped"]()
            message.header.stamp = self.node.get_clock().now().to_msg()
            message.header.frame_id = entry["parent"]
            message.child_frame_id = entry["child"]
            (
                message.transform.translation.x,
                message.transform.translation.y,
                message.transform.translation.z,
            ) = entry["xyz_m"]
            quaternion = _quaternion(*entry["rpy_rad"])
            (
                message.transform.rotation.x,
                message.transform.rotation.y,
                message.transform.rotation.z,
                message.transform.rotation.w,
            ) = quaternion
            messages.append(message)
        self.frames.sendTransform(messages)

    def wait_for_scene_frame(self, timeout: float = 120.0) -> bool:
        from rclpy.duration import Duration
        from rclpy.time import Time

        return self.buffer.can_transform(
            self.plan["base_link"], self.scene["frame_id"], Time(),
            timeout=Duration(seconds=timeout),
        )

    def apply(self) -> dict:
        scene = self.messages["PlanningScene"]()
        # A diff: move_group's scene already holds the robot's own state and its
        # allowed-collision matrix, and replacing it wholesale would discard both.
        scene.is_diff = True
        objects = []
        for name, body in sorted(self.scene["objects"].items()):
            primitive = self.messages["SolidPrimitive"]()
            primitive.type = self.messages["SolidPrimitive"].BOX
            primitive.dimensions = [float(value) for value in body["dimensions_m"]]
            obj = self.messages["CollisionObject"]()
            obj.id = name
            obj.header.frame_id = body["frame_id"]
            obj.primitives = [primitive]
            placed = self.messages["Pose"]()
            placed.position.x, placed.position.y, placed.position.z = body["xyz_m"]
            (
                placed.orientation.x,
                placed.orientation.y,
                placed.orientation.z,
                placed.orientation.w,
            ) = _quaternion(*body["rpy_rad"])
            obj.primitive_poses = [placed]
            obj.operation = self.messages["CollisionObject"].ADD
            objects.append(obj)
        scene.world.collision_objects = objects
        response = self.call(self.apply_scene, self.apply_type.Request(scene=scene))
        applied = bool(response is not None and response.success)

        # Applying is NOT trusted: `ApplyPlanningScene` reports success when the diff was
        # accepted, which is not the same as the objects being in the world.
        request = self.get_type.Request()
        request.components.components = self.messages["PlanningSceneComponents"].WORLD_OBJECT_NAMES
        readback = self.call(self.get_scene, request)
        present = (
            {obj.id for obj in readback.scene.world.collision_objects}
            if readback is not None else set()
        )
        return {
            "apply_reported_success": applied,
            "objects_expected": sorted(self.scene_ids),
            "objects_present_after_apply": sorted(present),
            "missing_after_apply": sorted(self.scene_ids - present),
            "scene_ok": applied and not (self.scene_ids - present),
        }

    def robot_state(self, configuration: dict, is_diff: bool):
        from moveit_msgs.msg import RobotState
        from sensor_msgs.msg import JointState

        state = RobotState()
        joint_state = JointState()
        joint_state.name = list(configuration)
        # Floats, explicitly. rosidl's Python conversion asserts on the C side rather than
        # raising, so an integer here kills the process with no traceback and no field name.
        joint_state.position = [float(value) for value in configuration.values()]
        state.joint_state = joint_state
        state.is_diff = is_diff
        return state

    def forward_kinematics(self, configuration: dict, links: list[str], frame: str) -> dict:
        request = self.fk_type.Request()
        request.header.frame_id = frame
        request.fk_link_names = list(links)
        request.robot_state = self.robot_state(configuration, is_diff=False)
        response = self.call(self.fk, request)
        if response is None:
            return {"answered": False}
        return {
            "answered": True,
            "error_code": int(response.error_code.val),
            "poses": {
                name: {
                    "translation": [
                        pose.pose.position.x, pose.pose.position.y, pose.pose.position.z
                    ],
                    "quaternion_xyzw": [
                        pose.pose.orientation.x, pose.pose.orientation.y,
                        pose.pose.orientation.z, pose.pose.orientation.w,
                    ],
                    "frame_id": pose.header.frame_id,
                }
                for name, pose in zip(response.fk_link_names, response.pose_stamped)
            },
        }

    def state_validity(self, configuration: dict) -> dict:
        request = self.validity_type.Request()
        request.robot_state = self.robot_state(configuration, is_diff=True)
        request.group_name = self.plan["group"]
        response = self.call(self.validity, request)
        if response is None:
            return {"answered": False}
        contacts = []
        touched: set[str] = set()
        for contact in response.contacts:
            bodies = {contact.contact_body_1, contact.contact_body_2}
            contacts.append(
                {"body_1": contact.contact_body_1, "body_2": contact.contact_body_2,
                 "depth": float(contact.depth)}
            )
            touched |= bodies & self.scene_ids
        return {
            "answered": True,
            "valid": bool(response.valid),
            "contacts": contacts,
            # `test_planning_pipeline.py:418`: intersected with the GENERATED object ids, so a
            # robot-self-collision contact contributes nothing. VALID1's clauses are stated
            # over robot-versus-scene pairs only.
            "touched_scene_objects": sorted(touched),
            "contact_pairs": sorted(
                {
                    f"{a}|{b}"
                    for contact in response.contacts
                    for a, b in ((contact.contact_body_1, contact.contact_body_2),
                                 (contact.contact_body_2, contact.contact_body_1))
                    if b in self.scene_ids
                }
            ),
        }


def _quaternion(roll: float, pitch: float, yaw: float):
    import math

    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def run_arm(arm: str, samples: list[dict], startup_ceiling_s: float) -> dict:
    """FK1 and VALID1 over one arm's share of the registered sample."""
    import numpy as np
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import geometry as geo

    # A SUBPROCESS, not a LaunchService on a thread. `LaunchService.run` installs asyncio
    # signal handlers, which only the main thread may do, and the main thread here holds the
    # rclpy executor; the shakedown's first attempt reported every service unadvertised and
    # `rows: 0` for exactly that reason. See `fk_rig.launch.py`.
    log = Path(f"/tmp/cite_wc_fk_{arm}.log")  # noqa: S108 - a launch log, not a data file
    with log.open("w") as handle:
        launch = subprocess.Popen(
            ["ros2", "launch", str(Path(__file__).resolve().parent / "fk_rig.launch.py")],
            stdout=handle,
            stderr=subprocess.STDOUT,
            env={**os.environ, "CITE_WC_FK_ARM": arm},
        )

    rclpy.init()
    rig = Rig(arm)
    executor = MultiThreadedExecutor()
    executor.add_node(rig.node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    report: dict = {"arm": arm, "samples": len(samples), "launch_log": str(log)}
    try:
        # An EVENT, not a sleep: `wait_for_service` returns the instant the service is
        # advertised (P4, V13).
        ready = {
            name: client.wait_for_service(timeout_sec=startup_ceiling_s)
            for name, client in (
                ("compute_fk", rig.fk),
                ("check_state_validity", rig.validity),
                ("apply_planning_scene", rig.apply_scene),
                ("get_planning_scene", rig.get_scene),
            )
        }
        report["services_advertised"] = ready
        if not all(ready.values()):
            report["fk1"] = None
            report["valid1"] = None
            report["why"] = f"move_group never advertised {sorted(k for k, v in ready.items() if not v)}"
            return report

        rig.publish_frames()
        report["scene_frame_resolved"] = rig.wait_for_scene_frame()
        report["scene"] = rig.apply()

        rows = []
        for sample in samples:
            configuration = sample["configuration"]
            # The state feed must carry the configuration being asked about, or the monitor
            # answers about a different pose than the request names.
            rig.state_names = list(configuration)
            rig.state_positions = [configuration[name] for name in rig.state_names]
            links = sorted(sample["i11_link_poses"])
            root = _root_of(sample)
            fk = rig.forward_kinematics(configuration, links, root)
            validity = rig.state_validity(configuration)
            row = {
                "capture": sample["capture"], "arm": arm,
                "trajectory": sample["trajectory"], "waypoint": sample["waypoint"],
                "fk_frame_requested": root,
                "fk": {"answered": fk.get("answered"), "error_code": fk.get("error_code")},
                "validity": {
                    "answered": validity.get("answered"),
                    "valid": validity.get("valid"),
                    "touched_scene_objects": validity.get("touched_scene_objects"),
                    "contact_pairs": validity.get("contact_pairs"),
                },
                "compute_stage_nonpositive_pairs": sample["nonpositive_pairs"],
                "compute_stage_all_pairs_positive": sample["all_pairs_positive"],
            }
            if fk.get("answered") and fk.get("error_code") == 1:
                worst_position = 0.0
                worst_angle = 0.0
                worst_link = None
                for link in links:
                    mine = sample["i11_link_poses"][link]
                    theirs = fk["poses"].get(link)
                    if theirs is None:
                        continue
                    position = float(
                        np.abs(np.array(mine["translation"]) - np.array(theirs["translation"])).max()
                    )
                    angle = geo.rotation_angle(
                        np.array(mine["rotation"]),
                        geo.quaternion_to_rotation(*theirs["quaternion_xyzw"]),
                    )
                    if position > worst_position:
                        worst_position, worst_link = position, link
                    worst_angle = max(worst_angle, angle)
                row["fk"]["worst_position_residual_m"] = worst_position
                row["fk"]["worst_angle_residual_rad"] = worst_angle
                row["fk"]["worst_link"] = worst_link
                row["fk"]["agrees"] = (
                    worst_position <= common.FK_TOLERANCE_M
                    and worst_angle <= common.FK_TOLERANCE_RAD
                )
            else:
                row["fk"]["agrees"] = None
            rows.append(row)
        report["rows"] = rows
        return report
    finally:
        try:
            executor.shutdown(timeout_sec=5.0)
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            rig.node.destroy_node()
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            rclpy.shutdown()
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            launch.terminate()
            launch.wait(timeout=30)
        except BaseException:  # noqa: BLE001
            try:
                launch.kill()
            except BaseException:  # noqa: BLE001, S110
                pass


def _root_of(sample: dict) -> str:
    """The model root frame I11 computes in, taken from the arm rather than written down."""
    return f"{sample['arm']}_mount"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=str(common.RAW))
    parser.add_argument("--block", action="append", default=None)
    parser.add_argument("--arm", default=None,
                        help="internal: run ONE arm in this process. Without it this script "
                             "re-executes itself once per arm, because two move_group nodes "
                             "for two arms in one process is a rig this campaign has no "
                             "evidence about")
    parser.add_argument("--startup-ceiling", type=float, default=180.0)
    parser.add_argument(
        "--computed-name", default="_computed.json",
        help="the compute-stage file to take the FK sample from. The default is the campaign "
             "path. `_diagnostic.json` reads compute.py's LABELLED DIAGNOSTIC output, which "
             "is NOT DATA, and writes its report under a matching name so that it cannot be "
             "mistaken for a campaign result",
    )
    arguments = parser.parse_args()
    tag = "" if arguments.computed_name == "_computed.json" else "_diagnostic"

    raw = Path(arguments.raw)
    suffix = arguments.computed_name
    labels = arguments.block or sorted(
        path.name[: -len(suffix)] for path in raw.glob(f"*{suffix}")
    )
    if not labels:
        print(f"ABORT: no *{suffix} at the top level of {raw}. Run compute.py first.",
              file=sys.stderr)
        return 2

    for label in labels:
        computed = json.loads((raw / f"{label}{suffix}").read_text())
        samples = computed.get("fk_sample") or []
        arms = sorted({sample["arm"] for sample in samples})
        if arguments.arm:
            mine = [sample for sample in samples if sample["arm"] == arguments.arm]
            report = run_arm(arguments.arm, mine, arguments.startup_ceiling)
            (raw / f"{label}_fkcheck{tag}_{arguments.arm}.json").write_text(
                json.dumps(report, indent=2, sort_keys=True, default=str)
            )
            print(f"== {label} {arguments.arm}: {len(mine)} sample(s) checked ==", flush=True)
            continue

        merged = {"label": label, "is_shakedown": computed.get("is_shakedown"),
                  "fk_sample_size_registered": common.FK1_SAMPLE,
                  "fk_sample_seed": common.FK1_SEED,
                  "fk_sample_drawn": len(samples), "arms": {}}
        for arm in arms:
            print(f"== {label}: FK1/VALID1 on {arm} ==", flush=True)
            code = subprocess.call(
                [sys.executable, "-u", str(Path(__file__).resolve()),
                 "--raw", str(raw), "--block", label, "--arm", arm,
                 "--computed-name", arguments.computed_name,
                 "--startup-ceiling", str(arguments.startup_ceiling)]
            )
            path = raw / f"{label}_fkcheck{tag}_{arm}.json"
            merged["arms"][arm] = (
                json.loads(path.read_text()) if path.exists()
                else {"arm": arm, "why": f"the per-arm run exited {code} and wrote nothing"}
            )
        (raw / f"{label}_fkcheck{tag}.json").write_text(
            json.dumps(merged, indent=2, sort_keys=True, default=str)
        )
        print(f"== {label}: FK1/VALID1 over {len(arms)} arm(s) -> {label}_fkcheck.json ==",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
