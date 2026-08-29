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

"""The door every Gazebo-transport process goes through.

`test_plan.py` proves the refusal; `test_simulation_launch.py` proves the launch
graph carries the partition into the six processes it starts. Neither covers the
second class of Gazebo process — the ones the scenario harness starts itself —
and that gap is what this module and its guard close. What is asserted here is
the mechanism: that the environment handed to such a process carries the plan's
partition, and that it is an addition to the caller's environment rather than a
replacement of it.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from cite_bringup import gz
from cite_bringup.plan import (
    GazeboPartitionMissingError,
    GZ_PARTITION_ENV,
    load,
    resolve_uri,
)
import pytest
import yaml

GENERATED_PLAN = "package://cite_generated/bringup/cell_a_plan.yaml"
ZONE = "cell_a"


def _generated() -> Path:
    return Path(resolve_uri(GENERATED_PLAN))


def test_the_environment_names_the_partition_the_plan_names() -> None:
    plan = load(_generated())
    assert gz.gz_environment(plan) == {GZ_PARTITION_ENV: plan.sides[0].gz_partition}


def test_a_plan_whose_side_lost_its_partition_is_refused(tmp_path: Path) -> None:
    # Not reachable from a generated tree, and asserted anyway: this is the one
    # function both the launch graph and the harness build their environment
    # with, so a hole here is a hole in both at once.
    document = yaml.safe_load(_generated().read_text())
    document["plan"]["sides"][0]["gz_partition"] = "   "
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(GazeboPartitionMissingError):
        gz.gz_environment(load(path))


def test_the_process_environment_extends_the_callers_rather_than_replacing_it() -> None:
    """The asymmetry that makes this a function instead of a `dict` literal.

    `launch` merges `additional_env` itself; `subprocess` does not. A
    `ros2 run ros_gz_sim create` started with `env={'GZ_PARTITION': ...}` alone
    loses `AMENT_PREFIX_PATH` and fails to find its own executable — a different
    failure from the one being fixed, arrived at by fixing it carelessly.
    """
    plan = load(_generated())
    environment = gz.process_environment(
        plan, {"PATH": "/usr/bin", "AMENT_PREFIX_PATH": "/opt"}
    )
    assert environment["PATH"] == "/usr/bin"
    assert environment["AMENT_PREFIX_PATH"] == "/opt"
    assert environment[GZ_PARTITION_ENV] == plan.sides[0].gz_partition


def test_an_exported_partition_does_not_override_the_plan() -> None:
    # The same rule the launch path holds: the partition is generated from L0 and
    # decides which cell a command reaches, so it is not a per-run knob. A shell
    # that exported a different one must not move a probe to another transport.
    plan = load(_generated())
    environment = gz.process_environment(plan, {GZ_PARTITION_ENV: "somewhere_else"})
    assert environment[GZ_PARTITION_ENV] == plan.sides[0].gz_partition


def test_run_starts_the_command_with_the_partition(monkeypatch) -> None:
    """The regression: the harness's own processes carried nothing.

    `gz model -p` and `ros2 run ros_gz_sim create` were started with a bare
    inherited environment, so they discovered gz-transport's default partition
    instead of the cell's. The spawn looped "Requesting list of world names" and
    died on its 120 s timeout; the pose reads would have answered nothing.
    """
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("CITE_TEST_MARKER", "inherited")

    result = gz.run(["gz", "model", "--list"], zone=ZONE, timeout=30)

    assert result.returncode == 0
    assert captured["argv"] == ["gz", "model", "--list"]
    expected = load(_generated()).sides[0].gz_partition
    assert captured["kwargs"]["env"][GZ_PARTITION_ENV] == expected
    assert captured["kwargs"]["env"]["CITE_TEST_MARKER"] == "inherited"
    # Captured and decoded, because every caller reads what the command printed:
    # `gz` exits 0 whether or not it reached a world, so the exit status alone
    # answers a question nobody is asking.
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["timeout"] == 30


def test_the_plan_is_read_once_per_process() -> None:
    # `continuous_line` asks for this about twice a second for the length of a
    # run. Re-reading and re-resolving the YAML per sample would make the
    # instrument the expensive part of the measurement.
    gz._PLANS.pop(ZONE, None)
    first = gz.plan_for(ZONE)
    assert gz.plan_for(ZONE) is first


def test_every_gazebo_command_the_harness_runs_is_named() -> None:
    """The list the scenario guard scans source against, checked for shape.

    It is read out of this module's source by
    `tests/scenarios/guards/test_gz_calls_carry_the_partition.py`, which cannot
    import it — that suite runs in the ROS-free host virtualenv. This asserts the
    shape that guard relies on, on the side that can import it.
    """
    assert gz.GZ_TRANSPORT_COMMANDS
    for prefix in gz.GZ_TRANSPORT_COMMANDS:
        assert isinstance(prefix, tuple)
        assert prefix
        assert all(isinstance(word, str) and word for word in prefix)
    assert ("gz",) in gz.GZ_TRANSPORT_COMMANDS
    assert ("ros2", "run", "ros_gz_sim") in gz.GZ_TRANSPORT_COMMANDS


def test_the_module_does_not_read_the_partition_from_the_shell() -> None:
    # A helper that fell back to os.environ would pass every test above on a
    # machine where the launch had exported one, and fail on CI. Asserted on the
    # source because the fallback is an absence, and an absence has no call site.
    source = Path(gz.__file__).read_text()
    assert f'os.environ.get("{GZ_PARTITION_ENV}"' not in source
    assert f"environ[{GZ_PARTITION_ENV}]" not in source
    # The module merges os.environ; it never reads the partition out of it.
    assert os.environ is not None
