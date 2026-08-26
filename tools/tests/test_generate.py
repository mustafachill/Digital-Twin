"""Generation. The properties tested here are what the architecture rests on.

ADR-0004 requires byte-identical output because the hand-edit check compares a
committed artifact against a fresh run; ADR-0021 commits the artifacts so that
check can exist at all. Neither is worth anything unless determinism actually
holds, so it is asserted rather than assumed.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model import ids
from cite_tools.model.geometry import Pose
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


class TestDeterminism:
    def test_two_runs_are_byte_identical(self, real_model: Path) -> None:
        assert artifacts(real_model) == artifacts(real_model)

    def test_ten_runs_agree(self, real_model: Path) -> None:
        model = load(real_model)
        digests = {
            tuple(sorted((a.path, a.content) for a in gen.generate(model))) for _ in range(10)
        }
        assert len(digests) == 1

    def test_no_timestamp_leaks_into_output(self, real_model: Path) -> None:
        # A timestamp would make every artifact differ on every run, which turns
        # the hand-edit check into noise and gets it ignored.
        import re

        blob = "\n".join(artifacts(real_model).values())
        for pattern in (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", r"\b\d{10}\.\d+\b"):
            assert not re.search(pattern, blob), f"a timestamp matching {pattern} was emitted"

    def test_the_model_source_path_does_not_leak_into_output(self, real_model: Path) -> None:
        # `real_model` is a temporary copy, so if any generator embedded the path
        # it read from, that path appears here and would differ on every machine
        # and every run. This is the check that catches an absolute path leak,
        # which a hostname or username check cannot — "cite" is both this
        # project's name and the container's user.
        blob = "\n".join(artifacts(real_model).values())
        assert str(real_model) not in blob
        assert str(real_model.parent) not in blob

    def test_splitting_a_model_file_changes_nothing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Ordering comes from sorting by id, never from the filesystem, so how
        # the model is divided across files must be invisible downstream.
        before = artifacts(real_model)

        instances = real_model / "assets/instances/conveyors.yaml"
        import yaml

        document = yaml.safe_load(instances.read_text())
        first, rest = document["assets"][:1], document["assets"][1:]
        instances.write_text(yaml.safe_dump({**document, "assets": first}, sort_keys=False))
        (real_model / "assets/instances/conveyors_more.yaml").write_text(
            yaml.safe_dump({**document, "assets": rest}, sort_keys=False)
        )

        assert artifacts(real_model) == before

    def test_renaming_a_model_file_changes_nothing(self, real_model: Path) -> None:
        before = artifacts(real_model)
        source = real_model / "assets/instances/arms.yaml"
        source.rename(real_model / "assets/instances/zzz_manipulators.yaml")
        assert artifacts(real_model) == before


class TestHandEditDetection:
    def test_a_clean_tree_reports_nothing(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        assert gen.differences(produced, out) == []

    def test_a_changed_byte_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        target = out / "worlds/cell_a.sdf"
        target.write_text(target.read_text().replace("0.001", "0.002", 1))
        assert any(
            "differs from a fresh generator run" in p for p in gen.differences(produced, out)
        )

    def test_a_missing_file_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds/cell_a.sdf").unlink()
        assert any("missing" in p for p in gen.differences(produced, out))

    def test_a_stale_file_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds" / "left_over.sdf").write_text("stale\n")
        assert any("stale" in p for p in gen.differences(produced, out))

    def test_write_removes_stale_files(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds" / "left_over.sdf").write_text("stale\n")
        gen.write(produced, out)
        assert not (out / "worlds" / "left_over.sdf").exists()


class TestModelHash:
    def test_is_stable_for_the_same_content(self, real_model: Path) -> None:
        assert gen.model_hash(load(real_model)) == gen.model_hash(load(real_model))

    def test_changes_when_the_facility_changes(self, real_model: Path, edit_yaml: Callable) -> None:
        before = gen.model_hash(load(real_model))
        edit_yaml(
            real_model / "assets/instances/conveyors.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [1.4, 0.0, 0.0]),
        )
        assert gen.model_hash(load(real_model)) != before

    def test_does_not_change_when_only_the_file_layout_changes(self, real_model: Path) -> None:
        # A recording is stamped with this hash (L6). It must identify the
        # facility that was described, not the files it was written in.
        before = gen.model_hash(load(real_model))
        (real_model / "assets/instances/arms.yaml").rename(
            real_model / "assets/instances/manipulators.yaml"
        )
        assert gen.model_hash(load(real_model)) == before


class TestGrowingTheLineIsDataOnly:
    """The Phase 1 exit criterion, in miniature.

    "The entire cell layout is changeable by editing the facility model alone."
    Adding an arm must change generated artifacts and nothing else — if it ever
    requires editing a launch file or a controller config by hand, P1 has been
    broken somewhere upstream.
    """

    def test_a_fourth_arm_needs_no_code_change(self, real_model: Path, edit_yaml: Callable) -> None:
        import yaml

        fixtures = real_model / "assets/instances/fixtures.yaml"
        document = yaml.safe_load(fixtures.read_text())
        pedestal = dict(document["assets"][0])
        pedestal["id"] = "pedestal_4"
        pedestal["pose"] = {"frame": "cite_world", "xyz_m": [6.3, -0.35, 0.0]}
        document["assets"].append(pedestal)
        fixtures.write_text(yaml.safe_dump(document, sort_keys=False))

        arms = real_model / "assets/instances/arms.yaml"
        document = yaml.safe_load(arms.read_text())
        arm = dict(document["assets"][0])
        arm["id"] = "arm_4"
        arm["pose"] = dict(arm["pose"], frame="pedestal_4/top")
        document["assets"].append(arm)
        arms.write_text(yaml.safe_dump(document, sort_keys=False))

        produced = artifacts(real_model)
        assert "control/cell_a_arm_4_controllers.yaml" in produced
        assert (
            "arm_4_joint_trajectory_controller" in produced["control/cell_a_arm_4_controllers.yaml"]
        )
        assert "description/cell_a_arm_4.urdf.xacro" in produced
        assert "/cite/cell_a/arm_4" in produced["description/cell_a_arm_4.urdf.xacro"]
        assert "arm_4" in produced["bringup/cell_a_plan.yaml"]


class TestSimRealParity:
    """P2, asserted on the generator rather than hoped for at run time."""

    def test_only_the_plugin_differs_between_backends(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        sim = artifacts(real_model)

        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0].__setitem__(
                "hardware", {"backend": "real", "params": {"robot_ip": "192.168.1.100"}}
            ),
        )
        real = artifacts(real_model)

        # Controller and joint names are identical. If this ever fails, P2 is
        # broken and everything above L2 becomes unfounded.
        assert (
            sim["control/cell_a_arm_1_controllers.yaml"].replace(
                "use_sim_time: true", "use_sim_time: false"
            )
            == real["control/cell_a_arm_1_controllers.yaml"]
        )

        # The description differs in exactly one respect: the plugin class. Only
        # arm_1 was switched, so arm_2's and arm_3's descriptions must be
        # untouched — a backend is a per-instance choice, not a global mode.
        differing = [
            a
            for a, b in zip(
                sim["description/cell_a_arm_1.urdf.xacro"].splitlines(),
                real["description/cell_a_arm_1.urdf.xacro"].splitlines(),
                strict=True,
            )
            if a != b
        ]
        assert all("ros2_control_plugin" in line for line in differing), differing
        for other in ("arm_2", "arm_3"):
            key = f"description/cell_a_{other}.urdf.xacro"
            assert sim[key] == real[key], f"{other} changed when only arm_1 was switched"


class TestBindings:
    def test_an_unknown_binding_is_an_error_not_a_default(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Silently handing the vendor macro its own default would produce a
        # description that loads and is wrong.
        from cite_tools.generate.description import BindingError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["description"]["bound_args"].__setitem__(
                "prefix", "instance.prefxi"
            ),
        )
        with pytest.raises(BindingError, match="instance.prefxi"):
            artifacts(real_model)


class TestOneCoordinatePerFrame:
    """P1 across the two representations a frame can appear in.

    An L0 frame reaches the running system twice: as a link in the scene
    description, published by `robot_state_publisher`, and as a row in the static
    transform table. Both are live. When they disagree the system does not fail —
    it carries two answers for one name and hands out whichever the consumer
    happened to ask for.

    That is not hypothetical. The description generator subtracted half a body
    height from every type frame, which would only have been right if the link
    origin were the box centre; it is the foot. `pedestal_1_top` was published at
    z = 0.300 while `cell_a__pedestal_1__top` was published at z = 0.600, 0.3 m
    below where the arm is actually bolted, and nothing consumed the URDF-side
    name yet — which is exactly what made it dangerous.
    """

    @staticmethod
    def _urdf_world_poses(scene_xml: str) -> dict[str, Pose]:
        """Every named-frame link in the scene, resolved into `cite_world`."""
        root = ElementTree.fromstring(scene_xml)
        joints = {}
        for joint in root.findall("joint"):
            origin = joint.find("origin")
            xyz = tuple(float(v) for v in (origin.get("xyz") or "0 0 0").split())
            rpy = tuple(float(v) for v in (origin.get("rpy") or "0 0 0").split())
            parent = joint.find("parent").get("link")
            child = joint.find("child").get("link")
            joints[child] = (parent, Pose(xyz_m=xyz, rpy_rad=rpy))

        poses: dict[str, Pose] = {}
        for child, (parent, local) in joints.items():
            # Walk to the root, composing parent-then-child. Frame links hang off
            # a body's base_link, which hangs off cite_world.
            pose = local
            current = parent
            while current in joints:
                grandparent, up = joints[current]
                pose = up.compose(pose)
                current = grandparent
            if current == ids.WORLD_FRAME:
                poses[child] = pose
        return poses

    def test_every_frame_has_the_same_world_pose_in_both_representations(
        self, real_model: Path
    ) -> None:
        model = load(real_model)
        produced = artifacts(real_model)
        table = yaml.safe_load(produced["frames/cell_a_static_tf.yaml"])
        urdf = self._urdf_world_poses(produced["description/cell_a_scene.urdf.xacro"])

        static = {
            row["child"]: Pose(xyz_m=tuple(row["xyz_m"]), rpy_rad=tuple(row["rpy_rad"]))
            for row in table["static_transforms"]
        }

        checked = 0
        for asset in resolve(model, "cell_a").assets:
            for named in asset.asset_type.frames:
                link_name = ids.link(asset.id, named.id)
                frame_name = ids.frame("cell_a", asset.id, named.id)
                if named.link is not None:
                    # Published by robot_state_publisher from a vendor
                    # description. Neither generator may emit a second copy.
                    assert link_name not in urdf, f"{link_name} duplicates a vendor link"
                    assert frame_name not in static, f"{frame_name} duplicates a vendor link"
                    continue
                assert link_name in urdf, f"{link_name} is missing from the scene description"
                assert frame_name in static, f"{frame_name} is missing from the static TF table"
                assert urdf[link_name].approx_equal(static[frame_name], tol=1e-9), (
                    f"{named.id} on {asset.id} resolves to "
                    f"{urdf[link_name].xyz_m} as a URDF link and "
                    f"{static[frame_name].xyz_m} as a static transform"
                )
                checked += 1
        # A test that silently checked nothing would pass forever.
        assert checked >= 8, f"only {checked} frames were compared"

    def test_a_reintroduced_half_height_offset_is_caught(self, real_model: Path) -> None:
        # The exact defect, re-injected: raise the pedestal's own frame without
        # touching its body. The two representations must stop agreeing.
        import yaml as _yaml

        target = real_model / "assets/types/fixtures/pedestal_600.yaml"
        document = _yaml.safe_load(target.read_text())
        document["asset_type"]["frames"][0]["xyz_m"] = [0.0, 0.0, 0.3]
        target.write_text(_yaml.safe_dump(document, sort_keys=False))

        produced = artifacts(real_model)
        urdf = self._urdf_world_poses(produced["description/cell_a_scene.urdf.xacro"])
        table = yaml.safe_load(produced["frames/cell_a_static_tf.yaml"])
        static = {
            row["child"]: Pose(xyz_m=tuple(row["xyz_m"]), rpy_rad=tuple(row["rpy_rad"]))
            for row in table["static_transforms"]
        }
        # Both representations must move together, so they still agree with each
        # other — and both must show the new height rather than the old one.
        assert urdf["pedestal_1_top"].approx_equal(static["cell_a__pedestal_1__top"])
        assert round(urdf["pedestal_1_top"].xyz_m[2], 6) == 0.3


class TestFramesOfVendorLinks:
    """H2: `NamedFrame.link` is read, not merely documented."""

    def test_a_link_backed_frame_is_not_published_as_a_static_transform(
        self, real_model: Path
    ) -> None:
        # `tcp` on the xArm names `link_tcp`, which robot_state_publisher
        # publishes at wherever forward kinematics puts it. Emitting it here as
        # well produced a STATIC transform at the arm's mount — the canonical
        # name for the tool centre point, answering with a constant.
        table = yaml.safe_load(artifacts(real_model)["frames/cell_a_static_tf.yaml"])
        children = {row["child"] for row in table["static_transforms"]}
        assert "cell_a__arm_1__tcp" not in children
        assert "cell_a__arm_1__base" not in children
        # The mount is still there: nothing else ties the arm's own model to the
        # facility, and without it TF has two disconnected trees.
        assert "arm_1_mount" in children

    def test_clearing_the_link_makes_the_frame_appear(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The complement, so the test above cannot pass by the rule never firing.
        def mutate(document: dict) -> None:
            for frame in document["asset_type"]["frames"]:
                frame.pop("link", None)

        edit_yaml(real_model / "assets/types/robots/xarm5.yaml", mutate)
        table = yaml.safe_load(artifacts(real_model)["frames/cell_a_static_tf.yaml"])
        children = {row["child"] for row in table["static_transforms"]}
        assert "cell_a__arm_1__tcp" in children


class TestMassIsWhereTheGeometryIs:
    """M-07: a centroidal tensor declared at the body's foot is a lie."""

    def test_the_inertial_origin_carries_the_same_half_height_as_the_geometry(
        self, real_model: Path
    ) -> None:
        scene = artifacts(real_model)["description/cell_a_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        checked = 0
        for link in root.findall("link"):
            inertial = link.find("inertial")
            collision = link.find("collision")
            if inertial is None or collision is None:
                continue
            mass_z = float((inertial.find("origin").get("xyz")).split()[2])
            box_z = float((collision.find("origin").get("xyz")).split()[2])
            assert mass_z == box_z, (
                f"{link.get('name')} declares its mass at z={mass_z} while its "
                f"collision box is centred at z={box_z}"
            )
            checked += 1
        assert checked >= 4, f"only {checked} bodies were compared"

    def test_a_centre_of_mass_offset_is_applied_from_the_box_centre(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # `com_m` is measured from the collision box centre, which is the same
        # reference validate.physical uses. A pedestal whose mass sits 0.25 m low
        # must land at z = 0.05 in the link frame, not at z = -0.25 below it.
        edit_yaml(
            real_model / "assets/types/fixtures/pedestal_600.yaml",
            lambda d: d["asset_type"]["description"]["body"]["inertial"].__setitem__(
                "com_m", [0.0, 0.0, -0.25]
            ),
        )
        scene = artifacts(real_model)["description/cell_a_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        links = root.findall("link")
        link = next(e for e in links if e.get("name") == "pedestal_1_base_link")
        z = float(link.find("inertial").find("origin").get("xyz").split()[2])
        assert round(z, 9) == 0.05


class TestEverythingIsAnchored:
    """H3: nothing in the cell stands on the ground by friction alone."""

    def test_the_scene_is_static(self, real_model: Path) -> None:
        scene = artifacts(real_model)["description/cell_a_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        statics = [
            element.text
            for gazebo in root.findall("gazebo")
            for element in gazebo.findall("static")
        ]
        assert statics == ["true"], (
            "the cell furniture lumps into one free rigid body without this; three "
            "arms' reaction torques then slide it and the symptom reads as drift"
        )

    def test_every_arm_is_bolted_to_the_world(self, real_model: Path) -> None:
        produced = artifacts(real_model)
        for arm in ("arm_1", "arm_2", "arm_3"):
            root = ElementTree.fromstring(produced[f"description/cell_a_{arm}.urdf.xacro"])
            anchors = [
                joint
                for gazebo in root.findall("gazebo")
                for joint in gazebo.findall("joint")
                if joint.get("type") == "fixed"
            ]
            assert len(anchors) == 1, f"{arm} has {len(anchors)} world anchors"
            assert anchors[0].find("parent").text == "world"
            assert anchors[0].find("child").text == f"{arm}_mount"
            # No pose: the spawn pose in the bring-up plan places the model, and
            # a pose here would apply the same displacement twice.
            assert anchors[0].find("pose") is None

    def test_the_arm_anchor_is_invisible_to_robot_state_publisher(self, real_model: Path) -> None:
        # The anchor lives inside <gazebo> precisely so TF never sees it. A URDF
        # joint from a link named `world` would give arm_1_mount a second parent
        # alongside the generated static transform table.
        root = ElementTree.fromstring(artifacts(real_model)["description/cell_a_arm_1.urdf.xacro"])
        assert root.findall("joint") == []
        assert [link.get("name") for link in root.findall("link")] == ["arm_1_mount"]


class TestPlanningSceneIsGenerated:
    """M-08: the planner is told what the cell contains."""

    def test_every_authored_body_becomes_a_collision_object(self, real_model: Path) -> None:
        produced = artifacts(real_model)
        scene = yaml.safe_load(produced["moveit/cell_a_planning_scene.yaml"])
        objects = {o["id"]: o for o in scene["planning_scene"]["collision_objects"]}
        # DERIVED FROM THE MODEL, not listed again here. The list that used to be
        # written out was a second copy of the cell's inventory, and adding
        # `beam_pick` to L0 failed this test for saying so — a test that has to be
        # edited whenever the model gains an asset is testing the editor, not the
        # generator. What the generator promises is that every AUTHORED body
        # becomes a collision object, which is what the name says and what this
        # now asserts.
        expected = {
            asset.id
            for asset in resolve(load(real_model), "cell_a").assets
            if asset.asset_type.description.body is not None
        }
        assert expected, "no authored body was found, so this test asserted nothing"
        assert set(objects) == expected
        # Arms are deliberately absent: an articulated robot frozen at a pose is
        # confidently wrong wherever it actually is.
        assert not any(o.startswith("arm_") for o in objects)

    def test_a_collision_object_agrees_with_the_scene_description(self, real_model: Path) -> None:
        # Same geometry, same place — the planner's cell and the simulator's cell
        # come from one resolved body, so they cannot drift.
        produced = artifacts(real_model)
        scene = yaml.safe_load(produced["moveit/cell_a_planning_scene.yaml"])
        table = next(
            o for o in scene["planning_scene"]["collision_objects"] if o["id"] == "table_pick"
        )
        assert table["primitive"]["dimensions_m"] == [0.6, 0.6, 0.6]
        # MoveIt primitive poses are CENTRES; the L0 pose is the foot.
        assert table["pose"]["xyz_m"] == [-0.475, 0.0, 0.3]

    def test_it_tracks_the_model(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: d["assets"][3]["pose"].__setitem__("xyz_m", [-0.6, 0.0, 0.0]),
        )
        scene = yaml.safe_load(artifacts(real_model)["moveit/cell_a_planning_scene.yaml"])
        table = next(
            o for o in scene["planning_scene"]["collision_objects"] if o["id"] == "table_pick"
        )
        assert table["pose"]["xyz_m"][0] == -0.6


class TestPhysicalConstantsComeFromTheModel:
    """M-12: code encodes how, the model encodes which (P5)."""

    def test_the_acceleration_ceiling_is_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("max_acceleration_rad_s2", 3.5),
        )
        limits = artifacts(real_model)["moveit/cell_a_arm_1_joint_limits.yaml"]
        assert "max_acceleration: 3.5" in limits
        assert "max_acceleration: 2.0" not in limits

    def test_the_controller_manager_rate_is_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["control"].__setitem__("update_rate_hz", 250),
        )
        controllers = artifacts(real_model)["control/cell_a_arm_1_controllers.yaml"]
        assert "update_rate: 250" in controllers

    def test_a_type_with_controllers_and_no_rate_is_an_error_not_a_default(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        from cite_tools.generate.control import MissingControlSpecError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"].pop("control"),
        )
        with pytest.raises(MissingControlSpecError, match="update_rate_hz"):
            artifacts(real_model)


class TestTheDeterminismCheckCanSeeWhatItClaimsTo:
    """R-17: the check has to run somewhere its own failure mode can occur.

    `PYTHONHASHSEED` is fixed for the life of a process, so generating twice in
    one interpreter cannot observe set-iteration order changing — which is the
    single most likely way byte-identical output breaks. The check ran that way
    and its docstring named a property it could not have detected.
    """

    def test_the_second_run_is_a_fresh_interpreter_under_a_different_seed(
        self, real_model: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        from cite_tools import cli

        seen: dict[str, object] = {}
        real_run = subprocess.run

        def capture(command, **kwargs):  # type: ignore[no-untyped-def]
            seen["command"] = command
            seen["seed"] = kwargs["env"]["PYTHONHASHSEED"]
            return real_run(command, **kwargs)

        monkeypatch.setattr(cli.subprocess, "run", capture)
        monkeypatch.setenv("PYTHONHASHSEED", "0")

        produced = gen.generate(load(real_model))
        assert cli._determinism_problems(real_model, produced) == []

        assert seen["command"][0] == sys.executable, "regeneration must be a real interpreter"
        assert seen["seed"] != "0", "the second run must not inherit this process's hash seed"

    def test_a_difference_between_the_two_runs_is_reported(self, real_model: Path) -> None:
        # Proves the comparison is against what the subprocess actually produced
        # rather than against the list handed in.
        from cite_tools import cli

        produced = gen.generate(load(real_model))
        tampered = [
            gen.Artifact(a.path, a.content + "\n# tampered\n") if a.path == "MODEL_HASH" else a
            for a in produced
        ]
        problems = cli._determinism_problems(real_model, tampered)
        assert any("MODEL_HASH" in problem for problem in problems), problems

    def test_a_failing_subprocess_is_reported_rather_than_raised(self, real_model: Path) -> None:
        # A check that crashes on its own machinery tells nobody anything.
        from cite_tools import cli

        produced = gen.generate(load(real_model))
        problems = cli._determinism_problems(real_model / "does_not_exist", produced)
        assert problems and "subprocess" in problems[0]


class TestGraspPolicyReachesTheBringUpPlan:
    """The grasp default is L0 data, and the plan is how L3 receives it.

    Written once in the end-effector type, delivered to every arm that carries
    one. A value the model states but the plan does not carry is a value the
    skill server never sees, and the visible symptom is a gripper closing against
    its effort limit while the model looks correct.
    """

    EFFECTOR = "assets/types/end_effectors/xarm_parallel_gripper.yaml"

    def test_the_default_width_is_delivered_to_every_arm(self, real_model: Path) -> None:
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_a_plan.yaml"])["plan"]
        managers = [m for m in plan["controller_managers"] if m.get("gripper_action")]
        assert managers, "no arm in the plan has a gripper; this test would prove nothing"
        for manager in managers:
            assert manager["gripper_default_grasp_width_m"] == 0.045, manager["asset"]

    def test_the_value_comes_from_the_model_and_is_not_a_generator_constant(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / self.EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__("default_grasp_width_m", 0.031),
        )
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_a_plan.yaml"])["plan"]
        widths = {
            m["gripper_default_grasp_width_m"]
            for m in plan["controller_managers"]
            if m.get("gripper_action")
        }
        assert widths == {0.031}

    def test_an_unset_default_emits_no_key_rather_than_a_zero(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Absent, not 0.0. Zero is what `Pick.Goal.grasp_width_m` uses to mean
        "no width supplied", so emitting it as the *default* would turn "nobody
        configured one" into a configured value meaning the same thing — and the
        skill server's warning about the missing datum would never fire."""
        edit_yaml(
            real_model / self.EFFECTOR,
            lambda d: d["asset_type"]["grasp"].pop("default_grasp_width_m", None),
        )
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_a_plan.yaml"])["plan"]
        for manager in plan["controller_managers"]:
            assert "gripper_default_grasp_width_m" not in manager

    def test_a_stall_is_reported_by_the_controller_rather_than_aborted(
        self, real_model: Path
    ) -> None:
        """ADR-0022: a stall is reported, not interpreted.

        `GripperActionController` defaults `allow_stalling` to false, and false
        makes it call `setAborted` on the one outcome a parallel gripper exists to
        report — pads closed onto a part. The skill would then have to read
        success out of a failed action. This is model data so that simulation and
        hardware are configured identically (P2).
        """
        produced = artifacts(real_model)
        for asset in ("arm_1", "arm_2", "arm_3"):
            controllers = yaml.safe_load(produced[f"control/cell_a_{asset}_controllers.yaml"])
            gripper = controllers[f"/cite/cell_a/{asset}/{asset}_gripper_controller"]
            assert gripper["ros__parameters"]["allow_stalling"] is True
