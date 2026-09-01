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

"""Every collision mesh the expanded description names resolves to a real file.

This is the check ADR-0028 names in "Four things about the pipeline's own tests"
and the one nothing performed: **compare the declared mesh list against the
collision references in the EXPANDED description.**

WHY EXPANSION IS THE ONLY INSTRUMENT THAT CAN ANSWER IT. The binding replaces one
collision-mesh **root** with another — wholesale, per root, never per file
(``external/patches/03-xarm_ros2-collision-mesh-root.patch``, which substitutes
``${collision_root}/${mesh_filename}`` and nothing else). So every collision
reference the vendor macro composes resolves under the new root, and any
``mesh_filename`` that is not among the thirteen derived hulls resolves to a file
that does not exist. Gazebo answers that with a warning line in a launch log and a
body that collides with **nothing** — an arm that passes through a fixture while
every gate in this repository reports success.

WHAT THE CHECKS BESIDE THIS ONE CANNOT SEE, which is why it exists:

* ``./scripts/hulls`` compares the declared list against the **vendor's** mesh
  tree. It never reads a description, so it is green whatever the description
  composes.
* ``test_declared_collision_meshes_are_installable.py`` compares the declared list
  against what this package **installs**. Same blind spot, from the other side.
* the validators read L0, and L0 does not know which links the vendor macro emits.

Model-validator demonstrated the gap with a one-line L0 edit and **zero findings
from every validator**: set ``model1300: true`` in the arm type's ``bound_args``
and ``link5_collision`` moves to a mesh the derived set does not contain. Three
other vendor arguments reach the same state — ``gripper_version: G2``,
``add_realsense_d435i: true``, ``mesh_suffix: dae``. A rule that listed those four
would be a list of the routes somebody happened to find; expanding the description
answers the question itself, for any route, including ones the vendor adds later.

It therefore lives in a package test rather than in ``tools/``: expansion needs
``xacro``, the vendor package and this package's install tree, none of which the
host-agnostic L0 layer has (ADR-0013). It runs in the container and so in CI.
"""

from pathlib import Path
import subprocess
from urllib.parse import urlparse
from xml.etree import ElementTree

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MODEL_TYPES = REPO_ROOT / 'model' / 'assets' / 'types'
DESCRIPTIONS = sorted(
    (REPO_ROOT / 'workspace' / 'src' / 'cite_generated' / 'description').glob(
        'cell_a_arm_*.urdf.xacro'
    )
)


def _arm_types():
    """Every asset type that declares a collision spec, with its document.

    Read with PyYAML rather than through ``cite_tools`` for the reason the test
    beside this one gives: this runs inside the ROS build, where the host tooling
    virtualenv is not on the path, and the declaration is plain data.
    """
    found = []
    for path in sorted(MODEL_TYPES.rglob('*.yaml')):
        document = yaml.safe_load(path.read_text()) or {}
        asset_type = document.get('asset_type') or {}
        collision = (asset_type.get('description') or {}).get('collision')
        if collision:
            found.append((asset_type['id'], collision))
    return found


def _selected_set(collision):
    """Return the set the model BINDS, which is the only one a description loads."""
    return next(s for s in collision['sets'] if s['id'] == collision['select'])


