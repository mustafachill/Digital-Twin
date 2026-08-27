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

"""The runtime side of the generated artifacts.

The boundary these tests defend is easy to erode and expensive to lose: this
package must never read `model/`. L0 says a running system reads what was
generated, not the model itself — that is what lets the model be validated on a
laptop with no ROS, and lets the robot run with no model present.
"""

from __future__ import annotations

from pathlib import Path

from cite_facility import artifacts
import pytest


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


def test_the_planning_scene_loads_with_the_cell_furniture() -> None:
    """Every plan in this cell used to be computed against an empty world.

    Not one collision object existed anywhere in the repository, and since every
    pick and place point lies exactly on a surface, a plan through that surface
    was the normal case rather than an exotic one.
    """
    frame_id, bodies = artifacts.planning_scene("cell_a")
    assert frame_id == "cite_world"
    ids = {body.object_id for body in bodies}
    for expected in ("table_pick", "conveyor_1", "pedestal_1", "table_accumulation"):
        assert expected in ids, expected
    assert len(bodies) == len(ids), "a duplicated id would silently replace an object"


def test_no_collision_object_stands_in_for_an_arm() -> None:
    """Deliberately absent, and asserted so that it stays deliberate.

    An articulated robot frozen at one pose is confidently wrong wherever it
    actually is. Coordinating arms needs the live scene and is L4's problem; a
    box where a robot used to be is worse than no box at all.
    """
    _, bodies = artifacts.planning_scene("cell_a")
    assert not {b.object_id for b in bodies} & {"arm_1", "arm_2", "arm_3"}


def test_every_collision_body_carries_a_frame_and_a_size() -> None:
    _, bodies = artifacts.planning_scene("cell_a")
    for body in bodies:
        assert body.frame_id, body.object_id
        assert body.primitive == "box", f"{body.object_id} is a {body.primitive}"
        assert len(body.dimensions_m) == 3, body.object_id
        assert all(d > 0.0 for d in body.dimensions_m), body.object_id
        assert len(body.xyz_m) == 3 and len(body.rpy_rad) == 3, body.object_id


def test_a_missing_artifact_says_how_to_produce_one() -> None:
    with pytest.raises(artifacts.ArtifactError, match="validate-model"):
        artifacts.read_yaml("nowhere/absent.yaml")


def test_every_installed_program_is_executable() -> None:
    """`install(PROGRAMS ...)` sets the executable bit; a symlink install does not.

    The workspace is built with `colcon --symlink-install`, so what lands in
    `lib/cite_facility/` is a symlink to the file in this tree and inherits its
    mode. A node whose source file is not executable is installed unrunnable, and
    launch reports it as `PermissionError` inside an asyncio traceback rather
    than as a missing executable — with no `ProcessExited` event, so no launch
    gate can catch it either. It cost a whole scenario run to find once.
    """
    # From this test's own path, not from `artifacts.__file__`: the module is
    # imported through the symlink install, so its `__file__` points into
    # site-packages where there is no CMakeLists.txt and no source tree.
    package_root = Path(__file__).resolve().parent.parent
    package = package_root / "cite_facility"
    cmake = (package_root / "CMakeLists.txt").read_text()
    programs = [
        line.strip().replace("${PROJECT_NAME}/", "")
        for line in cmake.split("install(PROGRAMS", 1)[1].split("DESTINATION", 1)[0].splitlines()
        if line.strip().endswith(".py")
    ]
    assert programs, "install(PROGRAMS ...) lists nothing"
    for name in programs:
        path = package / name
        assert path.is_file(), f"{name} is installed as a program but does not exist"
        # The mode bits, not `os.access`: on a Docker bind mount from macOS,
        # `os.access(..., X_OK)` answers True for a file whose mode is 0o644, so
        # a test written that way passes with the bit removed and proves nothing.
        assert path.stat().st_mode & 0o111, (
            f"{name} is installed with install(PROGRAMS) but is not executable in "
            "the source tree, so the symlink install is not executable either"
        )


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
