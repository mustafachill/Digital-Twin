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

"""The L0 half of ADR-0054: a backend declares whether it reaches a machine.

Three clauses of that record's promotion condition live here — 1 (the field is
required and unreachable by omission), 9 (the raw plan keys have one reader per
build unit) and 6 (the reproduction is refused end to end). None of them needs a
simulator, a running cell or a physical arm; there is no physical arm to need.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import REAL_MODEL

import cite_tools
from cite_tools.generate import generate as generate_artifacts
from cite_tools.model.loader import ModelError, load
from cite_tools.render import environment
from cite_tools.validate import referential

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- Clause 1: required, with no default -------------------------------------
#
# THE CLAUSE EVERY OTHER CLAUSE RESTS ON AT THE L0 LAYER. With a default, all ten
# others can pass while a backend becomes physical because a key was left out.


def test_a_backend_omitting_the_declaration_fails_to_load(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """Asserted on a scratch type, never on the shipped one.

    Asserting it on `model/` would prove only that the shipped model states the
    field, which is clause 2's question and a different one.
    """
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["real"].pop("commands_physical_hardware"),
    )
    with pytest.raises(ModelError) as raised:
        load(minimal_model)
    message = str(raised.value)
    # The error has to name BOTH, or its reader is told a field is missing
    # somewhere in a file that declares several backends.
    assert "commands_physical_hardware" in message
    assert "real" in message


def test_a_backend_omitting_the_declaration_is_not_quietly_simulated(
    minimal_model: Path, edit_yaml: Callable
) -> None:
    """The mutation the clause exists to kill: a default of `false`.

    A schema default would make an omitted key mean "this cannot reach a
    machine", which is ADR-0054's own defect with a shorter spelling — and
    nothing downstream could tell it from a stated `false`.
    """
    edit_yaml(
        minimal_model / "assets/types/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["sim"].pop("commands_physical_hardware"),
    )
    with pytest.raises(ModelError):
        load(minimal_model)


# --- Clause 9: one reader per build unit, checked by grep --------------------
#
# STATED AS A ROUTE AND NOT AS A BEHAVIOUR ON PURPOSE. Clauses 4 and 8 are both
# satisfied by an implementation that open-codes the two plan keys inside
# `require_hardware_opt_in` AND inside `twin_boundary` — four keys across two
# build units, which is exactly the P1 debt ADR-0048's clause-3 promotion had to
# retrofit eight days late.

#: The accessors `plan.py` publishes. Every other build unit reaches the fact
#: through one of these and never through the field or the document key.
ACCESSORS = (
    "commands_physical_hardware_on_or_none",
    "commands_physical_hardware_on",
)

#: What a READ of the raw datum looks like, as opposed to prose about it: an
#: attribute access, or the key written as a string. Matched this way rather than
#: by the bare token clause 9 names, because the token legitimately appears in
#: docstrings, in the generator's template and in this file - and a guard that
#: counts a string counts its own message.
#:
#: **WIDENED 2026-09-10, ON A MEASUREMENT.** It required `[.\[]` immediately
#: before the key, which is narrower than clause 9's plain `grep` and missed
#: three spellings a second build unit would plausibly reach for. Driven through
#: `_reads_the_raw_datum` on each: `entry.get("...")`, `getattr(manager, "...")`
#: and a named constant plus `entry[KEY]` all returned `False`. A quote now
#: counts as well as a dot or a bracket, which catches all three - the third
#: because the constant has to be SPELLED somewhere, and that spelling is a
#: quoted token. The three sanctioned forms in
#: `test_the_guard_itself_catches_a_raw_read` stay green, and the live offender
#: list is unchanged at empty.
#:
#: **Its residual, stated rather than left to a third report.** The key built by
#: arithmetic or by `.format` - `"commands_" + "physical_hardware"` - carries no
#: quoted whole token and is not caught, and neither is a read from anywhere this
#: guard does not walk (it walks non-test `*.py` under `workspace/src` only).
#: Widening further means matching the bare token, which fires on every docstring
#: that discusses the key, and a guard that counts its own prose is the one thing
#: this constant's first comment was written to avoid.
RAW_READ = re.compile(r"""(?:\.\s*|\[\s*|['"])(?:counterpart_)?commands_physical_hardware\b""")

#: The one file allowed to read it: it parses the two keys and owns the two
#: accessors.
PARSER = "workspace/src/cite_bringup/cite_bringup/plan.py"


def _sources() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "workspace/src"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [
        path
        for path in listed
        if path.endswith(".py") and "/test/" not in path and "/external/" not in path
    ]


def _reads_the_raw_datum(text: str) -> bool:
    for accessor in ACCESSORS:
        text = text.replace(accessor, "ACCESSOR")
    return RAW_READ.search(text) is not None


def test_only_the_parser_reads_the_raw_plan_keys() -> None:
    """Every other consumer asks the accessor.

    `cite_twin` reaches the fact through
    `commands_physical_hardware_on_or_none`, which is where the three-valued
    `None` this project needs is defined once. Naming the field in a second build
    unit is the value-in-two-places P1 forbids, and the field that stops being
    read is the one that goes stale.
    """
    offenders = sorted(
        path
        for path in _sources()
        if path != PARSER and _reads_the_raw_datum((REPO_ROOT / path).read_text())
    )
    assert offenders == [], (
        f"{offenders} read a raw plan key that only {PARSER} may read. Ask "
        "`ControllerManager.commands_physical_hardware_on(side)`, or its total "
        "sibling `..._on_or_none(side)` where an absent side is a real answer "
        "(ADR-0054, decision 3)."
    )


def test_the_guard_itself_catches_a_raw_read() -> None:
    """The guard has to fail on the thing it forbids, or it is a passing comment.

    Both spellings the clause names, plus the document-key form, because an
    implementation that open-coded the keys would most naturally reach for
    `entry["commands_physical_hardware"]` rather than for the field.

    **The last three were added 2026-09-10 and each was RED before the widening
    beside `RAW_READ`.** They are the spellings a second build unit reaches for
    when the plan entry is still a `dict` - `.get`, `getattr`, and a key lifted
    into a module constant - and clause 9's own plain `grep` catches all three,
    so a guard that did not was narrower than the clause it stands for.
    """
    for spelling in (
        "manager.commands_physical_hardware",
        "manager.counterpart_commands_physical_hardware",
        'entry["commands_physical_hardware"]',
        'entry.get("commands_physical_hardware")',
        'getattr(manager, "commands_physical_hardware")',
        'KEY = "commands_physical_hardware"',
    ):
        assert _reads_the_raw_datum(spelling), spelling
    # And it must not fire on the sanctioned routes or on prose about them.
    for allowed in (
        "manager.commands_physical_hardware_on(side)",
        "manager.commands_physical_hardware_on_or_none(side)",
        "the plan states `commands_physical_hardware: false` per manager",
    ):
        assert not _reads_the_raw_datum(allowed), allowed


# --- Clause 6, the half that runs without ROS ---------------------------------
#
# The whole of clause 6 crosses two build units and needs one interpreter holding
# both `cite_tools` (pydantic) and `cite_bringup` (`ament_index_python`).
# `./scripts/test`'s host half clears `PYTHONPATH` deliberately - it is ROS-free
# by design - so that clause cannot run here. It lives in
# `cite_bringup/test/test_the_reproduction_is_refused.py`, which runs under
# colcon in the container and drives the generator through a subprocess.
#
# What runs here is its L0-to-artifact leg: the reproduction's model is valid,
# generates, and the bring-up plan it produces states the truth. That is the half
# a reader of `tools/tests` can check, and it fails if decisions 1 to 3 land
# partially on this side of the boundary.


def reproduction_model(destination: Path) -> Path:
    """Write ADR-0054's scratch model: the vendor's plugin, keeping the id `sim`.

    Two edits to the type and its instances, and **no id anywhere changes** -
    which is the whole of the reproduction. Mirrored in the `cite_bringup` half,
    `test_the_reproduction_is_refused.py`, which cannot import this module
    because that tree is not on its interpreter's path; the two are asserted to
    agree by `test_the_two_halves_build_the_same_model` over there.

    **The zone is pinned to `single` rather than taken from the checkout**, and
    that is not cosmetic. The copied tree is the live `model/`, so on a checkout
    flipped to `twin: {sides: pair}` for a run - a real state, and how a pair is
    brought up at all - this model declares a PHYSICAL PLANT ON A PAIRED ZONE,
    which `physical-plant-on-paired-zone` refuses. The reproduction would then
    fail to validate and clause 6 would be measuring that refusal rather than the
    hardware gate. ADR-0054's Context was measured on the shipped `single` zone;
    this states that shape instead of inheriting whichever one is committed
    (open-work #40).
    """
    import yaml

    scratch = destination / "model"
    shutil.copytree(REAL_MODEL, scratch)
    zones = scratch / "facility/zones.yaml"
    declared = yaml.safe_load(zones.read_text())
    for zone in declared["zones"]:
        zone["twin"] = {"sides": "single"}
    zones.write_text(yaml.safe_dump(declared, sort_keys=False))
    path = scratch / "assets/types/robots/xarm5.yaml"
    document = yaml.safe_load(path.read_text())
    document["asset_type"]["hardware_backends"]["sim"] = {
        "ros2_control_plugin": "uf_robot_hardware/UFRobotSystemHardware",
        "commands_physical_hardware": True,
        "instance_params": ["robot_ip"],
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    arms = scratch / "assets/instances/arms.yaml"
    instances = yaml.safe_load(arms.read_text())
    for asset in instances["assets"]:
        if asset.get("hardware", {}).get("backend") == "sim":
            asset["hardware"]["params"] = {"robot_ip": "203.0.113.7"}
    arms.write_text(yaml.safe_dump(instances, sort_keys=False))
    return scratch


def test_the_reproduction_still_validates_and_generates(tmp_path: Path) -> None:
    """It must, or clause 6's refusal would be measuring an unrelated break.

    ADR-0054's Context reports **0** referential findings and 34 artifacts on
    this model, and none of the four decisions changes that: what a model may
    SAY is unchanged, and what is refused is a paired plant, which this zone is
    not.
    """
    model = load(reproduction_model(tmp_path))
    assert referential.check(model) == []
    assert generate_artifacts(model)


def test_the_generated_plan_states_the_truth_for_every_arm(tmp_path: Path) -> None:
    """The artifact the gate reads, produced from a model that declares honestly.

    Where the shipped plan says `commands_physical_hardware: false` beside
    `backend: sim`, this one says `true` beside the same id - which is the datum
    that makes the two models distinguishable at all, and the thing no name
    could have carried.
    """
    artifacts = generate_artifacts(load(reproduction_model(tmp_path)))
    plan = next(a for a in artifacts if a.path.endswith("bringup/cell_a_plan.yaml"))
    stated = [
        line.strip()
        for line in plan.content.splitlines()
        if line.strip().startswith("commands_physical_hardware:")
    ]
    assert stated == ["commands_physical_hardware: true"] * 3, stated
    assert "backend: sim" in plan.content, (
        "the reproduction keeps the friendly id throughout; a test that renamed "
        "it would be measuring something else"
    )


def test_the_template_refuses_to_render_an_unstated_declaration() -> None:
    """The last hop, where a required field could still acquire a default.

    ADR-0054 makes `commands_physical_hardware` required with no default because
    a hardware path must never be reachable by omission. The plan template
    rendered it as `{{ 'true' if manager.commands_physical_hardware else
    'false' }}` until 2026-09-09, and Jinja renders `None` there as **`false`**
    in silence - the schema's refused default, reintroduced at the point where
    the artifact the gate reads is written.

    `StrictUndefined` does not reach this: it catches a name the template never
    received, and this is a name that arrived carrying `None`.

    Nothing in the generator is believed to pass `None` today. What this asserts
    is that the template would SAY SO if it did, rather than writing the safe
    word.
    """
    env = environment()
    template = env.from_string(
        "{{ value | declared_bool }}"  # the spelling the plan template uses
    )
    assert template.render(value=True) == "true"
    assert template.render(value=False) == "false"
    with pytest.raises(TypeError, match="reachable by omission"):
        template.render(value=None)


def test_the_plan_template_renders_that_field_through_the_refusing_filter() -> None:
    """The route, not the behaviour - because the ordinary spelling still works.

    A rewrite back to `{{ 'true' if ... else 'false' }}` renders identically on
    every value the generator passes today, so no output test would notice it.
    Read from the template's source for that reason.
    """
    source = (Path(cite_tools.__file__).parent / "templates/bringup/plan.yaml.j2").read_text()
    for field in (
        "commands_physical_hardware",
        "counterpart_commands_physical_hardware",
    ):
        rendered = [line for line in source.splitlines() if line.strip().startswith(f"{field}:")]
        assert rendered, f"the template no longer emits {field}"
        for line in rendered:
            assert "| declared_bool" in line, (
                f"{field} is rendered as {line.strip()!r}; a boolean a hardware "
                "gate decides on must go through `declared_bool`, which refuses "
                "`None` instead of writing `false`"
            )
