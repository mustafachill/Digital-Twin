"""Referential integrity: does everything the model points at actually exist?

These are the checks a JSON Schema structurally cannot make. A schema can say
``type`` is a lower_snake_case string; only this can say that the string names a
type in the component library.

Each failure here corresponds to a real runtime symptom, and the messages say
which — a duplicate asset id is a namespace collision where two robots publish
the same topic, and finding that at validation time instead of at bring-up time
is the entire point of having this level.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from cite_tools.model import blockly
from cite_tools.model.ids import WORLD_FRAME
from cite_tools.model.loader import FacilityModel
from cite_tools.model.resolve import program_steps
from cite_tools.model.schema import (
    PLUGIN_BINDING,
    EnvReference,
    FlowEdge,
    xacro_would_evaluate,
)
from cite_tools.validate import Finding, error

#: Which configuration kind each category expects. `None` means the category
#: carries no configuration at all, so any configuration on it is a mistake.
_CATEGORY_CONFIG_KIND: dict[str, str | None] = {
    "robot": "robot",
    "conveyor": "conveyor",
    "sensor": "sensor",
    "fixture": None,
    "end_effector": None,
    "workpiece": None,
    "linear_axis": None,
}


def check(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    findings += _duplicate_ids(model)
    findings += _asset_types_exist(model)
    findings += _materials_exist(model)
    findings += _zones_exist(model)
    findings += _pose_frames_resolve(model)
    findings += _no_pose_cycles(model)
    findings += _hardware_backends_exist(model)
    findings += _instance_params_reach_a_bound_plugin(model)
    findings += _paired_zone_has_no_physical_plant(model)
    findings += _counterpart_backend_needs_a_paired_zone(model)
    findings += _plugin_less_backends_are_not_bound(model)
    findings += _configuration_matches_category(model)
    findings += _an_arm_rides_its_track_on_one_backend(model)
    findings += _programs_fit_the_arm(model)
    findings += _stations_reference_real_things(model)
    findings += _workpiece_models_exist(model)
    findings += _flow_is_consistent(model)
    return findings


def _duplicate_ids(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    # `identifiers` rather than `ids`, which is the module this file imports;
    # the loop variable used to shadow it harmlessly and stopped being harmless
    # the moment anything below wanted the module.
    for label, identifiers in (
        ("asset", [a.id for a in model.assets]),
        ("asset type", [t.id for t in model.types]),
        ("zone", [z.id for z in model.zones]),
        ("station", [s.id for s in model.stations]),
    ):
        for value, count in sorted(Counter(identifiers).items()):
            if count > 1:
                findings.append(
                    error(
                        "duplicate-id",
                        f"{label}.{value}",
                        f"{count} {label}s share the id {value!r}",
                        "Ids must be unique across the whole model: every topic, frame and "
                        "controller name derives from them, so a duplicate means two things "
                        "publishing to the same name and neither of them working.",
                    )
                )
    return findings


def _asset_types_exist(model: FacilityModel) -> list[Finding]:
    known = {t.id for t in model.types}
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.type not in known:
            findings.append(
                error(
                    "unknown-type",
                    f"assets.{asset.id}.type",
                    f"no component library entry named {asset.type!r}",
                    f"Known types: {', '.join(sorted(known)) or '(none)'}.",
                )
            )
        if asset.end_effector and asset.end_effector.type not in known:
            findings.append(
                error(
                    "unknown-type",
                    f"assets.{asset.id}.end_effector.type",
                    f"no component library entry named {asset.end_effector.type!r}",
                )
            )
    return findings


def _materials_exist(model: FacilityModel) -> list[Finding]:
    """Every appearance a body names must be in the facility's material library.

    THE FAILURE THIS REPORTS IS THE ONE THAT WENT UNREPORTED FOR THE WHOLE OF
    PHASE 1. `Body.material` carried a name on every authored body in this model
    — `table_top`, `conveyor_frame`, `pedestal_steel`, `sensor_housing`,
    `workpiece_stock` — and there was no library for them to resolve against and
    no rule asking. The generator dropped the field, every `<visual>` came out a
    bare `<geometry>`, and the project owner opened the Gazebo window to a cell
    in which the box, the table and everything else were black. Nothing anywhere
    printed a line.

    ERROR AND NOT WARNING, AND NO DEFAULT. A name that resolves to nothing is
    exactly the state above; falling back to a stock grey would make the cell
    look deliberate while the model said something else, which is the
    silently-wrong-value class this whole layer exists to eliminate. A body may
    legitimately have no appearance at all — `material` is optional and `None`
    emits nothing — so the model can still say "I have not decided"; what it
    cannot do is say a name nobody declared.

    The unused direction is deliberately NOT checked. A library entry no body
    wears costs nothing, is the normal state while a cell is being built up, and
    refusing it would make adding a colour and using it two commits that must
    land together.
    """
    known = {material.id for material in model.materials}
    findings: list[Finding] = []
    for asset_type in model.types:
        body = asset_type.description.body
        if body is None or body.material is None:
            continue
        if body.material not in known:
            findings.append(
                error(
                    "unknown-material",
                    f"types.{asset_type.id}.description.body.material",
                    f"no material named {body.material!r} in the facility's library",
                    "Declare it in the `cite/materials/v1` document, or remove the key. "
                    f"Known materials: {', '.join(sorted(known)) or '(none)'}. A name "
                    "that resolves to nothing reaches the generator as no appearance at "
                    "all, and a body with no appearance renders black.",
                )
            )
    return findings


def _zones_exist(model: FacilityModel) -> list[Finding]:
    known = {z.id for z in model.zones}
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.zone not in known:
            findings.append(
                error(
                    "unknown-zone",
                    f"assets.{asset.id}.zone",
                    f"no zone named {asset.zone!r}",
                    f"Known zones: {', '.join(sorted(known)) or '(none)'}.",
                )
            )
    for station in model.stations:
        if station.zone not in known:
            findings.append(
                error(
                    "unknown-zone", f"stations.{station.id}.zone", f"no zone named {station.zone!r}"
                )
            )
    for flow in model.flows:
        if flow.zone not in known:
            findings.append(
                error("unknown-zone", f"flow.{flow.id}.zone", f"no zone named {flow.zone!r}")
            )
    return findings


def _frames_of(model: FacilityModel, asset_id: str) -> set[str]:
    asset = model.asset(asset_id)
    if asset is None:
        return set()
    asset_type = model.asset_type(asset.type)
    if asset_type is None:
        return set()
    return {f.id for f in asset_type.frames}


def _pose_frames_resolve(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_assets = {a.id for a in model.assets}
    for asset in model.assets:
        ref = asset.pose.frame
        if ref == WORLD_FRAME:
            continue
        if "/" not in ref:
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"{ref!r} is neither {WORLD_FRAME!r} nor an <asset_id>/<frame_id> reference",
                )
            )
            continue
        target, frame_id = ref.split("/", 1)
        if target not in known_assets:
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"references asset {target!r}, which does not exist",
                )
            )
        elif frame_id not in _frames_of(model, target):
            available = sorted(_frames_of(model, target))
            findings.append(
                error(
                    "unresolved-frame",
                    f"assets.{asset.id}.pose.frame",
                    f"asset {target!r} has no frame named {frame_id!r}",
                    f"Frames on that asset's type: {', '.join(available) or '(none)'}. "
                    "Frames are declared on the type, so the coordinate is written once.",
                )
            )
    return findings


def _no_pose_cycles(model: FacilityModel) -> list[Finding]:
    """An asset placed relative to an asset placed relative to the first.

    Without this the resolver recurses until the stack runs out, and the
    traceback names the recursion rather than the two assets involved.
    """
    parent: dict[str, str] = {}
    for asset in model.assets:
        if asset.pose.frame != WORLD_FRAME and "/" in asset.pose.frame:
            parent[asset.id] = asset.pose.frame.split("/", 1)[0]

    findings: list[Finding] = []
    for start in sorted(parent):
        seen = [start]
        current = start
        while current in parent:
            current = parent[current]
            if current in seen:
                chain = " -> ".join([*seen[seen.index(current) :], current])
                findings.append(
                    error(
                        "pose-cycle",
                        f"assets.{start}.pose.frame",
                        f"placement cycle: {chain}",
                        "Every asset must ultimately be placed relative to cite_world.",
                    )
                )
                break
            seen.append(current)
    # One cycle produces a finding per member; keep only the first by chain text.
    return _unique_by_message(findings)


def _unique_by_message(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for f in findings:
        if f.message not in seen:
            seen.add(f.message)
            out.append(f)
    return out


def _hardware_backends_exist(model: FacilityModel) -> list[Finding]:
    """Every backend an asset names exists, and every parameter block matches it.

    Six answers. ADR-0053 decision 1 names the first four so that a reviewer and
    a model author can address the same finding by the same word; the fifth and
    sixth are about the value rather than the index:

    * `unknown-hardware-param-backend` — a key of `params` that is not a declared
      backend id of the type. This is the typo case, and it is the one thing a
      per-backend index catches that a flat map cannot.
    * `unexpected-hardware-param` — a parameter inside a block that the backend
      THAT BLOCK NAMES does not declare. It used to resolve against the plant's
      selected backend, which is a different question once the map has an index.
    * `missing-hardware-param` — a parameter the SELECTED backend declares and the
      asset does not supply. The mirror of the rule above, and the half a model
      author meets: the generator raises on the same condition (ADR-0053 decision
      2a) but a raise aborts the run, so an author fixes one key per invocation
      instead of reading a report. "Supply" is
      `HardwareSelection.supplied_params`, which the generator reads too, and a
      string that is empty after stripping does not count.
    * `hardware-param-contains-quote` — a value carrying a quote character, in any
      block, selected or not. A value lands in an XML attribute of the generated
      description, and a quote there is how one L0 string became two vendor macro
      arguments. The generator escapes it regardless; this reports it, because no
      connection parameter is right with one in it and an escaped mistake is still
      a mistake, found at the arm instead of on a laptop.
    * `hardware-param-contains-dollar` — a value carrying `$`, in any block. xacro
      evaluates `${...}` and `$(...)` inside the attribute after XML has unescaped
      it, so escaping does not reach this and the generator refuses the value
      rather than escaping it. A sibling of the quote rule rather than a widening
      of it: that id is cited as meaning a quote, and the generator treats the two
      differently. The predicate is `schema.xacro_would_evaluate`, which the
      generator's raise reads too.
    * `literal-param-on-physical-backend` — a literal value, in any block, for
      a parameter a backend declaring `commands_physical_hardware: true`
      declares. Such a parameter says how to reach a machine, and the owner
      decided on 2026-10-05 that no such value is committed (ADR-0070 item 2):
      it is written `{env: <VARIABLE>}` and read at launch. Any block, selected
      or not, for the reason the quote rule gives.
    * Nothing else for a block naming a declared backend nobody selects. That
      is deliberate and it is what makes flipping an arm to hardware a
      one-field edit.
    """
    paired = {z.id for z in model.zones if z.twin.sides == "pair"}
    findings: list[Finding] = []
    for asset in model.assets:
        asset_type = model.asset_type(asset.type)
        if asset_type is None:
            continue
        backends = asset_type.hardware_backends
        params = asset.hardware.params

        # IN FRONT OF THE SKIP BELOW, deliberately. `if not backends: continue`
        # is reached by 3 of this model's 15 assets and skipped by 12 — every
        # type that declares no backends at all. Behind it, `params: {typo: {…}}`
        # on a conveyor or a beam would go unread, which is the state this rule
        # exists to end. No special case is needed for that type: with no
        # declared backends, every key of a non-empty `params` fails the test on
        # this line, and there is no backend id such a key could legitimately
        # name.
        for name in sorted(set(params) - set(backends)):
            findings.append(
                error(
                    "unknown-hardware-param-backend",
                    f"assets.{asset.id}.hardware.params.{name}",
                    f"type {asset_type.id!r} declares no backend named {name!r}",
                    f"Declared backends: {', '.join(sorted(backends)) or '(none)'}.",
                )
            )

        # Every block, selected or not and declared or not. An unselected block is
        # the one a one-field flip to hardware makes live, so waiting for the flip
        # would move this finding to the moment the arm is switched over.
        for name in sorted(params):
            for key, value in sorted(params[name].items()):
                if isinstance(value, str) and any(quote in value for quote in "\"'"):
                    findings.append(
                        error(
                            "hardware-param-contains-quote",
                            f"assets.{asset.id}.hardware.params.{name}.{key}",
                            f"parameter {key!r} holds {value!r}, which contains a quote",
                            "A value reaches an XML attribute of the generated description. "
                            "No connection parameter contains a quote; check for a stray "
                            "one closing the value early.",
                        )
                    )
                if xacro_would_evaluate(value):
                    findings.append(
                        error(
                            "hardware-param-contains-dollar",
                            f"assets.{asset.id}.hardware.params.{name}.{key}",
                            f"parameter {key!r} holds {value!r}, which contains `$`",
                            "xacro evaluates `${...}` and `$(...)` in the generated "
                            "description, and XML escaping does not stop it. No connection "
                            "parameter contains a `$`.",
                        )
                    )

        # Each block against the backend IT NAMES, not against the plant's. This
        # runs whether or not the selected backend resolves, because the question
        # a block asks is about its own backend and is answerable either way.
        for name in sorted(set(params) & set(backends)):
            allowed = set(backends[name].instance_params)
            if backends[name].commands_physical_hardware:
                for key in sorted(set(params[name]) & allowed):
                    if isinstance(params[name][key], EnvReference):
                        continue
                    findings.append(
                        error(
                            "literal-param-on-physical-backend",
                            f"assets.{asset.id}.hardware.params.{name}.{key}",
                            f"backend {name!r} of type {asset_type.id!r} commands physical "
                            f"hardware, and parameter {key!r} is written as a literal value",
                            "A parameter of a physical backend says how to reach a machine "
                            "and is never committed (ADR-0070 item 2). Write it "
                            "`{env: <VARIABLE>}` and set the variable in your local .env.",
                        )
                    )
            for key in sorted(set(params[name]) - allowed):
                findings.append(
                    error(
                        "unexpected-hardware-param",
                        f"assets.{asset.id}.hardware.params.{name}.{key}",
                        f"backend {name!r} of type {asset_type.id!r} declares no "
                        f"parameter {key!r}",
                        f"Declared parameters: {', '.join(sorted(allowed)) or '(none)'}.",
                    )
                )

        if not backends:
            continue
        chosen = asset.hardware.backend
        # Both sides, because a backend is selected per (asset, side) and a
        # counterpart that names a plugin its type does not declare fails at
        # bring-up on the far side rather than here (ADR-0041, Decision 3). The
        # counterpart is checked under its own key so the message names the
        # field that is wrong; a `None` falls back to `backend`, which is the
        # value already checked on the line above.
        unknown = [
            (field, value)
            for field, value in (
                ("backend", chosen),
                ("counterpart_backend", asset.hardware.counterpart_backend),
            )
            if value is not None and value not in backends
        ]
        for field, value in unknown:
            findings.append(
                error(
                    "unknown-backend",
                    f"assets.{asset.id}.hardware.{field}",
                    f"type {asset_type.id!r} declares no backend named {value!r}",
                    f"Declared backends: {', '.join(sorted(backends))}.",
                )
            )
        if chosen not in backends:
            continue

        # EVERY SIDE THAT EXISTS, each against the backend it loads. The
        # counterpart of a paired zone gets a description of its own, valued from
        # ITS backend's block (ADR-0048 clause 2, ADR-0070), so a parameter that
        # backend declares and the asset does not supply would fail the generator
        # exactly as the plant's would. On an untwinned zone there is no
        # counterpart to describe, and its backend is not asked about.
        selected = [chosen]
        counterpart = asset.hardware.effective_counterpart_backend
        if asset.zone in paired and counterpart != chosen and counterpart in backends:
            selected.append(counterpart)

        # The mirror. A connection parameter has no default that could be right:
        # the vendor's own `robot_ip:=''` becomes `<param name="robot_ip">R</param>`
        # and `uf_robot_system_hardware.cpp` answers it with `exit(1)` from inside
        # a loaded plugin at `on_init`. Reporting it here moves that failure from
        # the machine standing next to the arm to a laptop, and reports every
        # missing key at once rather than the first (ADR-0053 decision 2a).
        #
        # "Supplied" is the model's one predicate, which the generator's backstop
        # reads as well, so the two cannot disagree about a model. A declared key
        # holding an empty string is unsupplied: decision 2a's reason is about the
        # value, and `robot_ip: ''` lands the same `exit(1)`.
        for backend_id in selected:
            supplied = set(asset.hardware.supplied_params(backend_id))
            for key in sorted(set(backends[backend_id].instance_params) - supplied):
                findings.append(
                    error(
                        "missing-hardware-param",
                        f"assets.{asset.id}.hardware.params.{backend_id}.{key}",
                        f"backend {backend_id!r} of type {asset_type.id!r} declares "
                        f"parameter {key!r}, which this asset does not supply a value for",
                        f"Add it under `hardware.params.{backend_id}`. An empty value is not "
                        "one; a value read at launch is written `{env: <VARIABLE>}`.",
                    )
                )
    return findings


def _instance_params_reach_a_bound_plugin(model: FacilityModel) -> list[Finding]:
    """A type that binds an instance parameter must also bind the backend's plugin.

    `unrouted-hardware-params`, one ERROR per type. An instance parameter exists
    only to reach the hardware component the selected backend names; without a
    `bound_args` entry carrying `instance.hardware.ros2_control_plugin`, the
    description loads the vendor macro's default plugin instead — for
    `xarm_description`, the physical one — while L0, the plan and the bring-up
    gate all read the backend's own `commands_physical_hardware`. Before
    ADR-0053 bound parameters at all, that combination reached the vendor with an
    empty address and failed at `on_init`; this keeps it failing, and moves the
    failure to validation.

    Referential, and so gating generation, because the generator refuses the same
    condition (`DescriptionSpec.unrouted_param_arguments`, which both read) and
    would otherwise abort with a traceback. Per type rather than per asset, and
    regardless of which backend is selected: the defect is in the type, and
    waiting for an asset to select a backend that declares parameters would move
    the finding to the moment an arm is switched over.

    This does not close `docs/open-work.md` #65. It does not check that the plugin
    is bound under the argument name the vendor reads, and a type that binds no
    instance parameter is not examined at all.
    """
    findings: list[Finding] = []
    for asset_type in model.types:
        unrouted = asset_type.description.unrouted_param_arguments()
        if unrouted:
            findings.append(
                error(
                    "unrouted-hardware-params",
                    f"types.{asset_type.id}.description.bound_args",
                    f"type {asset_type.id!r} binds {', '.join(unrouted)} to an instance "
                    f"parameter, and no entry binds {PLUGIN_BINDING}",
                    "Without it the description loads the vendor macro's default plugin, "
                    "not the one the selected backend declares, and the parameters reach "
                    "that component instead. Bind the plugin, or remove the parameter bindings.",
                )
            )
    return findings


def _plugin_less_backends_are_not_bound(model: FacilityModel) -> list[Finding]:
    """A backend declaring no plugin may not sit on a type that binds the plugin.

    `plugin-less-backend-on-a-bound-description`, one ERROR per (type, backend).
    `ros2_control_plugin: null` says that no `ros2_control` component serves this
    type's joints on that backend (ADR-0070 item 3), which the generator honours
    for joints IT emits — a track's — by emitting no `<ros2_control>` block. A
    vendor description is different: its `<ros2_control>` block is the vendor
    macro's, and binding no plugin into it hands the macro its OWN default, which
    for `xarm_description` is the physical component. The generator refuses the
    same condition as a backstop (`generate.description._binding_value`).
    """
    findings: list[Finding] = []
    for asset_type in model.types:
        if PLUGIN_BINDING not in asset_type.description.bound_args.values():
            continue
        for name, backend in sorted(asset_type.hardware_backends.items()):
            if backend.ros2_control_plugin is None:
                findings.append(
                    error(
                        "plugin-less-backend-on-a-bound-description",
                        f"types.{asset_type.id}.hardware_backends.{name}.ros2_control_plugin",
                        f"backend {name!r} of type {asset_type.id!r} declares no plugin, and "
                        f"the type's description binds {PLUGIN_BINDING}",
                        "The vendor macro would load its own default plugin on a side "
                        "selecting this backend. Declare the plugin, or stop binding it.",
                    )
                )
    return findings


def _paired_zone_has_no_physical_plant(model: FacilityModel) -> list[Finding]:
    """A twinned zone may not put a physical machine on its PLANT side.

    A schema cannot say this: `twin.sides` is a zone fact and `hardware.backend`
    is an asset fact, so the two live in different documents and only a
    cross-document check reaches both.

    WHY THIS PARTICULAR CELL OF THE CROSS PRODUCT IS CLOSED. A physical plant
    with a simulated counterpart and a simulated plant with a physical
    counterpart describe the same two machines, and they are genuinely different
    to this tool — they emit different bring-up plans, different controller
    configurations and a different MODEL_HASH. Being different is not being
    wanted. `plant` is by construction the side `./scripts/sim`, all three
    scenarios and every Phase 1 artifact already address, so `backend: real`
    under `twin.sides: pair` would point the whole existing test suite at a
    physical cell — behind an opt-in that is a BRING-UP refusal rather than a
    per-command one. Charter §8 scopes Phase 2 as one physical arm and two
    simulated ones, which is the other encoding by construction, so this one also
    buys nothing (ADR-0041, Decision 3).

    A physical machine on a paired zone is a ``counterpart_backend``. 2.B may
    reopen this with an argument; leaving it expressible by omission is a
    different thing.

    IT READS THE DECLARATION AND NOT THE ID (ADR-0054, decision 2). This rule
    compared ``hardware.backend`` against the literal ``sim`` and was therefore
    satisfied by a paired zone whose plant loads the vendor's physical component
    under that id — measured, at zero findings, in that record's Context. What
    decides is now the type's own ``commands_physical_hardware``, so the rule
    refuses a physical plant whatever its backend is called and permits a
    simulated one whatever it is called.

    THE RULE ID IS DELIBERATELY UNCHANGED, so no other record's citation of it
    goes stale; the message, the hints and the ``where`` move. The ``where``
    moves because the CAUSE moved: it was ``assets.<id>.hardware.backend``, the
    id the asset selected, and the cause is now the declaration on the type's
    backend, which is where a reader has to go to change the answer.
    """
    paired = {z.id for z in model.zones if z.twin.sides == "pair"}
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.zone not in paired:
            continue
        asset_type = model.asset_type(asset.type)
        if asset_type is None:
            # `_asset_types_exist` reports the missing type; this rule has
            # nothing to read and says nothing rather than reporting the same
            # cause twice.
            continue
        backend = asset_type.hardware_backends.get(asset.hardware.backend)
        if backend is None:
            # There is nothing here to read, and WHICH of the two ways that
            # happens decides whether anything else says so. This comment read
            # "`unknown-backend` reports it" and that is true of only one of
            # them.
            #
            # The type declares SOME backends and the asset selected one that is
            # not among them: `unknown-backend` reports exactly that, naming the
            # field and the value.
            #
            # The type declares NO backends at all: `unknown-backend` skips it
            # too, on its own `if not backends`, and deliberately - `hardware` is
            # required on every asset, so every conveyor, sensor and fixture in
            # this facility selects a backend on a type that declares none, and a
            # rule firing there would report the ordinary case. Both rules are
            # therefore silent, and this one going quiet costs nothing: a plugin
            # class string is authored only on a `HardwareBackend`, so a type
            # with no backends cannot name a physical component for this rule to
            # find. That is why it is a silence and not a hole - but it is a
            # silence, and `test_a_type_declaring_no_backends_is_silent_in_both_rules`
            # is what would notice if the first half of that argument stopped
            # holding.
            #
            # A SECOND ROUTE MAKES THE SILENCE STRONGER THAN THAT ARGUMENT, and
            # it does not depend on the argument at all. If such an asset has
            # controllers, nothing downstream is generated to be silent ABOUT:
            # `generate/bringup.py:392` asks `commands_physical_hardware_of` for
            # every controller manager, which resolves the backend through
            # `ResolvedAsset._backend` and raises `ResolveError: asset <id>
            # selects backend <id>, which type <type> does not declare` - so the
            # run stops before any plan or description exists. If it has no
            # controllers it gets no controller manager and no `<ros2_control>`
            # block, so there is no plugin anywhere to gate. Driven by
            # `safety-auditor` on 2026-09-10 and re-read here from those two call
            # sites. It is a second reason and not a replacement: this rule is
            # still the one that would have to speak if a plugin string ever
            # became authorable off a `HardwareBackend`.
            continue
        if not backend.commands_physical_hardware:
            continue
        findings.append(
            error(
                "physical-plant-on-paired-zone",
                f"types.{asset_type.id}.hardware_backends.{asset.hardware.backend}"
                ".commands_physical_hardware",
                f"zone {asset.zone!r} declares twin.sides: pair, so its plant side may not "
                f"command physical hardware, and asset {asset.id!r} selects backend "
                f"{asset.hardware.backend!r}, which type {asset_type.id!r} declares as "
                "commanding it",
                "`plant` is the side ./scripts/sim, every scenario and every Phase 1 "
                "artifact already address, so this would silently point the whole existing "
                "test suite at a physical cell — behind an opt-in that refuses at bring-up "
                "rather than per command. Write the physical machine as "
                f"`counterpart_backend: {asset.hardware.backend}` and leave the plant on a "
                "backend declaring `commands_physical_hardware: false`; that is the same "
                "two machines, it is what charter §8's Phase 2 scopes, and it is the "
                "encoding MODE_VIRTUAL_LEAD describes (ADR-0041, Decision 3). What decides "
                "here is the declaration on the type's backend and not the backend's name, "
                "so renaming the backend changes nothing (ADR-0054). The generator emits "
                "that counterpart a description and controller configuration of its own "
                "(ADR-0048 clause 2, ADR-0070).",
            )
        )
    return findings


def _counterpart_backend_needs_a_paired_zone(model: FacilityModel) -> list[Finding]:
    """A `counterpart_backend` other than `backend`, on a zone with no counterpart, is an ERROR.

    Other than `backend`, because the loaded model cannot tell a value equal to
    `backend` from an omitted one, by design: the fallback is applied at load so
    the two spellings are one facility (`HardwareSelection`). A differing value
    is the one that says something.

    On a `single` zone there is no side for it to select a backend for, so the
    value reaches no artifact and is silently inert (ADR-0041, Decision 3). That
    silence is the hazard: a model that writes `counterpart_backend: real` on an
    unpaired zone reads as if a physical counterpart were declared, and pairing
    the zone later would make it one without anyone writing it again. ADR-0070
    deleted `divergent-counterpart-backend`, which used to report this case as
    a side effect; this keeps the case reported on its own terms.
    """
    paired = {z.id for z in model.zones if z.twin.sides == "pair"}
    return [
        error(
            "counterpart-backend-on-unpaired-zone",
            f"assets.{asset.id}.hardware.counterpart_backend",
            f"asset {asset.id!r} declares counterpart_backend "
            f"{asset.hardware.counterpart_backend!r}, and its zone {asset.zone!r} has no "
            "counterpart side",
            "Set `twin: {sides: pair}` on the zone if it is twinned, or remove "
            "`counterpart_backend`; on an unpaired zone it selects nothing (ADR-0041, "
            "Decision 3).",
        )
        for asset in model.assets
        if asset.zone not in paired
        and asset.hardware.effective_counterpart_backend != asset.hardware.backend
    ]


def _configuration_matches_category(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    for asset in model.assets:
        asset_type = model.asset_type(asset.type)
        if asset_type is None or asset.configuration is None:
            continue
        expected = _CATEGORY_CONFIG_KIND.get(asset_type.category)
        actual = asset.configuration.kind
        if expected is None:
            findings.append(
                error(
                    "configuration-mismatch",
                    f"assets.{asset.id}.configuration",
                    f"type {asset_type.id!r} is a {asset_type.category}, which takes no "
                    "configuration",
                )
            )
        elif actual != expected:
            findings.append(
                error(
                    "configuration-mismatch",
                    f"assets.{asset.id}.configuration.kind",
                    f"is {actual!r} but type {asset_type.id!r} is a {asset_type.category}",
                    f"Expected kind {expected!r}.",
                )
            )
    return findings


def _an_arm_rides_its_track_on_one_backend(model: FacilityModel) -> list[Finding]:
    """An arm on a track selects the backend the track selects (ADR-0067).

    The track's joint is emitted into the ARM's description, under the arm's
    base, with the track's own `ros2_control` plugin. An arm on `real` above a
    track on `sim` would put a Gazebo plugin into a physical robot's description,
    and the reverse a physical plugin into a simulated one: a P2 break either
    way, and one no other rule sees, because each asset is valid on its own.
    """
    findings: list[Finding] = []
    for asset in model.assets:
        if asset.pose.frame == WORLD_FRAME:
            continue
        track = model.asset(asset.pose.frame.split("/", 1)[0])
        track_type = None if track is None else model.asset_type(track.type)
        if track is None or track_type is None or track_type.axis is None:
            continue
        mine = (asset.hardware.backend, asset.hardware.effective_counterpart_backend)
        theirs = (track.hardware.backend, track.hardware.effective_counterpart_backend)
        if mine != theirs:
            findings.append(
                error(
                    "track-backend-differs-from-its-arm",
                    f"assets.{asset.id}.hardware",
                    f"selects {mine} (plant, counterpart) while the track it rides, "
                    f"{track.id!r}, selects {theirs}",
                    "The track's joint lives in this arm's description, so the two load "
                    "one hardware plugin set. Select the same backends on both.",
                )
            )
    return findings


def _programs_fit_the_arm(model: FacilityModel) -> list[Finding]:
    """A program the arm cannot run is refused here, not at the robot (ADR-0067).

    Four things, each a way the program would otherwise fail part-way through a
    cycle with a part in the jaws:

    * `program-refused` — the reader refuses the file: a block the twin does not
      model, a blended move, a move that does not wait.
    * `program-pose-outside-joint-limits` — a pose past the vendor's own joint
      limits, which L0 states for exactly this check.
    * `program-track-*` — a track move on an arm with no track, or past the
      track's stroke or speed.
    """
    findings: list[Finding] = []
    for asset in model.assets:
        configuration = asset.configuration
        if configuration is None or configuration.kind != "robot" or not configuration.program:
            continue
        where = f"assets.{asset.id}.configuration.program"
        try:
            steps = program_steps(model, asset)
        except blockly.BlocklyError as exc:
            findings.append(
                error(
                    "program-refused",
                    where,
                    f"{configuration.program}: {exc}",
                    "The program is the real robot's, and is not edited here. Model the "
                    "block in cite_tools.model.blockly, or change the program on the robot "
                    "and export it again.",
                )
            )
            continue
        asset_type = model.asset_type(asset.type)
        limits = (
            asset_type.kinematics.joint_limits_rad
            if asset_type is not None and asset_type.kinematics is not None
            else None
        )
        # No rule reserves `home` here: the reader names every pose itself,
        # `zero` or `blockly_NN`, so a program pose cannot be called `home`
        # (see `cite_tools.model.blockly.POSE_PREFIX`).
        for name, values in blockly.poses(steps).items():
            if limits is None:
                findings.append(
                    error(
                        "program-pose-limits-unstated",
                        where,
                        f"type {asset.type!r} states no kinematics.joint_limits_rad, so the "
                        f"program's pose {name!r} cannot be checked against them",
                    )
                )
                continue
            outside = [
                f"joint{index + 1} {value:.4f} rad not in [{low:g}, {high:g}]"
                for index, (value, (low, high)) in enumerate(zip(values, limits, strict=True))
                if not low <= value <= high
            ]
            if outside:
                findings.append(
                    error(
                        "program-pose-outside-joint-limits",
                        where,
                        f"pose {name!r}: {'; '.join(outside)}",
                        "The planning group refuses it at MoveTo, mid-cycle. The program is "
                        "the robot's own, so the limits or the program are wrong, not the "
                        "reader.",
                    )
                )
        findings += _program_track_moves_fit(model, asset, steps, where)
    return findings


def _program_track_moves_fit(
    model: FacilityModel, asset, steps: tuple[blockly.Step, ...], where: str
) -> list[Finding]:
    moves = [step for step in steps if isinstance(step, blockly.Track)]
    if not moves:
        return []
    track = None if asset.pose.frame == WORLD_FRAME else model.asset(asset.pose.frame.split("/")[0])
    track_type = None if track is None else model.asset_type(track.type)
    axis = None if track_type is None else track_type.axis
    if axis is None:
        return [
            error(
                "program-track-without-a-track",
                where,
                f"the program moves a linear track and {asset.id!r} does not stand on one",
                "Place the arm on a track's carriage frame.",
            )
        ]
    findings: list[Finding] = []
    for move in moves:
        if not 0.0 <= move.position_m <= axis.stroke_m:
            findings.append(
                error(
                    "program-track-beyond-stroke",
                    where,
                    f"a track move to {move.position_m:.3f} m, outside the "
                    f"{axis.stroke_m:.3f} m stroke of {track_type.id!r}",  # type: ignore[union-attr]
                )
            )
        if move.speed_mps > axis.max_speed_mps:
            findings.append(
                error(
                    "program-track-too-fast",
                    where,
                    f"a track move at {move.speed_mps:.3f} m/s, over the "
                    f"{axis.max_speed_mps:.3f} m/s the track declares",
                )
            )
    return findings


def _stations_reference_real_things(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_assets = {a.id for a in model.assets}
    for station in model.stations:
        for asset_id in station.assets:
            if asset_id not in known_assets:
                findings.append(
                    error(
                        "unknown-asset",
                        f"stations.{station.id}.assets",
                        f"no asset named {asset_id!r}",
                    )
                )
        if station.actor is not None and station.actor not in known_assets:
            findings.append(
                error(
                    "unknown-asset",
                    f"stations.{station.id}.actor",
                    f"no asset named {station.actor!r}",
                )
            )
        for label, point in (("pick_from", station.pick_from), ("place_to", station.place_to)):
            if point is None:
                continue
            if point.asset not in known_assets:
                findings.append(
                    error(
                        "unknown-asset",
                        f"stations.{station.id}.{label}.asset",
                        f"no asset named {point.asset!r}",
                    )
                )
            elif point.frame not in _frames_of(model, point.asset):
                available = sorted(_frames_of(model, point.asset))
                findings.append(
                    error(
                        "unresolved-frame",
                        f"stations.{station.id}.{label}.frame",
                        f"asset {point.asset!r} has no frame named {point.frame!r}",
                        f"Frames on that asset's type: {', '.join(available) or '(none)'}.",
                    )
                )
        if station.trigger is not None and station.trigger.sensor not in known_assets:
            findings.append(
                error(
                    "unknown-asset",
                    f"stations.{station.id}.trigger.sensor",
                    f"no asset named {station.trigger.sensor!r}",
                )
            )
        if station.type == "transfer_station" and station.actor is None:
            findings.append(
                error(
                    "station-without-actor",
                    f"stations.{station.id}.actor",
                    "a transfer station must name the asset that does the work",
                )
            )
    return findings


def _workpiece_models_exist(model: FacilityModel) -> list[Finding]:
    """A work-piece the facility handles, with no type behind it.

    The name alone is not harmless. It reaches the generated world as the belt's
    ``<carry>`` list and the beam's ``<watch>`` list, so a misspelling produces a
    belt that carries nothing and a sensor that sees nothing, with no error
    anywhere — and it is now also the datum two validation rules size themselves
    from, which silently lose their bound when it does not resolve.
    """
    findings: list[Finding] = []
    by_id = {t.id: t for t in model.types}
    for name in model.facility.workpiece_models:
        asset_type = by_id.get(name)
        if asset_type is None:
            available = sorted(t.id for t in model.types if t.category == "workpiece")
            findings.append(
                error(
                    "unknown-type",
                    f"facility.workpiece_models.{name}",
                    f"no component library entry named {name!r}",
                    f"Declared work-piece types: {', '.join(available) or '(none)'}. "
                    "The name reaches the simulator as a Gazebo model name, so an "
                    "unresolved one gives a belt that carries nothing and a beam that "
                    "watches nothing, without an error.",
                )
            )
        elif asset_type.category != "workpiece":
            findings.append(
                error(
                    "workpiece-is-not-a-workpiece",
                    f"facility.workpiece_models.{name}",
                    f"names type {name!r}, which is a {asset_type.category}",
                    "Only a type of category 'workpiece' may be listed here. Listing a "
                    "fixture would tell the belt to carry the table.",
                )
            )
    return findings


def _flow_is_consistent(model: FacilityModel) -> list[Finding]:
    findings: list[Finding] = []
    known_stations = {s.id for s in model.stations}
    known_assets = {a.id for a in model.assets}
    for flow in model.flows:
        for index, edge in enumerate(flow.edges):
            where = f"flow.{flow.id}.edges[{index}]"
            for label, station_id in (("from", edge.from_station), ("to", edge.to_station)):
                if station_id not in known_stations:
                    findings.append(
                        error(
                            "unknown-station",
                            f"{where}.{label}",
                            f"no station named {station_id!r}",
                        )
                    )
            if edge.via is not None and edge.via not in known_assets:
                findings.append(
                    error("unknown-asset", f"{where}.via", f"no asset named {edge.via!r}")
                )
            if edge.from_station == edge.to_station:
                findings.append(
                    error("self-edge", where, f"station {edge.from_station!r} flows to itself")
                )

        reachable = _reachable_stations(flow.edges)
        orphans = sorted(
            s.id for s in model.stations if s.zone == flow.zone and s.id not in reachable
        )
        for station_id in orphans:
            findings.append(
                error(
                    "unreachable-station",
                    f"stations.{station_id}",
                    f"is in zone {flow.zone!r} but appears in no edge of flow {flow.id!r}",
                    "A station nothing flows into or out of can never receive work. "
                    "Either connect it or remove it.",
                )
            )
    return findings


def _reachable_stations(edges: Iterable[FlowEdge]) -> set[str]:
    reachable: set[str] = set()
    for edge in edges:
        reachable.add(edge.from_station)
        reachable.add(edge.to_station)
    return reachable
