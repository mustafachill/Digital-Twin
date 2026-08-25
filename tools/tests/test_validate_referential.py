"""Referential checks. Each test breaks exactly one thing in a valid model."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cite_tools.model.loader import load
from cite_tools.validate import Severity, referential


def rules(path: Path) -> set[str]:
    findings = referential.check(load(path))
    return {f.rule for f in findings if f.severity is Severity.ERROR}


def test_the_fixture_is_clean(minimal_model: Path) -> None:
    assert rules(minimal_model) == set()


def test_dangling_type_reference(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("type", "xarm7"),
    )
    assert "unknown-type" in rules(minimal_model)


def test_duplicate_asset_id(minimal_model: Path, edit_yaml: Callable) -> None:
    # A duplicate id is a namespace collision: two things publishing the same
    # topic, and neither of them working.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("id", d["assets"][0]["id"]),
    )
    assert "duplicate-id" in rules(minimal_model)


def test_unknown_zone(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][0].__setitem__("zone", "cell_b"),
    )
    assert "unknown-zone" in rules(minimal_model)


def test_pose_references_a_frame_the_type_does_not_have(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1]["pose"].__setitem__("frame", "pedestal_1/lid"),
    )
    assert "unresolved-frame" in rules(minimal_model)


def test_pose_references_an_asset_that_does_not_exist(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1]["pose"].__setitem__("frame", "pedestal_9/top"),
    )
    assert "unresolved-frame" in rules(minimal_model)


def test_placement_cycle(minimal_model: Path, edit_yaml: Callable) -> None:
    # Without this check the resolver recurses until the stack runs out, and the
    # traceback names the recursion rather than the two assets involved.
    def mutate(d: dict) -> None:
        d["assets"][0]["pose"]["frame"] = "arm_1/base"
        d["assets"][1]["pose"]["frame"] = "pedestal_1/top"

    edit_yaml(minimal_model / "assets/instances/cell.yaml", mutate)
    assert "pose-cycle" in rules(minimal_model)


def test_unknown_hardware_backend(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("hardware", {"backend": "mock"}),
    )
    assert "unknown-backend" in rules(minimal_model)


def test_hardware_param_the_backend_does_not_declare(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "real", "params": {"robot_prt": "192.168.1.1"}}
        ),
    )
    assert "unexpected-hardware-param" in rules(minimal_model)


def test_station_references_a_missing_asset(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "topology/line.yaml",
        lambda d: d["stations"][0].__setitem__("actor", "arm_9"),
    )
    assert "unknown-asset" in rules(minimal_model)


def test_transfer_station_without_an_actor(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "topology/line.yaml",
        lambda d: d["stations"][0].pop("actor"),
    )
    assert "station-without-actor" in rules(minimal_model)


def test_flow_edge_to_a_missing_station(minimal_model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        minimal_model / "topology/flow.yaml",
        lambda d: d["flow"]["edges"][0].__setitem__("to", "station_nowhere"),
    )
    assert "unknown-station" in rules(minimal_model)


def test_station_in_the_zone_that_no_edge_touches(minimal_model: Path, edit_yaml: Callable) -> None:
    # A station nothing flows into or out of can never receive work. v1 had
    # exactly this shape and nothing noticed.
    edit_yaml(
        minimal_model / "topology/line.yaml",
        lambda d: d["stations"].append(
            {"id": "station_orphan", "zone": "cell_a", "type": "sink_station", "capacity": 1}
        ),
    )
    assert "unreachable-station" in rules(minimal_model)
