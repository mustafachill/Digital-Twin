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

"""Every node here still goes through `cite_runtime`, and says so in its manifest.

The shutdown mechanism is tested where it lives, in `cite_runtime`. What this
file covers is the edge between the two packages, which is the half a move can
break silently.

`ament_python_install_package` puts both packages on one `PYTHONPATH`, so
`from cite_runtime import runtime` resolves from any sourced workspace whether or
not a manifest mentions it. That is exactly the property the move exists to
remove: a Phase 2 consumer's dependency would otherwise be invisible to `rosdep`,
to CMake and to review. The declaration is therefore asserted here as well as
being `find_package`d in `CMakeLists.txt` — the import alone would go on working
the day somebody deleted it.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ElementTree

from cite_facility import frame_server, model_info, planning_scene_loader, topology_server
from cite_runtime import runtime
import pytest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Everything in this package that owns a process.
ENTRY_POINTS = [frame_server, model_info, planning_scene_loader, topology_server]


@pytest.mark.parametrize("module", ENTRY_POINTS, ids=lambda m: m.__name__)
def test_each_node_starts_and_stops_through_cite_runtime(module) -> None:
    """Not "imports something called runtime" — the same object, from the package."""
    assert module.runtime is runtime


def test_the_dependency_is_declared_where_rosdep_can_see_it() -> None:
    manifest = ElementTree.parse(PACKAGE_ROOT / "package.xml").getroot()
    declared = {
        element.text.strip()
        for tag in ("depend", "build_depend", "exec_depend")
        for element in manifest.findall(tag)
        if element.text
    }
    assert "cite_runtime" in declared, (
        "cite_facility imports cite_runtime but does not declare it. The import "
        "would keep working from a shared PYTHONPATH; rosdep would not install "
        "it and colcon would not order the two."
    )


def test_the_dependency_is_declared_where_cmake_can_see_it() -> None:
    """The declaration above is a promise; this is what makes the build keep it."""
    cmake = (PACKAGE_ROOT / "CMakeLists.txt").read_text()
    assert "find_package(cite_runtime REQUIRED)" in cmake


def test_the_loader_does_not_restate_the_shutdown_exception_set() -> None:
    """P1: which exceptions mean "shut down" is written down once, in `runtime`.

    The loader's POLICY is its own — an interrupted load stays a failure — and
    that is not what this asserts. What it asserts is that the loader gets the
    SET, and the rule for the one conditional member, from `runtime` rather than
    re-deriving either. Both are subtle and upstream-dependent, and they were
    stated in two places until this move.
    """
    source = (
        PACKAGE_ROOT / "cite_facility" / "planning_scene_loader.py"
    ).read_text()
    assert "runtime.SHUTDOWN_EXCEPTIONS" in source
    assert "runtime.caused_by_shutdown" in source
    assert "ExternalShutdownException" not in source.replace(
        "runtime.SHUTDOWN_EXCEPTIONS", ""
    ), "the loader has gone back to naming the exception set itself"
