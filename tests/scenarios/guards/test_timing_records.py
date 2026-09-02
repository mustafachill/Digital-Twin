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

"""Guard: the `CITE_TIMING` record has one shape, and all three scenarios write it.

The defect this closes, stated as a class rather than as an incident: **a machine
-readable record emitted by three files, consumed by a parser none of them can
see, bound by no test.**

`CITE_TIMING` exists so that a measurement campaign can re-derive this project's
wall-clock scenario ceilings from measurement instead of from the proxies
`docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md` §3 had to
use. The records are printed by three scenario modules, are read by a parser that
does not exist yet, and will be read into a `criteria.md` that is FROZEN before
its first trial. A key silently renamed in one of the three, or added in one and
not the others, is not a test failure anywhere — it is a column that is empty for
a third of the table, discovered after the thresholds are locked.

So this asserts the contract itself, with nothing ROS-shaped in the way: the
`CITE_TIMING ` prefix, one line, `json.loads`-parseable, and the exact key set —
no more and no fewer keys, in every scenario.

**What it cannot see.** It calls the emitter directly, so it proves what the
writer writes, not that any particular wait calls it. Which intervals emit at all
is a property of the scenarios and is stated in each `_spin_until` docstring; a
wait that stops calling `_emit_timing` is invisible here. The
`test_every_scenario_has_exactly_one_writer` check below is the partial
compensation: it fails if the format is printed from anywhere but the one method.
"""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

import pytest

#: The sibling guard that already knows how to execute a scenario module without
#: ROS. Imported rather than copied: it owns the stub finder, the by-path loader
#: and the allowlist of ROS-provided modules, and two copies of that machinery
#: would drift. The `sys.path` insert makes the import independent of pytest's
#: collection order — under the default `prepend` import mode pytest inserts this
#: directory itself, but only once it has collected a file from it, and this
#: module must not depend on being collected second.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_scenario_modules_load as loader

#: Every key a `CITE_TIMING` record carries, and the type each must have. This is
#: the contract. Adding a key here without adding it to all three scenarios fails
#: below, which is the point: the campaign parser is written against this set.
EXPECTED_KEYS: dict[str, type | tuple[type, ...]] = {
    "scenario": str,
    "test": str,
    "what": str,
    "ceiling_s": float,
    "elapsed_s": float,
    "spins": int,
    "monotonic_s": float,
}

#: The prefix a consumer greps for. One space, then the JSON object.
PREFIX = "CITE_TIMING "

#: A method name that no scenario defines, so a record echoing it proves the
#: field is read from the running test rather than hard-coded.
FAKE_TEST_METHOD = "test_a_name_no_scenario_defines"


def _emitters() -> list[tuple[Path, object]]:
    """Load every scenario and return its `_emit_timing`, unbound.

    Unbound on purpose. Constructing the `TestCase` would need `setUpClass`, which
    calls `rclpy.init()` and brings a ROS context up; the emitter reads exactly one
    attribute off `self` and is called below with a stand-in that has it.
    """
    found: list[tuple[Path, object]] = []
    dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for path in loader.scenario_paths():
            with loader._ros_stubs():
                module = loader._load_like_launch_test(path)
            emitters = [
                value._emit_timing
                for value in vars(module).values()
                if isinstance(value, type) and "_emit_timing" in vars(value)
            ]
            assert len(emitters) == 1, (
                f"{path.name} defines {len(emitters)} classes with an `_emit_timing`; "
                "the record has one writer per scenario"
            )
            found.append((path, emitters[0]))
    finally:
        sys.dont_write_bytecode = dont_write_bytecode
    return found


def _emit(emitter, **kwargs) -> None:
    emitter(
        types.SimpleNamespace(_testMethodName=FAKE_TEST_METHOD),
        kwargs.pop("what", 'a milestone with "quotes" and a , comma'),
        kwargs.pop("ceiling_s", 420.0),
        kwargs.pop("elapsed_s", 1.23456),
        kwargs.pop("spins", 7),
    )


@pytest.fixture(scope="module")
def emitters() -> list[tuple[Path, object]]:
    return _emitters()


def test_at_least_three_scenarios_are_checked(emitters) -> None:
    """A guard that silently checks nothing is not a guard.

    If a scenario stops defining `_emit_timing`, `_emitters` raises. If the
    scenario directory moves, it returns an empty list and every test below
    passes vacuously. This is the tripwire for the second case.
    """
    assert len(emitters) >= 3, (
        f"found {len(emitters)} scenario emitter(s); bringup, pick_and_place and "
        "continuous_line all write this format"
    )


