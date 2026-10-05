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

"""Each side's EXPANDED description loads the plugin L0 declares for that side.

This is open-work #65's strong form: "nothing verifies that the plugin L0
declares is the plugin the description loads". The hardware gate decides on
`commands_physical_hardware`, which L0 states one line from the plugin string;
the plugin reaches the description through a binding and then through the vendor
macro, which has its own default (the physical component) and its own switches
(it omits the gripper's block for that component). Only expansion sees the
result, so this expands every description a side loads, the way a controller
manager or a simulator does, and asks every `<ros2_control>` block which plugin
it loads and which joints it claims.

Per SIDE (ADR-0048 clause 2, ADR-0070): the plant's description and, where the
counterpart's backend differs, the counterpart's own one. The plan says which
file each side loads and which xacro arguments it reads from the environment;
those are handed a documentation address (RFC 5737) here, never a real one.

It lives in a package test for the reason the collision test beside it gives:
expansion needs `xacro` and the vendor package, which only the container has.
L0 is read with PyYAML, because the host tooling is not on the path here.
"""

from pathlib import Path
import subprocess
from xml.etree import ElementTree

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MODEL = REPO_ROOT / 'model'
GENERATED = REPO_ROOT / 'workspace' / 'src' / 'cite_generated'
PACKAGE_URI = 'package://cite_generated/'

#: TEST-NET-3 (RFC 5737): reserved for documentation, routes nowhere.
TEST_ADDRESS = '203.0.113.7'


def _documents(directory: Path, key: str) -> dict:
    """Every entry under ``key`` in every YAML document below ``directory``, by id."""
    found = {}
    for path in sorted(directory.rglob('*.yaml')):
        for document in yaml.safe_load_all(path.read_text()):
            if not isinstance(document, dict) or key not in document:
                continue
            entries = document[key]
            for entry in entries if isinstance(entries, list) else [entries]:
                found[entry['id']] = entry
    return found


def _l0():
    return (
        _documents(MODEL / 'assets' / 'types', 'asset_type'),
        _documents(MODEL / 'assets' / 'instances', 'assets'),
    )


def _backend_of(instance: dict, side: str) -> str:
    """Return the backend ``instance`` loads on ``side``, with ADR-0041's fallback applied."""
    hardware = instance['hardware']
    if side == 'counterpart':
        return hardware.get('counterpart_backend') or hardware['backend']
    return hardware['backend']


def _sides():
    """(plan, manager, side, description file, xacro arguments) for every description loaded."""
    cases = []
    for plan_path in sorted((GENERATED / 'bringup').glob('*_plan.yaml')):
        plan = yaml.safe_load(plan_path.read_text())['plan']
        side_names = [side['name'] for side in plan['sides']]
        for manager in plan['controller_managers']:
            for side in side_names:
                if side == 'counterpart' and 'counterpart_description' in manager:
                    uri = manager['counterpart_description']
                    arguments = manager.get('counterpart_description_args', {})
                else:
                    uri = manager['description']
                    arguments = manager.get('description_args', {})
                path = GENERATED / uri[len(PACKAGE_URI):]
                cases.append((plan['zone'], manager, side, path, arguments))
    return cases


SIDES = _sides()


