"""Read ``model/`` into a typed, deterministically ordered object graph.

Two properties matter more than anything else here.

**Dispatch on content, not on location.** Every model file declares its own
``schema:`` key and the loader routes on that. A file in the wrong directory is
then an error rather than a silent omission — and a silent omission in a model
that generates the whole system is the worst available failure.

**Deterministic ordering.** Everything is sorted by identity before it leaves
this module, so generated output cannot depend on filesystem order, glob order,
or how the model was split across files. Renaming or splitting a model file
therefore produces no diff at all in generated artifacts, which is what makes the
hand-edit check readable (ADR-0004, ADR-0021).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from cite_tools.model.schema import (
    DOCUMENT_TYPES,
    AssetInstance,
    AssetInstancesDocument,
    AssetType,
    AssetTypeDocument,
    Facility,
    FacilityDocument,
    Flow,
    FlowDocument,
    Station,
    StationsDocument,
    Zone,
    ZonesDocument,
)


class ModelError(Exception):
    """A model file could not be read, parsed, or validated against the schema."""


@dataclass(frozen=True)
class FacilityModel:
    """The whole model, loaded and ordered. Nothing here has been cross-checked yet.

    Schema validity is guaranteed by construction; referential, geometric and
    physical validity are separate levels handled by ``cite_tools.validate``,
    because they are not things a schema can express.
    """

    facility: Facility
    zones: tuple[Zone, ...]
    types: tuple[AssetType, ...]
    assets: tuple[AssetInstance, ...]
    stations: tuple[Station, ...]
    flows: tuple[Flow, ...]
    source_files: tuple[Path, ...]

    def zone(self, zone_id: str) -> Zone | None:
        return next((z for z in self.zones if z.id == zone_id), None)

    def asset_type(self, type_id: str) -> AssetType | None:
        return next((t for t in self.types if t.id == type_id), None)

    def asset(self, asset_id: str) -> AssetInstance | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def station(self, station_id: str) -> Station | None:
        return next((s for s in self.stations if s.id == station_id), None)

    def assets_in(self, zone_id: str) -> tuple[AssetInstance, ...]:
        return tuple(a for a in self.assets if a.zone == zone_id)


def model_files(root: Path) -> list[Path]:
    """Every YAML file under ``root``, in a stable order.

    ``model/schema/`` is skipped: it holds the generated JSON Schema export, not
    model content.
    """
    if not root.is_dir():
        raise ModelError(f"model directory not found: {root}")
    files = [p for p in root.rglob("*.yaml") if "schema" not in p.relative_to(root).parts]
    return sorted(files, key=lambda p: p.as_posix())


def _read_document(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ModelError(f"{path}: not valid YAML: {exc}") from exc
    if raw is None:
        raise ModelError(f"{path}: file is empty")
    if not isinstance(raw, dict):
        raise ModelError(f"{path}: expected a mapping at the top level, got {type(raw).__name__}")
    schema = raw.get("schema")
    if not isinstance(schema, str):
        raise ModelError(
            f"{path}: missing a top-level `schema:` key. Every model file declares "
            f"its own kind so that a misfiled file is an error rather than ignored. "
            f"Expected one of: {', '.join(sorted(DOCUMENT_TYPES))}."
        )
    if schema not in DOCUMENT_TYPES:
        raise ModelError(
            f"{path}: unknown schema {schema!r}. "
            f"Expected one of: {', '.join(sorted(DOCUMENT_TYPES))}."
        )
    return schema, raw


def load(root: Path) -> FacilityModel:
    """Load and schema-validate every model file under ``root``."""
    facility: Facility | None = None
    zones: list[Zone] = []
    types: list[AssetType] = []
    assets: list[AssetInstance] = []
    stations: list[Station] = []
    flows: list[Flow] = []
    seen: list[Path] = []

    files = model_files(root)
    if not files:
        raise ModelError(f"no model files found under {root}")

    for path in files:
        schema, raw = _read_document(path)
        document_type = DOCUMENT_TYPES[schema]
        try:
            document = document_type.model_validate(raw)
        except ValidationError as exc:
            raise ModelError(f"{path}: {_format_validation_error(exc)}") from exc

        seen.append(path)
        if isinstance(document, FacilityDocument):
            if facility is not None:
                raise ModelError(
                    f"{path}: a second facility document. The model describes exactly "
                    "one facility; zones are how it is subdivided."
                )
            facility = document.facility
        elif isinstance(document, ZonesDocument):
            zones.extend(document.zones)
        elif isinstance(document, AssetTypeDocument):
            types.append(document.asset_type)
        elif isinstance(document, AssetInstancesDocument):
            assets.extend(document.assets)
        elif isinstance(document, StationsDocument):
            stations.extend(document.stations)
        elif isinstance(document, FlowDocument):
            flows.append(document.flow)

    if facility is None:
        raise ModelError(
            f"no facility document under {root}. Exactly one file must declare "
            "`schema: cite/facility/v1`."
        )

    # Sort everything by identity. From here on, nothing downstream can observe
    # how the model was split across files or what order the filesystem returned.
    return FacilityModel(
        facility=facility,
        zones=tuple(sorted(zones, key=lambda z: z.id)),
        types=tuple(sorted(types, key=lambda t: t.id)),
        assets=tuple(sorted(assets, key=lambda a: a.id)),
        stations=tuple(sorted(stations, key=lambda s: s.id)),
        flows=tuple(sorted(flows, key=lambda f: f.id)),
        source_files=tuple(seen),
    )


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic error as something a person can act on.

    Pydantic's default rendering buries the location. Since the most common
    error this will report is a mistyped key — the failure mode `additionalProperties: false`
    exists to catch — the key and its path need to be the first thing visible.
    """
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        message = error["msg"]
        if error["type"] == "extra_forbidden":
            message = (
                "unknown key. The schema rejects unknown keys deliberately: a typo "
                "must be an error, never a silent default (L0-facility-model.md)."
            )
        lines.append(f"  {location}: {message}")
    return "schema validation failed:\n" + "\n".join(lines)
