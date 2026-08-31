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

"""The names L5 owns, checked against the names the two sides own.

**This file is ADR-0050 decision 1 clause 3 as a test:** *nothing is republished
across the boundary, and no L5 endpoint carries a name a side already owns.*
Both sides carry byte-identical names by rule (ADR-0044 clause 1), so an L5
publisher on a side-owned name would be a second publisher of a name that
already has one, feeding every consumer on that side a mixture of two cells.

It is a static check over the generated plan and the frozen contracts, so it
runs without bringing anything up — which is the point: the defect it guards
against produces no symptom at run time.
"""

from __future__ import annotations

from cite_bringup.plan import default_plan_path, load, SkillActions
from cite_twin.boundary import (
    asset_namespace,
    BoundaryError,
    operator_endpoint,
    ROOT,
    SKILL_ACTION_TYPES,
    twin_endpoints,
    TWIN_SCOPE,
)
import pytest

PLAN = load(default_plan_path("cell_a"))


def side_owned_names() -> set[str]:
    """Every ROS name the generated plan states for a side.

    Read off the plan rather than listed, so a name the model grows is included
    here without anyone remembering to add it.
    """
    names: set[str] = set()
    for manager in PLAN.controller_managers:
        names.add(manager.node)
        names.add(manager.description_topic)
        for optional in (manager.trajectory_action, manager.gripper_action):
            if optional:
                names.add(optional)
        if manager.skills is not None:
            names.update(
                getattr(manager.skills, field)
                for field in SkillActions.__dataclass_fields__
            )
    for conveyor in PLAN.conveyors:
        names.update({conveyor.state_topic, conveyor.command_topic})
    for sensor in PLAN.sensors:
        names.update({sensor.detection_topic, sensor.level_topic})
    if PLAN.detection is not None:
        names.add(PLAN.detection.detect_action)
    return names


def l5_owned_names() -> set[str]:
    """Every name L5 advertises: its own products, plus one endpoint per skill."""
    names = set(twin_endpoints())
    for manager in PLAN.controller_managers:
        if manager.skills is None:
            continue
        for field in SKILL_ACTION_TYPES:
            names.add(operator_endpoint(getattr(manager.skills, field)))
    return names


class TestNothingIsRepublishedOntoANameASideOwns:
    def test_the_two_name_sets_are_disjoint(self) -> None:
        overlap = side_owned_names() & l5_owned_names()
        assert overlap == set(), (
            f"L5 would advertise {sorted(overlap)}, which the sides already own. "
            "Both sides carry identical names, so this is a second publisher of a "
            "name that already has one on whichever side it lands (ADR-0050, "
            "decision 1 clause 3)."
        )

    def test_every_l5_name_is_under_the_reserved_scope(self) -> None:
        for name in sorted(l5_owned_names()):
            assert name.startswith(f"{TWIN_SCOPE}/"), name

    def test_no_side_owns_anything_under_the_reserved_scope(self) -> None:
        """`/cite/twin/...` is reserved for L5 (`naming-and-namespaces.md`)."""
        for name in sorted(side_owned_names()):
            assert not name.startswith(f"{TWIN_SCOPE}/"), name

    def test_the_plan_actually_carried_some_names(self) -> None:
        """A guard on the guard: an empty set is disjoint from everything."""
        assert len(side_owned_names()) > 10
        assert len(l5_owned_names()) > 10


class TestTheOperatorEndpointIsDerivedRatherThanComposed:
    def test_the_reserved_scope_is_the_only_thing_it_adds(self) -> None:
        assert (
            operator_endpoint("/cite/cell_a/arm_1/move_to")
            == "/cite/twin/cell_a/arm_1/move_to"
        )

    def test_a_name_this_system_did_not_form_is_refused(self) -> None:
        with pytest.raises(BoundaryError):
            operator_endpoint("/somebody_elses/topic")

    def test_the_root_is_not_decided_here(self) -> None:
        """Read the root back off a name rather than composing one.

        A generated name that stopped starting with `/cite` then fails here
        rather than producing a plausible endpoint under a scope nobody
        reserved.
        """
        assert TWIN_SCOPE.startswith(f"{ROOT}/")


class TestTheAssetNamespaceIsReadOffTheModel:
    def test_it_is_a_prefix_of_every_other_name_the_plan_states_for_that_asset(
        self,
    ) -> None:
        """What makes taking the controller manager's parent a derivation.

        The zone and the asset are stated once, in L0, and reach here inside
        every generated name. If the namespace taken here were not a prefix of
        the asset's own action and topic names, it would be a guess.
        """
        for manager in PLAN.controller_managers:
            namespace = asset_namespace(manager)
            owned = [manager.description_topic]
            if manager.skills is not None:
                owned += [
                    getattr(manager.skills, field) for field in SKILL_ACTION_TYPES
                ]
            for name in owned:
                assert name.startswith(f"{namespace}/"), (namespace, name)

    def test_it_names_the_asset(self) -> None:
        for manager in PLAN.controller_managers:
            assert asset_namespace(manager).endswith(f"/{manager.asset}")


def test_every_skill_the_plan_declares_is_routable() -> None:
    """A skill L5 does not know about is one an operator cannot reach, silently.

    `cite_twin.boundary` refuses to import when the two lists differ; this
    states the same thing where a reader looking for the guarantee will find it.
    """
    assert set(SKILL_ACTION_TYPES) == set(SkillActions.__dataclass_fields__)
