# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The bring-up plan reader.

Pure logic, so it is tested here rather than only by bringing the cell up — most
of what can go wrong in bring-up configuration is in this half, and a unit test
finds it in milliseconds instead of after a simulator start.
"""

from __future__ import annotations

import copy
from pathlib import Path

from cite_bringup.plan import (
    ARM_KEYS,
    ControllerManager,
    ControllerRef,
    GazeboPartitionMissingError,
    GRIPPER_KEYS,
    GZ_PARTITION_ENV,
    HARDWARE_OPT_IN_ENV,
    HardwareNotPermittedError,
    load,
    PlanError,
    require_gz_partition,
    require_hardware_opt_in,
    resolve_uri,
    Side,
)
import pytest
import yaml

GENERATED_PLAN = "package://cite_generated/bringup/cell_a_plan.yaml"


def _generated() -> Path:
    return Path(resolve_uri(GENERATED_PLAN))


def _document() -> dict:
    return yaml.safe_load(_generated().read_text())


def _written(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def test_the_generated_plan_loads() -> None:
    plan = load(_generated())
    assert plan.zone == "cell_a"
    assert plan.scene.exists()
    assert plan.world.exists()
    assert len(plan.controller_managers) == 3, "one controller manager per arm"
    for manager in plan.controller_managers:
        assert manager.description.exists(), manager.asset


def test_each_arm_has_its_own_description() -> None:
    """One Gazebo model per arm, so one controller manager per arm's hardware.

    With all three arms in a single model, every controller manager claimed all
    eighteen joints and wrote to them each cycle. Nothing reports that; it would
    surface much later as motion nobody can account for.
    """
    plan = load(_generated())
    descriptions = {m.description for m in plan.controller_managers}
    assert len(descriptions) == len(plan.controller_managers)
    assert plan.scene not in descriptions


def test_every_manager_is_namespaced_by_asset() -> None:
    # P2 is made of these names. A manager outside /cite/<zone>/<asset_id> would
    # put its controllers' actions somewhere the rest of the system does not look.
    plan = load(_generated())
    for manager in plan.controller_managers:
        assert manager.node == f"/cite/{plan.zone}/{manager.asset}/controller_manager"


def test_stages_are_ordered_with_the_broadcaster_first() -> None:
    plan = load(_generated())
    for manager in plan.controller_managers:
        stages = manager.stages()
        assert [s for s, _ in stages] == sorted(s for s, _ in stages)
        first_stage_names = stages[0][1]
        assert any("joint_state_broadcaster" in n for n in first_stage_names), (
            "the broadcaster must be in the first stage: the controllers after it "
            "read the state it publishes"
        )


def test_stage_grouping_is_deterministic() -> None:
    manager = ControllerManager(
        asset="arm_1",
        node="/cite/cell_a/arm_1/controller_manager",
        backend="sim",
        # No counterpart: this manager stands for an untwinned zone, which is
        # what `None` means here — never "the key was left out".
        counterpart_backend=None,
        hosted_by="simulator",
        description_topic="/robot_description",
        description=Path("/dev/null"),
        spawn_xyz_m=(0.0, 0.0, 0.0),
        spawn_rpy_rad=(0.0, 0.0, 0.0),
        parameters="package://cite_generated/control/x.yaml",
        controllers=(
            ControllerRef("b", 1),
            ControllerRef("a", 1),
            ControllerRef("jsb", 0),
        ),
        moveit=None,
        trajectory_action=None,
        gripper_action=None,
        skills=None,
        gripper={},
        arm={},
    )
    assert manager.stages() == [(0, ("jsb",)), (1, ("a", "b"))]


def test_every_arm_gets_a_planning_configuration() -> None:
    """Both planners must be told the same controller names.

    MoveIt and ros2_control disagreeing about what a controller is called fails
    at run time with an error naming neither.

    Both come from the same L0 model here, so they cannot disagree — a mismatch
    fails at run time with an error naming neither of them.
    """
    plan = load(_generated())
    for manager in plan.controller_managers:
        assert manager.moveit is not None, manager.asset
        assert manager.moveit.group.startswith(manager.asset)
        assert manager.moveit.srdf.exists()
        assert manager.moveit.controllers.exists()

        declared = yaml.safe_load(manager.moveit.controllers.read_text())
        named = set(declared["moveit_simple_controller_manager"]["controller_names"])
        spawned = {c.name for c in manager.controllers}
        assert named <= spawned, (
            f"{manager.asset}: MoveIt is configured for {sorted(named - spawned)}, "
            "which ros2_control never spawns"
        )


def test_a_manager_with_no_controllers_is_rejected(tmp_path: Path) -> None:
    # Bring-up would otherwise report success having activated nothing.
    document = {
        "plan": {
            "zone": "cell_a",
            "world": "package://cite_generated/worlds/cell_a.sdf",
            "scene": "package://cite_generated/description/cell_a_scene.urdf.xacro",
            "static_frames": "package://cite_generated/frames/cell_a_static_tf.yaml",
            "topology": "package://cite_generated/topology/cell_a_flow.yaml",
            "sides": [{"name": "plant", "gz_partition": "cite/cell_a/plant"}],
            "controller_managers": [
                {
                    "asset": "arm_1",
                    "node": "/cite/cell_a/arm_1/controller_manager",
                    "backend": "sim",
                    "hosted_by": "simulator",
                    "description_topic": "/robot_description",
                    "description": (
                        "package://cite_generated/description/cell_a_arm_1.urdf.xacro"
                    ),
                    "spawn_xyz_m": "0 0 0",
                    "spawn_rpy_rad": "0 0 0",
                    "parameters": "package://cite_generated/control/x.yaml",
                    "controllers": [],
                }
            ],
        }
    }
    with pytest.raises(PlanError, match="lists no controllers"):
        load(_written(tmp_path, document))


def test_a_missing_plan_says_how_to_produce_one(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="validate-model"):
        load(tmp_path / "absent.yaml")


def test_an_unresolvable_package_uri_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="not on the ament index"):
        resolve_uri("package://not_a_real_package/thing.yaml")


# --- A malformed plan is a PlanError, never a KeyError or a ValueError ---------
#
# `simulation.launch.py` catches PlanError and turns it into a message plus a
# Shutdown. Anything else escapes an OpaqueFunction as a raw traceback naming the
# launch machinery instead of the key that is wrong, which is what these lock in.


def test_a_missing_manager_key_is_a_plan_error(tmp_path: Path) -> None:
    document = _document()
    del document["plan"]["controller_managers"][0]["node"]
    with pytest.raises(PlanError, match="missing required key 'node'"):
        load(_written(tmp_path, document))


def test_a_missing_top_level_key_is_a_plan_error(tmp_path: Path) -> None:
    document = _document()
    del document["plan"]["zone"]
    with pytest.raises(PlanError, match="missing required key 'zone'"):
        load(_written(tmp_path, document))


def test_a_non_numeric_value_is_a_plan_error(tmp_path: Path) -> None:
    document = _document()
    document["plan"]["conveyors"] = [
        {
            "asset": "conveyor_1",
            "state_topic": "/cite/cell_a/conveyor_1/state",
            "command_topic": "/cite/cell_a/conveyor_1/command",
            "installed_speed_mps": "quite fast",
        }
    ]
    with pytest.raises(PlanError, match="must be a number"):
        load(_written(tmp_path, document))


def test_a_list_where_a_triple_was_expected_is_a_plan_error(tmp_path: Path) -> None:
    # YAML happily reads `spawn_xyz_m: [1, 2, 3]` as a list. float("[1,") does not.
    document = _document()
    document["plan"]["controller_managers"][0]["spawn_xyz_m"] = [1.0, 2.0, 3.0]
    with pytest.raises(PlanError, match="three space-separated numbers"):
        load(_written(tmp_path, document))


def test_a_mapping_where_a_list_was_expected_is_a_plan_error(tmp_path: Path) -> None:
    document = _document()
    document["plan"]["controller_managers"][0]["controllers"] = {"name": "a", "stage": 0}
    with pytest.raises(PlanError, match="must be a list"):
        load(_written(tmp_path, document))


# --- The hardware gate --------------------------------------------------------


def _with_backend(document: dict, backend: str) -> dict:
    document = copy.deepcopy(document)
    document["plan"]["controller_managers"][1]["backend"] = backend
    return document


def test_the_generated_plan_needs_no_opt_in() -> None:
    """Every arm is simulated today, so nothing is gated. The gate must not fire."""
    require_hardware_opt_in(load(_generated()), {})


def test_a_hardware_backend_is_refused_without_the_opt_in(tmp_path: Path) -> None:
    plan = load(_written(tmp_path, _with_backend(_document(), "real")))
    with pytest.raises(HardwareNotPermittedError) as raised:
        require_hardware_opt_in(plan, {})
    message = str(raised.value)
    # The refusal must name the asset. "Hardware is not permitted" sends the
    # reader looking through three arms for the one that is not simulated.
    assert "arm_2" in message
    assert "real" in message
    assert HARDWARE_OPT_IN_ENV in message


def test_a_hardware_backend_starts_with_the_opt_in(tmp_path: Path) -> None:
    """The gate is a refusal, not a ban. With the opt-in the plan loads normally."""
    plan = load(_written(tmp_path, _with_backend(_document(), "real")))
    require_hardware_opt_in(plan, {HARDWARE_OPT_IN_ENV: "1"})


def test_the_opt_in_must_say_exactly_one(tmp_path: Path) -> None:
    """`CITE_ALLOW_HARDWARE=0`, `=false`, or empty is not an opt-in.

    The shell gate compares against "1" and this must not be more permissive, or
    the two disagree about what an opt-in is and a person meets two rules.
    """
    plan = load(_written(tmp_path, _with_backend(_document(), "real")))
    for value in ("0", "", "true", "yes", "1 "):
        with pytest.raises(HardwareNotPermittedError):
            require_hardware_opt_in(plan, {HARDWARE_OPT_IN_ENV: value})


def test_an_unknown_backend_is_refused_rather_than_allowed(tmp_path: Path) -> None:
    """An allowlist, not a denylist.

    A backend nobody anticipated — a new vendor plugin, a typo — must not be
    treated as simulation. cross-cutting-safety.md is explicit that a hardware
    path is never reachable by omission, and a denylist is reachable by omission
    by construction.
    """
    plan = load(_written(tmp_path, _with_backend(_document(), "mock_components")))
    with pytest.raises(HardwareNotPermittedError):
        require_hardware_opt_in(plan, {})


# --- The simulation-fidelity aids: two topics per beam, not two names for one --


def test_every_beam_carries_a_level_topic_and_an_event_topic() -> None:
    """A beam has two interfaces and they must not collide.

    `detection_topic` is already spoken for: `cell_a_flow.yaml` gives it to a
    station as a `DetectionEvent` trigger and `StationTopology.msg` documents it
    as one. Bridging the raw `std_msgs/Bool` level onto that name would put two
    publishers of two types on the topic the line acts on.
    """
    plan = load(_generated())
    assert plan.sensors, "the generated plan declares no sensors at all"
    for sensor in plan.sensors:
        assert sensor.detection_topic != sensor.level_topic, sensor.asset
        assert sensor.asset in sensor.detection_topic
        assert sensor.asset in sensor.level_topic
        assert sensor.frame_id.startswith(f"{plan.zone}__{sensor.asset}__"), (
            "a beam's detections are reported in a frame the generated static TF "
            "table publishes; this one names a frame from nowhere"
        )


def test_a_beam_whose_two_topics_are_one_name_is_refused(tmp_path: Path) -> None:
    """Refused when the plan says it, not discovered when the line stalls.

    The two would connect, both publish, and `ros2 topic echo` would show a
    stream of deserialisation errors naming neither publisher.
    """
    document = _document()
    sensor = document["plan"]["sensors"][0]
    sensor["level_topic"] = sensor["detection_topic"]
    with pytest.raises(PlanError, match="fight over it"):
        load(_written(tmp_path, document))


def test_sensors_without_a_detection_block_are_refused(tmp_path: Path) -> None:
    """Beams bridged into ROS and read by nobody is a silent half-system."""
    document = _document()
    del document["plan"]["detection"]
    with pytest.raises(PlanError, match="turns their levels into typed events"):
        load(_written(tmp_path, document))


def test_the_detection_server_is_zone_scoped() -> None:
    plan = load(_generated())
    assert plan.detection is not None
    assert plan.detection.namespace == f"/cite/{plan.zone}/detection"
    assert plan.detection.detect_action == f"{plan.detection.namespace}/detect"
    # Not an arm's namespace: one server watches every belt in the zone, and
    # three would give the same question three answers.
    for manager in plan.controller_managers:
        assert manager.asset not in plan.detection.namespace


# --- The skill actions L4 calls come from the model ---------------------------


def test_every_planned_arm_declares_its_skill_actions() -> None:
    """The names used to be assembled by whoever launched the coordinator.

    That is an asset name written a second time, outside `ids.py` and outside
    every test that covers it — which is exactly what CLAUDE.md §8 forbids.
    """
    plan = load(_generated())
    for manager in plan.controller_managers:
        if manager.moveit is None:
            continue
        assert manager.skills is not None, manager.asset
        prefix = f"/cite/{plan.zone}/{manager.asset}/"
        for skill in ("move_to", "pick", "place", "grasp", "transfer"):
            name = getattr(manager.skills, skill)
            assert name == f"{prefix}{skill}", (name, skill)


def test_a_partial_skills_block_is_refused(tmp_path: Path) -> None:
    """Half a skill table is worse than none: the missing one fails at goal time."""
    document = _document()
    del document["plan"]["controller_managers"][0]["skills"]["pick"]
    with pytest.raises(PlanError, match="missing required key 'pick'"):
        load(_written(tmp_path, document))


# --- The gripper values reach L3 because the plan carries them ----------------


def test_every_gripper_key_the_plan_states_is_read() -> None:
    """The P1 defect that worked because two copies agreed.

    `cite_bringup` delivered four keys, one of which — `gripper_max_width_m` —
    exists in neither the plan nor the skill server's declared parameters and was
    therefore accepted and dropped. Meanwhile the default grasp width, the goal
    tolerance, the drive rate and all seven linkage dimensions never arrived, and
    the node ran on compiled defaults that happen to equal the L0 values.
    """
    plan = load(_generated())
    document = _document()
    for manager, entry in zip(
        plan.controller_managers, document["plan"]["controller_managers"]
    ):
        if manager.gripper_action is None:
            continue
        stated = {key for key in GRIPPER_KEYS if entry.get(key) is not None}
        assert stated == set(manager.gripper), (
            f"{manager.asset}: the plan states {sorted(stated)} and the reader "
            f"produced {sorted(manager.gripper)}"
        )
        assert stated, f"{manager.asset} has a gripper action and no gripper values"
        for key in stated:
            assert manager.gripper[key] == pytest.approx(float(entry[key])), key


#: The skill server's own source. `GRIPPER_KEYS` claims its entries are spelled
#: "under the exact name the skill server declares it", and that claim is about
#: another package — the kind of statement that is true when written and rots in
#: silence. Reading the declarations is what turns it into a test.
SKILL_SERVER = (
    Path(__file__).resolve().parents[2] / "cite_skills" / "src" / "skill_server.cpp"
)


def test_every_gripper_key_is_one_the_skill_server_declares() -> None:
    """A key the server does not declare is delivered, dropped and reported by nobody.

    `rclcpp` ignores an override for a parameter that was never declared: launch
    accepts it, the node discards it, and neither says so. That is how
    `gripper_default_grasp_width_m` and seven linkage dimensions never arrived
    while the node ran on compiled defaults which happened to equal the L0 values
    — a P1 defect that worked because two copies agreed.

    `gripper_max_drive_rate_rad_s` was the twelfth key and was in exactly that
    state at the commit before this test: carried by the plan, delivered by
    `_skill_parameters`, and declared by nothing.
    """
    assert SKILL_SERVER.is_file(), f"the skill server's source is not at {SKILL_SERVER}"
    source = SKILL_SERVER.read_text()
    undeclared = [
        key for key in GRIPPER_KEYS if f'declare_parameter("{key}"' not in source
    ]
    assert not undeclared, (
        f"{sorted(undeclared)} are delivered to the skill server and declared by it "
        f"nowhere in {SKILL_SERVER.name}, so rclcpp drops them without a word"
    )


def test_a_gripper_key_the_plan_omits_is_absent_rather_than_zero(tmp_path: Path) -> None:
    """Omission must not become a value.

    A zero manufactured here would be passed as a parameter and would override
    the skill server's own declared default with a number the model never stated
    — silently, and in the direction of a gripper that thinks it is fully open.
    """
    document = _document()
    del document["plan"]["controller_managers"][0]["gripper_default_grasp_width_m"]
    plan = load(_written(tmp_path, document))
    assert "gripper_default_grasp_width_m" not in plan.controller_managers[0].gripper
    assert "gripper_open_position" in plan.controller_managers[0].gripper


# --- The arm values reach L3 by the same route, and need the same guards -----
#
# `ARM_KEYS` is `GRIPPER_KEYS`' younger sibling (ADR-0037) and arrived with none
# of its guards. The three below are the gripper's three, applied to it. They
# exist because of a defect that had already happened once: eight values were
# delivered to a node that declared none of them, `rclcpp` dropped every one
# without a word, and nothing noticed because the compiled defaults happened to
# equal the L0 values — a P1 defect that worked because two copies agreed.
#
# `arm_goal_tolerance_rad` is in exactly that position. The skill server declares
# it with a compiled default of 0.01 and L0 currently declares 0.01, so the day
# the model changes and the delivery breaks, nothing downstream would tell the
# difference. These are what tell the difference.


def test_every_arm_key_the_plan_states_is_read() -> None:
    """A key the plan states must reach the reader, with the plan's own value."""
    plan = load(_generated())
    document = _document()
    for manager, entry in zip(
        plan.controller_managers, document["plan"]["controller_managers"]
    ):
        if manager.trajectory_action is None:
            continue
        stated = {key for key in ARM_KEYS if entry.get(key) is not None}
        assert stated == set(manager.arm), (
            f"{manager.asset}: the plan states {sorted(stated)} and the reader "
            f"produced {sorted(manager.arm)}"
        )
        assert stated, f"{manager.asset} has a trajectory action and no arm values"
        for key in stated:
            assert manager.arm[key] == pytest.approx(float(entry[key])), key


