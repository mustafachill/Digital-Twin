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

"""Guard: no test starts a Gazebo-transport process outside the partitioned door.

The defect this closes, stated as a class rather than as an incident: **a
gz-transport subprocess started without `GZ_PARTITION`, failing silently.**

ADR-0042 made the partition structural for the launch graph — the environment is
built from the plan and bring-up refuses without it — and the guarantee stopped
exactly at the edge of the launch graph. The scenario harness starts its own
gz-transport processes: `ros2 run ros_gz_sim create` to spawn a work-piece,
`gz model -p` to read where it went, `gz model --list` to diagnose, `gz service`
to remove it. Every one of them carried a bare inherited environment. The spawn
hung for 120 s and raised `TimeoutExpired`; the pose reads would simply have
returned nothing, which is worse, because "the work-piece is nowhere" is a
sentence this harness has an assertion for and a diagnosis it does not.

Care is not a control. This is, and it is deliberately blunt: any call in
`tests/` whose argument vector begins with a Gazebo-transport command must be the
helper that sets the partition, and any other caller fails here — with the name
of the file and the line. It does not check that the helper is *correct*; that is
`cite_bringup`'s own suite. It checks that nothing goes around it.

Two things keep the check honest. The leading-word list is read out of
`cite_bringup/gz.py` rather than restated here, so a new kind of Gazebo command
extends the mechanism and the guard in one edit (P1). And the detector is run
against a crafted bad source and a crafted good one, so a detector that has
quietly stopped matching anything fails instead of passing.

**What it cannot see.** An argv assembled at run time, or a command passed as a
shell string, is invisible to a source scan. Neither exists in `tests/` today and
the test below counts what it did find, so a rewrite into that shape shows up as
the count changing rather than as silence.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_ROOT = REPO_ROOT / "tests"

#: Where the leading-word list lives. Read as source rather than imported: this
#: suite runs in the ROS-free host virtualenv (ADR-0013), where `cite_bringup` is
#: a workspace package and is not importable at all.
GZ_MODULE = REPO_ROOT / "workspace" / "src" / "cite_bringup" / "cite_bringup" / "gz.py"

#: The module every partitioned call must come from, and the function within it.
HELPER_MODULE = "cite_bringup.gz"
HELPER_FUNCTION = "run"


def gz_transport_commands() -> tuple[tuple[str, ...], ...]:
    """The leading words of every command that speaks the Gazebo transport.

    Fail-closed on every way this can go wrong — a moved module, a renamed
    constant, a value that is no longer a literal. A guard that silently falls
    back to an empty list would pass on a tree with the defect in it, which is
    the failure mode this whole file exists to remove.
    """
    if not GZ_MODULE.is_file():
        pytest.fail(
            f"{GZ_MODULE} does not exist. It is where the partitioned door lives; "
            "if it moved, move this guard with it rather than deleting the check."
        )
    tree = ast.parse(GZ_MODULE.read_text(), filename=str(GZ_MODULE))
    for node in tree.body:
        targets = [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "GZ_TRANSPORT_COMMANDS":
                if node.value is None:
                    continue
                return tuple(tuple(entry) for entry in ast.literal_eval(node.value))
    pytest.fail(
        f"{GZ_MODULE} no longer defines GZ_TRANSPORT_COMMANDS as a literal. That list is "
        "the one statement of which commands speak the Gazebo transport; this guard reads "
        "it rather than keeping a second copy."
    )
    raise AssertionError("unreachable")  # pragma: no cover - pytest.fail does not return


def _leading_words(node: ast.AST) -> tuple[str, ...]:
    """The constant strings at the front of a list-literal argument vector."""
    if not isinstance(node, ast.List | ast.Tuple):
        return ()
    words: list[str] = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            words.append(element.value)
        else:
            break
    return tuple(words)


def _callee(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_callee(node.value)}.{node.attr}"
    return "<expression>"


def _approved_names(tree: ast.Module) -> set[str]:
    """Local names this module bound to the partitioned helper.

    Taken from the module's own imports rather than matched against a hard-coded
    alias, so the check is "this call is the function in `cite_bringup.gz`" and
    not "this call is spelled `gz_run`".
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == HELPER_MODULE:
            for alias in node.names:
                if alias.name == HELPER_FUNCTION:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == HELPER_MODULE and alias.asname is None:
                    names.add(f"{HELPER_MODULE}.{HELPER_FUNCTION}")
                elif alias.name == HELPER_MODULE:
                    names.add(f"{alias.asname}.{HELPER_FUNCTION}")
    return names


def unpartitioned_calls(source: str, filename: str) -> list[tuple[int, str, tuple[str, ...]]]:
    """Every call in ``source`` that starts a Gazebo command outside the helper."""
    commands = gz_transport_commands()
    tree = ast.parse(source, filename=filename)
    approved = _approved_names(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        words = _leading_words(node.args[0])
        if not any(words[: len(prefix)] == prefix for prefix in commands):
            continue
        if _callee(node.func) in approved:
            continue
        found.append((node.lineno, _callee(node.func), words))
    return found


def python_files() -> list[Path]:
    return sorted(TESTS_ROOT.rglob("*.py"))


@pytest.mark.parametrize("path", python_files(), ids=lambda p: str(p.relative_to(TESTS_ROOT)))
def test_no_test_starts_a_gazebo_process_outside_the_partitioned_helper(path: Path) -> None:
    offences = unpartitioned_calls(path.read_text(), str(path))
    assert not offences, "\n".join(
        f"{path}:{line}: {callee}({list(words)}...) starts a Gazebo-transport process "
        f"without the partition. Route it through "
        f"`from {HELPER_MODULE} import {HELPER_FUNCTION}`: without GZ_PARTITION the "
        "command discovers a different transport, and it does not fail — it hangs, or "
        "answers nothing (ADR-0042)."
        for line, callee, words in offences
    )


def test_the_detector_fires_on_a_call_that_goes_around_the_helper() -> None:
    """A detector that matches nothing passes every file. Check it still bites."""
    bad = (
        "import subprocess\n"
        "subprocess.run(['gz', 'model', '--list'], timeout=30)\n"
        "subprocess.Popen(['ros2', 'run', 'ros_gz_sim', 'create', '-file', 'x.sdf'])\n"
    )
    offences = unpartitioned_calls(bad, "<crafted>")
    assert [line for line, _, _ in offences] == [2, 3]


def test_the_detector_accepts_a_call_that_goes_through_the_helper() -> None:
    good = (
        f"from {HELPER_MODULE} import {HELPER_FUNCTION} as gz_run\n"
        "gz_run(['gz', 'model', '--list'], zone='cell_a', timeout=30)\n"
    )
    assert unpartitioned_calls(good, "<crafted>") == []


def test_the_scan_actually_reaches_the_scenario_call_sites() -> None:
    """The guard must be looking at real Gazebo calls, not at an empty tree.

    Counted rather than asserted as non-zero: an argv assembled at run time is
    invisible to a source scan, so a rewrite into that shape has to change this
    number and be argued, instead of quietly emptying the guard.
    """
    commands = gz_transport_commands()
    seen = 0
    for path in python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                words = _leading_words(node.args[0])
                if any(words[: len(prefix)] == prefix for prefix in commands):
                    seen += 1
    assert seen == 7, (
        f"the guard found {seen} Gazebo command sites under tests/, not the 7 it was "
        "written against: two spawns, two pose reads, two diagnostics listings, one "
        "removal. If a call was added, this number moves with it; if one vanished, "
        "check it was not rewritten into an argv this scan cannot see."
    )