def _expand(path: Path, arguments: dict) -> ElementTree.Element:
    """Expand with every argument the plan says the description reads, and no other."""
    mappings = [f'{name}:={TEST_ADDRESS}' for name in sorted(arguments)]
    completed = subprocess.run(
        ['xacro', str(path), *mappings], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, (
        f'xacro failed on {path.name}: {completed.stderr.strip()[-2000:]}'
    )
    return ElementTree.fromstring(completed.stdout)


def _blocks(robot: ElementTree.Element):
    """Every `<ros2_control>` block as (plugin, claimed joint names)."""
    return [
        (
            block.find('hardware').findtext('plugin'),
            {joint.get('name') for joint in block.findall('joint')},
        )
        for block in robot.findall('ros2_control')
    ]


def test_every_side_has_a_description_to_expand():
    """Guard against the parametrised tests below running over nothing."""
    assert SIDES, 'no generated plan names a description'
    assert any(side == 'counterpart' for _, _, side, _, _ in SIDES), (
        'cell_b is paired (ADR-0059); a plan with no counterpart side means this '
        'test stopped reading the plan it was written for'
    )


@pytest.mark.parametrize(
    'zone, manager, side, path, arguments',
    SIDES,
    ids=[f'{zone}-{manager["asset"]}-{side}' for zone, manager, side, _, _ in SIDES],
)
def test_each_block_loads_the_plugin_l0_declares_for_this_side(
    zone, manager, side, path, arguments
):
    """Every block's plugin is its owner's declared plugin on this side, and nothing else.

    A block claiming the track's joint belongs to the track; every other block in
    an arm's description belongs to the arm (its own joints, and the gripper's,
    which the vendor emits under the arm's plugin). Then three things must hold:

    * every block loads exactly the plugin its owner's backend declares here;
    * the track's joint is claimed exactly when its backend declares a plugin —
      the physical track's does not (ADR-0070 item 3);
    * the gripper's drive joint is claimed exactly when the arm's backend says
      its plugin exports the end effector's joints (ADR-0070 item 4).
    """
    types, instances = _l0()
    arm = instances[manager['asset']]
    arm_backend = types[arm['type']]['hardware_backends'][_backend_of(arm, side)]
    blocks = _blocks(_expand(path, arguments))

    track = manager.get('track')
    track_plugin = None
    if track is not None:
        track_instance = instances[track['asset']]
        track_backend = types[track_instance['type']]['hardware_backends'][
            _backend_of(track_instance, side)
        ]
        track_plugin = track_backend['ros2_control_plugin']
        claiming = [plugin for plugin, joints in blocks if track['joint'] in joints]
        assert claiming == ([] if track_plugin is None else [track_plugin]), (
            f'{path.name} ({side}): the track joint {track["joint"]} is claimed by '
            f'{claiming}, and L0 declares {track_plugin!r} for it on this side'
        )

    arm_blocks = [
        (plugin, joints)
        for plugin, joints in blocks
        if track is None or track['joint'] not in joints
    ]
    assert arm_blocks, f'{path.name} ({side}): no <ros2_control> block for the arm at all'
    loaded = {plugin for plugin, _ in arm_blocks}
    assert loaded == {arm_backend['ros2_control_plugin']}, (
        f'{path.name} ({side}) loads {sorted(loaded)} for {manager["asset"]}; L0 declares '
        f'{arm_backend["ros2_control_plugin"]!r} for backend {_backend_of(arm, side)!r}. '
        'The vendor macro applies its own default when the plugin is not bound '
        '(open-work #65).'
    )

    drive = f'{manager["asset"]}_drive_joint'
    claimed = {joint for _, joints in arm_blocks for joint in joints}
    exports = arm_backend.get('exports_end_effector_joints', True)
    fitted = bool((arm.get('end_effector') or {}).get('vendor_integrated', False))
    assert (drive in claimed) == (fitted and exports), (
        f'{path.name} ({side}): the gripper drive joint is '
        f'{"claimed" if drive in claimed else "not claimed"}, and L0 says this backend '
        f'{"exports" if exports else "does not export"} end-effector joints'
    )


@pytest.mark.parametrize(
    'zone, manager, side, path, arguments',
    [case for case in SIDES if case[4]],
    ids=[f'{c[0]}-{c[1]["asset"]}-{c[2]}' for c in SIDES if c[4]],
)
def test_a_description_reading_the_environment_fails_without_it(
    zone, manager, side, path, arguments
):
    """No argument, no description: an unresolved address never becomes an empty one.

    The vendor component answers an empty `robot_ip` with `exit(1)` inside a
    loaded plugin (ADR-0053). Expanding without the argument must fail in xacro,
    on the developer's machine, rather than produce a description that would.
    """
    completed = subprocess.run(['xacro', str(path)], capture_output=True, text=True, check=False)
    assert completed.returncode != 0
    assert all(name in completed.stderr for name in arguments), completed.stderr[-2000:]