def test_every_arm_key_is_one_the_skill_server_declares() -> None:
    """An undeclared key is delivered, dropped by rclcpp, and reported by nobody.

    The same silence that hid `gripper_default_grasp_width_m` and seven linkage
    dimensions. `arm_goal_tolerance_rad` is the threshold ADR-0037 classifies an
    aborted motion against, so a delivery that is dropped leaves the classifier
    judging against a compiled constant while the model says something else.
    """
    assert SKILL_SERVER.is_file(), f"the skill server's source is not at {SKILL_SERVER}"
    source = SKILL_SERVER.read_text()
    undeclared = [key for key in ARM_KEYS if f'declare_parameter("{key}"' not in source]
    assert not undeclared, (
        f"{sorted(undeclared)} are delivered to the skill server and declared by it "
        f"nowhere in {SKILL_SERVER.name}, so rclcpp drops them without a word"
    )


def test_an_arm_key_the_plan_omits_is_absent_rather_than_zero(tmp_path: Path) -> None:
    """Omission must not become a value.

    A zero manufactured here would be passed as a parameter and would override
    the skill server's declared default with a number the model never stated —
    and `arm_goal_tolerance_rad` at zero makes every aborted motion classify as
    MOTION_INTERRUPTED, which is the answer that blocks a station for an operator.
    The server refuses a non-positive value on configure for that reason; this
    keeps the plan from ever handing it one.
    """
    document = _document()
    del document["plan"]["controller_managers"][0]["arm_goal_tolerance_rad"]
    plan = load(_written(tmp_path, document))
    assert "arm_goal_tolerance_rad" not in plan.controller_managers[0].arm
    assert plan.controller_managers[1].arm["arm_goal_tolerance_rad"] > 0.0


