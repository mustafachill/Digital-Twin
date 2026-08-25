"""Validation levels above the schema.

`L0-facility-model.md` fixes five levels and this package implements the middle
three. The split is not cosmetic: it decides what the exported JSON Schema is
allowed to claim.

===========  ==========================================================  =========
Level        Catches                                                     Where
===========  ==========================================================  =========
Schema       Structural errors, missing fields, wrong types, typos       pydantic
Referential  Dangling references, duplicate ids, cycles                  this package
Geometric    Overlaps, containment, unreachable stations                 this package
Physical     Implausible mass, invalid inertia, missing collision        this package
Generated    Output that does not match a fresh generator run            cite_tools.generate
===========  ==========================================================  =========

A constraint pydantic can express declaratively belongs on the field, so that it
survives the JSON Schema export and gives editors inline validation. A constraint
it cannot express belongs here, and the exported schema never claims it. That
rule is what stops the same check existing in two places.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One problem, named precisely enough to fix without searching.

    ``where`` is the model path — ``assets.arm_1.pose.frame`` — rather than a
    file name, because a fact's identity in this model is its position in the
    object graph, not which file someone happened to put it in.
    """

    severity: Severity
    rule: str
    where: str
    message: str
    hint: str | None = None

    def __str__(self) -> str:
        head = f"{self.severity.value}: [{self.rule}] {self.where}: {self.message}"
        return f"{head}\n    {self.hint}" if self.hint else head


def error(rule: str, where: str, message: str, hint: str | None = None) -> Finding:
    return Finding(Severity.ERROR, rule, where, message, hint)


def warning(rule: str, where: str, message: str, hint: str | None = None) -> Finding:
    return Finding(Severity.WARNING, rule, where, message, hint)
