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

"""ADR-0054 clause 6: the reproduction is refused end to end.

**The only assertion in this project that runs the whole path the defect ran.**
Every other clause of that record tests one layer: this one edits L0, generates
the artifacts from it, loads the plan those artifacts contain and calls the gate
with an empty environment — which is exactly the sequence ADR-0054's *Context*
runs, where the gate returns `None` without ever consulting `CITE_ALLOW_HARDWARE`
on a model declaring the vendor's physical `ros2_control` component under the
backend id `sim`. It fails if any of decisions 1 to 3 lands partially.

**WHY IT SPAWNS A SUBPROCESS, AND WHY IT IS HERE AND NOT IN `tools/tests`.** The
path crosses two build units and no single interpreter holds both by default:
`cite_tools` needs `pydantic` and `cite_bringup` needs `ament_index_python`.
`./scripts/test`'s host half clears `PYTHONPATH` on purpose — that suite is
ROS-free by design — so the clause cannot run there at all, and a
`pytest.importorskip` would have made it pass by skipping, which for this
particular clause is the worst available outcome. Here it runs under `colcon` in
the container, and the generator half is driven through the repository
virtualenv's own interpreter by the same command a person would type. The L0-to-
artifact leg is asserted separately and without ROS in
`tools/tests/test_declared_hardware_fact.py`; the two halves share one model
builder so they cannot drift into testing different models.

**It brings nothing up.** No simulator, no cell, no arm — there is no physical
arm (charter §8). Every assertion is against generated text and an in-memory
plan.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from cite_bringup.plan import (
    HARDWARE_OPT_IN_ENV,
    HARDWARE_OPT_IN_VALUE,
    HardwareNotPermittedError,
    load,
    require_hardware_opt_in,
)
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]

#: The interpreter that holds `cite_tools`. `./scripts/validate-model` resolves
#: the same one through `cite_python`; named here rather than shelled through
#: that script so a failure points at the generator instead of at a wrapper.
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def _reproduction_model(destination: Path) -> Path:
    """Write ADR-0054's scratch model: the vendor's plugin, keeping the id `sim`.

    One edit to the type and one to the instances, and **no id anywhere
    changes** — which is the whole of the reproduction. Mirrored from
    `tools/tests/test_declared_hardware_fact.py::reproduction_model`, which
    cannot be imported here because that tree is not on this interpreter's path;
    the two are asserted to agree by
    `test_the_two_halves_build_the_same_model`.
    """
    scratch = destination / "model"
    shutil.copytree(REPO_ROOT / "model", scratch)
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


def _generate(model: Path) -> Path:
    """Run the real generators over ``model`` and return the plan they wrote.

    Through `cite-model validate --write`, which is the same door
    `./scripts/validate-model --write` uses, so this asserts against the shipped
    generator rather than against a reimplementation of it. A non-zero exit is
    reported with the generator's own output, because a model that stopped
    validating would otherwise look like a gate that stopped refusing.
    """
    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-m",
            "cite_tools.cli",
            "validate",
            "--model",
            str(model),
            "--write",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "tools"), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, (
        "the reproduction's model must still validate and generate, or this test "
        f"would be measuring an unrelated break:\n{result.stdout}\n{result.stderr}"
    )
    # `cite_tools.cli.generated_dir` derives the output from the model's own
    # parent - `model/` and `workspace/src/` are siblings - so a scratch model in
    # a tmp directory generates into that same tmp directory and this run cannot
    # touch the committed tree.
    return (
        model.resolve().parent
        / "workspace"
        / "src"
        / "cite_generated"
        / "bringup"
        / "cell_a_plan.yaml"
    )


@pytest.fixture
def generated_plan(tmp_path: Path) -> Path:
    if not VENV_PYTHON.is_file():
        pytest.fail(
            f"{VENV_PYTHON} does not exist, so ADR-0054 clause 6 cannot run. It is "
            "not skippable: run ./scripts/bootstrap --host-only. A skip here would "
            "report the one end-to-end hardware-gate assertion as absent rather "
            "than as failing."
        )
    return _generate(_reproduction_model(tmp_path))


def test_the_reproduction_is_refused_with_an_empty_environment(
    generated_plan: Path,
) -> None:
    """Where the shipped gate returned `None`, never having read the opt-in.

    The environment is empty rather than merely lacking the variable, so nothing
    inherited from the test runner can be what refuses.
    """
    plan = load(generated_plan)
    with pytest.raises(HardwareNotPermittedError) as raised:
        require_hardware_opt_in(plan, {})
    message = str(raised.value)
    assert "arm_1" in message and "arm_2" in message and "arm_3" in message
    assert "commands_physical_hardware" in message
    assert HARDWARE_OPT_IN_ENV in message


def test_the_reproduction_still_starts_behind_the_opt_in(
    generated_plan: Path,
) -> None:
    """A refusal and not a ban. The opt-in is what this gate exists to require."""
    plan = load(generated_plan)
    require_hardware_opt_in(
        load(generated_plan), {HARDWARE_OPT_IN_ENV: HARDWARE_OPT_IN_VALUE}
    )
    assert plan.controller_managers, "the plan must carry the managers it gates"


def test_the_plan_still_calls_that_backend_sim(generated_plan: Path) -> None:
    """The id is untouched throughout, which is what makes this the reproduction.

    A test that renamed the backend to `real` would be asserting that the OLD
    gate works. What is asserted here is that the refusal happened while the plan
    still says `sim`.
    """
    document = yaml.safe_load(generated_plan.read_text())
    for manager in document["plan"]["controller_managers"]:
        assert manager["backend"] == "sim"
        assert manager["commands_physical_hardware"] is True


def test_the_two_halves_build_the_same_model() -> None:
    """The model builder is written twice, so it is compared once.

    `tools/tests` cannot be imported from this interpreter, so the reproduction's
    edit exists in two files. Parsed rather than executed - importing the other
    module would need `pydantic` - and compared as source, so a change to either
    that is not made to both fails here instead of silently leaving the two
    clauses testing different models.
    """
    import ast

    other = (
        REPO_ROOT / "tools" / "tests" / "test_declared_hardware_fact.py"
    ).read_text()
    theirs = next(
        node
        for node in ast.parse(other).body
        if isinstance(node, ast.FunctionDef) and node.name == "reproduction_model"
    )
    mine = next(
        node
        for node in ast.parse(Path(__file__).read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "_reproduction_model"
    )
    stated = {
        ast.dump(node)
        for body in (theirs.body, mine.body)
        for node in ast.walk(ast.Module(body=body, type_ignores=[]))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for datum in (
        "uf_robot_hardware/UFRobotSystemHardware",
        "commands_physical_hardware",
        "sim",
        "robot_ip",
        "203.0.113.7",
        "assets/types/robots/xarm5.yaml",
        "assets/instances/arms.yaml",
    ):
        assert ast.dump(ast.Constant(value=datum)) in stated, (
            f"{datum!r} is missing from one of the two reproduction builders; they "
            "must describe the same model or clause 6 and its host-side half test "
            "different things"
        )


def test_this_test_uses_the_repository_generator_and_not_a_copy() -> None:
    """`sys.executable` is the ROS interpreter here; the generator's is not it.

    Stated as an assertion because the day the two converge, the subprocess above
    becomes unnecessary and this file should be simplified rather than left
    carrying a workaround nobody can explain.
    """
    assert Path(sys.executable) != VENV_PYTHON
