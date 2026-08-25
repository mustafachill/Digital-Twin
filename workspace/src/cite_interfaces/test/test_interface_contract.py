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

"""Every interface definition, checked against a stored baseline.

`cross-cutting-testing.md` requires it: "Interface definitions are checked
against a stored baseline. A breaking change to a `.msg`, `.srv`, or `.action`
fails the build rather than surfacing at runtime in a consumer nobody thought
about." Nothing implemented it, so nineteen definitions were unguarded — a field
could be renamed, retyped, reordered, or a constant's value changed, and the only
symptom would be a consumer deserialising nonsense at run time.

What the baseline stores is the *semantic* content of each definition: field
lines and constant lines, comments and blank lines removed, whitespace collapsed.
So reformatting a definition or rewriting its comments does not fail this test,
and changing a type, a name, an order, or a constant's value does.

The baseline is deliberately not self-updating. A diff here is a question — is
this change breaking, and does it need a version decision? — and answering it by
regenerating the file without reading it is how the guarantee is lost. Regenerate
consciously with:

    CITE_WRITE_INTERFACE_BASELINE=1 python3 -m pytest <this file>

and put the reason in the commit message.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
import re

PACKAGE = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).resolve().parent / "interfaces.baseline"
DIRECTORIES = ("msg", "srv", "action")

#: Set to regenerate the baseline. Read the diff first.
WRITE_ENV = "CITE_WRITE_INTERFACE_BASELINE"


def _significant(line: str) -> str | None:
    """One definition line, stripped of everything that is not the contract.

    A `#` inside a quoted string constant is content, not a comment, so the
    comment strip stops at a quote. Getting that wrong would silently truncate
    `string TOPIC="/cite/line/topology"` at nothing and let its value change
    unnoticed, which is precisely the class of change this test exists to catch.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped == "---":  # the service and action section separator: contract
        return stripped
    out: list[str] = []
    quote: str | None = None
    for character in stripped:
        if quote:
            out.append(character)
            if character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
            out.append(character)
            continue
        if character == "#":
            break
        out.append(character)
    collapsed = re.sub(r"\s+", " ", "".join(out)).strip()
    return collapsed or None


def snapshot() -> str:
    """Collect the current contract of every interface in this package."""
    lines: list[str] = []
    for directory in DIRECTORIES:
        for path in sorted((PACKAGE / directory).glob(f"*.{directory}")):
            lines.append(f"{directory}/{path.name}")
            for raw in path.read_text().splitlines():
                significant = _significant(raw)
                if significant is not None:
                    lines.append(f"  {significant}")
    return "\n".join(lines) + "\n"


def test_no_interface_changed_without_the_baseline_changing() -> None:
    current = snapshot()

    if os.environ.get(WRITE_ENV) == "1":
        BASELINE.write_text(current)

    assert BASELINE.is_file(), (
        f"no interface baseline at {BASELINE}. Generate it with "
        f"{WRITE_ENV}=1 and review it before committing."
    )
    stored = BASELINE.read_text()
    if current == stored:
        return

    diff = "\n".join(
        difflib.unified_diff(
            stored.splitlines(),
            current.splitlines(),
            fromfile="interfaces.baseline",
            tofile="the definitions as they are now",
            lineterm="",
        )
    )
    raise AssertionError(
        "an interface definition changed.\n\n"
        f"{diff}\n\n"
        "Removing or renaming a field, changing a type, reordering fields, or "
        "changing a constant's value BREAKS every consumer already built against "
        "it, including recordings on disk. Adding a field or a new constant at "
        "the end does not. Decide which this is, then regenerate the baseline "
        f"with {WRITE_ENV}=1 and say why in the commit message."
    )


def test_every_definition_is_built() -> None:
    """A definition file that CMake never lists is not an interface.

    It sits in the tree looking like a contract, `ros2 interface show` cannot
    find it, and nothing generates bindings for it. Catching that here is cheaper
    than a consumer discovering it.
    """
    cmake = (PACKAGE / "CMakeLists.txt").read_text()
    for directory in DIRECTORIES:
        for path in sorted((PACKAGE / directory).iterdir()):
            if path.suffix.lstrip(".") not in ("msg", "srv", "action"):
                continue
            relative = f"{directory}/{path.name}"
            assert relative in cmake, (
                f"{relative} exists but rosidl_generate_interfaces() does not list it, "
                "so no bindings are generated and no consumer can use it"
            )
