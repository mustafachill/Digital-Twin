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

"""The host-side scripts have to run on the host, including a macOS one.

`./scripts/format` never re-executes itself inside the container: it runs `ruff`
from the host virtualenv, and `ament_uncrustify` only if the host happens to have
it. So every line of it executes under whatever `/bin/bash` the developer has —
and on macOS that is **bash 3.2.57**, the last GPLv2 release Apple can ship.

It used `mapfile`, a bash 4 builtin. On the development host the script aborted
with `mapfile: command not found` before formatting anything, which is how the
one command whose entire job is to fix formatting came to be the command nobody
could run. Reaching for `ruff format` by hand instead skips the C++ half, and
with it the single guarantee the script's own header exists to make.

`scripts/lint` and `scripts/test` also call `mapfile`, and those calls are
correct: both re-execute themselves inside the container, and the calls sit in
the half that only ever runs there — their host-side halves already use a `while
read` loop, with a comment saying why. This test therefore covers the host-side
script specifically rather than banning the builtin outright. The rule is about
*where* a line runs, not about the builtin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Builtins and expansions bash 3.2 does not have. Every one of them fails at run
#: time rather than at parse time, so `bash -n` cannot catch any of them — which
#: is why this is a test and not a linter setting.
BASH_4_ONLY = {
    "mapfile": "bash 4 builtin; use `while IFS= read -r line; do ...; done < <(...)`",
    "readarray": "bash 4 synonym for mapfile",
    "declare -A": "associative arrays are bash 4",
    "local -A": "associative arrays are bash 4",
}

#: Scripts that run on the developer's own machine from first line to last.
HOST_SIDE_SCRIPTS = ("format",)


def _strip_comments(text: str) -> str:
    """Drop comments, so prose explaining the rule does not trip the rule."""
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        kept.append(line.split(" #", 1)[0] if " #" in line else line)
    return "\n".join(kept)


@pytest.mark.parametrize("name", HOST_SIDE_SCRIPTS)
def test_host_side_script_avoids_bash_4_only_constructs(name: str) -> None:
    script = REPO_ROOT / "scripts" / name
    assert script.is_file(), f"{script} is missing"

    code = _strip_comments(script.read_text())
    offenders = [f"{token!r} — {why}" for token, why in BASH_4_ONLY.items() if token in code]
    assert not offenders, (
        f"scripts/{name} runs on the host, where macOS ships bash 3.2, and uses:\n  "
        + "\n  ".join(offenders)
    )


def test_format_collects_python_trees_with_a_portable_read_loop() -> None:
    """The collection itself, not merely the absence of a token.

    A later edit could drop `mapfile` and still collect nothing, and an empty
    array is exactly as broken as an aborted script while being quieter about it.
    This pins the shape that does the collecting.
    """
    code = _strip_comments((REPO_ROOT / "scripts" / "format").read_text())
    assert (
        "while IFS= read -r" in code
    ), "scripts/format no longer reads python_trees with a portable read loop"
    assert "PY_TREES+=(" in code, "scripts/format no longer accumulates the tree list"
