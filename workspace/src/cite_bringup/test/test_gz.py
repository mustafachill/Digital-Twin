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
import sys
import time

from cite_bringup import gz
from cite_bringup.plan import (
    GazeboPartitionMissingError,
    GZ_PARTITION_ENV,
    load,
    resolve_uri,
)
import pytest
import yaml

GENERATED_PLAN = "package://cite_generated/bringup/cell_b_plan.yaml"
ZONE = "cell_b"


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


def test_a_reordered_plan_still_yields_the_plants_partition(tmp_path: Path) -> None:
    """The regression for asking by name instead of by `plan.sides[0]`.

    Nothing in the plan schema fixes the order of `sides:`, and nothing needs to:
    each entry states its own name and its own offset precisely so that position
    carries no meaning (ADR-0044, clause 4). So a plan listing the counterpart
    first is a well-formed plan, and against `plan.sides[0]` this module answers
    it with the COUNTERPART's partition while calling it the plant.

    That failure is silent by construction, which is the whole reason this module
    exists: a process on the wrong partition does not error, it discovers an
    empty topic list and waits. Reverting `gz.py` to `plan.sides[0]` fails this
    test and nothing else in the suite — verified.
    """
    document = yaml.safe_load(_generated().read_text())
    plant = document["plan"]["sides"][0]
    counterpart = {
        "name": "counterpart",
        "gz_partition": f"cite/{ZONE}/counterpart",
        "domain_offset": 1,
        "gui_config": f"package://cite_generated/worlds/counterpart/{ZONE}_gui.config",
    }
    # The counterpart first, which is the ordering the generator does not emit
    # today and that no rule forbids a future one from emitting.
    document["plan"]["sides"] = [counterpart, plant]
    for manager in document["plan"]["controller_managers"]:
        manager["counterpart_backend"] = manager["backend"]
        manager["counterpart_commands_physical_hardware"] = manager[
            "commands_physical_hardware"
        ]
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(document))

    plan = load(path)
    assert [side.name for side in plan.sides] == ["counterpart", "plant"]
    assert gz.gz_environment(plan) == {GZ_PARTITION_ENV: plant["gz_partition"]}
    assert gz.gz_environment(plan)[GZ_PARTITION_ENV] != counterpart["gz_partition"]


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


class _FakeNode:
    """Stands in for `gz.transport13.Node` so no snapshot reaches a real partition."""

    instances: list = []

    def __init__(self, options) -> None:
        self.partition = options.partition
        self.subscribed: dict = {}
        self.unsubscribed: list[str] = []
        _FakeNode.instances.append(self)

    def subscribe_raw(self, topic, callback, msg_type, options) -> bool:
        self.subscribed[topic] = (callback, msg_type)
        return True

    def unsubscribe(self, topic) -> bool:
        self.unsubscribed.append(topic)
        return True


def _snapshot(**models: tuple[float, float, float]) -> bytes:
    from gz.msgs10.pose_v_pb2 import Pose_V

    message = Pose_V()
    for name, (x, y, z) in models.items():
        pose = message.pose.add()
        pose.name = name
        pose.position.x, pose.position.y, pose.position.z = x, y, z
    return message.SerializeToString()


def test_model_poses_answers_from_the_newest_snapshot_only(monkeypatch) -> None:
    """One subscription, on the plan's partition; absence is read, never remembered.

    A wait for a work-piece's removal depends on the last clause: a cached
    pose from before the removal would keep the work-piece "in the world" for
    ever.
    """
    import importlib

    transport = importlib.import_module("gz.transport13")
    monkeypatch.setattr(transport, "Node", _FakeNode)
    _FakeNode.instances.clear()

    poses = gz.ModelPoses(zone=ZONE, world="w")
    (node,) = _FakeNode.instances
    assert node.partition == load(_generated()).sides[0].gz_partition
    callback, msg_type = node.subscribed["/world/w/dynamic_pose/info"]
    assert msg_type == "gz.msgs.Pose_V"

    assert poses.position("workpiece") is None, "no snapshot yet is not a pose"
    callback(_snapshot(link=(9.0, 9.0, 9.0), workpiece=(0.5, -0.25, 1.0)), None)
    assert poses.position("workpiece") == (0.5, -0.25, 1.0)
    callback(_snapshot(link=(9.0, 9.0, 9.0)), None)
    assert poses.position("workpiece") is None, "a removed model kept its old pose"

    poses.close()
    poses.close()
    assert node.unsubscribed == ["/world/w/dynamic_pose/info"]
    assert poses.position("workpiece") is None


def test_the_plan_is_read_once_per_process() -> None:
    # A scenario polling a pose asks for this about twice a second for the
    # length of a run. Re-reading and re-resolving the YAML per sample would make the
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


def test_a_command_run_with_a_stop_is_killed_when_the_stop_comes() -> None:
    """ADR-0071: the console's stop reaches a spawn in flight rather than waiting it out."""
    asked: list[int] = []

    def interrupted() -> bool:
        asked.append(1)
        return len(asked) > 2

    started = time.monotonic()
    with pytest.raises(gz.CommandInterrupted):
        gz.run(["sleep", "30"], zone=ZONE, timeout=60, interrupted=interrupted)
    assert time.monotonic() - started < 10.0


