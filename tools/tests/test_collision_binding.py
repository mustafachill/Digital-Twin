"""Binding a collision-geometry set to a vendor description (ADR-0028).

Three things are checked here and they answer three different questions:

* the **shipped selection is what it says it is** — it moved from the vendor's
  meshes to the derived hulls on 2026-09-01 (ADR-0028, promoted against the clause
  ADR-0051 restates), and it moves again only by changing a test;
* **selecting a set actually reaches the description**, and reaches it as the
  vendor macro parameter the model names rather than as a value the generator
  invented, **and the generated package declares what that description now
  needs** — this file used to assert the opposite, which is the defect below;
* the **validator now fires on a vendor description**, which it structurally
  could not do before this field existed.
"""

from __future__ import annotations

from collections import Counter
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
    def test_the_derived_set_is_what_ships(self, real_model: Path) -> None:
        """Stated as a test so that moving it cannot be a quiet edit.

        This asserted `vendor_meshes` until 2026-09-01, with a docstring saying
        that whoever moved it would have to change this test, and that that was
        the point. It moved: ADR-0028 is `Accepted` against the clause ADR-0051
        restates, and the shipped selection is the derived hulls. The assertion
        keeps its shape and changes its side, so moving it back is the same
        deliberate act.
        """
        model = load(real_model)
        arm = next(t for t in model.types if t.id == "xarm5")
        assert arm.description.collision is not None
        assert arm.description.collision.select == "convex_hull"
        assert arm.description.collision.selected.kind == "convex_hull"

    def test_the_shipped_selection_emits_the_collision_argument(self, real_model: Path) -> None:
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert "collision_mesh_path" in description

    def test_the_vendor_selection_emits_no_collision_argument(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The other side of the substitution, kept because it is the fallback.

        Selecting the vendor's set has to leave the description exactly as it was
        before this field existed — that is what makes it a real answer rather
        than a differently-spelled hull, and it is the answer ADR-0051's range
        rule tells a model author to reach for.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert "collision_mesh_path" not in description


class TestSelectingADerivedSet:
    def test_the_root_reaches_the_vendor_macro(self, real_model: Path) -> None:
        """No mutation: this is the shipped selection since 2026-09-01."""
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

        Multiset difference, and it was set difference until 2026-08-31. A line
        that already appears once and is emitted a second time is `in` the
        before-text, so it entered neither `added` nor `removed` and the assertion
        below passed while the generated xacro carried a duplicated vendor
        argument. Verified by mutation: making the generator emit the collision
        argument AND duplicate an existing one left all fourteen tests green.
        `Counter` counts occurrences, which is the question this test means to ask.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
        before = artifacts(real_model)[ARM_DESCRIPTION]
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "convex_hull"))
        after = artifacts(real_model)[ARM_DESCRIPTION]

        before_lines = Counter(before.splitlines())
        after_lines = Counter(after.splitlines())
        added = list((after_lines - before_lines).elements())
        removed = list((before_lines - after_lines).elements())
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
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
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
        self, real_model: Path
    ) -> None:
        """Every `$(find X)` in a generated description needs X in `package.xml`.

        Without this the failure is not a build error but a run-time one, and it
        arrives late: `colcon build --packages-up-to cite_bringup` succeeds
        because nothing declares the ordering, and `robot_state_publisher` then
        dies with `PackageNotFoundError: cite_description` when the cell comes up.
        """
        generated = artifacts(real_model)
        description = generated[ARM_DESCRIPTION]
        assert "$(find cite_description)" in description
        assert "<exec_depend>cite_description</exec_depend>" in generated["package.xml"]

    def test_a_declared_but_unselected_set_brings_no_dependency(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The other direction, and it is why the derivation reads `selected`.

        Select the vendor's meshes and `convex_hull` is still declared on the
        type. Nothing loads it, so `cite_generated` must not depend on it — a
        derivation that read the declared sets instead of the bound one would make
        every model that merely *offers* a hull depend on the package that holds
        it. This ran without a mutation until 2026-09-01, when the shipped
        selection moved and the unselected set became the vendor's.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
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

    def test_a_gazebo_backend_gets_the_file_scheme(self, real_model: Path) -> None:
        description = artifacts(real_model)[ARM_DESCRIPTION]
        assert (
            'collision_mesh_path="file://$(find cite_description)'
            '/meshes/collision/xarm5/convex_hull"' in description
        )

    def test_the_real_backend_gets_the_package_scheme(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The case the unconditional `file://` got wrong."""
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

    def test_the_shipped_model_does_not_trip_it(self, real_model: Path) -> None:
        """The shipped selection is the hulls, so the rule has nothing to say.

        This test asserted the opposite until 2026-09-01 — one WARNING on
        `xarm5`, and no error anywhere — because the shipped selection was the
        vendor's own rendering meshes and the project had decided to stay there
        until ADR-0028's gate was met.
        """
        findings = physical.check(load(real_model))
        assert not [f for f in findings if f.rule == "collision-reuses-visual-mesh"]
        assert not [f for f in findings if f.severity is Severity.ERROR]

    def test_selecting_the_vendor_meshes_is_now_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """WARNING until 2026-09-01, and the promotion is what this change is.

        `_vendor_collision_is_declared`'s docstring recorded the severity as a
        compromise and said in terms: promote it in the change that moves the
        default, and not before. The default has moved, so colliding a rendering
        mesh is once again the plain defect CLAUDE.md §10 names, with a generated
        alternative one field away.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
        findings = physical.check(load(real_model))
        reuse = [f for f in findings if f.rule == "collision-reuses-visual-mesh"]
        assert [f.where for f in reuse] == ["types.xarm5.description.collision"]
        assert reuse[0].severity is Severity.ERROR

    def test_the_vendor_selection_fails_validation_without_strict(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The severity change is the whole of the behaviour change, so assert it.

        `--strict` used to be the only way to make this question hard, and a
        severity that only `--strict` reads is a severity `./scripts/validate-model`
        never enforces. Now the ordinary run refuses.
        """
        edit_yaml(real_model / ARM_TYPE, lambda d: _select(d, "vendor_meshes"))
        errors = [f for f in physical.check(load(real_model)) if f.severity is Severity.ERROR]
        assert [f.rule for f in errors] == ["collision-reuses-visual-mesh"]

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
