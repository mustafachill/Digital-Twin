"""Referential checks. Each test breaks exactly one thing in a valid model."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools.model.loader import ModelError, load
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


# The four answers `hardware.params` can produce, one test each, asserted by rule
# name (ADR-0053 decision 1, promotion clause 5). `params` is indexed by backend
# id, so each block is checked against the backend THAT BLOCK NAMES rather than
# against the plant's selected one — which is the question a flat map could not
# ask.


def _findings(path: Path) -> list:
    return [f for f in referential.check(load(path)) if f.severity is Severity.ERROR]


def _hardware(document: dict, block: dict) -> None:
    """Rewrite `arm_1`'s whole `hardware:` block in the minimal fixture."""
    document["assets"][1]["hardware"] = block


def test_hardware_param_the_named_backend_does_not_declare(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # Against `real`, which is the backend the BLOCK names — and the message has
    # to say so, or a facility with two backends declaring one name gets an
    # ambiguous error instead of a wrong value.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(
            d,
            {"backend": "real", "params": {"real": {"robot_ip": "203.0.113.7", "robot_prt": "x"}}},
        ),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "unexpected-hardware-param")
    assert finding.where == "assets.arm_1.hardware.params.real.robot_prt"
    assert "'real'" in finding.message


def test_a_params_key_that_is_not_a_declared_backend_id(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # The typo case, and the one thing the index catches that a flat map cannot.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "sim", "params": {"raal": {"robot_ip": "203.0.113.7"}}}),
    )
    finding = next(
        f for f in _findings(minimal_model) if f.rule == "unknown-hardware-param-backend"
    )
    assert finding.where == "assets.arm_1.hardware.params.raal"


def test_a_params_block_on_a_type_declaring_no_backends_at_all(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The skip, which is why the rule above runs in FRONT of `if not backends`.

    `pedestal` declares no `hardware_backends`, so it never reaches the rest of
    this check — and 12 of the real model's 15 assets are in that position. A
    rule written behind that line would bind three assets and be silent on
    twelve.
    """
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][0].__setitem__(
            "hardware", {"backend": "sim", "params": {"real": {"robot_ip": "203.0.113.7"}}}
        ),
    )
    finding = next(
        f for f in _findings(minimal_model) if f.rule == "unknown-hardware-param-backend"
    )
    assert finding.where == "assets.pedestal_1.hardware.params.real"


def test_a_declared_parameter_the_asset_does_not_supply(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # The mirror of `unexpected-hardware-param`, and the half a model author
    # meets: an unsupplied `robot_ip` reaches the far side as
    # `<param name="robot_ip">R</param>` and takes the ros2_control_node down at
    # on_init. This moves it to a laptop.
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "real"}),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "missing-hardware-param")
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


def test_two_missing_parameters_yield_two_findings(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Non-aborting, so an author sees every missing key at once.

    This is the whole reason decision 2a puts the reporting half in the
    validator: the generator's raise is correct and aborts the run, so an author
    would fix one key per invocation.
    """
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["real"].__setitem__(
            "instance_params", ["robot_ip", "report_type"]
        ),
    )
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "real"}),
    )
    missing = [f for f in _findings(minimal_model) if f.rule == "missing-hardware-param"]
    assert [f.where for f in missing] == [
        "assets.arm_1.hardware.params.real.report_type",
        "assets.arm_1.hardware.params.real.robot_ip",
    ]


@pytest.mark.parametrize("empty", ["", "   ", "\t"])
def test_a_declared_parameter_supplied_empty_is_not_supplied(
    minimal_model: Path, edit_yaml: Callable, empty: str
) -> None:
    """R-01. `missing-hardware-param` answers about the VALUE, not the key.

    ADR-0053 decision 2a's reason is that a connection parameter has no default
    that could be right, and `robot_ip: ''` reaches the vendor component as the
    same `R` it answers with `exit(1)`. Testing key membership alone passes a
    declared key holding nothing, at every validation level.
    """
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "real", "params": {"real": {"robot_ip": empty}}}),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "missing-hardware-param")
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


