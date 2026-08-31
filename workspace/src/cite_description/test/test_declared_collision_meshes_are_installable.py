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

"""Every declared derived collision mesh exists where this package installs from.

The binding ADR-0028 adds replaces one collision-mesh **root** with another. A
mesh missing from the tree this package installs is therefore not a missing file
in the ordinary sense — it is a link whose collision geometry resolves to nothing
once the root is substituted, and Gazebo answers that with a warning in a launch
log and a body that collides with nothing.

This is the half of that question a test can answer without a simulator: the
model declares the paths, this package installs the tree, and the two must agree.
The other half — that the description actually names them, and that Gazebo
actually loads them — is a scenario's job.

It reads the model with PyYAML rather than importing ``cite_tools``: this test
runs inside the ROS build, where the host tooling virtualenv is not on the path,
and the declaration is plain data.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MODEL_TYPES = REPO_ROOT / "model" / "assets" / "types"
ASSET_MESHES = REPO_ROOT / "assets" / "meshes"


def _derived_sets():
    """Every ``convex_hull`` collision set any robot type declares, with its root."""
    found = []
    for path in sorted(MODEL_TYPES.rglob("*.yaml")):
        document = yaml.safe_load(path.read_text()) or {}
        description = (document.get("asset_type") or {}).get("description") or {}
        collision = description.get("collision")
        if not collision:
            continue
        for mesh_set in collision.get("sets") or []:
            if mesh_set.get("kind") == "convex_hull":
                found.append((path.stem, mesh_set))
    return found


def test_the_model_declares_at_least_one_derived_collision_set():
    """Guard against the test passing vacuously.

    Every assertion below is a loop over the declared sets. If the declaration
    were renamed or dropped, the loops would run zero times and this file would
    report success having checked nothing — the failure mode CLAUDE.md §4 lists
    as a standing prohibition in its own right.
    """
    assert _derived_sets(), "no type declares a convex_hull collision set"


@pytest.mark.parametrize(("type_id", "mesh_set"), _derived_sets())
def test_every_declared_mesh_is_present(type_id, mesh_set):
    root = ASSET_MESHES.parent / mesh_set["root"]
    missing = [name for name in mesh_set["meshes"] if not (root / name).is_file()]
    assert not missing, f"{type_id}/{mesh_set['id']}: not derived yet: {missing}"


@pytest.mark.parametrize(("type_id", "mesh_set"), _derived_sets())
def test_the_set_installs_from_this_package(type_id, mesh_set):
    """The declared root is under what this package's CMakeLists installs.

    Without this, a model could name ``package://cite_description/somewhere_else``
    and every other check here would still pass, while the description resolved
    to a path that is installed by nobody.
    """
    assert mesh_set["package"] == "cite_description"
    assert mesh_set["root"].startswith("meshes/")
