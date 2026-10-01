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

"""A scaling factor with no stated basis is not a contract.

`test_interface_contract.py` stores the *semantic* content of every definition
with comments stripped, by design — so reformatting or rewriting a comment does
not fail it. That is the right decision for a baseline and it leaves a gap this
file covers: a field comment can state the wrong contract indefinitely and no
test notices.

The gap was real. `MoveTo.action` documented `velocity_scaling` as "0..1 of the
arm's configured limit" while the server passes it to MoveIt's
`setMaxVelocityScalingFactor`, which scales the limits in the robot description.
The configured default is 0.35 on that same scale, so a caller that read the
interface and sent 1.0 asked for the configured ceiling and got several times
it. Nothing sends the field today, which is the only reason this was cheap.

**What this proves and what it does not.** These are assertions about wording,
and wording is all an interface consumer has: `ros2 interface show` prints these
comments and nothing else explains the units. It cannot prove the server still
behaves this way — that belongs to `cite_skills`, which is a layer above this
package and must not be reached down into from here. What it does prove is that
the specific wrong basis cannot come back silently.
"""

from __future__ import annotations

from pathlib import Path
import re

PACKAGE = Path(__file__).resolve().parent.parent
DIRECTORIES = ("msg", "srv", "action")

#: The wrong basis, in the words it was written in. A scaling factor is a
#: fraction of the description's limits; the configured default is another
#: fraction on that same scale and is not a ceiling anything is measured
#: against.
WRONG_BASIS = re.compile(r"configured limit", re.IGNORECASE)

#: A field whose name ends this way is a scaling factor and owes the reader a
#: basis. Matched on the definition line, so a mention inside a comment is not
#: mistaken for a declaration.
SCALING_FIELD = re.compile(r"^\s*float64\s+(\w*scaling)\b")


def _definitions() -> list[Path]:
    found: list[Path] = []
    for directory in DIRECTORIES:
        found.extend(sorted((PACKAGE / directory).glob("*")))
    assert found, "no interface definitions found — this test would pass vacuously"
    return found


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _documentation(text: str, line_number: int) -> str:
    """Everything a reader of that field's declaration would take as its docs.

    Two directions, because these files use two comment shapes and they belong
    to different fields. A block starting at column 0 introduces the field below
    it; an indented comment continues the inline comment of the field above it.
    Walking up through indented comments would hand a field the tail of its
    predecessor's explanation — which is exactly how the first version of this
    test passed `acceleration_scaling` on the strength of `velocity_scaling`'s
    words.
    """
    lines = text.splitlines()
    collected = [lines[line_number]]

    index = line_number - 1
    while index >= 0 and _is_comment(lines[index]) and not lines[index][:1].isspace():
        collected.append(lines[index])
        index -= 1

    index = line_number + 1
    while index < len(lines) and _is_comment(lines[index]) and lines[index][:1].isspace():
        collected.append(lines[index])
        index += 1

    return "\n".join(collected)


def test_no_definition_states_the_wrong_scaling_basis() -> None:
    """The exact defect, in every definition rather than only the one that had it."""
    for path in _definitions():
        text = path.read_text()
        for number, line in enumerate(text.splitlines()):
            if not SCALING_FIELD.match(line):
                continue
            documentation = _documentation(text, number)
            assert not WRONG_BASIS.search(documentation), (
                f"{path.name}: a scaling factor is documented against the arm's "
                f"configured limit. MoveIt scales the robot description's limits; "
                f"the configured default is a fraction on that same scale, not a "
                f"ceiling.\n{documentation}"
            )


def test_every_scaling_field_names_the_limits_it_scales() -> None:
    """A number between 0 and 1 means nothing until the reader knows of what."""
    checked = 0
    for path in _definitions():
        text = path.read_text()
        for number, line in enumerate(text.splitlines()):
            match = SCALING_FIELD.match(line)
            if not match:
                continue
            checked += 1
            documentation = _documentation(text, number).lower()
            assert "description" in documentation, (
                f"{path.name}: {match.group(1)} does not say which limits it is a "
                f"fraction of. `ros2 interface show` prints this comment and "
                f"nothing else tells a caller what 1.0 asks for."
            )
    assert checked, "no scaling fields found — this test would pass vacuously"
