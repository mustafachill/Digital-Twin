"""The material library: what it declares, what it refuses, and what it emits.

The defect behind all of it: `Body.material` carried a name on every authored
body and nothing resolved it, so every visual in the generated scene was a bare
`<geometry>` and the whole cell rendered black without one line of output.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cite_tools import generate as gen
from cite_tools.generate import description, materials
from cite_tools.model.loader import load
from cite_tools.model.resolve import ResolveError, resolve
from cite_tools.model.schema import MaterialsDocument
from cite_tools.validate import Severity, referential


def rules(path: Path) -> set[str]:
    findings = referential.check(load(path))
    return {f.rule for f in findings if f.severity is Severity.ERROR}


def materials_file(model: Path) -> Path:
    """The material document, found by its own `schema:` key and not by its name.

    The loader dispatches on content rather than on location, so a test that
    hard-coded `facility/materials.yaml` would be asserting a convention the
    loader does not enforce and would silently stop testing anything if the file
    were legitimately moved.
    """
    found = [
        path
        for path in sorted(model.rglob("*.yaml"))
        if "schema" not in path.parts
        and (document := yaml.safe_load(path.read_text())) is not None
        and document.get("schema") == "cite/materials/v1"
    ]
    assert len(found) == 1, f"expected exactly one material document, found {found}"
    return found[0]


# --------------------------------------------------------------------------- #
# The library resolves
# --------------------------------------------------------------------------- #
def test_every_material_a_body_names_is_declared(real_model: Path) -> None:
    """The shipped model's own names resolve. This is the defect, asked directly."""
    assert "unknown-material" not in rules(real_model)


def test_every_authored_body_in_the_shipped_model_has_an_appearance(real_model: Path) -> None:
    """Not required by any rule, and true of this facility — so it is asserted.

    `material` is optional on purpose: a body may legitimately say "nobody has
    decided". What must not happen quietly is this cell losing an appearance it
    had, which is how it came to render black in the first place.
    """
    model = load(real_model)
    without = sorted(
        asset_type.id
        for asset_type in model.types
        if asset_type.description.body is not None and asset_type.description.body.material is None
    )
    assert without == [], f"authored bodies with no declared appearance: {without}"


def test_a_name_no_material_declares_is_an_error(real_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        real_model / "assets/types/fixtures/work_table_600.yaml",
        lambda d: d["asset_type"]["description"]["body"].__setitem__("material", "nonexistent"),
    )
    assert "unknown-material" in rules(real_model)


def test_removing_the_library_makes_every_name_dangle(real_model: Path) -> None:
    """The state this model was in before the library existed, asserted as an error.

    Not merely "some finding": the count is the number of authored bodies that
    name a material, so a rule that fired once and stopped would fail here.
    """
    model = load(real_model)
    expected = sum(
        1
        for asset_type in model.types
        if asset_type.description.body is not None and asset_type.description.body.material
    )
    materials_file(real_model).unlink()
    findings = [f for f in referential.check(load(real_model)) if f.rule == "unknown-material"]
    assert len(findings) == expected > 0


def test_a_material_no_body_wears_is_not_an_error(real_model: Path, edit_yaml: Callable) -> None:
    """The unused direction is deliberately not checked; see the rule's docstring."""
    edit_yaml(
        materials_file(real_model),
        lambda d: d["materials"].append(
            {"id": "unused_paint", "ambient": [0.1, 0.1, 0.1, 1.0], "diffuse": [0.2, 0.2, 0.2, 1.0]}
        ),
    )
    assert rules(real_model) == set()


def test_a_model_with_no_library_and_no_named_material_is_valid(minimal_model: Path) -> None:
    """A facility owes a library only once a body names one."""
    assert rules(minimal_model) == set()


# --------------------------------------------------------------------------- #
# The schema
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_a_colour_component_outside_zero_to_one_is_refused(bad: float) -> None:
    with pytest.raises(ValidationError):
        MaterialsDocument.model_validate(
            {
                "schema": "cite/materials/v1",
                "materials": [
                    {"id": "m", "ambient": [bad, 0.0, 0.0, 1.0], "diffuse": [0.0, 0.0, 0.0, 1.0]}
                ],
            }
        )


def test_a_colour_needs_all_four_components() -> None:
    """Three is a triple, not a colour: alpha is not optional here."""
    with pytest.raises(ValidationError):
        MaterialsDocument.model_validate(
            {
                "schema": "cite/materials/v1",
                "materials": [
                    {"id": "m", "ambient": [0.0, 0.0, 0.0], "diffuse": [0.0, 0.0, 0.0, 1.0]}
                ],
            }
        )


def test_an_unknown_key_in_a_material_is_refused() -> None:
    """`specular` is deliberately not declared; a typo must not be a silent default."""
    with pytest.raises(ValidationError):
        MaterialsDocument.model_validate(
            {
                "schema": "cite/materials/v1",
                "materials": [
                    {
                        "id": "m",
                        "ambient": [0.0, 0.0, 0.0, 1.0],
                        "diffuse": [0.0, 0.0, 0.0, 1.0],
                        "specular": [0.0, 0.0, 0.0, 1.0],
                    }
                ],
            }
        )


