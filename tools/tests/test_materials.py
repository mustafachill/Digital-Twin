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
from cite_tools.validate import Severity, physical, referential


def rules(path: Path) -> set[str]:
    findings = referential.check(load(path))
    return {f.rule for f in findings if f.severity is Severity.ERROR}


def physical_findings(path: Path, rule: str) -> list:
    """Every ERROR of one rule from the physical level, in a stable order.

    The list rather than the rule names, because the interesting assertions about
    this rule are which colour it names and what its message says — a set of rule
    names would pass on a rule that fired for the wrong reason.
    """
    return [
        finding
        for finding in physical.check(load(path))
        if finding.rule == rule and finding.severity is Severity.ERROR
    ]


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


# --------------------------------------------------------------------------- #
# The colour a standing body wears has to survive the URDF channel
# --------------------------------------------------------------------------- #
def test_no_shipped_scene_material_clips(real_model: Path) -> None:
    """The shipped library passes. Asked directly, because it is what ships."""
    assert physical_findings(real_model, "scene-material-clips") == []


def test_a_colour_a_standing_body_wears_may_not_exceed_the_bound(
    real_model: Path, edit_yaml: Callable
) -> None:
    """The rule FIRING, on the entry a body in this cell actually wears.

    `pedestal_steel` is worn by `pedestal_600`, which is instantiated in both
    zones, so brightening it is exactly the change the bound refuses.
    """
    edit_yaml(
        materials_file(real_model),
        lambda d: next(m for m in d["materials"] if m["id"] == "pedestal_steel").__setitem__(
            "diffuse", [0.92, 0.53, 0.56, 1.0]
        ),
    )
    findings = physical_findings(real_model, "scene-material-clips")
    assert len(findings) == 1
    assert findings[0].where == "materials.pedestal_steel.diffuse[0]"


def test_the_finding_says_why_the_bound_is_what_it_is(
    real_model: Path, edit_yaml: Callable
) -> None:
    """A reader must learn the multiply, not be handed a number to obey.

    The gain is read from the module rather than written here: a test that spelled
    `1.25` itself would be a second statement of a measured constant, which is the
    duplication this rule was added to stop.
    """
    edit_yaml(
        materials_file(real_model),
        lambda d: next(m for m in d["materials"] if m["id"] == "table_top").__setitem__(
            "ambient", [0.9, 0.16, 0.08, 1.0]
        ),
    )
    finding = physical_findings(real_model, "scene-material-clips")[0]
    text = f"{finding.message} {finding.hint}"
    assert str(physical.URDF_TO_SDF_COLOUR_GAIN) in text
    assert str(physical.MAX_SCENE_COLOUR_COMPONENT) in text
    assert "work_table_600" in finding.message, "the body that wears it must be named"


def test_the_bound_is_derived_from_the_measured_gain() -> None:
    """0.8 is what reaches exactly 1.0, not a round number someone liked."""
    assert physical.MAX_SCENE_COLOUR_COMPONENT * physical.URDF_TO_SDF_COLOUR_GAIN == 1.0
    assert physical.MAX_SCENE_COLOUR_COMPONENT == 0.8


def test_the_bound_is_inclusive(real_model: Path, edit_yaml: Callable) -> None:
    """Exactly at the bound the conversion reaches 1.0 and clips nothing."""
    edit_yaml(
        materials_file(real_model),
        lambda d: next(m for m in d["materials"] if m["id"] == "pedestal_steel").__setitem__(
            "diffuse", [physical.MAX_SCENE_COLOUR_COMPONENT, 0.53, 0.56, 1.0]
        ),
    )
    assert physical_findings(real_model, "scene-material-clips") == []


def test_alpha_is_not_bounded(real_model: Path, edit_yaml: Callable) -> None:
    """Measured: the alpha passes through the conversion untouched.

    A rule that bounded it would refuse `1.0` — which every entry in this library
    declares, and which is shown exactly as declared.
    """
    edit_yaml(
        materials_file(real_model),
        lambda d: next(m for m in d["materials"] if m["id"] == "pedestal_steel").__setitem__(
            "diffuse", [0.52, 0.53, 0.56, 1.0]
        ),
    )
    assert physical_findings(real_model, "scene-material-clips") == []


def test_the_workpiece_material_is_above_the_bound_and_is_not_refused(
    real_model: Path,
) -> None:
    """The shipped exception, asserted rather than trusted to prose.

    `workpiece_stock` declares 0.90, which is above the bound, and is legal
    because its type has no instances and the thing that spawns one emits SDF.
    Both halves are checked here: if the model ever gives the work-piece an
    instance, the test below is what says so.
    """
    model = load(real_model)
    stock = next(m for m in model.materials if m.id == "workpiece_stock")
    assert max(stock.diffuse[:3]) > physical.MAX_SCENE_COLOUR_COMPONENT
    assert "workpiece" not in {asset.type for asset in model.assets}
    assert physical_findings(real_model, "scene-material-clips") == []


def test_instantiating_the_workpiece_would_refuse_that_colour(
    real_model: Path, edit_yaml: Callable
) -> None:
    """The exception above is a property of the model, and the rule holds it.

    This is the case the prose could not: a work-piece given an instance renders
    through the scene URDF like anything else, and the 0.90 then clips. Nothing
    but the rule reports it.

    ONE finding and not two, which is the bound being inclusive rather than the
    rule missing a channel: that entry's ambient is 0.80 exactly, which reaches
    1.0 after the multiply and is shown as declared. The expectation here was
    written as two and the rule was right.
    """
    edit_yaml(
        real_model / "assets/instances/fixtures.yaml",
        lambda d: d["assets"].append(
            {
                "id": "stray_block",
                "type": "workpiece",
                "zone": "cell_b",
                "pose": {"frame": "cite_world", "xyz_m": [0.0, 3.0, 0.0]},
                "hardware": {"backend": "sim"},
            }
        ),
    )
    model = load(real_model)
    stock = next(m for m in model.materials if m.id == "workpiece_stock")
    assert stock.ambient[0] == physical.MAX_SCENE_COLOUR_COMPONENT, "the inclusive edge"

    findings = physical_findings(real_model, "scene-material-clips")
    assert [f.where for f in findings] == ["materials.workpiece_stock.diffuse[0]"]
    assert "stray_block" not in findings[0].message, "the TYPE is named, not the instance"
    assert "workpiece" in findings[0].message


def test_a_material_no_instantiated_body_wears_is_not_bounded(
    real_model: Path, edit_yaml: Callable
) -> None:
    """Nothing renders it through a URDF, so nothing about it can clip."""
    edit_yaml(
        materials_file(real_model),
        lambda d: d["materials"].append(
            {"id": "unused_paint", "ambient": [1.0, 1.0, 1.0, 1.0], "diffuse": [1.0, 1.0, 1.0, 1.0]}
        ),
    )
    assert physical_findings(real_model, "scene-material-clips") == []


def test_a_dangling_material_is_reported_once_and_by_the_other_rule(
    real_model: Path, edit_yaml: Callable
) -> None:
    """Two rule names for one fact would send the reader to two places."""
    edit_yaml(
        real_model / "assets/types/fixtures/pedestal_600.yaml",
        lambda d: d["asset_type"]["description"]["body"].__setitem__("material", "nonexistent"),
    )
    assert "unknown-material" in rules(real_model)
    assert physical_findings(real_model, "scene-material-clips") == []
