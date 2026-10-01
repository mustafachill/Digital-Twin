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

"""Which cell a boundary spans is stated, never defaulted (ADR-0056 decision 4).

L5 is the one component in this system holding endpoints in BOTH domains, and it
computes a hardware gate from the backends its plan declares. A `--zone` that
defaulted to `cell_a` therefore decided, silently, which cell's two sides a
process was wired across and which cell's hardware declarations a mode change
was checked against.

The condition is genuinely `--zone OR --plan` rather than `required=True`: the
zone is used here for exactly one thing, locating the generated plan, and a
caller that passes a plan has already answered the question. So both branches
are tested — the refusal is worthless if it also refuses the paired launch tests,
and `required=True` would make those state the same fact twice.
"""

from __future__ import annotations

from cite_twin.twin_boundary import _arguments
import pytest


def test_naming_neither_a_zone_nor_a_plan_is_refused(capsys) -> None:
    """The refusing branch. Nothing reads a plan, because parsing exits first."""
    with pytest.raises(SystemExit) as exit_code:
        _arguments([])
    assert exit_code.value.code == 2
    message = capsys.readouterr().err
    assert "--zone" in message, message
    # The remedy has to name both doors, or a test author reading it adds a zone
    # to a launch test that was correctly passing a plan.
    assert "--plan" in message, message


def test_a_named_zone_is_accepted() -> None:
    arguments = _arguments(["--zone", "cell_b"])
    assert arguments.zone == "cell_b"
    assert arguments.plan == ""


def test_a_plan_alone_is_accepted() -> None:
    """The branch the two paired launch tests take.

    They drive L5 against a plan that declares a counterpart without editing L0,
    and they name no zone because the plan carries one. If this ever starts
    refusing, those tests stop testing the boundary and start testing argparse.
    """
    arguments = _arguments(["--plan", "/tmp/whatever_plan.yaml"])
    assert arguments.plan == "/tmp/whatever_plan.yaml"
    assert arguments.zone == ""


def test_arguments_this_parser_does_not_own_are_still_ignored() -> None:
    """`launch_ros` appends `--ros-args` unconditionally, and that is not an error.

    Asserted beside the refusal because the two share one `parse_known_args`
    call: a refusal implemented with `parse_args` would satisfy every test above
    and make every launched boundary die on an argument ROS itself added.
    """
    arguments = _arguments(["--zone", "cell_b", "--ros-args", "-r", "__ns:=/cite/twin"])
    assert arguments.zone == "cell_b"


# --- and they may not disagree ------------------------------------------------


def test_a_zone_that_contradicts_the_plan_is_refused(capsys) -> None:
    """`--zone cell_b --plan .../cell_a_plan.yaml` used to span `cell_a` silently.

    `--zone` is never read again once the plan is located: `main` spans
    `plan.zone`. So the conditional in `_arguments` was satisfied by an argument
    that then decided nothing, and the caller's stated intention and the cell
    actually wired across were two different things with no error anywhere.

    Driven through `main`, which is where the comparison is: `_arguments` cannot
    make it, because it has not read the plan yet.
    """
    from cite_bringup.plan import default_plan_path
    from cite_twin.twin_boundary import main

    other = "cell_b" if default_plan_path("cell_a").is_file() else "cell_a"
    assert main(["--zone", other, "--plan", str(default_plan_path("cell_a"))]) == 2
    message = capsys.readouterr().err
    assert other in message and "cell_a" in message, message


def test_a_zone_that_agrees_with_the_plan_is_not_refused(capsys) -> None:
    """The other half. Stating the same fact twice is redundant, not wrong.

    It gets past the comparison and fails later for its own reason — `cell_a`,
    the zone this case names, declares `sides: single` and a boundary needs two
    (ADR-0059 pairs `cell_b` and leaves this one alone) — which is what shows the
    comparison let it through rather than stopping it.
    """
    from cite_bringup.plan import default_plan_path
    from cite_twin.twin_boundary import main

    assert main(["--zone", "cell_a", "--plan", str(default_plan_path("cell_a"))]) == 2
    assert "cannot both be honoured" not in capsys.readouterr().err
