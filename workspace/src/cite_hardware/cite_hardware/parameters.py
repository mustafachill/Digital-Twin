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

"""Parameters with no defaults, refused at configure when absent.

Every parameter these nodes take is a fact of the asset — a name, a range, a
timeout — and a fact of the asset comes from L0 through the generated plan
(P1). A default here would be that fact written a second time, in a place no
validator reads, and a node started without its configuration would run on it
quietly. So nothing is defaulted: each is declared with its TYPE only, and
`configure` fails naming every one that is missing or unusable.

A value of the wrong type supplied at launch is caught at declaration and
reported at configure the same way, rather than raising out of a constructor
where the lifecycle cannot report it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from rcl_interfaces.msg import ParameterDescriptor
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from rclpy.parameter import Parameter


class ParameterError(ValueError):
    """One or more required parameters are missing or unusable."""


@dataclass(frozen=True)
class Spec:
    """One required parameter: its name, its type, and what it means."""

    name: str
    kind: Parameter.Type
    description: str
    #: For a DOUBLE: whether the value must be strictly positive.
    positive: bool = False


class RequiredParameters:
    """Declare a set of required parameters on a node, and read them all or none."""

    def __init__(self, node: Node, specs: tuple[Spec, ...]) -> None:
        self._node = node
        self._specs = specs
        self._declaration_errors: list[str] = []
        for spec in specs:
            try:
                node.declare_parameter(
                    spec.name,
                    spec.kind,
                    ParameterDescriptor(description=spec.description),
                )
            except Exception as error:  # noqa: B902 - reported at configure
                self._declaration_errors.append(f"{spec.name}: {error}")

    def read(self) -> dict[str, Any]:
        """Return every value by name, or raise naming every problem at once."""
        problems = list(self._declaration_errors)
        values: dict[str, Any] = {}
        for spec in self._specs:
            if any(problem.startswith(f"{spec.name}:") for problem in problems):
                continue
            try:
                parameter = self._node.get_parameter(spec.name)
            except ParameterUninitializedException:
                parameter = None
            if parameter is None or parameter.type_ == Parameter.Type.NOT_SET:
                problems.append(f"{spec.name}: not supplied ({spec.description})")
                continue
            value = parameter.value
            problem = _unusable(spec, value)
            if problem:
                problems.append(f"{spec.name}: {problem}")
                continue
            values[spec.name] = list(value) if isinstance(value, (list, tuple)) else value
        if problems:
            raise ParameterError(
                "required parameter(s) missing or unusable — they are facts of the asset "
                "and have no default (ADR-0070): " + "; ".join(problems)
            )
        return values


def _unusable(spec: Spec, value: Any) -> str:
    if spec.kind == Parameter.Type.STRING and not value:
        return "empty"
    if spec.kind == Parameter.Type.STRING_ARRAY:
        if not value:
            return "empty list"
        if any(not item for item in value):
            return f"contains an empty name: {list(value)}"
    if spec.kind == Parameter.Type.DOUBLE:
        if not math.isfinite(value):
            return f"{value} is not finite"
        if spec.positive and value <= 0.0:
            return f"{value} must be positive"
    return ""
