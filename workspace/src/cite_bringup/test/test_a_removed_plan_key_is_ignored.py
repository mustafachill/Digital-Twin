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

"""A plan key the generator stopped emitting is ignored, not rejected.

ADR-0048 clause 3 removed `hosted_by` from the bring-up plan: it stated whether a
controller manager is created inside the Gazebo process or runs its own
`ros2_control_node`, it was a total function of the backend the plan already
states per side, and nothing read it. A consumer that needs the distinction
derives it from `ControllerManager.backend_on` instead.

**Why this is its own file.** The key is barred from every other source file
under `workspace/`, `tools/`, `tests/` and `scripts/` by
`tools/tests/test_a_removed_plan_key_stays_removed.py`, which exempts this one
and itself. A field is deleted so that nothing acquires a consumer for it, and a
guard with a scattering of exemptions cannot say that; a guard with two, each
whose whole subject is the removal, can.

**Why ignored rather than rejected**, which is a decision and not an oversight.
Turning a required key into a refused one would refuse the document most likely
to still carry it — a plan left in a stale build tree, or one a developer kept
from before the change — and the refusal would name a key where the cause is a
rebuild. `./scripts/validate-model` already refuses a stale committed tree, and
it names the regeneration.
"""

from __future__ import annotations

from pathlib import Path

from cite_bringup.plan import load, PlanError, resolve_uri
import pytest
import yaml

GENERATED_PLAN = "package://cite_generated/bringup/cell_a_plan.yaml"

#: The key itself. The one place in `workspace/` it may still be spelled.
REMOVED_KEY = "hosted_by"


def _generated_document() -> dict:
    return yaml.safe_load(Path(resolve_uri(GENERATED_PLAN)).read_text())


def test_the_generated_plan_no_longer_states_it() -> None:
    """The emission is gone, asked of the committed artifact rather than of the template."""
    document = _generated_document()
    for manager in document["plan"]["controller_managers"]:
        assert REMOVED_KEY not in manager, (
            f"{manager['asset']} still states {REMOVED_KEY!r}. The generated tree is "
            "stale - run ./scripts/validate-model --write, then ./scripts/build"
        )


def test_a_plan_carrying_the_removed_host_key_loads_cleanly(tmp_path: Path) -> None:
    """A stale plan still loads, and every field the reader does use survives it.

    Asserted on the loaded object and not only on the absence of an exception: a
    parser that swallowed the whole entry would also raise nothing.
    """
    document = _generated_document()
    for manager in document["plan"]["controller_managers"]:
        manager[REMOVED_KEY] = "simulator"
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))

    plan = load(path)
    assert [manager.asset for manager in plan.controller_managers] == [
        manager["asset"] for manager in document["plan"]["controller_managers"]
    ]
    for manager in plan.controller_managers:
        assert manager.backend == "sim"
        assert manager.controllers, f"{manager.asset} lost its controllers"
        assert not hasattr(manager, REMOVED_KEY), (
            f"the reader grew a {REMOVED_KEY!r} attribute again. The field was "
            "removed so that nothing could start reading it (ADR-0048, clause 3); "
            "what needs the distinction asks `ControllerManager.backend_on`"
        )


def test_the_reader_still_refuses_a_key_it_does_use(tmp_path: Path) -> None:
    """Ignoring is not the same as tolerating, and the difference is worth pinning.

    The removed key is ignored because nothing reads it. A key the reader DOES
    read is still required, so this cannot be read as the parser having become
    permissive.
    """
    document = _generated_document()
    del document["plan"]["controller_managers"][0]["backend"]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(PlanError, match="missing required key 'backend'"):
        load(path)
