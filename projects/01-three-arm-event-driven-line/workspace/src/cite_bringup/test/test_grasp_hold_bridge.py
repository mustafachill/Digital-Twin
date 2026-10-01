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

"""Which custody transition produces which message (ADR-0065, clause 2).

It brings nothing up: no simulator, no partition, no arm. `Custody` is free of
ROS and of gz-transport on purpose, and `_on_state` is driven unbound against a
fabricated `self` — the same way `tests/scenarios/guards/` drives the shipped
scenario functions — so that the one thing under test is the mapping from a
change of custody onto a topic name.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from ament_index_python.packages import get_package_prefix
from cite_bringup.grasp_hold_bridge import Custody, GraspHoldBridge
import rclpy
import rclpy.node

ATTACH = "/cite/cell_b/picker/grasp/attach"
DETACH = "/cite/cell_b/picker/grasp/detach"


def custody() -> Custody:
    return Custody(ATTACH, DETACH)


def test_taking_hold_publishes_on_the_attach_topic() -> None:
    assert custody().topic_for(True) == ATTACH


def test_letting_go_publishes_on_the_detach_topic() -> None:
    rule = custody()
    rule.topic_for(True)
    assert rule.topic_for(False) == DETACH


def test_the_two_topics_are_not_the_same_name() -> None:
    # A rig that gave one topic twice would pass every mapping test above while
    # attaching and detaching on one message.
    assert ATTACH != DETACH


def test_a_repeated_state_publishes_nothing() -> None:
    # The state topic is latched and republished on every change of custody OR of
    # the running skill, so the same custody arrives more than once per cycle.
    rule = custody()
    assert rule.topic_for(True) == ATTACH
    assert rule.topic_for(True) is None
    assert rule.topic_for(True) is None


def test_the_first_message_acts_whichever_way_it_reads() -> None:
    # THE REGRESSION THIS LOCKS DOWN. Starting from `False` rather than from "not
    # yet known" would make an arm that comes up already holding something — L3's
    # custody latched unknown across a restart — silently fail to attach, with
    # every layer above reporting a grasp.
    assert custody().topic_for(False) == DETACH
    assert custody().topic_for(True) == ATTACH


def test_a_full_cycle_alternates() -> None:
    rule = custody()
    assert [rule.topic_for(h) for h in (True, True, False, False, True)] == [
        ATTACH,
        None,
        DETACH,
        None,
        ATTACH,
    ]


def bridge() -> SimpleNamespace:
    """Build a fabricated `self`: the rule, and a record of what was published."""
    return SimpleNamespace(
        _custody=custody(),
        _attach_topic=ATTACH,
        published=[],
        _publish=lambda topic: None,
    )


def test_on_state_publishes_the_topic_the_rule_chose() -> None:
    fake = bridge()
    fake._publish = fake.published.append
    GraspHoldBridge._on_state(fake, SimpleNamespace(gripper_holding=True))
    GraspHoldBridge._on_state(fake, SimpleNamespace(gripper_holding=True))
    GraspHoldBridge._on_state(fake, SimpleNamespace(gripper_holding=False))
    assert fake.published == [ATTACH, DETACH]


def test_on_state_publishes_nothing_at_all_when_custody_has_not_moved() -> None:
    # Distinct from the test above: that one shows the LIST is right, this one
    # shows `_publish` is not reached at all, so a publisher with no subscriber
    # does not log a warning once per message.
    fake = bridge()

    def refuse(topic: str) -> None:
        raise AssertionError(f"published {topic} for a state that did not change")

    fake._custody.topic_for(True)
    fake._publish = refuse
    GraspHoldBridge._on_state(fake, SimpleNamespace(gripper_holding=True))


def test_the_installed_program_can_reach_gz_transport() -> None:
    """THE REGRESSION THIS LOCKS DOWN, and nothing above could have caught it.

    `./scripts/build` installs this program as a SYMLINK back into
    `src/cite_bringup/cite_bringup/`, Python puts the resolved script directory at
    `sys.path[0]`, and that directory holds `gz.py` — this package's own
    Gazebo-environment door. It shadowed the `gz` namespace package, and the
    bridge died at start-up with `ModuleNotFoundError: No module named
    'gz.transport13'; 'gz' is not a package`, which stopped the whole cell.

    Every other test in this file IMPORTS the module, where `cite_bringup` is
    reached through `PYTHONPATH` and its directory is never `sys.path[0]`. Only
    running the installed program the way the launch runs it can see this, so
    that is what this does. It is started with no parameters, so it refuses —
    and the refusal is raised BELOW the gz import for exactly this reason.
    """
    program = (
        Path(get_package_prefix("cite_bringup")) / "lib" / "cite_bringup"
        / "grasp_hold_bridge.py"
    )
    assert program.exists(), f"{program} is not installed, so this test checks nothing"

    finished = subprocess.run(  # noqa: S603 - a program this package installs
        [sys.executable, str(program)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = finished.stdout + finished.stderr
    assert "ModuleNotFoundError" not in output, (
        "the installed program cannot import what it needs; `sys.path[0]` is its own "
        f"directory and something in it shadows a package:\n{output}"
    )
    assert "GRASP HOLD BRIDGE FAILED" in output, (
        "the program was expected to reach its own refusal, which sits BELOW the gz "
        f"import. It exited {finished.returncode} saying:\n{output}"
    )


def test_the_bridge_shadows_no_attribute_rclpy_owns() -> None:
    """THE REGRESSION THIS LOCKS DOWN, and it survived a whole clean run.

    `GraspHoldBridge` is an `rclpy.node.Node`, and `Node.__init__` sets instance
    attributes of its own. One of them is `_publishers`, a LIST that
    `destroy_node` walks by index. Holding the Gazebo publishers in a dict of the
    same name made the node work perfectly and then die at teardown with
    `KeyError: 0` — after `pick_and_place` had picked and placed, so the cycle
    passed and only the post-shutdown check saw it.

    Compared against a real `Node`'s instance attributes rather than against a
    remembered list: which names rclpy claims is rclpy's to change, and a list
    written here would go stale silently in exactly the way that produced this.
    """
    assigned = set()
    source = ast.parse(Path(inspect.getfile(GraspHoldBridge)).read_text())
    for klass in ast.walk(source):
        if not isinstance(klass, ast.ClassDef) or klass.name != "GraspHoldBridge":
            continue
        for node in ast.walk(klass):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    assigned.add(target.attr)
    assert assigned, "no `self.x = ...` was found, so this test is checking nothing"

    rclpy.init()
    try:
        probe = rclpy.node.Node("shadowing_probe")
        owned = set(vars(probe))
        probe.destroy_node()
    finally:
        rclpy.shutdown()
    assert "_publishers" in owned, (
        "the probe does not carry `_publishers`, so rclpy has changed and this test "
        "is no longer comparing against what it thinks it is"
    )

    collisions = sorted(assigned & owned)
    assert not collisions, (
        f"the bridge assigns {collisions}, which `rclpy.node.Node` already uses for "
        "its own state. The node will work and then fail at teardown, or worse"
    )
