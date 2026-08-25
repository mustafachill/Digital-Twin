"""Generation of every derived artifact, and the checks that keep it honest.

Everything the running system reads is produced here from the L0 model and
committed to ``workspace/src/cite_generated/`` (ADR-0021). Two properties make
that arrangement work, and both are enforced in this module rather than trusted:

**Determinism.** The same model produces byte-identical output. Collections are
sorted before emission, no timestamp or random identifier is embedded, and
nothing iterates a set or depends on filesystem order. Without this the hand-edit
check reports false positives and gets ignored, which quietly disables the
mechanism the whole architecture rests on.

**Wholeness.** The generated package is generated *in its entirety*, including
its own ``package.xml`` and ``CMakeLists.txt``. That makes the hand-edit check a
single whole-tree diff, which catches an added file, a missing file, or one
changed byte anywhere — strictly stronger than any per-file check.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cite_tools.model.loader import FacilityModel
from cite_tools.model.resolve import resolve

#: The generated package. Nothing in it is authored, and its presence marker is
#: what tells an editor, a reviewer and CI that the whole directory is output.
PACKAGE = "cite_generated"
MARKER = "GENERATED"


@dataclass(frozen=True)
class Artifact:
    """One generated file, addressed relative to the generated package root."""

    path: str
    content: str


def model_hash(model: FacilityModel) -> str:
    """A stable digest of the model's *content*, not of its files.

    Computed from the loaded and sorted object graph rather than from the bytes
    on disk, so reformatting a model file, renaming it, or splitting it across
    two files does not change the hash. What the hash identifies is the facility
    that was described, which is the thing a recording needs stamped on it (L6).
    """
    digest = hashlib.sha256()
    for part in (
        model.facility.model_dump_json(),
        *[z.model_dump_json() for z in model.zones],
        *[t.model_dump_json() for t in model.types],
        *[a.model_dump_json() for a in model.assets],
        *[s.model_dump_json() for s in model.stations],
        *[f.model_dump_json() for f in model.flows],
    ):
        digest.update(part.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def generate(model: FacilityModel) -> list[Artifact]:
    """Every artifact, in a stable order."""
    from cite_tools.generate import (
        bringup,
        control,
        description,
        frames,
        moveit,
        package,
        topology,
        world,
    )

    artifacts: list[Artifact] = [
        Artifact(MARKER, _marker_text()),
        Artifact("MODEL_HASH", model_hash(model) + "\n"),
    ]
    for zone in model.zones:
        cell = resolve(model, zone.id)
        artifacts += description.generate(cell)
        artifacts += world.generate(cell)
        artifacts += control.generate(cell)
        artifacts += moveit.generate(cell)
        artifacts += frames.generate(cell)
        artifacts += topology.generate(model, cell)
        artifacts += bringup.generate(cell)
    artifacts += package.generate(model)
    return sorted(artifacts, key=lambda a: a.path)


def _marker_text() -> str:
    return (
        "This directory is generated in its entirety by `cite-model generate`.\n"
        "Nothing here is authored, including package.xml and CMakeLists.txt.\n"
        "\n"
        "Edit model/ and regenerate. A hand edit is a Critical review finding\n"
        "(ADR-0004) and ./scripts/validate-model will fail on it.\n"
    )


def write(artifacts: list[Artifact], out_dir: Path) -> list[Path]:
    """Write the artifacts, removing anything stale.

    Stale removal matters: renaming an asset changes a filename, and leaving the
    old file behind would give the workspace a description of something that no
    longer exists, which colcon would happily install.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = {a.path for a in artifacts}

    written: list[Path] = []
    for artifact in artifacts:
        path = out_dir / artifact.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact.content)
        written.append(path)

    for existing in sorted(out_dir.rglob("*")):
        if existing.is_file():
            relative = existing.relative_to(out_dir).as_posix()
            if relative not in expected:
                existing.unlink()

    for directory in sorted(out_dir.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    return written


def differences(artifacts: list[Artifact], out_dir: Path) -> list[str]:
    """How the committed tree differs from a fresh generator run.

    An empty list is the only acceptable state in CI. Anything else is a hand
    edit, a stale file, or a model change whose regeneration was not committed —
    and this check cannot distinguish them, which is fine, because the remedy is
    the same.
    """
    problems: list[str] = []
    expected = {a.path: a.content for a in artifacts}

    for path, content in sorted(expected.items()):
        target = out_dir / path
        if not target.is_file():
            problems.append(f"{target}: missing from the generated tree")
        elif target.read_text() != content:
            problems.append(f"{target}: differs from a fresh generator run — hand edited?")

    if out_dir.is_dir():
        for existing in sorted(out_dir.rglob("*")):
            if existing.is_file():
                relative = existing.relative_to(out_dir).as_posix()
                if relative not in expected:
                    problems.append(f"{existing}: not produced by any generator — stale")

    return problems