def _expand(path: Path) -> str:
    """Expand the description the way a planner or a simulator does.

    ``xacro`` rather than a hand-rolled include walk: the vendor macro branches on
    six arguments and composes its own mesh names, and reimplementing that here
    would produce a second, disagreeing answer about what the description says —
    which is the class of defect this file exists to catch.
    """
    completed = subprocess.run(
        ['xacro', str(path)], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, (
        f'xacro failed on {path.name}: {completed.stderr.strip()[-2000:]}'
    )
    return completed.stdout


def _collision_mesh_uris(expanded: str):
    """Every mesh a ``<collision>`` element names, in document order.

    Collision only. The visual half is rooted by the vendor and is not what this
    binding substitutes, so including it would make the assertions below fail for
    a reason that has nothing to do with the derived set.
    """
    robot = ElementTree.fromstring(expanded)
    return [
        mesh.get('filename')
        for link in robot.findall('link')
        for collision in link.findall('collision')
        for mesh in collision.iter('mesh')
    ]


def _to_path(uri: str) -> Path:
    """Resolve a ``file://`` or ``package://`` mesh URI to a filesystem path.

    Both spellings occur by design: the root's scheme is L0 data per backend,
    because the vendor's own ``mesh_path`` branches the same way
    (``description.collision.root_uri_scheme``). A check that understood only the
    simulated spelling would be silent on exactly the half a planner uses.
    """
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        return Path(parsed.path)
    if parsed.scheme == 'package':
        from ament_index_python.packages import get_package_share_directory

        return Path(get_package_share_directory(parsed.netloc)) / parsed.path.lstrip('/')
    raise AssertionError(f'unhandled mesh URI scheme in {uri!r}')


def test_there_is_a_description_to_expand():
    """Guard against every parametrised test below running zero times.

    A file that reports success having checked nothing is the failure mode
    CLAUDE.md §4 lists as a standing prohibition, and the campaign behind ADR-0051
    shipped one: a pre-flight check naming a directory that does not exist,
    reporting nothing in all four of its blocks, noticed by nobody.
    """
    assert DESCRIPTIONS, 'no generated arm description was found to expand'
    assert _arm_types(), 'no asset type declares a collision spec'


@pytest.mark.parametrize('description', DESCRIPTIONS, ids=lambda p: p.stem)
def test_every_collision_mesh_the_description_names_exists(description: Path):
    """The failure M-01 names, caught where it happens rather than where it is declared.

    A missing collision mesh is not an ordinary missing file: the link keeps its
    inertia, keeps its visual and collides with nothing, so the cell comes up, the
    scenarios run, and the arm passes through whatever it was supposed to stop
    against.
    """
    uris = _collision_mesh_uris(_expand(description))
    assert uris, f'{description.name} expanded to no collision meshes at all'
    missing = [uri for uri in uris if not _to_path(uri).is_file()]
    assert not missing, (
        f'{description.name} names collision meshes that do not exist: {missing}. '
        'The collision root is substituted wholesale, so a mesh outside the '
        'declared derived set resolves to nothing and the link collides with '
        'nothing (ADR-0028).'
    )


@pytest.mark.parametrize('description', DESCRIPTIONS, ids=lambda p: p.stem)
def test_no_collision_reference_falls_outside_the_declared_set(description: Path):
    """The declared list is exhaustive, checked against the description that uses it.

    L0's ``meshes:`` list says of itself that it is EXHAUSTIVE and must be. This
    is the assertion that makes that true rather than hoped: expand the
    description, take every collision reference under the bound root, and require
    each one to be a mesh the model declared.

    Skipped-by-construction if the model binds the vendor's own set, because then
    there is no derived root to fall outside of — and the test above still runs,
    which is the one that would catch a broken vendor reference.
    """
    declared_by_root = {}
    for type_id, collision in _arm_types():
        selected = _selected_set(collision)
        if selected['kind'] == 'vendor_meshes':
            continue
        declared_by_root[selected['root']] = (type_id, set(selected['meshes']))
    if not declared_by_root:
        pytest.skip('no type binds a derived collision set; nothing to be outside of')

    outside = []
    for uri in _collision_mesh_uris(_expand(description)):
        for root, (type_id, declared) in declared_by_root.items():
            marker = f'/{root}/'
            if marker in uri:
                name = uri.split(marker, 1)[1]
                if name not in declared:
                    outside.append(f'{uri} (not declared by type {type_id})')
    assert not outside, (
        f'{description.name} composes collision references the model does not '
        f'declare: {outside}. One vendor argument in the arm type bound_args — '
        'model1300, gripper_version, add_realsense_d435i, mesh_suffix — moves a '
        'mesh name, and the substitution is per ROOT, so the new name resolves to '
        'a file nothing derived.'
    )


@pytest.mark.parametrize('description', DESCRIPTIONS, ids=lambda p: p.stem)
def test_no_declared_mesh_is_dead_weight(description: Path):
    """The other direction: a hull nothing loads is a hull nobody would notice breaking.

    Separate from the test above on purpose, because the two failures need
    different answers. A reference outside the declared set is a **missing
    collision body** and is urgent; a declared mesh nothing references is a
    committed asset, a manifest entry and a `./scripts/hulls` comparison that
    guard nothing, and it is the state a vendor bump would leave behind after
    quietly renaming a link.
    """
    referenced = set()
    uris = _collision_mesh_uris(_expand(description))
    for type_id, collision in _arm_types():
        selected = _selected_set(collision)
        if selected['kind'] == 'vendor_meshes':
            continue
        marker = f"/{selected['root']}/"
        declared = set(selected['meshes'])
        for uri in uris:
            if marker in uri:
                referenced.add(uri.split(marker, 1)[1])
        unused = sorted(declared - referenced)
        assert not unused, (
            f'type {type_id} declares hulls that {description.name} never loads: '
            f'{unused}'
        )
