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

"""The one statement of the model a work-piece is spawned as.

It brings nothing up: the module builds a string from a YAML file, so every case
here is driven against a document this file writes, plus one against the
generated artifact the running cell actually reads.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ElementTree

from cite_bringup.workpiece import (
    appearance,
    APPEARANCE_URI,
    FRICTION_MU,
    MASS_KG,
    SIDE_M,
    workpiece_sdf,
    WorkpieceError,
)
import pytest
import yaml

#: The generated artifact, as this checkout has it. Read from the source tree
#: rather than through `resolve_uri`, so this file answers on a host with no
#: overlay as well as inside one. `test_the_installed_artifact_answers` is what
#: checks the package route.
GENERATED = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "cite_generated"
    / "materials"
    / "appearance.yaml"
)


def document(tmp_path: Path, bodies: dict, materials: dict) -> Path:
    path = tmp_path / "appearance.yaml"
    path.write_text(yaml.safe_dump({"appearance": {"materials": materials, "bodies": bodies}}))
    return path


@pytest.fixture
def one(tmp_path: Path) -> Path:
    return document(
        tmp_path,
        bodies={"workpiece": "workpiece_stock"},
        materials={
            "workpiece_stock": {
                "ambient": [0.8, 0.3, 0.1, 1.0],
                "diffuse": [0.9, 0.4, 0.1, 1.0],
            }
        },
    )


def test_the_colour_comes_from_the_document(one: Path) -> None:
    assert appearance("workpiece", one) == ((0.8, 0.3, 0.1, 1.0), (0.9, 0.4, 0.1, 1.0))


def test_the_model_carries_the_declared_colour(one: Path) -> None:
    """The point of the whole change: the spawned box is not black."""
    visual = ElementTree.fromstring(workpiece_sdf("workpiece", one)).find(".//visual")
    material = visual.find("material")
    assert material is not None
    assert material.find("ambient").text == "0.8 0.3 0.1 1"
    assert material.find("diffuse").text == "0.9 0.4 0.1 1"


def test_a_different_colour_reaches_the_model(tmp_path: Path) -> None:
    """Mutation check: the values above come from the document, not from here."""
    path = document(
        tmp_path,
        bodies={"workpiece": "green"},
        materials={"green": {"ambient": [0.0, 0.5, 0.0, 1.0], "diffuse": [0.0, 0.8, 0.0, 1.0]}},
    )
    material = ElementTree.fromstring(workpiece_sdf("workpiece", path)).find(".//visual/material")
    assert material.find("diffuse").text == "0 0.8 0 1"


def test_a_body_the_facility_does_not_declare_is_refused(one: Path) -> None:
    """No fallback colour. A default here would be a second statement of one."""
    with pytest.raises(WorkpieceError, match="no body of type 'brick'"):
        workpiece_sdf("brick", one)


def test_a_material_the_library_does_not_declare_is_refused(tmp_path: Path) -> None:
    path = document(tmp_path, bodies={"workpiece": "ghost"}, materials={})
    with pytest.raises(WorkpieceError, match="unknown-material"):
        workpiece_sdf("workpiece", path)


def test_the_model_is_well_formed_and_named(one: Path) -> None:
    root = ElementTree.fromstring(workpiece_sdf("workpiece", one))
    assert root.tag == "sdf"
    assert root.find("model").get("name") == "workpiece"


def test_the_physics_is_unchanged(one: Path) -> None:
    """The numbers both scenarios carried, moved here and not re-derived.

    EVERY GRASP FIGURE THIS PROJECT HAS PUBLISHED WAS MEASURED AGAINST THEM.
    The appearance change that created this module was explicitly not allowed to
    move a mass, an inertia, a friction coefficient or a collision geometry, and
    this is that constraint written down where a later edit will meet it. The
    inertia is spelled as the arithmetic rather than as a literal for the same
    reason the module computes it: a guessed tensor makes a pick behave oddly for
    reasons that look like a controller fault.
    """
    link = ElementTree.fromstring(workpiece_sdf("workpiece", one)).find(".//link")
    assert SIDE_M == 0.05
    assert MASS_KG == 0.2
    assert FRICTION_MU == 1.0
    assert link.find("inertial/mass").text == "0.2"
    expected = MASS_KG * (SIDE_M * SIDE_M + SIDE_M * SIDE_M) / 12.0
    for axis in ("ixx", "iyy", "izz"):
        assert float(link.find(f"inertial/inertia/{axis}").text) == expected
    for axis in ("ixy", "ixz", "iyz"):
        assert float(link.find(f"inertial/inertia/{axis}").text) == 0.0
    assert link.find("collision/geometry/box/size").text == "0.05 0.05 0.05"
    assert link.find("visual/geometry/box/size").text == "0.05 0.05 0.05"
    friction = link.find("collision/surface/friction/ode")
    assert friction.find("mu").text == "1.0"
    assert friction.find("mu2").text == "1.0"


def test_the_generated_artifact_in_this_checkout_answers() -> None:
    """The real document, so this file fails if the generator stops emitting it.

    Every work-piece the facility declares, because a part spawned with no
    appearance is the black box this module exists to prevent — and the set comes
    from the artifact rather than from a name written here.
    """
    assert GENERATED.is_file(), f"{GENERATED} is generated from L0 and is missing"
    bodies = yaml.safe_load(GENERATED.read_text())["appearance"]["bodies"]
    assert "workpiece" in bodies
    material = ElementTree.fromstring(workpiece_sdf("workpiece", GENERATED)).find(
        ".//visual/material"
    )
    assert material.find("ambient").text
    assert material.find("diffuse").text


def test_the_appearance_uri_names_the_generated_package() -> None:
    """The path this module composes is the one the generator writes to."""
    assert APPEARANCE_URI.startswith("package://cite_generated/")
    assert APPEARANCE_URI.endswith("/" + GENERATED.parent.name + "/" + GENERATED.name)