# --------------------------------------------------------------------------- #
# What is emitted
# --------------------------------------------------------------------------- #
def scenes(model_path: Path) -> list[tuple[str, ElementTree.Element]]:
    """Every generated scene, parsed.

    PARSED AND NOT GREPPED, which this file learned the hard way: counting
    `"<visual>"` in the text also counted the word inside the template's own
    explanatory comment, and the test failed on a scene that was correct.
    """
    parsed = [
        (artifact.path, ElementTree.fromstring(artifact.content))
        for artifact in gen.generate(load(model_path))
        if artifact.path.endswith("_scene.urdf.xacro")
    ]
    assert parsed, "no scene was generated"
    return parsed


def test_every_visual_in_every_generated_scene_carries_a_material(real_model: Path) -> None:
    """The assertion the defect is about, over the whole generated tree.

    Every visual, not "the file mentions a material": one material in a scene of
    a dozen visuals is exactly the state this change was written to leave behind.
    """
    for path, root in scenes(real_model):
        visuals = root.findall("./link/visual")
        assert visuals, f"{path}: no visual at all"
        for visual in visuals:
            material = visual.find("material")
            assert material is not None and material.get(
                "name"
            ), f"{path}: a visual carries no material and renders black"


def test_a_scene_defines_each_material_it_uses_exactly_once(real_model: Path) -> None:
    """urdfdom keeps the first definition of a repeated name and warns about it."""
    for path, root in scenes(real_model):
        defined = [material.get("name") for material in root.findall("./material")]
        assert len(defined) == len(set(defined)), f"{path}: repeated definition"
        assert all(material.find("color") is not None for material in root.findall("./material"))


def test_every_material_a_scene_references_is_defined_in_that_scene(real_model: Path) -> None:
    """A reference to a name the document does not define resolves to nothing."""
    for path, root in scenes(real_model):
        defined = {material.get("name") for material in root.findall("./material")}
        used = {material.get("name") for material in root.findall("./link/visual/material")}
        assert used <= defined, f"{path}: undefined material(s) {sorted(used - defined)}"


def test_a_scene_defines_only_the_materials_its_bodies_wear(real_model: Path) -> None:
    model = load(real_model)
    for zone in model.zones:
        cell = resolve(model, zone.id)
        bodies = description.body_views(cell)
        worn = {body.material.id for body in bodies if body.material is not None}
        defined = {m.id for m in description.scene_materials(bodies)}
        assert defined == worn


def test_the_scene_carries_the_declared_diffuse(real_model: Path) -> None:
    """URDF has one colour; the library's diffuse is the one that survives."""
    model = load(real_model)
    cell = resolve(model, model.zones[0].id)
    table = cell.material("table_top")
    root = next(
        parsed
        for path, parsed in scenes(real_model)
        if path == f"description/{cell.zone}_scene.urdf.xacro"
    )
    colour = next(
        material.find("color").get("rgba")
        for material in root.findall("./material")
        if material.get("name") == "table_top"
    )
    assert colour == " ".join(_short(component) for component in table.diffuse)


def _short(value: float) -> str:
    from cite_tools.model.units import fmt

    return fmt(value)


def test_the_appearance_artifact_states_the_library_and_the_binding(real_model: Path) -> None:
    model = load(real_model)
    artifact = next(a for a in gen.generate(model) if a.path == materials.PATH)
    document = yaml.safe_load(artifact.content)["appearance"]

    assert set(document["materials"]) == {m.id for m in model.materials}
    for entry in model.materials:
        assert document["materials"][entry.id]["ambient"] == list(entry.ambient)
        assert document["materials"][entry.id]["diffuse"] == list(entry.diffuse)

    expected = {
        asset_type.id: asset_type.description.body.material
        for asset_type in model.types
        if asset_type.description.body is not None and asset_type.description.body.material
    }
    assert document["bodies"] == expected


def test_the_appearance_artifact_carries_the_workpiece(real_model: Path) -> None:
    """The one consumer outside the generated tree asks for exactly this entry."""
    model = load(real_model)
    artifact = next(a for a in gen.generate(model) if a.path == materials.PATH)
    document = yaml.safe_load(artifact.content)["appearance"]
    for name in model.facility.workpiece_models:
        assert name in document["bodies"], f"{name} is spawned and has no appearance"


def test_the_appearance_artifact_states_no_colour_twice(real_model: Path) -> None:
    """The library and the binding, never the join: `bodies` carries names only."""
    model = load(real_model)
    artifact = next(a for a in gen.generate(model) if a.path == materials.PATH)
    document = yaml.safe_load(artifact.content)["appearance"]
    assert all(isinstance(value, str) for value in document["bodies"].values())


def test_the_model_hash_moves_when_a_colour_moves(real_model: Path, edit_yaml: Callable) -> None:
    """A recording stamped with this hash must identify what the cell looked like."""
    before = gen.model_hash(load(real_model))
    edit_yaml(
        materials_file(real_model),
        lambda d: d["materials"][0].__setitem__("diffuse", [0.11, 0.12, 0.13, 1.0]),
    )
    assert gen.model_hash(load(real_model)) != before


def test_a_generator_asking_for_an_undeclared_material_raises(real_model: Path) -> None:
    """The resolver refuses rather than returning None, which would emit nothing."""
    cell = resolve(load(real_model), "cell_b")
    with pytest.raises(ResolveError):
        cell.material("no_such_material")
