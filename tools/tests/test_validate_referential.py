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


def test_a_workpiece_name_with_no_type_behind_it(real_model: Path, edit_yaml: Callable) -> None:
    # The name is not decoration: it reaches the generated world as the belt's
    # <carry> list and the beam's <watch> list, so a misspelling gives a belt
    # that carries nothing and a sensor that sees nothing, with no error
    # anywhere. It is also the datum two validation rules size themselves from.
    edit_yaml(
        real_model / "facility/facility.yaml",
        lambda d: d["facility"].__setitem__("workpiece_models", ["workpeice"]),
    )
    assert "unknown-type" in rules(real_model)


def test_a_workpiece_naming_a_fixture(real_model: Path, edit_yaml: Callable) -> None:
    # Listing a fixture here would tell the belt to carry the table.
    edit_yaml(
        real_model / "facility/facility.yaml",
        lambda d: d["facility"].__setitem__("workpiece_models", ["work_table_600"]),
    )
    assert "workpiece-is-not-a-workpiece" in rules(real_model)


def test_the_real_model_resolves_its_workpieces(real_model: Path) -> None:
    assert rules(real_model) == set()


# --- A paired zone may not put a physical machine on its plant side ----------
#
# ADR-0041's Decision 3 closes one cell of the cross product deliberately. It is
# a cross-DOCUMENT rule — `twin.sides` is on the zone and `hardware.backend` is
# on the instance — which is why no schema can express it and it lives here.


def _pair_the_zone(model: Path, edit_yaml: Callable) -> None:
    edit_yaml(
        model / "facility/zones.yaml",
        lambda d: d["zones"][0].__setitem__("twin", {"sides": "pair"}),
    )


def test_a_paired_zone_alone_is_valid(minimal_model: Path, edit_yaml: Callable) -> None:
    # Pairing a zone whose assets are all simulated is the Phase 2.A shape and
    # must pass on its own: the refusal below has to fire on the backend, not on
    # the pairing.
    _pair_the_zone(minimal_model, edit_yaml)
    assert rules(minimal_model) == set()


def test_a_physical_plant_on_a_paired_zone_is_refused(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("hardware", {"backend": "real"}),
    )
    assert "physical-plant-on-paired-zone" in rules(minimal_model)


def test_the_refusal_says_which_encoding_to_use_instead(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # A message that only says "refused" leaves the author with a configuration
    # they cannot express, when in fact the same two machines are expressible —
    # the refusal exists to move them to the other encoding, not to forbid them.
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("hardware", {"backend": "real"}),
    )
    findings = referential.check(load(minimal_model))
    refusal = next(f for f in findings if f.rule == "physical-plant-on-paired-zone")
    assert "counterpart_backend: real" in (refusal.hint or "")


def test_a_physical_plant_on_an_untwinned_zone_is_still_allowed(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # The refusal is a property of PAIRING, not a second hardware gate. An
    # untwinned zone with a real backend is the single-sided case, guarded at
    # bring-up by the opt-in, which is where that gate belongs.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("hardware", {"backend": "real"}),
    )
    assert "physical-plant-on-paired-zone" not in rules(minimal_model)


def test_a_physical_counterpart_on_a_paired_zone_is_allowed(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # This is Phase 2.B as charter section 8 scopes it — one physical arm, the
    # rest simulated — and it is the encoding that must stay expressible.
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    assert rules(minimal_model) == set()


def test_a_counterpart_backend_the_type_does_not_declare_is_refused(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # Same class of error as an unknown `backend`, and it would otherwise fail at
    # bring-up on the far side rather than here.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "hydraulic"}
        ),
    )
    assert "unknown-backend" in rules(minimal_model)
