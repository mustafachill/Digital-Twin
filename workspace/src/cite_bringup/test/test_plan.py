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
    ControllerManager,
    ControllerRef,
    GRIPPER_KEYS,
    HARDWARE_OPT_IN_ENV,
    HardwareNotPermittedError,
    load,
    PlanError,
    require_hardware_opt_in,
    resolve_uri,
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