# --- The Gazebo transport partition -------------------------------------------
#
# `ROS_DOMAIN_ID` does not isolate Gazebo transport. Two `gz sim` servers in one
# container on separate ROS domains were measured with two publishers on one
# world's stats topic and two subscribers on one belt's command topic, so one
# conveyor setpoint would have started both cells' belts — with nothing logged,
# and with every ROS-side instrument this project has reporting clean isolation
# at the same moment (ADR-0042). What kept the measured pairs apart was the
# container hostname, which gz-transport derives its default partition from.
#
# These are the tests that make the replacement structural rather than
# conventional. The defect is invisible at runtime and cannot occur at all on a
# hardware side, so no amount of running the cell will surface it.


def test_the_generated_plan_names_a_partitioned_side() -> None:
    plan = load(_generated())
    assert plan.sides
    assert all(side.gz_partition for side in plan.sides)


def test_the_partition_carried_by_the_environment_is_accepted() -> None:
    side = load(_generated()).sides[0]
    require_gz_partition(side, {GZ_PARTITION_ENV: side.gz_partition})


def test_a_side_started_without_a_partition_is_refused() -> None:
    side = load(_generated()).sides[0]
    with pytest.raises(GazeboPartitionMissingError) as raised:
        require_gz_partition(side, {})
    message = str(raised.value)
    assert GZ_PARTITION_ENV in message
    # The refusal must name the value that was expected. "Partition missing"
    # leaves the reader with nothing to set it to.
    assert side.gz_partition in message


