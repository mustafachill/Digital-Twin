"""The one statement of how wide the parts this facility handles are.

ADR-0052 §A.7, which absorbs option E rather than deferring it. Under option F
the L3 grasp predicate judges a stall against the *part* instead of against the
commanded width, and the validator's grasp ceiling reasons from the same part.
Two layers now answer one physical question, so the question has to have one
answer — and it did not: ``ResolvedCell.workpiece_types`` and a private
``_narrowest_workpiece_width_m`` inside ``cite_tools.validate.physical`` walked
``Facility.workpiece_models`` by two separate routes, agreeing by inspection.

**Two functions that happen to agree do not satisfy this** (§A.7). What F makes
of a disagreement is not untidiness: it is a model that validates against one
part and a cell that judges against another, with nothing to report it.

WHY IT TAKES A PAIR RATHER THAN A MODEL OR A CELL. The two call sites hold
different objects — ``physical.check`` takes a `FacilityModel`, the generator a
`ResolvedCell` — and neither is reachable from the other without an import that
runs the wrong way. What they *both* have is the pair this module takes: the
names the facility declares, and the asset types those names may resolve to. So
the accessor is expressed on the pair and both call sites adapt to it, which is
the only shape in which there is genuinely one function.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from cite_tools.model.schema import AssetType


@dataclass(frozen=True)
class WorkpieceWidths:
    """The interval of declared work-piece widths, and the silence beside it.

    ``narrowest_m`` and ``widest_m`` are the minimum and maximum horizontal
    extent over every declared work-piece type that states one. On a facility
    declaring a single part the interval is degenerate and both are the same
    number, which is today's model (ADR-0052 §A.5).

    THE TWO SILENCES ARE KEPT APART, and that is the whole reason this is a
    record rather than a float. ``None`` used to mean both "this facility handles
    no parts" and "this facility handles a part nobody has stated the width of",
    and collapsing them is what let one line in L0 — changing the cube to a mesh
    — switch two rules off at once with no finding at all. ``unstated`` names the
    types in the second state, so a caller can refuse rather than fall silent.
    """

    narrowest_m: float | None
    widest_m: float | None
    #: Declared work-piece types whose horizontal footprint is not a stated
    #: number — a mesh part, or one with no ``description.body`` at all. Their
    #: extents live in a file L1 owns and this layer deliberately does not read,
    #: so nothing here can measure across them. A legitimate way to describe a
    #: part; not a legitimate way to acquire a bound.
    unstated: tuple[str, ...]

    @property
    def is_stated(self) -> bool:
        """Whether the interval is usable as a bound at all."""
        return self.narrowest_m is not None and self.widest_m is not None


def workpiece_types(names: Sequence[str], types: Iterable[AssetType]) -> tuple[AssetType, ...]:
    """The types ``names`` refers to, resolved to their geometry.

    ``workpiece_models`` carries names because a name is what the simulator
    matches on. A rule that needs to know how wide a part is needs the type
    behind the name, and resolving it here rather than at each call site keeps
    the rules that do from each writing their own lookup.

    A name with no type behind it is dropped rather than raised on:
    ``referential`` reports it as ``unknown-type`` and runs first, so by the time
    a generator or a geometric rule sees this the model has been checked.
    Dropping it means a rule sized from work-piece geometry reports nothing
    rather than a wrong bound.
    """
    by_id = {t.id: t for t in types}
    return tuple(
        asset_type
        for name in names
        if (asset_type := by_id.get(name)) is not None and asset_type.category == "workpiece"
    )


def workpiece_widths(names: Sequence[str], types: Iterable[AssetType]) -> WorkpieceWidths:
    """The interval of declared work-piece widths, from one walk of one list.

    Measured across the horizontal footprint: a part rests on a surface in a
    known attitude and a parallel gripper closes across it, so
    ``Body.horizontal_extents_m[0]`` is the width the pads meet. Its own
    docstring names this as the consumer it exists for.

    NARROWEST **AND** WIDEST, where the validator once wanted only the narrowest.
    ADR-0052's predicate is a window with two edges and the widest declared part
    sets the far one; the ceiling on ``default_grasp_width_m`` still reasons from
    the narrowest, because a default has to stall on *every* part the line
    handles and the narrowest is the one it comes closest to missing.
    """
    resolved = workpiece_types(names, types)
    widths = [
        extents[0]
        for asset_type in resolved
        if (body := asset_type.description.body) is not None
        and (extents := body.horizontal_extents_m) is not None
    ]
    unstated = tuple(
        sorted(
            asset_type.id
            for asset_type in resolved
            if (body := asset_type.description.body) is None or body.horizontal_extents_m is None
        )
    )
    return WorkpieceWidths(
        narrowest_m=min(widths) if widths else None,
        widest_m=max(widths) if widths else None,
        unstated=unstated,
    )