@pytest.mark.parametrize("quote", ['"', "'"])
def test_a_quote_in_a_parameter_value(minimal_model: Path, edit_yaml: Callable, quote: str) -> None:
    """S-02, the laptop half. A value lands in an XML attribute of the generated
    description, and a quote there is how one L0 string became two macro
    arguments. The generator escapes it; this refuses it, because no connection
    parameter is ever right with one in it."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(
            d,
            {
                "backend": "real",
                "params": {"real": {"robot_ip": f"203.0.113.7{quote} report_type={quote}dev"}},
            },
        ),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "hardware-param-contains-quote")
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


def test_a_quote_in_an_unselected_blocks_value_is_refused_too(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Not gated on selection. An unselected block is inert today and is the
    block a one-field flip to hardware makes live, so waiting for the flip would
    move the finding to the moment the arm is switched over."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(
            d, {"backend": "sim", "params": {"real": {"robot_ip": '203.0.113.7" x="y'}}}
        ),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "hardware-param-contains-quote")
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


@pytest.mark.parametrize(
    "value", ["${1+2}.$(env HOSTNAME)", "$(env HOSTNAME)", "${1+2}", "203.0.113.$", "$$"]
)
def test_a_dollar_in_a_parameter_value(
    minimal_model: Path, edit_yaml: Callable, value: str
) -> None:
    """ADR-0053, B-2. xacro evaluates `${...}` and `$(...)` inside an attribute
    after XML has unescaped it: `${1+2}.$(env HOSTNAME)` expanded to
    `R3.<hostname>`. Any `$`, so that xacro's own `$$` escape is not a way in."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "real", "params": {"real": {"robot_ip": value}}}),
    )
    finding = next(
        f for f in _findings(minimal_model) if f.rule == "hardware-param-contains-dollar"
    )
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


def test_a_dollar_in_an_unselected_blocks_value_is_refused_too(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Not gated on selection, for the reason the quote rule is not."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": "sim", "params": {"real": {"robot_ip": "$(env X)"}}}),
    )
    finding = next(
        f for f in _findings(minimal_model) if f.rule == "hardware-param-contains-dollar"
    )
    assert finding.where == "assets.arm_1.hardware.params.real.robot_ip"


def test_a_plain_address_carries_no_dollar_finding(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The control for the two above."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(
            d, {"backend": "real", "params": {"real": {"robot_ip": "203.0.113.7"}}}
        ),
    )
    assert "hardware-param-contains-dollar" not in rules(minimal_model)


def _bind(document: dict, bindings: dict) -> None:
    """Add `bound_args` entries to the minimal fixture's arm type."""
    document["asset_type"]["description"]["bound_args"].update(bindings)


def test_a_parameter_bound_without_the_plugin_binding(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """ADR-0053, and the parameter half of `docs/open-work.md` #65 only.

    Without a binding carrying the plugin string the vendor macro loads its own
    default component, and an instance parameter bound beside it reaches that
    component instead of the one the backend declares. Per type, so no asset
    has to select anything for the finding to appear.
    """
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: _bind(d, {"robot_ip": "instance.hardware.params.robot_ip"}),
    )
    finding = next(f for f in _findings(minimal_model) if f.rule == "unrouted-hardware-params")
    assert finding.where == "types.xarm5.description.bound_args"
    assert "robot_ip" in finding.message


def test_a_parameter_bound_beside_the_plugin_binding_is_clean(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The control: the same parameter binding, with the plugin routed, is not
    refused. Keyed on the binding value, so the argument name carrying it is
    whatever the type says the vendor calls it."""
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: _bind(
            d,
            {
                "robot_ip": "instance.hardware.params.robot_ip",
                "hardware_plugin": "instance.hardware.ros2_control_plugin",
            },
        ),
    )
    assert "unrouted-hardware-params" not in rules(minimal_model)


def test_a_type_binding_no_parameter_is_not_examined(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The fixture binds neither, and stays clean. This rule is not #65's check:
    a type with no parameter binding and no plugin binding is silent here."""
    assert "unrouted-hardware-params" not in rules(minimal_model)


def test_a_block_for_a_declared_backend_nobody_selects_is_clean(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """No finding of any severity. This is what makes flipping an arm to
    hardware a one-field edit, and ADR-0053 decision 1 states its cost: an
    unexercised block is indistinguishable from a deliberate pre-declaration."""
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(
            d, {"backend": "sim", "params": {"real": {"robot_ip": {"env": "CITE_XARM_IP"}}}}
        ),
    )
    assert referential.check(load(minimal_model)) == []


@pytest.mark.parametrize("backend", ["sim", "real"])
def test_a_literal_parameter_of_a_physical_backend_is_an_error(
    minimal_model: Path, edit_yaml: Callable, backend: str
) -> None:
    """R-05 (ADR-0070 item 2): a physical backend's parameter is a reference, never a value.

    Selected or not: an unselected block is committed all the same.
    """
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: _hardware(d, {"backend": backend, "params": {"real": {"robot_ip": "203.0.113.7"}}}),
    )
    findings = [
        f for f in referential.check(load(minimal_model)) if f.rule == "literal-param-on-physical-backend"
    ]
    assert [(f.severity, f.where) for f in findings] == [
        (Severity.ERROR, "assets.arm_1.hardware.params.real.robot_ip")
    ]
    assert "203.0.113.7" not in findings[0].message, "the value is not repeated"


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


