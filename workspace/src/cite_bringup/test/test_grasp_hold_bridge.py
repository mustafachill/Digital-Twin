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

from types import SimpleNamespace

from cite_bringup.grasp_hold_bridge import Custody, GraspHoldBridge

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