def test_a_side_started_with_the_wrong_partition_is_refused() -> None:
    # Not the same failure as an absent one, and worth its own answer: an
    # exported GZ_PARTITION that disagrees with the plan puts the server
    # somewhere the plan does not describe, which is how a developer debugging
    # two sides in one shell would produce two cells on one transport.
    side = load(_generated()).sides[0]
    with pytest.raises(GazeboPartitionMissingError) as raised:
        require_gz_partition(side, {GZ_PARTITION_ENV: "somewhere_else"})
    assert "somewhere_else" in str(raised.value)


def test_a_plan_with_no_sides_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    # A plan generated before this existed, or hand-edited to remove the block.
    # Defaulting a partition here would put the derivation in a second place,
    # which is the failure the emission exists to prevent.
    document = _document()
    del document["plan"]["sides"]
    with pytest.raises(GazeboPartitionMissingError, match="no `sides:`"):
        load(_written(tmp_path, document))


def test_a_side_with_an_empty_partition_is_refused(tmp_path: Path) -> None:
    document = _document()
    document["plan"]["sides"][0]["gz_partition"] = "  "
    with pytest.raises(GazeboPartitionMissingError, match="empty gz_partition"):
        load(_written(tmp_path, document))


def test_two_sides_sharing_one_partition_are_refused(tmp_path: Path) -> None:
    # The measured defect itself, written down. Two servers on one partition see
    # each other's topics, and one belt command drives both cells.
    document = _document()
    shared = document["plan"]["sides"][0]["gz_partition"]
    document["plan"]["sides"].append({"name": "counterpart", "gz_partition": shared})
    with pytest.raises(GazeboPartitionMissingError, match="share the Gazebo partition"):
        load(_written(tmp_path, document))


