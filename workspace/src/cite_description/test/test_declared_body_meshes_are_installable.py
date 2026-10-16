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

"""Every mesh an authored body declares exists where this package installs from.

ADR-0079 lets an authored body wear a generated visual mesh, reached as
``file://$(find cite_description)/meshes/<path>``. A URI whose file is missing
from ``assets/meshes`` is a body that Gazebo draws as nothing, with only a
warning in a launch log, so the declaration and the installed tree must agree.

It reads the model with PyYAML for the reason its collision sibling gives: the
host tooling virtualenv is not on the path inside the ROS build.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MODEL_TYPES = REPO_ROOT / 'model' / 'assets' / 'types'
ASSET_MESHES = REPO_ROOT / 'assets' / 'meshes'
PREFIXES = (
    'file://$(find cite_description)/meshes/',
    'package://cite_description/meshes/',
)


def _body_meshes():
    """Every (type, field, uri) where an authored body's geometry is a mesh."""
    found = []
    for path in sorted(MODEL_TYPES.rglob('*.yaml')):
        document = yaml.safe_load(path.read_text()) or {}
        description = (document.get('asset_type') or {}).get('description') or {}
        body = description.get('body') or {}
        for field in ('visual', 'collision'):
            geometry = body.get(field) or {}
            if geometry.get('kind') == 'mesh':
                found.append((path.stem, field, geometry['uri']))
    return found


def test_the_model_declares_at_least_one_body_mesh():
    """Guard against the loops below passing having checked nothing."""
    assert _body_meshes(), 'no authored body declares a mesh'


@pytest.mark.parametrize(('type_id', 'field', 'uri'), _body_meshes())
def test_every_body_mesh_installs_from_this_package(type_id, field, uri):
    prefix = next((p for p in PREFIXES if uri.startswith(p)), None)
    assert prefix is not None, f'{type_id}.{field}: {uri} is not under cite_description/meshes'
    relative = uri[len(prefix):]
    assert (ASSET_MESHES / relative).is_file(), f'{type_id}.{field}: {relative} is missing'
