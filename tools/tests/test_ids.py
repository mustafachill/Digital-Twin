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


class TestGazeboPartition:
    """The one name that is not a ROS name, and the reason it is built here.

    `ROS_DOMAIN_ID` does not isolate Gazebo transport: two servers in one
    container on separate domains were measured with two publishers on one
    world's stats topic and two subscribers on one belt's command topic
    (ADR-0042). The partition is what does isolate them, so it is a name like
    every other name in this system rather than a string in a launch file.
    """

    def test_the_plant_side_of_a_zone(self) -> None:
        assert ids.partition("cell_a", ids.PLANT_SIDE) == "cite/cell_a/plant"

    def test_the_counterpart_side_of_a_zone(self) -> None:
        assert ids.partition("cell_a", ids.COUNTERPART_SIDE) == "cite/cell_a/counterpart"

    def test_the_two_sides_of_one_zone_differ(self) -> None:
        # The whole decision reduces to this. Two sides that agreed on a
        # partition would subscribe to each other's belt commands, silently.
        assert ids.partition("cell_a", ids.PLANT_SIDE) != ids.partition(
            "cell_a", ids.COUNTERPART_SIDE
        )

    def test_the_same_side_of_two_zones_differs(self) -> None:
        assert ids.partition("cell_a", ids.PLANT_SIDE) != ids.partition("cell_b", ids.PLANT_SIDE)

    def test_a_side_that_is_not_a_side_is_refused(self) -> None:
        # `virtual` and `physical` are backends, not sides: a Phase 2.A pair has
        # two simulated sides, and a side name that moved with the backend or
        # with TwinMode would change the transport partition at runtime.
        with pytest.raises(ids.InvalidIdentifierError):
            ids.partition("cell_a", "virtual")

    def test_a_partition_is_a_valid_gz_transport_namespace(self) -> None:
        # gz-transport prefixes the partition to every topic name and validates
        # it as a namespace: lowercase, digits, underscores and slashes, no
        # leading slash and no empty segment.
        import re

        for side in ids.SIDES:
            value = ids.partition("cell_a", side)
            assert re.fullmatch(r"[a-z0-9_]+(/[a-z0-9_]+)*", value), value


class TestDomainOffset:
    """The second isolation a side needs, and why it is an offset.

    `GZ_PARTITION` does not isolate the ROS graph — move_group, the controller
    managers and the skill servers speak DDS and have never heard of it — so a
    pair separated only by partition collides on every node name, because both
    sides carry byte-identical names by rule (ADR-0044, clauses 1 and 2).
    """

    def test_the_plant_takes_the_zero_offset(self) -> None:
        # Not arbitrary: zero is what makes an untwinned zone resolve to exactly
        # the domain it uses today, so nothing in Phase 1 moves and a shell from
        # a checkout still lands on the side every existing script addresses.
        assert ids.domain_offset(ids.PLANT_SIDE) == 0

    def test_the_counterpart_takes_the_next_offset(self) -> None:
        assert ids.domain_offset(ids.COUNTERPART_SIDE) == 1

    def test_the_two_sides_of_one_zone_differ(self) -> None:
        # The clause reduces to this. Two sides resolving one domain would put
        # two identically named node sets in one graph.
        assert ids.domain_offset(ids.PLANT_SIDE) != ids.domain_offset(ids.COUNTERPART_SIDE)

    def test_every_side_has_an_offset_and_no_two_share_one(self) -> None:
        offsets = [ids.domain_offset(side) for side in ids.SIDES]
        assert len(set(offsets)) == len(ids.SIDES)

    def test_an_offset_is_not_a_domain(self) -> None:
        # A domain id is a host-scoped resource allocation and cannot be emitted
        # into a committed, hashed tree: derived from the deployment it differs
        # in every clone and breaks the byte-identity check; derived from the
        # model it is identical everywhere and two checkouts discover each other.
        # What this function returns is neither — it is an index into the sides,
        # and the base travels on its own channel.
        assert all(ids.domain_offset(side) < len(ids.SIDES) for side in ids.SIDES)

    def test_a_side_that_is_not_a_side_is_refused(self) -> None:
        # Refused for the same reason the partition refuses it: `virtual` and
        # `physical` are backends, and a Phase 2.A pair has two simulated sides.
        with pytest.raises(ids.InvalidIdentifierError):
            ids.domain_offset("virtual")

    def test_the_two_isolations_are_derived_from_one_side_identity(self) -> None:
        # The property clause 2 rests on: both isolations come from the same
        # tuple in the same module, so a side cannot acquire one and not the
        # other, and a third isolation added later has an obvious home.
        for side in ids.SIDES:
            assert ids.partition("cell_a", side)
            assert ids.domain_offset(side) is not None
