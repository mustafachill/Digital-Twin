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


@pytest.fixture
def edit_yaml() -> Callable[[Path, Callable[[dict], None]], None]:
    """Mutate one YAML document in place, preserving nothing else."""

    def _edit(path: Path, mutate: Callable[[dict], None]) -> None:
        document = yaml.safe_load(path.read_text())
        mutate(document)
        path.write_text(yaml.safe_dump(document, sort_keys=False))

    return _edit
