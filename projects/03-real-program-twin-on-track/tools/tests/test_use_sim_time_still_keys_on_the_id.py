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

"""Characterisation tests for a gap ADR-0054 deliberately did not close.

**NOTHING HERE IS A REQUIREMENT.** Both tests below assert what the generator
does today and both describe a defect. They exist so that a later reader does not
infer from ADR-0054's title — which is about keying a hardware gate on a declared
fact rather than on a backend's name — that the same defect was closed for the
clock. It was not: `generate/control.py` still derives `use_sim_time` from the
backend ID, and ADR-0054's Context measures that rule wrong in both directions.

WHY IT WAS LEFT (ADR-0054, decision 2). `use_sim_time` asks *does this
controller manager take its clock from the simulator*, which is a different
question from *can this backend reach a physical machine*. The two coincide on
the two backends this repository declares and diverge on the third kind, which
is in this checkout twice: `mock_components/GenericSystem`, loaded by four
`cite_bringup` launch rigs of which three want `use_sim_time: false` and the
fourth wants it `true`; and the vendor's `UFRobotFakeSystemHardware`, which
nothing forbids naming in `model/`. Deriving the clock from the safety fact would
transcribe a coincidence, which is the move ADR-0054 exists to refuse.

**THE SECOND TEST IS THE DIRECTION ADR-0054 UNBLOCKED, AND THAT IS WHY THERE ARE
TWO.** A Gazebo plugin declared under the id `real` is refused at bring-up today
ONLY because the gate keys on the id — a false refusal, but a loud one, and
currently the only thing stopping that model from starting. After ADR-0054 the
same model declares `commands_physical_hardware: false`, is correctly permitted,
and starts a Gazebo-driven arm on `use_sim_time: false`: CLAUDE.md §10's "a
mixed-time system produces plausible, wrong results". ADR-0054's *What promotion
does not claim* traces the consequence — every quantity in that control path,
including ADR-0036's tolerances and every deadline, is then owned by a process
that is not the arm, and if the simulator stalls mid-trajectory none of them ever
expires while the arm holds its last command.

Neither test may be "fixed" by widening anything. What closes them is a record
that decides whether the clock is a per-backend fact at all.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cite_tools.generate.control import generate
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve


def _controllers_yaml(model_dir: Path) -> str:
    cell = resolve(load(model_dir), "cell_a")
    arm = next(a for a in generate(cell) if a.path.endswith("cell_a_arm_1_controllers.yaml"))
    return arm.content


def test_a_physical_backend_named_sim_still_generates_use_sim_time_true(
    real_model: Path, edit_yaml: Callable
) -> None:
    """The physical direction. A characterisation of a known gap, not a rule.

    After ADR-0054 this model is refused at bring-up, so reaching it needs either
    a deliberate `CITE_ALLOW_HARDWARE` opt-in or a false declaration. That is
    what makes it a residual rather than a blocker — it is never the first thing
    that has to go wrong.
    """
    edit_yaml(
        real_model / "assets/types/robots/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["sim"].update(
            {
                "ros2_control_plugin": "uf_robot_hardware/UFRobotSystemHardware",
                "commands_physical_hardware": True,
            }
        ),
    )
    assert "use_sim_time: true" in _controllers_yaml(real_model), (
        "the clock still keys on the backend id, so a PHYSICAL arm selecting a "
        "backend named `sim` is configured to take its time from the simulator "
        "(ADR-0054, decision 2)"
    )


def test_a_simulated_backend_named_real_still_generates_use_sim_time_false(
    real_model: Path, edit_yaml: Callable
) -> None:
    """The direction ADR-0054 unblocked, and the one that produces a running cell.

    Nothing refuses this model after ADR-0054 — correctly, because nothing
    physical is there — and it starts an arm Gazebo drives under the wrong clock.
    """
    edit_yaml(
        real_model / "assets/types/robots/xarm5.yaml",
        lambda d: d["asset_type"]["hardware_backends"]["real"].update(
            {
                "ros2_control_plugin": "gz_ros2_control/GazeboSimSystem",
                "commands_physical_hardware": False,
                "instance_params": [],
            }
        ),
    )
    edit_yaml(
        real_model / "assets/instances/arms.yaml",
        lambda d: [
            asset["hardware"].__setitem__("backend", "real")
            for asset in d["assets"]
            if asset.get("hardware")
        ],
    )
    assert "use_sim_time: false" in _controllers_yaml(real_model), (
        "the clock still keys on the backend id, so a GAZEBO-DRIVEN arm selecting "
        "a backend named `real` is configured off the simulator's clock "
        "(ADR-0054, decision 2)"
    )
