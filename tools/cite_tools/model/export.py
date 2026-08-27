"""Export the pydantic models to JSON Schema.

The schema is a *generated artifact* (ADR-0021), not a second declaration of the
model's shape. Its purpose is to be consumed by things that are not this Python
package: editors, through the ``yaml-language-server`` comment at the top of each
model file, and any future non-Python reader.

Determinism applies here exactly as it does to every other generated artifact:
sorted keys, a fixed indent, a trailing newline, and no timestamp.
"""

from __future__ import annotations

import json
from pathlib import Path

from cite_tools.model.schema import DOCUMENT_TYPES, Document


#: Filename stem per schema id, so ``cite/asset_type/v1`` becomes
#: ``asset_type.schema.json``. Derived rather than listed, so a new document type
#: cannot be added without its schema appearing.
def schema_filename(schema_id: str) -> str:
    """``cite/asset_instances/v1`` -> ``asset_instances.schema.json``."""
    parts = schema_id.split("/")
    if len(parts) != 3 or parts[0] != "cite":
        raise ValueError(f"unexpected schema id {schema_id!r}; expected 'cite/<name>/<version>'")
    return f"{parts[1]}.schema.json"


def render(document_type: type[Document], schema_id: str) -> str:
    """Render one document type as a JSON Schema document."""
    schema = document_type.model_json_schema(by_alias=True, mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://cite.shsu.edu/schema/{schema_id}"
    schema["title"] = schema_id
    schema["description"] = (
        "GENERATED from tools/cite_tools/model/schema.py by `cite-model schema`. "
        "Do not edit. The pydantic models are authoritative (ADR-0021)."
    )
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_all() -> dict[str, str]:
    """Every schema document, keyed by filename."""
    return {
        schema_filename(schema_id): render(document_type, schema_id)
        for schema_id, document_type in sorted(DOCUMENT_TYPES.items())
    }


def write(out_dir: Path) -> list[Path]:
    """Write every schema file, returning the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in sorted(render_all().items()):
        path = out_dir / name
        path.write_text(text)
        written.append(path)
    return written


def differences(out_dir: Path) -> list[str]:
    """Describe how the schema on disk differs from a fresh export.

    An empty list means the committed schema matches the models. Anything else is
    either a hand-edit or a model change whose export was not regenerated — both
    of which must fail rather than be silently tolerated.
    """
    expected = render_all()
    problems: list[str] = []

    for name, text in sorted(expected.items()):
        path = out_dir / name
        if not path.is_file():
            problems.append(f"{path}: missing — run `cite-model schema --write`")
        elif path.read_text() != text:
            problems.append(
                f"{path}: differs from a fresh export — run `cite-model schema --write`"
            )

    if out_dir.is_dir():
        for path in sorted(out_dir.glob("*.schema.json")):
            if path.name not in expected:
                problems.append(f"{path}: not produced by any document type — stale, delete it")

    return problems
