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

"""The grasp-hold bridge is reachable from the simulated launch and nothing else.

ADR-0065's third promotion clause, as a check rather than as a sentence. The
bridge is the only simulation-only NODE this repository starts. Everything else
that is simulation-only is a Gazebo system plugin, which cannot reach the
hardware path because there is no simulator there to load it; a ROS node has no
such property, and what keeps this one off that path today is one launch file.

**Why a source scan and not a review.** A launch file is data. A reviewer reading
`simulation.launch.py` sees the bridge started correctly and cannot see the
hardware launch that also starts it, and the failure that would produce is P2
broken in the worst direction — a physical cell publishing attach messages into a
partition that does not exist, while the code that drives it is no longer the
code that drives the simulated one.

**What it scans and what it does not.** The code trees only: `workspace`,
`tools`, `tests`, `scripts`, `.github` and `model`. `docs/` is deliberately out —
a record naming this node is a record doing its job, and ADR-0065 does exactly
that. This guard is about what STARTS it.
"""

from __future__ import annotations

from pathlib import Path

#: The executable's name, which is also the module's and the node's. One token,
#: because all three move together and a scan for one of them would miss a launch
#: file that named another.
TOKEN = "grasp_hold_bridge"

#: The trees a launch, a plan, a script or a workflow could live in.
TREES = ("workspace", "tools", "tests", "scripts", ".github", "model")

#: Directories that hold build output or caches rather than source.
#:
#: The dot-prefixed rule is not tidiness: this guard's first run reported
#: `tools/.pytest_cache/v/cache/nodeids`, which names the bridge because pytest
#: records the node ids of the tests IT RAN. A cache of a test run is not a place
#: anything is started from, and a guard that fails on one teaches a reader to
#: add entries to `PERMITTED` to make it quiet — which is how a guard stops
#: guarding. `.github` is kept, because a workflow genuinely could start a node.
PRUNED = {"build", "install", "log", "__pycache__"}
KEPT_DOT_DIRECTORIES = {".github"}

#: Every file in those trees that may name the bridge, and why.
#:
#: A file that starts naming it fails this test until it is added here WITH a
#: reason, which is the point: adding a line to this dictionary is a decision a
#: reviewer sees, where adding a `Node(...)` to a second launch file is not.
PERMITTED = {
    "workspace/src/cite_bringup/cite_bringup/grasp_hold_bridge.py": "the node itself",
    "workspace/src/cite_bringup/CMakeLists.txt": "installs it, and registers these tests",
    "workspace/src/cite_bringup/launch/simulation.launch.py": (
        "the one launch that starts it, and the only simulated one"
    ),
    "workspace/src/cite_bringup/test/test_grasp_hold_bridge.py": "its unit tests",
    "workspace/src/cite_bringup/test/test_the_bridge_is_simulation_only.py": "this guard",
    "workspace/src/cite_bringup/README.md": "says what it is, and that it is simulation-only",
}


def repository_root() -> Path:
    root = Path(__file__).resolve().parents[4]
    assert (root / "CLAUDE.md").is_file(), f"{root} is not the repository root"
    return root


def files_naming_the_bridge() -> set[str]:
    root = repository_root()
    found: set[str] = set()
    for tree in TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            parts = set(path.relative_to(root).parts)
            if PRUNED & parts:
                continue
            if any(
                part.startswith(".") and part not in KEPT_DOT_DIRECTORIES for part in parts
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if TOKEN in text:
                found.add(str(path.relative_to(root)))
    return found


def test_only_the_permitted_files_name_the_bridge() -> None:
    found = files_naming_the_bridge()
    unexpected = sorted(found - set(PERMITTED))
    assert not unexpected, (
        f"these files name {TOKEN!r} and are not on this guard's list: {unexpected}. "
        "It is a simulation-only node: a launch, plan or script on the hardware path "
        "that starts it breaks P2 in the direction that matters (ADR-0065). If the new "
        "reference is legitimate, add it to PERMITTED with a reason."
    )


def test_the_guard_is_not_scanning_an_empty_tree() -> None:
    # The whole check passes vacuously if the walk finds nothing, which is what a
    # wrong root, a pruned tree or a renamed executable would produce.
    found = files_naming_the_bridge()
    missing = sorted(set(PERMITTED) - found)
    assert not missing, (
        f"these files are expected to name {TOKEN!r} and do not: {missing}. Either the "
        "node was renamed — in which case TOKEN is stale and this guard is checking "
        "nothing — or it is no longer started at all."
    )


def test_it_is_started_by_exactly_one_launch_file() -> None:
    # Stated separately from the list above, because it is the property ADR-0065
    # asks for and the list is the mechanism. A second launch file added to
    # PERMITTED by mistake still fails here.
    root = repository_root()
    launches = {
        name
        for name in files_naming_the_bridge()
        if name.endswith(".launch.py") or "/launch/" in name
    }
    assert launches == {"workspace/src/cite_bringup/launch/simulation.launch.py"}, (
        f"exactly one launch file may start the bridge; these do: {sorted(launches)}"
    )
    assert (root / "workspace/src/cite_bringup/launch").is_dir()


def test_no_generated_artifact_starts_it() -> None:
    # The bring-up plan is generated from L0 and read by every launch, including
    # any hardware one. It carries the two Gazebo topics the plugin listens on,
    # which are data; it must never carry this node, which would be a process
    # every reader of the plan could start.
    generated = {
        name
        for name in files_naming_the_bridge()
        if name.startswith("workspace/src/cite_generated/")
    }
    assert not generated, (
        f"the generated tree names {TOKEN!r} in {sorted(generated)}. A plan that names "
        "a simulation-only process is a process the hardware path can reach."
    )
