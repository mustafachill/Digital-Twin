"""The runtime side of the generated artifacts.

The boundary these tests defend is easy to erode and expensive to lose: this
package must never read `model/`. L0 says a running system reads what was
generated, not the model itself — that is what lets the model be validated on a
laptop with no ROS, and lets the robot run with no model present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cite_facility import artifacts


def test_the_generated_package_is_found() -> None:
    assert artifacts.generated_dir().is_dir()


def test_the_model_hash_is_available() -> None:
    digest = artifacts.model_hash()
    assert len(digest) == 64, "expected a SHA-256 hex digest"
    assert digest == digest.strip()


def test_static_transforms_load_and_are_rooted_in_the_world() -> None:
    transforms = artifacts.static_transforms("cell_a")
    assert transforms
    assert {t.parent for t in transforms} == {"cite_world"}


def test_every_arm_mount_is_tied_to_the_facility() -> None:
    """Without this an arm's own model is a disconnected TF tree.

    A skill given a pose in cite_world could then never resolve it into the arm's
    planning frame, and the failure reads as an extrapolation or lookup error
    naming the frames rather than the missing link.
    """
    children = {t.child for t in artifacts.static_transforms("cell_a")}
    for arm in ("arm_1", "arm_2", "arm_3"):
        assert f"{arm}_mount" in children, f"{arm} has no transform from cite_world"


def test_no_transform_is_declared_twice() -> None:
    """Two publishers for one transform make TF alternate between them.

    The resulting behaviour is intermittent and very hard to attribute, so the
    reader rejects a table that would cause it rather than publishing anyway.
    """
    transforms = artifacts.static_transforms("cell_a")
    children = [t.child for t in transforms]
    assert len(children) == len(set(children))


def test_station_frames_are_present() -> None:
    """A station reaches for a named frame; it must exist in the TF table."""
    children = {t.child for t in artifacts.static_transforms("cell_a")}
    for expected in (
        "cell_a__table_pick__surface",
        "cell_a__conveyor_1__infeed",
        "cell_a__conveyor_1__outfeed",
        "cell_a__table_accumulation__surface",
    ):
        assert expected in children, expected


def test_topology_loads_with_its_stations() -> None:
    topology = artifacts.topology("cell_a")
    stations = {s["id"] for s in topology["stations"]}
    assert "station_transfer_1" in stations
    assert topology["zone"] == "cell_a"


def test_a_missing_artifact_says_how_to_produce_one() -> None:
    with pytest.raises(artifacts.ArtifactError, match="validate-model"):
        artifacts.read_yaml("nowhere/absent.yaml")


def test_nothing_here_reads_the_model_directory() -> None:
    """Enforced mechanically, because the rule is easy to break by accident.

    Checked against the code rather than the text: an earlier version of this
    test matched on prose and failed on a docstring that merely *described* the
    rule. A comment saying "never read model/" is the opposite of a violation.
    """
    import ast

    package = Path(artifacts.__file__).parent
    for source in sorted(package.glob("*.py")):
        tree = ast.parse(source.read_text())

        # Docstrings are documentation, not access. Everything else is code.
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                assert "model/" not in node.value, (
                    f"{source.name} builds a path into the model directory: "
                    f"{node.value!r}. A running system reads what was generated "
                    "from the model, never the model itself (L0)."
                )

            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("cite_tools"), (
                    f"{source.name} imports {name}: cite_tools is host-agnostic "
                    "tooling with no ROS dependency (ADR-0013) and is deliberately "
                    "not installed alongside the runtime."
                )