def test_a_paired_plan_keeps_its_two_partitions_apart(tmp_path: Path) -> None:
    document = _document()
    document["plan"]["sides"].append(
        {"name": "counterpart", "gz_partition": "cite/cell_a/counterpart"}
    )
    plan = load(_written(tmp_path, document))
    assert [side.name for side in plan.sides] == ["plant", "counterpart"]
    assert len({side.gz_partition for side in plan.sides}) == 2


def test_the_partition_refusal_is_a_plan_error() -> None:
    # simulation.launch.py catches PlanError and turns it into a message plus a
    # Shutdown. A partition refusal that escaped as something else would surface
    # as a traceback naming the launch machinery.
    assert issubclass(GazeboPartitionMissingError, PlanError)


def test_a_side_is_named_as_well_as_partitioned() -> None:
    # The name is what a second side's launch will select on, and it comes from
    # the plan rather than from whoever starts it.
    side = load(_generated()).sides[0]
    assert isinstance(side, Side)
    assert side.name


# --- A hardware backend on the counterpart side -------------------------------


def _with_counterpart_backend(document: dict, backend: str) -> dict:
    document = copy.deepcopy(document)
    for manager in document["plan"]["controller_managers"]:
        manager["counterpart_backend"] = "sim"
    document["plan"]["controller_managers"][1]["counterpart_backend"] = backend
    document["plan"]["sides"].append(
        {"name": "counterpart", "gz_partition": "cite/cell_a/counterpart"}
    )
    return document


