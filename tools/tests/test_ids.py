"""Naming rules. P2 is made of these names, so they are tested first."""

from __future__ import annotations

import pytest

from cite_tools.model import ids


class TestDocumentedExamples:
    """Every name the design documents write out by hand must come back exactly.

    These are not illustrative. `naming-and-namespaces.md` and
    `operations/bring-up.md` print these strings, and a generator that emitted
    anything else would make those documents wrong.
    """

    def test_joint_states_topic(self) -> None:
        assert ids.interface("cell_a", "arm_1", "joint_states") == (
            "/cite/cell_a/arm_1/joint_states"
        )

    def test_follow_joint_trajectory_action(self) -> None:
        assert (
            ids.controller_action(
                "cell_a", "arm_1", "joint_trajectory_controller", "follow_joint_trajectory"
            )
            == "/cite/cell_a/arm_1/joint_trajectory_controller/follow_joint_trajectory"
        )

    def test_conveyor_state_topic(self) -> None:
        assert ids.interface("cell_a", "conveyor_1", "state") == "/cite/cell_a/conveyor_1/state"

    def test_sensor_detection_topic(self) -> None:
        assert ids.interface("cell_a", "sensor_belt_1_end", "detection") == (
            "/cite/cell_a/sensor_belt_1_end/detection"
        )

    def test_base_link_frame(self) -> None:
        assert ids.frame("cell_a", "arm_1", "link_base") == "cell_a__arm_1__link_base"

    def test_joint_names(self) -> None:
        assert [ids.joint("arm_1", f"joint{n}") for n in range(1, 6)] == [
            "arm_1_joint1",
            "arm_1_joint2",
            "arm_1_joint3",
            "arm_1_joint4",
            "arm_1_joint5",
        ]

    def test_controller_name(self) -> None:
        assert ids.controller("arm_1", "joint_trajectory_controller") == (
            "arm_1_joint_trajectory_controller"
        )

    def test_reserved_scopes(self) -> None:
        assert ids.scope("twin", "mode") == "/cite/twin/mode"
        assert ids.scope("twin", "divergence") == "/cite/twin/divergence"
        assert ids.scope("line", "state") == "/cite/line/state"

    def test_world_frame_is_unprefixed(self) -> None:
        assert ids.WORLD_FRAME == "cite_world"


class TestRejection:
    @pytest.mark.parametrize(
        "bad",
        ["Cell_A", "cell-a", "1_cell", "cell a", "", "cellA", "cell.a"],
    )
    def test_illegal_identifiers_are_rejected(self, bad: str) -> None:
        with pytest.raises(ids.InvalidIdentifierError):
            ids.namespace(bad, "arm_1")

    @pytest.mark.parametrize("reserved", ["facility", "twin", "line"])
    def test_reserved_scope_cannot_be_a_zone(self, reserved: str) -> None:
        with pytest.raises(ids.InvalidIdentifierError):
            ids.namespace(reserved, "arm_1")

    def test_unknown_scope_is_rejected(self) -> None:
        with pytest.raises(ids.InvalidIdentifierError):
            ids.scope("cell_a", "state")

    def test_frame_has_no_leading_slash(self) -> None:
        # A slash-prefixed TF frame id is accepted by tf2 and then never matches
        # anything, which is among the least obvious failures in ROS 2.
        assert not ids.frame("cell_a", "arm_1", "link_base").startswith("/")


class TestSeparation:
    def test_two_instances_of_one_type_never_collide(self) -> None:
        a = {ids.joint("arm_1", f"joint{n}") for n in range(1, 6)}
        b = {ids.joint("arm_2", f"joint{n}") for n in range(1, 6)}
        assert not a & b

    def test_double_underscore_keeps_single_underscore_links_unambiguous(self) -> None:
        # 'link_base' contains an underscore; splitting on the double underscore
        # must still recover exactly three parts.
        assert ids.frame("cell_a", "arm_1", "link_base").split(ids.FRAME_SEP) == [
            "cell_a",
            "arm_1",
            "link_base",
        ]