def test_the_record_is_one_parseable_line_with_the_exact_key_set(emitters, capsys) -> None:
    """The contract, asserted for every scenario at once."""
    for path, emitter in emitters:
        _emit(emitter)
        out = capsys.readouterr().out
        assert out.endswith("\n"), f"{path.name}: the record is not terminated"
        lines = out.rstrip("\n").split("\n")
        assert len(lines) == 1, (
            f"{path.name}: emitted {len(lines)} lines. A consumer reads this stream "
            f"line by line out of a launch log:\n{out}"
        )
        line = lines[0]
        assert line.startswith(PREFIX), f"{path.name}: {line!r} does not start with {PREFIX!r}"

        record = json.loads(line[len(PREFIX) :])
        assert isinstance(record, dict), f"{path.name}: the payload is not a JSON object"
        assert set(record) == set(EXPECTED_KEYS), (
            f"{path.name}: key set is {sorted(record)}, contract is "
            f"{sorted(EXPECTED_KEYS)}. Missing: {sorted(set(EXPECTED_KEYS) - set(record))}; "
            f"unexpected: {sorted(set(record) - set(EXPECTED_KEYS))}"
        )
        for key, kind in EXPECTED_KEYS.items():
            # `bool` is an `int` and would pass `spins`; nothing emits one today,
            # and a rule that would not notice is not worth writing.
            assert not isinstance(record[key], bool), f"{path.name}: {key} is a bool"
            assert isinstance(record[key], kind), (
                f"{path.name}: {key}={record[key]!r} is {type(record[key]).__name__}, "
                f"not {kind.__name__}"
            )

        assert record["scenario"] == path.stem, (
            f"{path.name}: reports scenario {record['scenario']!r}; a campaign keys its "
            "table on this and every ceiling name is scenario-local"
        )
        assert record["test"] == FAKE_TEST_METHOD, (
            f"{path.name}: reports test {record['test']!r} rather than the running "
            "test method. Without it a campaign cannot tell bring-up waits that "
            "measured a cold start from the ones the first test already absorbed"
        )


def test_a_wait_satisfied_on_entry_is_distinguishable(emitters, capsys) -> None:
    """`spins: 0` is the field that says "this measured nothing".

    `_spin_until` evaluates its predicate once before it spins, so a wait that was
    already satisfied reports an elapsed time near zero — indistinguishable, from
    the record alone, from a milestone that genuinely took no time. The spin count
    says which it was, structurally, and a campaign discards those by rule rather
    than by eye.
    """
    for path, emitter in emitters:
        _emit(emitter, spins=0, elapsed_s=0.0001)
        record = json.loads(capsys.readouterr().out.split(PREFIX, 1)[1])
        assert record["spins"] == 0, f"{path.name}: the spin count did not survive"
        assert record["elapsed_s"] == 0.0, (
            f"{path.name}: elapsed_s={record['elapsed_s']!r}; it is rounded to "
            "milliseconds, which is what makes a non-measurement look like one"
        )


def test_the_payload_survives_a_hostile_description(emitters, capsys) -> None:
    """`what` is interpolated from frame names, milestones and topics.

    It carries quotes, colons, commas and slashes. The record is JSON precisely so
    that none of those can break a parser, and this is what holds the emitter to
    `json.dumps` rather than to an f-string that looks like JSON.
    """
    hostile = 'piece 1: on_link(station_transfer_1: "a/b", {c: d}) \\ end'
    for path, emitter in emitters:
        _emit(emitter, what=hostile)
        record = json.loads(capsys.readouterr().out.split(PREFIX, 1)[1])
        assert record["what"] == hostile, f"{path.name}: `what` did not round-trip"


def _prefix_literals(source: str) -> list[int]:
    """Line numbers of every string literal that OPENS with the `CITE_TIMING` prefix.

    An AST walk rather than a substring count, and the reason is the shape of the
    second writer someone would actually add. A plain string is an `ast.Constant`;
    the literal pieces of an f-string are `ast.Constant` children of an
    `ast.JoinedStr`, so `print(f"CITE_TIMING {json.dumps(record)}")` is found here.
    It was invisible to the substring count this replaced, which looked for the
    prefix together with its closing quote and therefore saw `"CITE_TIMING {` as an
    unrelated string — while that f-string is exactly what a developer re-adding a
    call-site emission reaches for first.

    Matching is on the prefix with its trailing space stripped, so a writer that
    formats the separator some other way is caught too. Comments and the record's
    own JSON keys are not string constants and cannot trip it, and a docstring
    mentioning the prefix in passing does not START with it, so it cannot either.
    """
    token = PREFIX.rstrip()
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(token)
    )


def test_every_scenario_has_exactly_one_writer() -> None:
    """The format is stated in three files; it must not be stated four times.

    A source scan, because the check is about where the string is written and not
    about what a call produces. Each scenario opens the prefix in exactly one
    string literal, inside `_emit_timing`. A second one anywhere in the file fails
    here — `print("CITE_TIMING " + ...)` and `print(f"CITE_TIMING {...}")` alike,
    which are the two shapes a call-site emission takes and the first of which is
    the shape this code had, at every call site, before `_emit_timing` existed.
    """
    for path in loader.scenario_paths():
        lines = _prefix_literals(path.read_text())
        assert len(lines) == 1, (
            f"{path.name} opens the {PREFIX!r} prefix in {len(lines)} string "
            f"literal(s), at line(s) {lines}; exactly one, in `_emit_timing`, "
            "is the rule"
        )