def test_a_simulated_counterpart_needs_no_opt_in(tmp_path: Path) -> None:
    # Phase 2.A: both sides simulated, so nothing is gated and the gate must not
    # fire on the mere presence of a counterpart.
    plan = load(_written(tmp_path, _with_counterpart_backend(_document(), "sim")))
    require_hardware_opt_in(plan, {})


def test_a_physical_counterpart_is_refused_without_the_opt_in(tmp_path: Path) -> None:
    # This is Phase 2.B arriving. A backend is selected per (asset, side), so a
    # gate that read only `backend` would let the far side become physical
    # without ever looking at it (ADR-0041, Decision 2).
    plan = load(_written(tmp_path, _with_counterpart_backend(_document(), "real")))
    with pytest.raises(HardwareNotPermittedError) as raised:
        require_hardware_opt_in(plan, {})
    message = str(raised.value)
    assert "arm_2" in message
    assert "counterpart_backend" in message
    assert HARDWARE_OPT_IN_ENV in message


def test_a_physical_counterpart_starts_with_the_opt_in(tmp_path: Path) -> None:
    plan = load(_written(tmp_path, _with_counterpart_backend(_document(), "real")))
    require_hardware_opt_in(plan, {HARDWARE_OPT_IN_ENV: "1"})


def test_an_unknown_counterpart_backend_is_refused_rather_than_allowed(
    tmp_path: Path,
) -> None:
    # The same allowlist as the plant side. A backend nobody anticipated must not
    # be treated as simulation on either side.
    plan = load(
        _written(tmp_path, _with_counterpart_backend(_document(), "mock_components"))
    )
    with pytest.raises(HardwareNotPermittedError):
        require_hardware_opt_in(plan, {})


def test_an_untwinned_plan_states_no_counterpart_backend() -> None:
    # `None` here means "there is no such side", never "the model left the key
    # out": the generator writes the key for every asset of a paired zone and for
    # none of an untwinned one.
    plan = load(_generated())
    assert all(m.counterpart_backend is None for m in plan.controller_managers)
