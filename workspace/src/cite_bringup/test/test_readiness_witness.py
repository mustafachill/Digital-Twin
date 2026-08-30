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

"""What "this side is up" is made of, and what it refuses to be made of.

ADR-0047 clause 3. `endpoints()` IS the definition of a side's readiness: the
launch announces the token when that list has been answered, and the pair
supervisor reports the pair up when both tokens arrive. **Nothing tested it**, so
a plan naming almost nothing produced a witness that exited 0 having checked
almost nothing, and every layer above it reported success.

The list is bound to the plan HERE rather than to the loader's field access: the
expectation below is read out of the generated YAML by its own keys, so an edit
that stopped `endpoints()` reading a controller manager's skills fails even
though both sides of the comparison come from the same tree.

Nothing here brings a cell up. `endpoints()` is a pure function of a loaded plan,
and `main`'s refusal is reached before any ROS context is created.
"""

from __future__ import annotations

from pathlib import Path

from cite_bringup import readiness_witness
from cite_bringup.plan import load, resolve_uri
from cite_bringup.readiness_witness import endpoints, main
from cite_interfaces.action import Detect, Grasp, MoveTo, Pick, Place, Transfer
import pytest
import yaml

GENERATED_PLAN = "package://cite_generated/bringup/cell_a_plan.yaml"

#: The plan's own key for each skill action, and the type its server advertises.
#: Written out here rather than imported from the module under test, because a
#: test that reuses the mapping it is checking checks nothing.
_SKILL_TYPES = {
    "move_to": MoveTo,
    "pick": Pick,
    "place": Place,
    "grasp": Grasp,
    "transfer": Transfer,
}


def _generated() -> Path:
    return Path(resolve_uri(GENERATED_PLAN))


def _document() -> dict:
    return yaml.safe_load(_generated().read_text())


def _written(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def _declared(document: dict) -> set[tuple[str, type]]:
    """Every action the plan document declares, read from the YAML by its keys."""
    plan = document["plan"]
    declared: set[tuple[str, type]] = set()
    for manager in plan["controller_managers"]:
        skills = manager.get("skills")
        if skills is None:
            continue
        declared.update((skills[key], action) for key, action in _SKILL_TYPES.items())
    detection = plan.get("detection")
    if detection is not None:
        declared.add((detection["detect_action"], Detect))
    return declared


def test_the_condition_is_every_action_the_plan_declares() -> None:
    """The binding the witness had none of, in both directions.

    That nothing is MISSING is what stops a side announcing readiness while its
    third arm never came up. That nothing is EXTRA is what stops a witness
    waiting out its deadline on a name the plan does not carry.
    """
    wanted = endpoints(load(_generated()))
    assert set(wanted) == _declared(_document())
    # One entry per name, so a duplicated wait cannot stand in for a missing one.
    assert len(wanted) == len({name for name, _ in wanted})
    # And it is not empty on the shipped plan, which is what the refusal below
    # depends on being a real distinction.
    assert wanted


def test_a_plan_whose_managers_declare_no_skills_leaves_almost_nothing_to_wait_on(
    tmp_path: Path,
) -> None:
    """The measurement this file exists for, made a fact.

    `plan.load` accepts a plan with no `skills:` block on any controller manager
    - the field is optional, because a manager can exist before its skill server
    does - and it accepts it without complaint. So the shipped plan yields every
    arm's skills plus the zone's detection, and the same plan with `skills:`
    removed yields the detection alone. The witness used to exit 0 on that, and
    the launch announced the side ready.
    """
    document = _document()
    for manager in document["plan"]["controller_managers"]:
        manager.pop("skills", None)
    stripped = endpoints(load(_written(tmp_path, document)))
    assert set(stripped) == _declared(document)
    assert len(stripped) < len(endpoints(load(_generated())))


def test_a_plan_that_names_no_endpoint_at_all_is_refused_rather_than_satisfied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A witness may never answer that there was nothing to wait on.

    An empty condition is satisfied instantly, so the witness would exit 0, the
    launch would emit the readiness token, and the supervisor would report the
    pair up - over two cells serving nothing. Refused before a context is
    created, because there is nothing for a context to observe.
    """
    document = _document()
    for manager in document["plan"]["controller_managers"]:
        manager.pop("skills", None)
    # The sensors go with it: `plan.load` refuses sensors with no `detection:`
    # block, which is the one part of this shape the loader does catch. What it
    # does not catch is a plan that declares neither, which loads cleanly and
    # names nothing for the witness to observe.
    document["plan"].pop("detection", None)
    document["plan"].pop("sensors", None)
    path = _written(tmp_path, document)
    assert endpoints(load(path)) == []

    monkeypatch.setattr(readiness_witness, "default_plan_path", lambda zone="cell_a": path)
    assert main(["--zone", "cell_a", "--side", "plant"]) == 2
    assert "no action server" in capsys.readouterr().err
