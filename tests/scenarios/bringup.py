"""Scenario: the cell comes up, is correctly named, and actually delivers data.

This is the scenario every other one depends on. `cross-cutting-testing.md` lists
standing guarantees the tester verifies on every run regardless of what changed;
the ones that do not need a skill server are asserted here:

  * deterministic bring-up — reaches fully active with no timing assumption (P4)
  * sim/hardware interface parity — every name matches /cite/<zone>/<asset_id>,
    which is what P2 is made of
  * message delivery — a subscriber actually RECEIVES, rather than merely
    existing. A QoS mismatch connects silently and delivers nothing, and a test
    that only creates a publisher and a subscriber passes happily against one.
  * clean shutdown, no orphans — the next run's failure is this run's fault

Assertions are on outcomes and constraints, never on exact trajectories.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import launch_testing
import launch_testing.markers
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from cite_interfaces.action import MoveTo
from cite_interfaces.msg import ModelVersion, ResultCode
from cite_interfaces.qos import LATCHED, STATE
from control_msgs.action import FollowJointTrajectory, GripperCommand
from controller_manager_msgs.srv import ListControllers
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

ZONE = "cell_a"
ARMS = ("arm_1", "arm_2", "arm_3")

#: The five axes of an xArm 5.
ARM_JOINT_SUFFIXES = tuple(f"joint{n}" for n in range(1, 6))

#: The gripper's one actuated joint.
DRIVE_JOINT_SUFFIX = "drive_joint"

#: The five joints of the parallel linkage that follow `drive_joint` through URDF
#: <mimic> tags. They are on `/joint_states` because
#: `external/patches/01-xarm_ros2-gripper-mimic-joints.patch` declares them in the
#: gripper's <ros2_control> block; the vendor lists only `drive_joint` there, and
#: a <mimic> tag that never reaches ros2_control couples nothing.
FOLLOWER_JOINT_SUFFIXES = (
    "left_finger_joint",
    "left_inner_knuckle_joint",
    "right_finger_joint",
    "right_inner_knuckle_joint",
    "right_outer_knuckle_joint",
)

#: Every joint one arm publishes. Written once, because more than one test below
#: asserts against it and they must not be able to disagree.
JOINT_SUFFIXES = (*ARM_JOINT_SUFFIXES, DRIVE_JOINT_SUFFIX, *FOLLOWER_JOINT_SUFFIXES)


def joints_of(arm: str) -> set[str]:
    return {f"{arm}_{suffix}" for suffix in JOINT_SUFFIXES}


#: How far a follower may sit from `drive_joint` and still count as tracking it.
#: Generous next to the failure it exists to catch — an uncoupled follower rests
#: near zero while the drive joint is most of a radian away — because its job is
#: only to absorb the residual of gz_ros2_control's proportional mimic servo, not
#: to measure it.
TRACKING_TOLERANCE_RAD = 0.05


#: Wall-clock ceilings, not schedules. Nothing is sequenced by them; they exist so
#: a hang fails the run with a diagnosis instead of blocking CI indefinitely.
#:
#: Their basis, because a bare number tells the next reader nothing: they were
#: chosen against a Linux workstation running near real time. Measured real-time
#: factor on the macOS development host is about 0.14 — `joint_states` arrives at
#: roughly 21 Hz against a configured 150 Hz — so a timeout here is evidence of a
#: slow machine at least as often as it is evidence of a hang. Raise them for a
#: slower host rather than reading a timeout as a defect.
BRING_UP_CEILING_S = 240.0
DELIVERY_CEILING_S = 30.0
TRAJECTORY_CEILING_S = 60.0
#: Planning is stochastic, so a skill takes longer and varies more than a raw
#: trajectory. Still a ceiling, not a schedule.
SKILL_CEILING_S = 120.0


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> LaunchDescription:
    simulation = (
        Path(get_package_share_directory("cite_bringup")) / "launch" / "simulation.launch.py"
    )
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(str(simulation)),
                launch_arguments={"headless": "true", "zone": ZONE}.items(),
            ),
            launch_testing.actions.ReadyToTest(),
        ]
    )


class TestCellBringUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rclpy.init()
        cls.node = Node("scenario_bringup")
        # No seed is read here. There was a `cls.seed` that nothing used, beside
        # a comment claiming scenarios are deterministic — a claim this
        # repository cannot currently support. `./scripts/scenario` exports
        # CITE_PHYSICS_SEED and nothing consumes it: `gz sim` takes a seed as a
        # command-line flag rather than an SDF element and `simulation.launch.py`
        # passes none, and MoveIt exposes no way to seed OMPL's RNG at all. The
        # script itself now says so on every run. Assertions below are on
        # outcomes and constraints precisely because a plan cannot be reproduced.

    @classmethod
    def tearDownClass(cls) -> None:
        cls.node.destroy_node()
        rclpy.shutdown()

    def _spin_until(self, predicate, ceiling_s: float, what: str):
        """Spin until `predicate` returns something other than None, or fail.

        `is not None`, not truthiness. A measurement of exactly 0.0 or an empty
        but valid answer is a perfectly good result, and treating it as "not
        ready yet" produces a timeout whose message points at the wrong thing.
        Predicates that answer with a bool convert it at the call site, where the
        meaning of False is obvious.
        """
        end = self.node.get_clock().now().nanoseconds + int(ceiling_s * 1e9)
        result = predicate()
        while result is None and self.node.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self.node, timeout_sec=0.5)
            result = predicate()
        self.assertIsNotNone(result, f"timed out after {ceiling_s:.0f}s waiting for {what}")
        return result

    def test_every_controller_reaches_active(self) -> None:
        """Bring-up completes, on this machine, without any step being timed."""
        for arm in ARMS:
            manager = f"/cite/{ZONE}/{arm}/controller_manager"
            client = self.node.create_client(ListControllers, f"{manager}/list_controllers")
            self._spin_until(
                lambda c=client: c.wait_for_service(timeout_sec=0.5) or None,
                BRING_UP_CEILING_S,
                f"{manager} to appear",
            )

            def active(c=client, a=arm):
                future = c.call_async(ListControllers.Request())
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=10.0)
                if future.result() is None:
                    return None
                names = {ctrl.name for ctrl in future.result().controller if ctrl.state == "active"}
                expected = {
                    f"{a}_joint_state_broadcaster",
                    f"{a}_joint_trajectory_controller",
                    f"{a}_gripper_controller",
                }
                return names if expected <= names else None

            self._spin_until(active, BRING_UP_CEILING_S, f"{arm}'s controllers to be active")

    def test_joint_states_are_actually_delivered(self) -> None:
        """Not that a subscriber exists — that a message ARRIVES.

        A QoS mismatch connects silently and delivers nothing: the topic is listed,
        both endpoints show in `ros2 topic info`, and no error is raised anywhere.
        Only asserting on receipt catches it.
        """
        for arm in ARMS:
            received: list[JointState] = []
            topic = f"/cite/{ZONE}/{arm}/joint_states"
            subscription = self.node.create_subscription(JointState, topic, received.append, STATE)
            try:
                # `received` is bound as a default argument, not captured. Each
                # iteration rebinds the name to a fresh list, so a closure over it
                # reads whichever list the loop is on when the predicate finally
                # runs — correct today only because `_spin_until` calls it before
                # the loop moves on. That is the kind of accident that turns into a
                # test which passes while watching the wrong arm's topic. Binding
                # at definition removes the hazard rather than the warning, and
                # matches how `active(c=client, a=arm)` above already does it.
                self._spin_until(
                    lambda messages=received: messages or None,
                    DELIVERY_CEILING_S,
                    f"a message on {topic}",
                )
                names = set(received[-1].name)
                self.assertEqual(
                    names,
                    joints_of(arm),
                    f"{topic} carries {sorted(names)}; every joint must be prefixed "
                    f"with the L0 asset id, because P2 is made of these names",
                )
            finally:
                self.node.destroy_subscription(subscription)

    def test_no_joint_name_is_shared_between_arms(self) -> None:
        """Two instances of one component type must never collide.

        Read from the arms that are actually running. This test used to build the
        joint names from a local tuple with f-strings and then assert that the
        strings it had just built did not collide — it queried nothing, touched no
        node, and could not fail. What it claimed to verify is real and important:
        three instances of one component type share every vendor joint name, and
        only the generated `<asset_id>_` prefix keeps them apart. If that prefix
        were ever dropped, three controller managers would claim the same
        eighteen joints and write to them every cycle.
        """
        owners: dict[str, str] = {}
        for arm in ARMS:
            received: list[JointState] = []
            topic = f"/cite/{ZONE}/{arm}/joint_states"
            subscription = self.node.create_subscription(JointState, topic, received.append, STATE)
            try:
                self._spin_until(
                    lambda r=received: r or None, DELIVERY_CEILING_S, f"a message on {topic}"
                )
                live = sorted(received[-1].name)
                self.assertTrue(live, f"{topic} delivered a message naming no joints")
                for joint in live:
                    self.assertNotIn(
                        joint,
                        owners,
                        f"{joint} is published by both {owners.get(joint)} and {arm}; "
                        "the L0 asset-id prefix is what keeps two instances of one "
                        "component type apart, and it is missing here",
                    )
                    owners[joint] = arm
            finally:
                self.node.destroy_subscription(subscription)
        # Three five-axis arms, each with a gripper whose drive joint and five
        # linkage followers are all real, actuated and published: 3 x 11 = 33
        # distinct names.
        #
        # This read 18 while the five followers were absent from the gripper's
        # <ros2_control> block. Their absence was the defect, not the baseline:
        # the joints exist in the vendor URDF, move under the linkage, and should
        # have been observable all along. Raising the count is a correction, not a
        # relaxation — and on its own it is a weak one, which is why
        # `test_the_gripper_linkage_is_actually_coupled` asserts that they TRACK
        # the drive joint. A count alone would pass again the day the patch is
        # reverted and the followers reappear as five joints that never move.
        self.assertEqual(len(owners), len(ARMS) * len(JOINT_SUFFIXES), sorted(owners))
        self.assertEqual(len(owners), 33, sorted(owners))

    def test_the_gripper_linkage_is_actually_coupled(self) -> None:
        """The five follower joints track `drive_joint`, rather than merely existing.

        This is the assertion that has teeth. Counting joint names proves only
        that they are declared; a gripper whose followers are declared and then
        stand still passes a count and grasps nothing, which is exactly the state
        this cell was in for the whole of Phase 1.C. Three mechanisms that could
        have coupled them were dead at once: the vendor's <ros2_control> block
        lists only `drive_joint`, Gazebo Harmonic's dartsim does not implement
        SetMimicConstraintFeature, and the vendor's Gazebo Classic mimic plugin
        cannot load under Harmonic. The measured symptom was a right finger that
        moved 1.5 mm across the entire stroke — gravity sag, not actuation — and
        a left finger that tilted instead of closing parallel, so the pads never
        touched a 50 mm block at all.

        Commanding the gripper is what makes this test able to fail: at rest every
        joint reads zero and any broken coupling looks perfect.
        """
        arm = ARMS[0]
        action = f"/cite/{ZONE}/{arm}/{arm}_gripper_controller/gripper_cmd"
        client = ActionClient(self.node, GripperCommand, action)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=0.5) or None,
            BRING_UP_CEILING_S,
            action,
        )

        # Mid-stroke, well clear of both limits, so a follower that is merely
        # resting at its own zero cannot be mistaken for one that is tracking.
        commanded = 0.40
        goal = GripperCommand.Goal()
        goal.command.position = commanded
        goal.command.max_effort = 60.0

        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=TRAJECTORY_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, "the gripper goal was never accepted")
        self.assertTrue(handle.accepted, "the gripper controller rejected the command")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result, timeout_sec=TRAJECTORY_CEILING_S)
        self.assertIsNotNone(result.result(), "the gripper never reported a result")

        received: list[JointState] = []
        topic = f"/cite/{ZONE}/{arm}/joint_states"
        subscription = self.node.create_subscription(JointState, topic, received.append, STATE)
        try:
            # Read a state published after the close finished, not one buffered
            # from before it: a stale message would show the pre-command pose and
            # the comparison would be against the wrong instant.
            received.clear()
            self._spin_until(
                lambda messages=received: messages or None,
                DELIVERY_CEILING_S,
                f"a joint state after the gripper closed on {topic}",
            )

            # Then wait for the followers to SETTLE before judging them. They are
            # driven by a proportional velocity servo, so for a short while after
            # the goal completes they are legitimately still catching up, and a
            # state sampled in that window says nothing about whether the linkage
            # is coupled. This is a wait on an observed condition with a ceiling,
            # not a sleep: nothing here is sequenced by elapsed time (P4), and if
            # the followers never converge the assertions below still run and fail
            # with the numbers that prove it.
            deadline = self.node.get_clock().now().nanoseconds + int(DELIVERY_CEILING_S * 1e9)
            by_name: dict[str, float] = {}
            while self.node.get_clock().now().nanoseconds < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.2)
                by_name = dict(zip(received[-1].name, received[-1].position, strict=True))
                leader = by_name.get(f"{arm}_{DRIVE_JOINT_SUFFIX}")
                if leader is None:
                    continue
                if all(
                    abs(by_name[f"{arm}_{suffix}"] - leader) <= TRACKING_TOLERANCE_RAD
                    for suffix in FOLLOWER_JOINT_SUFFIXES
                    if f"{arm}_{suffix}" in by_name
                ):
                    break
        finally:
            self.node.destroy_subscription(subscription)

        drive = by_name[f"{arm}_{DRIVE_JOINT_SUFFIX}"]
        self.assertGreater(
            drive,
            0.25,
            f"{arm}_{DRIVE_JOINT_SUFFIX} reads {drive:.4f} after being commanded to "
            f"{commanded}; the gripper did not close, so this test can say nothing "
            "about whether the linkage follows it",
        )

        for suffix in FOLLOWER_JOINT_SUFFIXES:
            follower = by_name[f"{arm}_{suffix}"]
            self.assertAlmostEqual(
                follower,
                drive,
                delta=TRACKING_TOLERANCE_RAD,
                msg=(
                    f"{arm}_{suffix} settled at {follower:.4f} while "
                    f"{arm}_{DRIVE_JOINT_SUFFIX} is at {drive:.4f}, so the pads are not "
                    "parallel and a grasp cannot be evidenced by a stall.\n"
                    "  If EVERY follower sits near zero, the coupling is absent "
                    "entirely — check that "
                    "external/patches/01-xarm_ros2-gripper-mimic-joints.patch applied.\n"
                    "  If only left_finger_joint is adrift, at its 0.85 limit, this is "
                    "the known open defect: it is the one follower whose parent link is "
                    "the child of the position-commanded drive joint, so it receives a "
                    "step where the others receive a ramp, and gz_ros2_control's "
                    "proportional mimic servo does not recover it. See the fix report "
                    "for this branch"
                ),
            )

    def test_a_trajectory_executes(self) -> None:
        """The arm moves when commanded, through the action the skills will use."""
        arm = ARMS[0]
        action = f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller/follow_joint_trajectory"
        client = ActionClient(self.node, FollowJointTrajectory, action)
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=0.5) or None,
            BRING_UP_CEILING_S,
            action,
        )

        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = [f"{arm}_joint{n}" for n in range(1, 6)]
        point = JointTrajectoryPoint()
        # Every one of these is inside its joint's declared limit, and joint3 is
        # the one that has to be checked rather than assumed: its upper limit is
        # 0.19198 rad, not something round. This asked for 0.200 — a goal the
        # robot may not legally reach.
        #
        # It was silent until `enforce_command_limits` was turned on, because
        # nothing was enforcing any declared limit anywhere in this cell. Now the
        # limiter clamps it and logs a throttled ERROR for as long as the goal is
        # held, which is the enforcement working. The defect is the goal: a
        # bring-up scenario that proves the arm moves must ask for motion the arm
        # is allowed to make, or it proves the limiter instead.
        point.positions = [0.4, -0.3, 0.15, 0.0, 0.3]
        point.time_from_start.sec = 3
        goal.trajectory.points = [point]

        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=TRAJECTORY_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, "the trajectory goal was never accepted")
        self.assertTrue(handle.accepted, "the controller rejected the trajectory goal")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result, timeout_sec=TRAJECTORY_CEILING_S)
        self.assertIsNotNone(result.result(), "the trajectory never returned a result")
        self.assertEqual(
            result.result().result.error_code,
            FollowJointTrajectory.Result.SUCCESSFUL,
            result.result().result.error_string,
        )

    def test_the_facility_publishes_its_model_version(self) -> None:
        """L6 stamps this into every recording.

        A bag recorded against yesterday's layout is not comparable to today's,
        and without this the two are indistinguishable after the fact. Published
        LATCHED, so a node that starts later still receives it.
        """
        received: list[ModelVersion] = []
        subscription = self.node.create_subscription(
            ModelVersion, "/cite/facility/model_version", received.append, LATCHED
        )
        try:
            self._spin_until(lambda: received or None, DELIVERY_CEILING_S, "the model version")
            self.assertEqual(len(received[-1].model_hash), 64)
            self.assertIn(ZONE, received[-1].zones)
        finally:
            self.node.destroy_subscription(subscription)

    def test_station_frames_resolve_against_the_world(self) -> None:
        """Without this an arm's model is a disconnected TF tree.

        A skill given a pose in cite_world could never resolve it into the arm's
        planning frame, and the failure reads as a lookup error naming the frames
        rather than the missing link between them.
        """
        import tf2_ros

        buffer = tf2_ros.Buffer()
        listener = tf2_ros.TransformListener(buffer, self.node)
        try:
            for frame in (
                f"{ZONE}__table_pick__surface",
                f"{ZONE}__conveyor_1__infeed",
                "arm_1_mount",
                "arm_1_link_base",
            ):
                self._spin_until(
                    lambda target=frame: buffer.can_transform(
                        "cite_world", target, rclpy.time.Time()
                    )
                    or None,
                    DELIVERY_CEILING_S,
                    f"a transform from cite_world to {frame}",
                )
        finally:
            del listener

    def test_a_skill_moves_the_arm_to_its_home_configuration(self) -> None:
        """The vertical slice, end to end: L3 goal -> MoveIt -> ros2_control.

        `home` comes from the L0 model, not from the vendor's SRDF — where an arm
        rests between cycles is a fact about this facility.
        """
        arm = ARMS[0]
        client = ActionClient(self.node, MoveTo, f"/cite/{ZONE}/{arm}/move_to")
        self._spin_until(
            lambda: client.wait_for_server(timeout_sec=0.5) or None,
            BRING_UP_CEILING_S,
            f"the {arm} skill server",
        )

        goal = MoveTo.Goal()
        goal.named_configuration = "home"
        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, send, timeout_sec=TRAJECTORY_CEILING_S)
        handle = send.result()
        self.assertIsNotNone(handle, "the MoveTo goal was never accepted")
        self.assertTrue(handle.accepted, "the skill server rejected a MoveTo goal")

        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result, timeout_sec=SKILL_CEILING_S)
        self.assertIsNotNone(result.result(), "MoveTo never returned a result")
        outcome = result.result().result.result
        self.assertEqual(
            outcome.code,
            ResultCode.SUCCESS,
            f"MoveTo failed with code {outcome.code}: {outcome.detail}",
        )


@launch_testing.post_shutdown_test()
class TestCleanShutdown(unittest.TestCase):
    """Shutdown is a designed path, not an afterthought.

    An orphaned `gz sim` holds ports and names, and the NEXT bring-up then fails
    pointing nowhere near the cause. That is why this is asserted rather than
    assumed.
    """

    #: move_group does not exit cleanly, and the shape of that is NOT understood.
    #: This exemption was written as though it were a characterised upstream bug
    #: ("segfaults during its own teardown ... reproduced on every run"). Two
    #: independent sets of runs since then contradict each other and that claim:
    #: one saw all three move_group processes exit -11 with no SIGTERM
    #: escalation, another saw -15 on six consecutive runs and no -11 at all.
    #: Same code. Mutually exclusive outcomes point at one defect — an unmanaged
    #: racing teardown whose visible form depends on machine speed — rather than
    #: at a deterministic upstream segfault.
    #:
    #: The consequence for THIS test is that it is currently weak: tolerating
    #: -11 for move_group means the process that most needs a shutdown assertion
    #: is the one exempt from it. The exemption is left in place unchanged
    #: because the underlying teardown defect is owned elsewhere; neither -11 nor
    #: -15 should be read as the expected outcome, and this must be narrowed once
    #: the teardown is managed rather than raced.
    UPSTREAM_TEARDOWN_SEGFAULT = "move_group"

    def test_nothing_of_ours_exited_badly(self, proc_info) -> None:
        allowed = [0, launch_testing.asserts.EXIT_SIGINT]
        for info in proc_info:
            name = str(info.process_name)
            expected = (
                [*allowed, -11] if name.startswith(self.UPSTREAM_TEARDOWN_SEGFAULT) else allowed
            )
            self.assertIn(
                info.returncode,
                expected,
                f"{name} exited with {info.returncode}",
            )
