"""Binding a collision-geometry set to a vendor description (ADR-0028).

Three things are checked here and they answer three different questions:

* the **default does not move** — with the shipped selection the generated
  description is what it was before the field existed, which is what lets the
  byte-identity check tell "unchanged" from "changed";
* **selecting a set actually reaches the description**, and reaches it as the
  vendor macro parameter the model names rather than as a value the generator
  invented, **and the generated package declares what that description now
  needs** — this file used to assert the opposite, which is the defect below;
* the **validator now fires on a vendor description**, which it structurally
  could not do before this field existed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.model.schema import CollisionMeshSet, CollisionSpec
from cite_tools.validate import Severity, physical

ARM_TYPE = "assets/types/robots/xarm5.yaml"
ARM_INSTANCES = "assets/instances/arms.yaml"
ARM_DESCRIPTION = "description/cell_a_arm_1.urdf.xacro"


def _use_real_backend(document: dict) -> None:
    """Every arm on the hardware backend, which is the case R-04 got wrong."""
    for asset in document["assets"]:
        asset["hardware"]["backend"] = "real"


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def _select(document: dict, set_id: str) -> None:
    document["asset_type"]["description"]["collision"]["select"] = set_id


class TestTheShippedDefault:
    def test_the_vendor_set_is_what_ships(self, real_model: Path) -> None:
        """Stated as a test so that moving it cannot be a quiet edit.

        ADR-0028's promotion gate requires the friction-grasp campaign re-run
        against hull geometry before the default may move. Whoever moves it will
        have to change this test, and that is the point.
        """
        model = load(real_model)
        arm = next(t for t in model.types if t.id == "xarm5")
        assert arm.description.collision is not None
        assert arm.description.collision.select == "vendor_meshes"
        assert arm.description.collision.selected.kind == "vendor_meshes"

    def test_the_vendor_selection_emits_no_collision_argument(self, real_model: Path) -> None:
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert "collision_mesh_path" not in description


class TestSelectingADerivedSet:
    def test_the_root_reaches_the_vendor_macro(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert (
            'collision_mesh_path="file://$(find cite_description)'
            '/meshes/collision/xarm5/convex_hull"' in description
        )

    def test_nothing_else_about_the_description_changes(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """A geometry switch must be a geometry switch and nothing else.

        If selecting a set moved a joint, renamed a link or changed a controller,
        the A/B comparison the campaign needs would be measuring two things.
        """
        before = artifacts(real_model)[ARM_DESCRIPTION]
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        after = artifacts(real_model)[ARM_DESCRIPTION]

        added = [line for line in after.splitlines() if line not in before.splitlines()]
        removed = [line for line in before.splitlines() if line not in after.splitlines()]
        assert removed == []
        assert len(added) == 1
        assert "collision_mesh_path" in added[0]

    def test_the_descriptions_the_hash_and_the_package_move(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """`package.xml` is in this set, and it was the defect that it was not.

        This test asserted the opposite until 2026-08-31: the expected set named
        the three descriptions and the hash, so it *required* the generated
        `package.xml` to stay still while the descriptions it declares the
        dependencies for started naming a package it did not list. A dependency
        derivation that a test pins shut is not a derivation.
        """
        before = artifacts(real_model)
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        after = artifacts(real_model)

        changed = {path for path in before if before[path] != after[path]}
        assert changed == {
            "MODEL_HASH",
            "package.xml",
            "description/cell_a_arm_1.urdf.xacro",
            "description/cell_a_arm_2.urdf.xacro",
            "description/cell_a_arm_3.urdf.xacro",
        }

    def test_the_generated_package_declares_the_set_it_installs_from(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Every `$(find X)` in a generated description needs X in `package.xml`.

        Without this the failure is not a build error but a run-time one, and it
        arrives late: `colcon build --packages-up-to cite_bringup` succeeds
        because nothing declares the ordering, and `robot_state_publisher` then
        dies with `PackageNotFoundError: cite_description` when the cell comes up.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        generated = artifacts(real_model)
        description = generated[ARM_DESCRIPTION]
        assert "$(find cite_description)" in description
        assert "<exec_depend>cite_description</exec_depend>" in generated["package.xml"]

    def test_a_declared_but_unselected_set_brings_no_dependency(self, real_model: Path) -> None:
        """The other direction, and it is why the derivation reads `selected`.

        `convex_hull` is declared on the shipped type and is not bound. Nothing
        loads it, so `cite_generated` must not depend on it — and if it did, the
        shipped default would stop emitting the bytes it emitted before the field
        existed, which is the property the byte-identity check rests on.
        """
        generated = artifacts(real_model)
        assert "cite_description" not in generated["package.xml"]
        assert "cite_description" not in generated[ARM_DESCRIPTION]


class TestTheRootResolvesTheWayTheVendorsDoes:
    """R-04. The substituted root has to branch on the backend, and it did not.

    `xarm_device_macro.xacro` sets `mesh_path` to `file://$(find ...)` for a
    Gazebo plugin and `package://` for anything else. The generator emitted
    `file://` unconditionally, which was right on `sim` — where every scenario
    runs — and wrong on `real`, where nothing runs yet. The result was a
    description whose visual half resolved through the package path and whose
    collision half was absolute paths into the generating machine's install
    prefix: unportable, and the half a planner uses.
    """

    def test_a_gazebo_backend_gets_the_file_scheme(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert (
            'collision_mesh_path="file://$(find cite_description)'
            '/meshes/collision/xarm5/convex_hull"' in description
        )

    def test_the_real_backend_gets_the_package_scheme(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The case the unconditional `file://` got wrong."""
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        edit_yaml(real_model / ARM_INSTANCES, _use_real_backend)
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert (
            'collision_mesh_path="package://cite_description'
            '/meshes/collision/xarm5/convex_hull"' in description
        )
        assert "file://" not in description

    def test_no_generated_collision_root_is_an_absolute_path(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Whatever the backend, the artifact carries no path from this machine.

        `$(find ...)` is expanded by xacro at load time; a literal `/Users/...`
        or `/opt/...` in a committed artifact is a description that only resolves
        on the machine that generated it.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        for mutate in (None, _use_real_backend):
            if mutate is not None:
                edit_yaml(real_model / ARM_INSTANCES, mutate)
            line = next(
                text
                for text in artifacts(real_model)[ARM_DESCRIPTION].splitlines()
                if "collision_mesh_path" in text
            )
            assert "$(find" in line or line.count("package://") == 1
            assert str(real_model) not in line

    def test_a_backend_with_no_scheme_is_refused_at_load(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Never a default: a silently wrong scheme is how this defect survived."""
        edit_yaml(
            real_model / ARM_TYPE,
            lambda d: d["asset_type"]["description"]["collision"]["root_uri_scheme"].pop("real"),
        )
        with pytest.raises(Exception, match="root_uri_scheme"):
            load(real_model)

    def test_a_declared_derived_set_must_state_its_schemes(self) -> None:
        """Required on DECLARATION, so that flipping `select` stays one field."""
        with pytest.raises(ValidationError, match="root_uri_scheme"):
            CollisionSpec(
                select="vendor_meshes",
                root_arg="collision_mesh_path",
                sets=[
                    CollisionMeshSet(id="vendor_meshes", kind="vendor_meshes"),
                    CollisionMeshSet(
                        id="convex_hull",
                        kind="convex_hull",
                        package="cite_description",
                        root="meshes/x",
                        source_package="xarm_description",
                        source_root="meshes",
                        meshes=["a.stl"],
                    ),
                ],
            )


class TestTheSchemaRefusesAnUnusableDeclaration:
    def test_select_must_name_a_set(self) -> None:
        with pytest.raises(ValidationError, match="names no set"):
            CollisionSpec(
                select="nothing_like_this",
                sets=[CollisionMeshSet(id="vendor_meshes", kind="vendor_meshes")],
            )

    def test_a_derived_selection_needs_a_macro_parameter(self) -> None:
        """Without one the set is generated, committed, and never bound."""
        with pytest.raises(ValidationError, match="root_arg"):
            CollisionSpec(
                select="convex_hull",
                sets=[
                    CollisionMeshSet(
                        id="convex_hull",
                        kind="convex_hull",
                        package="cite_description",
                        root="meshes/x",
                        source_package="xarm_description",
                        source_root="meshes",
                        meshes=["a.stl"],
                    )
                ],
            )

    def test_a_derived_set_needs_somewhere_to_come_from_and_go_to(self) -> None:
        with pytest.raises(ValidationError, match="convex_hull set needs"):
            CollisionMeshSet(id="convex_hull", kind="convex_hull")

    def test_a_vendor_set_may_not_name_paths(self) -> None:
        """A path here would be a second place for the vendor's own layout to live."""
        with pytest.raises(ValidationError, match="names no paths"):
            CollisionMeshSet(id="vendor_meshes", kind="vendor_meshes", meshes=["a.stl"])

    def test_duplicate_set_ids_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            CollisionSpec(
                select="vendor_meshes",
                sets=[
                    CollisionMeshSet(id="vendor_meshes", kind="vendor_meshes"),
                    CollisionMeshSet(id="vendor_meshes", kind="vendor_meshes"),
                ],
            )


class TestTheValidatorReachesAVendorDescription:
    """ADR-0028 decision 4.

    Before this field there was no way for `_collision_is_not_a_visual_mesh` to
    fire on a `xacro_macro` type: it reads `description.body`, and a vendor type
    has none. It had been passing on the twelve links per arm where the failure it
    names actually occurs, for as long as it had existed.
    """

    def test_the_shipped_model_is_warned_about_and_not_failed(self, real_model: Path) -> None:
        findings = physical.check(load(real_model))
        reuse = [f for f in findings if f.rule == "collision-reuses-visual-mesh"]
        assert [f.where for f in reuse] == ["types.xarm5.description.collision"]
        assert reuse[0].severity is Severity.WARNING
        assert not [f for f in findings if f.severity is Severity.ERROR]

    def test_selecting_hulls_silences_it(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        findings = physical.check(load(real_model))
        assert not [f for f in findings if f.rule == "collision-reuses-visual-mesh"]

    def test_an_undeclared_vendor_description_is_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """ "Nobody has looked" is the state that made the rule silent."""
        edit_yaml(
            real_model / ARM_TYPE,
            lambda d: d["asset_type"]["description"].pop("collision"),
        )
        findings = physical.check(load(real_model))
        undeclared = [f for f in findings if f.rule == "vendor-collision-undeclared"]
        assert len(undeclared) == 1
        assert undeclared[0].severity is Severity.ERROR

    def test_a_type_whose_description_is_not_emitted_is_not_asked(self, real_model: Path) -> None:
        """The parallel gripper names a macro and emits nothing.

        Its geometry is built into the arm's description by `add_gripper`, so
        demanding a collision declaration of it would be demanding a second
        answer to a question the arm has already answered.
        """
        model = load(real_model)
        gripper = next(t for t in model.types if t.id == "xarm_parallel_gripper")
        assert gripper.description.provider == "xacro_macro"
        assert gripper.description.collision is None
        assert not gripper.emits_vendor_description
        assert not [
            f for f in physical.check(model) if f.where.startswith("types.xarm_parallel_gripper")
        ]
