"""Which authored bodies wear a generated visual mesh, and the command that writes them.

Every type whose body visual is a mesh under ``meshes/visual/<drawer>/`` is drawn
by that drawer, inside that body's collision box. The model therefore says
*which* bodies wear a mesh and which drawer draws each one, by the URI it
declares; the drawers say only *how* (P5). A URI under ``meshes/visual/`` that
names no drawer is an error, never silently skipped.

Usage::

    python -m cite_tools.visuals           # check every committed mesh
    python -m cite_tools.visuals --write   # regenerate them
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cite_tools.model.loader import FacilityModel, load
from cite_tools.visuals import VisualMeshError, asset_path, conveyor, parts, table, track

#: The directory a generated visual lives in, under the installed meshes.
VISUAL_ROOT = Path("assets") / "meshes" / "visual"

#: A drawer's directory under `VISUAL_ROOT`, and the function that draws it.
DRAWERS: dict[str, Callable[[parts.Triple], parts.Parts]] = {
    "conveyors": conveyor.parts,
    "tables": table.parts,
    "tracks": track.parts,
}


@dataclass(frozen=True)
class Target:
    """One type that wears a generated visual mesh."""

    type_id: str
    drawer: str
    size_m: parts.Triple
    path: Path

    def glb(self) -> bytes:
        """The bytes the committed file must equal."""
        return parts.glb(DRAWERS[self.drawer](self.size_m))


def targets(model: FacilityModel, repo_root: Path) -> list[Target]:
    """Every type whose body wears a generated visual mesh, sorted by id."""
    visual_root = repo_root / VISUAL_ROOT
    found = []
    for asset_type in sorted(model.types, key=lambda t: t.id):
        body = asset_type.description.body
        if body is None or body.visual.kind != "mesh":
            continue
        path = asset_path(repo_root, body.visual.uri)
        if not path.is_relative_to(visual_root):
            continue
        drawer = path.relative_to(visual_root).parts[0]
        if drawer not in DRAWERS:
            raise VisualMeshError(
                f"{asset_type.id}: no drawer for {VISUAL_ROOT / drawer}; "
                f"known: {', '.join(sorted(DRAWERS))}"
            )
        if body.collision.kind != "box":
            raise VisualMeshError(
                f"{asset_type.id}: a generated visual fills the collision box, "
                f"and this collision is a {body.collision.kind}"
            )
        if tuple(body.visual.scale) != (1.0, 1.0, 1.0):
            raise VisualMeshError(
                f"{asset_type.id}: the generated visual is drawn at the collision box's "
                "size, so a scale other than 1 would draw it at another"
            )
        x, y, z = body.collision.size_m
        found.append(Target(type_id=asset_type.id, drawer=drawer, size_m=(x, y, z), path=path))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cite_tools.visuals", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--model", type=Path, default=Path("model"), help="the model/ directory")
    parser.add_argument("--write", action="store_true", help="rewrite the committed meshes")
    args = parser.parse_args(argv)

    repo_root = args.model.resolve().parent
    problems = []
    found = targets(load(args.model), repo_root)
    for target in found:
        fresh = target.glb()
        shown = target.path.relative_to(repo_root)
        if args.write:
            target.path.parent.mkdir(parents=True, exist_ok=True)
            target.path.write_bytes(fresh)
            print(f"wrote {shown} ({target.type_id})")
        elif not target.path.is_file():
            problems.append(f"{shown}: missing ({target.type_id})")
        elif target.path.read_bytes() != fresh:
            problems.append(f"{shown}: differs from a fresh generation ({target.type_id})")
    for problem in problems:
        print(f"error {problem}", file=sys.stderr)
    if not args.write and not problems:
        print(f"ok {len(found)} visual mesh(es) match a fresh generation")
    return 1 if problems else 0
