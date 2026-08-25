"""Locate and read the generated artifacts.

The boundary this module marks is worth stating plainly, because it is easy to
erode: **nothing here opens anything under `model/`.** L0 says a running system
never reads the model; it reads what was generated from it. Keeping that true is
what lets the model be validated on a laptop with no ROS, and lets the robot run
with no model present at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory

GENERATED_PACKAGE = "cite_generated"


class ArtifactError(Exception):
    """A generated artifact is missing or unreadable."""


def generated_dir() -> Path:
    try:
        return Path(get_package_share_directory(GENERATED_PACKAGE))
    except Exception as exc:  # noqa: BLE001 - ament raises its own type
        raise ArtifactError(
            f"{GENERATED_PACKAGE} is not on the ament index. It is generated from the "
            "L0 model — run ./scripts/validate-model --write, then ./scripts/build."
        ) from exc


def read_yaml(relative: str) -> dict:
    path = generated_dir() / relative
    if not path.is_file():
        raise ArtifactError(
            f"no generated artifact at {path}. Every artifact here comes from the L0 "
            "model — run ./scripts/validate-model --write, then ./scripts/build. If it "
            "is still missing afterwards, no generator emits it."
        )
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict):
        raise ArtifactError(f"{path}: expected a mapping at the top level")
    return document


def model_hash() -> str:
    """The hash of the model these artifacts were generated from.

    Stamped into every recording (L6): a bag recorded against yesterday's layout
    is not comparable to today's, and without this the two are indistinguishable
    after the fact.
    """
    path = generated_dir() / "MODEL_HASH"
    if not path.is_file():
        raise ArtifactError(
            f"no MODEL_HASH at {path}. Run ./scripts/validate-model --write, then "
            "./scripts/build."
        )
    return path.read_text().strip()


@dataclass(frozen=True)
class StaticTransform:
    parent: str
    child: str
    xyz_m: tuple[float, float, float]
    rpy_rad: tuple[float, float, float]


def static_transforms(zone: str) -> list[StaticTransform]:
    document = read_yaml(f"frames/{zone}_static_tf.yaml")
    entries = document.get("static_transforms") or []
    transforms = [
        StaticTransform(
            parent=entry["parent"],
            child=entry["child"],
            xyz_m=tuple(float(v) for v in entry["xyz_m"]),
            rpy_rad=tuple(float(v) for v in entry["rpy_rad"]),
        )
        for entry in entries
    ]

    # One publisher per transform is a hard rule: two publishers for one transform
    # make TF alternate between them, and the resulting behaviour is intermittent
    # and very hard to attribute. A duplicate here would mean this node is the
    # source of that on its own.
    children = [t.child for t in transforms]
    duplicates = sorted({c for c in children if children.count(c) > 1})
    if duplicates:
        raise ArtifactError(
            f"the generated frame table declares more than one transform for "
            f"{', '.join(duplicates)}. TF would alternate between them."
        )
    return transforms


def topology(zone: str) -> dict:
    return read_yaml(f"topology/{zone}_flow.yaml")["topology"]
