"""The bring-up plan reader.

Pure logic, so it is tested here rather than only by bringing the cell up — most
of what can go wrong in bring-up configuration is in this half, and a unit test
finds it in milliseconds instead of after a simulator start.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cite_bringup.plan import ControllerManager, ControllerRef, PlanError, load, resolve_uri


def test_the_generated_plan_loads() -> None:
    plan = load(Path(resolve_uri("package://cite_generated/bringup/cell_a_plan.yaml")))
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
    plan = load(Path(resolve_uri("package://cite_generated/bringup/cell_a_plan.yaml")))
    descriptions = {m.description for m in plan.controller_managers}
    assert len(descriptions) == len(plan.controller_managers)
    assert plan.scene not in descriptions


def test_every_manager_is_namespaced_by_asset() -> None:
    # P2 is made of these names. A manager outside /cite/<zone>/<asset_id> would
    # put its controllers' actions somewhere the rest of the system does not look.
    plan = load(Path(resolve_uri("package://cite_generated/bringup/cell_a_plan.yaml")))
    for manager in plan.controller_managers:
        assert manager.node == f"/cite/{plan.zone}/{manager.asset}/controller_manager"


def test_stages_are_ordered_with_the_broadcaster_first() -> None:
    plan = load(Path(resolve_uri("package://cite_generated/bringup/cell_a_plan.yaml")))
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
    )
    assert manager.stages() == [(0, ("jsb",)), (1, ("a", "b"))]


def test_every_arm_gets_a_planning_configuration() -> None:
    """MoveIt and ros2_control must be told the same controller names.

    Both come from the same L0 model here, so they cannot disagree — a mismatch
    fails at run time with an error naming neither of them.
    """
    plan = load(Path(resolve_uri("package://cite_generated/bringup/cell_a_plan.yaml")))
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
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(PlanError, match="lists no controllers"):
        load(path)


def test_a_missing_plan_says_how_to_produce_one(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="validate-model"):
        load(tmp_path / "absent.yaml")


def test_an_unresolvable_package_uri_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="not on the ament index"):
        resolve_uri("package://not_a_real_package/thing.yaml")