def test_a_command_run_with_a_stop_answers_as_without_one() -> None:
    result = gz.run(
        ["sh", "-c", "echo out; echo err >&2; exit 3"],
        zone=ZONE,
        timeout=30,
        interrupted=lambda: False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (3, "out\n", "err\n")


def test_a_command_run_with_a_stop_still_has_its_ceiling() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        gz.run(["sleep", "30"], zone=ZONE, timeout=0.3, interrupted=lambda: False)


#: A command that forks a child holding its output pipes, as `ros2 run` forks
#: the executable it wraps; the child's pid is printed first.
_FORKING = ["bash", "-c", "sleep 30 & echo $!; wait"]


def _gone(pid: int) -> bool:
    """Whether ``pid`` no longer runs: absent, or a zombie waiting for its reaper."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return True
    return state == "Z"


def _until_gone(pid: int, what: str) -> None:
    """Wait, within a bound, for ``pid`` to be gone or a zombie; fail otherwise."""
    deadline = time.monotonic() + 5.0
    while not _gone(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _gone(pid), what


def test_a_stop_kills_a_forked_child_holding_the_pipes(tmp_path: Path) -> None:
    """R2-01: a stop reaches the wrapper's child too, and never waits on its pipes.

    The child's pid is written to a file rather than read off the output the
    stop discards, and the stop comes only once it is there (R-02): the child
    itself is then watched until it is gone, rather than its group asked once
    while the kernel may still be tearing the group down.
    """
    pid_file = tmp_path / "child.pid"
    forking = ["bash", "-c", f"sleep 30 & echo $! > {pid_file}; wait"]

    def interrupted() -> bool:
        return pid_file.exists() and pid_file.read_text().strip() != ""

    started = time.monotonic()
    with pytest.raises(gz.CommandInterrupted):
        gz.run(forking, zone=ZONE, timeout=60, interrupted=interrupted)
    assert time.monotonic() - started < 10.0
    _until_gone(int(pid_file.read_text()), "the forked child outlived the stop")


def test_a_command_dies_with_the_process_that_started_it(tmp_path: Path) -> None:
    """R-01: its own session takes it out of the caller's group; its starter's end still kills it.

    A starter killed with SIGKILL runs no cleanup at all, as a console the
    supervisor had to kill: the command it started is killed by the kernel.
    """
    pid_file = tmp_path / "command.pid"
    starter = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; from cite_bringup import gz; "
            "gz.run(['bash', '-c', 'echo $$ > ' + sys.argv[1] + '; exec sleep 30'], "
            "zone=sys.argv[2], timeout=60, interrupted=lambda: False)",
            str(pid_file),
            ZONE,
        ]
    )
    try:
        deadline = time.monotonic() + 30.0
        while not (pid_file.exists() and pid_file.read_text().strip()):
            assert starter.poll() is None, "the starter ended before its command began"
            assert time.monotonic() < deadline, "the command never began"
            time.sleep(0.05)
        command = int(pid_file.read_text())
        # In a session of its own, so the starter's group does not hold it.
        assert os.getsid(command) == command
        starter.kill()
        starter.wait(timeout=10)
        _until_gone(command, "the command outlived the process that started it")
    finally:
        if starter.poll() is None:
            starter.kill()
            starter.wait(timeout=10)


def test_the_death_signal_is_set_by_a_prefix_and_no_python_runs_in_the_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-02: `setpriv` sets it before the command; `Popen` is handed no `preexec_fn`."""
    seen: dict = {}

    class Recorded(Exception):
        pass

    def popen(args, **kwargs):
        seen.update(kwargs, args=args)
        raise Recorded

    monkeypatch.setattr(gz.subprocess, "Popen", popen)
    with pytest.raises(Recorded):
        gz.run(["gz", "topic", "-l"], zone=ZONE, timeout=1, interrupted=lambda: False)
    assert "preexec_fn" not in seen and seen["start_new_session"] is True
    prefix = gz._die_with_the_caller(os.getpid())
    assert seen["args"] == [*prefix, "gz", "topic", "-l"]
    assert prefix[:4] == ["setpriv", "--pdeathsig", "KILL", "--"]


def test_a_command_whose_starter_is_already_gone_never_runs() -> None:
    """R-01's race, kept by the prefix: a parent that is not the starter exits at once."""
    marker = "the command ran"
    own = subprocess.run(
        [*gz._die_with_the_caller(os.getpid()), "echo", marker],
        capture_output=True, text=True, timeout=10,
    )
    assert own.returncode == 0 and own.stdout.strip() == marker
    # No starter can have pid 0, so this child's parent is never it.
    gone = subprocess.run(
        [*gz._die_with_the_caller(0), "echo", marker],
        capture_output=True, text=True, timeout=10,
    )
    assert gone.returncode == 1 and marker not in gone.stdout


def test_the_ceiling_kills_a_forked_child_holding_the_pipes() -> None:
    """R2-01: the deadline path kills the group too, and returns what was printed."""
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        gz.run(_FORKING, zone=ZONE, timeout=0.5, interrupted=lambda: False)
    assert time.monotonic() - started < 10.0
    child = int(raised.value.output.split()[0])
    deadline = time.monotonic() + 5.0
    while not _gone(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _gone(child), "the forked child outlived the ceiling"