def test_the_paired_plant_refusal_reads_the_declaration_and_not_the_backends_name(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """ADR-0054 clause 7. The mutation the id could not catch.

    Asserted by rule id and `where`, never by message substring. The `where`
    MOVED with this change and moving it was the decision: the cause is no
    longer the id the asset selected but the declaration on the type's backend,
    which is the line a reader has to edit to change the answer.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    # The reproduction: the vendor's physical component under the friendly id.
    # Nothing renames the backend, so a rule reading the name sees `sim` and is
    # satisfied - which is exactly what ADR-0054's Context measured, at zero
    # findings.
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["sim"].update(
            {
                "ros2_control_plugin": "uf_robot_hardware/UFRobotSystemHardware",
                "commands_physical_hardware": True,
            }
        ),
    )
    findings = referential.check(load(minimal_model))
    refusal = next(f for f in findings if f.rule == "physical-plant-on-paired-zone")
    assert refusal.where == ("types.xarm5.hardware_backends.sim.commands_physical_hardware")


def test_a_paired_plant_is_permitted_whatever_its_backend_is_called(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The other direction of clause 7, and the one a name gets wrong too.

    A backend named `real` that declares it commands nothing physical is a
    simulation with an unfortunate id, and the rule must not refuse it at any
    severity. Under the old rule this was an ERROR.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["real"].update(
            {
                "ros2_control_plugin": "gz_ros2_control/GazeboSimSystem",
                "commands_physical_hardware": False,
                "instance_params": [],
            }
        ),
    )
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__("hardware", {"backend": "real"}),
    )
    findings = referential.check(load(minimal_model))
    assert not [f for f in findings if f.rule == "physical-plant-on-paired-zone"]


def test_a_type_declaring_no_backends_is_silent_in_both_rules(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The one case `physical-plant-on-paired-zone` hands to nobody.

    That rule skips an asset whose selected backend is not on its type, with a
    comment pointing at `unknown-backend`. That is right when the type declares
    SOME backends. When it declares NONE, `unknown-backend` skips too — on its
    own `if not backends`, and deliberately, since `hardware` is required on
    every asset and every conveyor, sensor and fixture here selects a backend on
    a type that declares none.

    **So this asserts a silence, and it asserts the reason the silence is safe
    in the same breath.** A plugin class string is authored only on a
    `HardwareBackend`, so a type with no backends cannot name a physical
    component at all; the second half below is what fails if that ever stops
    being true, rather than leaving the first half looking like coverage.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"].pop("hardware_backends", None),
    )
    model = load(minimal_model)
    findings = referential.check(model)
    assert not [
        f for f in findings if f.rule in ("physical-plant-on-paired-zone", "unknown-backend")
    ], "both rules are silent here; if one starts speaking, say which and why"
    # And the reason that costs nothing: there is no plugin string to find.
    assert not model.asset_type("xarm5").hardware_backends


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


#: The counterpart's address as the shipped model writes it: a reference to the
#: environment, never a value (ADR-0070 item 2).
_ADDRESS_FROM_THE_ENVIRONMENT = {"real": {"robot_ip": {"env": "CITE_XARM_IP"}}}


def test_a_physical_counterpart_on_a_paired_zone_is_accepted(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Phase 2.B's encoding, now generated as well as expressible (ADR-0070).

    This test asserted `rules(...) == set()` until ADR-0048 clause 1 landed, then
    `== {"divergent-counterpart-backend"}`: every generator site that branched on
    a backend read the plant's, so the counterpart would have been handed a
    description of a simulated cell. ADR-0070 built clause 2 — each side's
    artifacts are generated from that side's own backend — and deleted the rule.
    So the shipped encoding is clean again, and set EQUALITY keeps this the
    mutation check: no rule may refuse it.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware",
            {
                "backend": "sim",
                "counterpart_backend": "real",
                "params": _ADDRESS_FROM_THE_ENVIRONMENT,
            },
        ),
    )
    assert rules(minimal_model) == set()


def test_a_physical_counterpart_must_supply_what_its_backend_declares(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """`missing-hardware-param` reads the counterpart's backend too.

    It read the plant's alone, which was enough while both sides loaded one
    backend. The counterpart now gets a description valued from ITS backend's
    block, so an address it does not supply would stop the generator exactly as
    the plant's would — reported here instead, against the block it belongs in.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    findings = referential.check(load(minimal_model))
    assert {f.rule for f in findings if f.severity is Severity.ERROR} == {"missing-hardware-param"}
    (missing,) = (f for f in findings if f.rule == "missing-hardware-param")
    assert missing.where == "assets.arm_1.hardware.params.real.robot_ip"


def test_a_physical_plant_under_a_simulated_counterpart_is_still_refused(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The cell of the cross product that stays closed, by the rule that closes it.

    This was the mutation check for `divergent-counterpart-backend`'s key. With
    that rule deleted, the reversed pair — physical plant, simulated
    counterpart — is refused by `physical-plant-on-paired-zone` and by nothing
    else, which is what ADR-0070 keeps.
    """
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware",
            {
                "backend": "real",
                "counterpart_backend": "sim",
                "params": _ADDRESS_FROM_THE_ENVIRONMENT,
            },
        ),
    )
    assert rules(minimal_model) == {"physical-plant-on-paired-zone"}


def test_the_divergence_rule_is_gone(minimal_model: Path, edit_yaml: Callable) -> None:
    """ADR-0070 deletes `divergent-counterpart-backend`; no model may produce it."""
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "real"}
        ),
    )
    findings = referential.check(load(minimal_model))
    assert "divergent-counterpart-backend" not in {f.rule for f in findings}


def test_a_counterpart_naming_the_backend_it_already_has_is_allowed(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    # Writing the value the fallback would have supplied is the same model as
    # omitting it, so it stays clean on a paired zone.
    _pair_the_zone(minimal_model, edit_yaml)
    edit_yaml(
        minimal_model / "assets/instances/cell.yaml",
        lambda d: d["assets"][1].__setitem__(
            "hardware", {"backend": "sim", "counterpart_backend": "sim"}
        ),
    )
    assert rules(minimal_model) == set()


def test_a_counterpart_on_an_untwinned_zone_is_inert_rather_than_refused(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """On a `single` zone there is no counterpart for the value to describe.

    The deleted rule refused this with a hint of its own. It is now accepted,
    and nothing it implies is asked of the model: no parameter is required for a
    side that does not exist (`missing-hardware-param` reads the counterpart only
    on a paired zone), and the generator emits no artifact for it —
    `test_a_counterpart_on_an_untwinned_zone_generates_nothing` holds that half.
    """
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


def test_a_taught_pose_in_l0_is_refused_rather_than_ignored(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """ADR-0069 removed L0's `configuration.poses_rad`; a model that still states one fails.

    A program's poses come from its program file (ADR-0067). A key the model kept
    accepting after nothing read it would be a pose an author believes the arm
    uses and the cell never sees, so the schema refuses it outright.
    """

    def taught(d: dict) -> None:
        arm = next(a for a in d["assets"] if a["type"] == "xarm5")
        arm.setdefault("configuration", {"kind": "robot"})["poses_rad"] = {
            "pick": [0.0, 0.1, -0.2, 0.0, 1.0]
        }

    edit_yaml(minimal_model / "assets/instances/cell.yaml", taught)
    with pytest.raises(ModelError, match="poses_rad"):
        load(minimal_model)
