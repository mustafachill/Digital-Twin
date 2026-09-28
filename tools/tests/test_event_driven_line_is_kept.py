"""The event-driven line is parked, not deleted, and this is what keeps it so.

ADR-0066 runs the cell from a fixed program and PARKS the beam-triggered line
beside it: every file stays at its path and stays built and tested, and the git
tag `event-driven-line-v1` marks the commit before the switch. This test is the
in-tree half of that promise. A file of the parked line that disappears fails
here, so removing it is a decision somebody writes down rather than an accident
a refactor makes.

The list is explicit rather than globbed. A glob over `line_*.hpp` would keep
passing if every header matching it were deleted at once, which is the one
failure this file exists to catch.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

ORCHESTRATION = "workspace/src/cite_orchestration"

#: Every tracked file the parked line is made of.
PARKED_LINE = (
    f"{ORCHESTRATION}/src/line_orchestrator.cpp",
    f"{ORCHESTRATION}/src/line_coordinator.cpp",
    f"{ORCHESTRATION}/trees/line_station.xml",
    f"{ORCHESTRATION}/trees/station_cycle.xml",
    f"{ORCHESTRATION}/include/cite_orchestration/line_fault.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/line_maintenance.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/line_nodes.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/line_plan.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/line_tree.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/conveyor_index.hpp",
    f"{ORCHESTRATION}/include/cite_orchestration/skill_nodes.hpp",
    "workspace/src/cite_skills/src/detection_server.cpp",
    "workspace/src/cite_bringup/launch/simulation.launch.py",
    "workspace/src/cite_bringup/cite_bringup/demo.py",
    "scripts/demo",
    "tests/scenarios/continuous_line.py",
)


def _tracked() -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return set(listed.stdout.splitlines())


@pytest.mark.parametrize("path", PARKED_LINE)
def test_a_file_of_the_parked_line_is_still_tracked(path: str) -> None:
    assert path in _tracked(), (
        f"{path} is part of the parked event-driven line (ADR-0066) and is no longer "
        "tracked. Parking means it stays at its path and stays tested; removing it is "
        "a decision that needs its own record, and this list is where it is undone."
    )


def test_the_list_names_no_file_twice() -> None:
    assert len(set(PARKED_LINE)) == len(PARKED_LINE)
