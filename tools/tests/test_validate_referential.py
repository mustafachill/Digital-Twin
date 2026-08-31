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


def test_a_physical_counterpart_on_a_paired_zone_is_refused(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Phase 2.B's encoding stays expressible; GENERATING from it does not.

    This test asserted `rules(...) == set()` until ADR-0048 clause 1 landed, on
    the comment "it is the encoding that must stay expressible". That comment is
    right about the vocabulary and was wrong about the tree: the encoding is
    still `counterpart_backend` and this record proposes no other, but all three
    generator sites that branch on a backend read the plant's, so the model
    validated cleanly and the counterpart was handed a description of a
    simulated cell. Rewritten rather than deleted, for that reason.

    The assertion is set EQUALITY rather than membership, which makes it the
    mutation check as well: the model is otherwise clean, so deleting the new
    rule turns this back into the empty set it used to assert, and no other rule
    can be the one refusing.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    assert rules(minimal_model) == {"divergent-counterpart-backend"}


def test_the_divergence_refusal_says_what_would_have_been_generated(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # The trade ADR-0048 takes is that someone writes a true fact about the
    # facility and is told no, so the message has to be good enough to move
    # them: it names what the generator would have emitted and the record that
    # lifts the refusal.
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    findings = referential.check(load(minimal_model))
    refusal = next(f for f in findings if f.rule == "divergent-counterpart-backend")
    assert refusal.where == "assets.arm_1.hardware.counterpart_backend"
    hint = refusal.hint or ""
    assert "use_sim_time: true" in hint
    assert "ADR-0048" in hint


def test_the_refusal_is_keyed_on_difference_rather_than_on_a_physical_backend(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The mutation check: `real` is not what the rule reads.

    Keying on the literal would leave a third backend to rediscover the gap, so
    the rule is asserted against a counterpart that is not physical at all. The
    plant here is `real` and the counterpart `sim` — a case no other rule
    touches on an untwinned zone, which is also what makes this the mutation
    check for the rule's key.
    """
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "real", "counterpart_backend": "sim"}
        ),
    )
    assert "divergent-counterpart-backend" in rules(minimal_model)


def test_a_counterpart_naming_the_backend_it_already_has_is_allowed(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # The other half of the mutation check, and the property the refusal must not
    # break: writing the value the fallback would have supplied is the same model
    # as omitting it, so it stays clean on a paired zone.
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "sim"}
        ),
    )
    assert rules(minimal_model) == set()


def test_a_divergent_counterpart_on_an_untwinned_zone_is_refused_with_its_own_hint(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # One rule, two hints. On a `single` zone the value states a fact about a
    # side the zone does not have, which is a different thing to tell the author
    # than what the generator would have emitted for a side that exists.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    findings = referential.check(load(minimal_model))
    refusal = next(f for f in findings if f.rule == "divergent-counterpart-backend")
    assert "twin.sides: single" in (refusal.hint or "")


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
