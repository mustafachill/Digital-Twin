"""Fixtures for the model tests.

Every validator test starts from a known-good model and breaks exactly one
thing. That shape matters: a test that builds a broken model from scratch proves
the checker fires, but not that it fires *because of the break* — the model
might be failing for an unrelated reason the test never notices.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

FIXTURES = Path(__file__).parent / "fixtures"
#: The real model. Testing the validators against it rather than a toy keeps the
#: two from drifting apart, and means a change to the cell that breaks a rule is
#: caught by the unit suite rather than at simulation time.
REAL_MODEL = Path(__file__).resolve().parents[2] / "model"


def paired_twin() -> dict:
    """The shipped model's `twin:` block of a paired zone, read rather than restated.

    A test that pairs a zone writes this whole block, because a pair states its
    heartbeat period and, where its counterpart is physical, that side's
    timing (ADR-0070 item 5); copying the numbers here would be a second
    statement of them.
    """
    zones = yaml.safe_load((REAL_MODEL / "facility/zones.yaml").read_text())["zones"]
    (twin,) = [zone["twin"] for zone in zones if zone["twin"]["sides"] == "pair"][:1]
    return dict(twin)


@pytest.fixture
def minimal_model(tmp_path: Path) -> Path:
    destination = tmp_path / "model"
    shutil.copytree(FIXTURES / "minimal", destination)
    return destination


@pytest.fixture
def real_model(tmp_path: Path) -> Path:
    destination = tmp_path / "model"
    shutil.copytree(REAL_MODEL, destination)
    return destination


#: Two break beams and their housing type, as cell_b declared them until
#: 2026-10-16. The shipped model no longer has any — nothing in the main tree
#: read them (ADR-0079 addendum) — but the schema, the validators and the world
#: generator still support a declared beam, and the tests of that support need
#: one to stand on. They are the cell's own former beams rather than invented
#: ones, so every margin those tests were written against still holds.
BEAMS = FIXTURES / "beams"
#: The housing's appearance, which left the material library with the beams.
SENSOR_HOUSING = {
    "id": "sensor_housing",
    "ambient": [0.36, 0.28, 0.04, 1.0],
    "diffuse": [0.78, 0.62, 0.10, 1.0],
}


def add_beams(model: Path) -> None:
    """Put the two former break beams back into a copied model."""
    (model / "assets/types/sensors").mkdir(parents=True, exist_ok=True)
    shutil.copy(BEAMS / "break_beam.yaml", model / "assets/types/sensors/break_beam.yaml")
    shutil.copy(BEAMS / "sensors.yaml", model / "assets/instances/sensors.yaml")
    library = model / "facility/materials.yaml"
    document = yaml.safe_load(library.read_text())
    document["materials"].append(dict(SENSOR_HOUSING))
    library.write_text(yaml.safe_dump(document, sort_keys=False))


@pytest.fixture
def beams(real_model: Path) -> Path:
    """The real model with its two former break beams restored (see `add_beams`)."""
    add_beams(real_model)
    return real_model


@pytest.fixture
def edit_yaml() -> Callable[[Path, Callable[[dict], None]], None]:
    """Mutate one YAML document in place, preserving nothing else."""

    def _edit(path: Path, mutate: Callable[[dict], None]) -> None:
        document = yaml.safe_load(path.read_text())
        mutate(document)
        path.write_text(yaml.safe_dump(document, sort_keys=False))

    return _edit


@pytest.fixture
def remove_flow() -> Callable[[Path, str], str]:
    """Delete the flow document that names ``zone``, and return the zone.

    A fixture rather than three lines in the one test that needs it, because
    finding the document means reading every `cite/flow/v1` file in the tree
    rather than guessing its name: the loader dispatches on a document's own
    `schema:` key and not on its path, so `cell_b`'s flow lives in
    `flow_cell_b.yaml` today only by convention and could legitimately move.
    """

    def _remove(model: Path, zone: str) -> str:
        removed = [
            path
            for path in sorted(model.rglob("*.yaml"))
            if "schema" not in path.parts
            and (document := yaml.safe_load(path.read_text())) is not None
            and document.get("schema") == "cite/flow/v1"
            and document["flow"]["zone"] == zone
        ]
        assert len(removed) == 1, f"expected one flow document for {zone}, found {removed}"
        removed[0].unlink()
        return zone

    return _remove


@pytest.fixture
def add_arm() -> Callable[..., str]:
    """Declare one more arm in the shipped zone, on a copy of the model.

    The shipped model has one arm (ADR-0069), and several properties the suite
    asserts are about TWO instances of one type — that a backend or a parameter is
    a per-instance choice, that every arm gets the same controller policy, that
    adding an arm is a data change. A copy of the shipped arm standing on the
    floor, with no program, is the smallest model those properties can be asked
    of. Where it stands is not the question: a test that validates geometry must
    not use it.
    """

    def _add(model: Path, asset_id: str = "picker_2") -> str:
        arms = model / "assets/instances/arms.yaml"
        document = yaml.safe_load(arms.read_text())
        arm = yaml.safe_load(yaml.safe_dump(document["assets"][0]))
        arm["id"] = asset_id
        arm["pose"] = {
            "frame": "cite_world",
            "xyz_m": [2.0, 3.6, 0.0],
            "rpy_rad": [0.0, 0.0, 0.0],
        }
        arm["configuration"].pop("program", None)
        document["assets"].append(arm)
        arms.write_text(yaml.safe_dump(document, sort_keys=False))
        return asset_id

    return _add
