"""``cite-model`` — validate the L0 facility model and generate from it.

The entry point name and the ``validate --model <dir>`` signature are a fixed
contract: ``scripts/validate-model`` invokes exactly that, and CI invokes the
script. Renaming either breaks the toolchain contract that CLAUDE.md §7 exists
to keep stable.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from cite_tools import generate as gen
from cite_tools import manifest, meshes
from cite_tools.generate.moveit import PlanningConfigurationError
from cite_tools.model import export
from cite_tools.model.loader import ModelError, load
from cite_tools.model.resolve import ResolveError, resolve
from cite_tools.validate import Finding, Severity, geometric, physical, referential

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Validate and generate from the CITE facility model (L0).",
)

console = Console()
err_console = Console(stderr=True)

ModelOption = Annotated[
    Path,
    typer.Option("--model", "-m", help="Path to the model/ directory.", show_default=False),
]


def _generate(facility_model):
    """Run the generators, reporting a model problem as a finding rather than a trace.

    A generator raises when the model asks for something it cannot emit — an
    unknown planning pipeline, a planner the pipeline does not register. That is
    a MODEL problem and belongs in the same shape as every other one, `error
    <rule> <where>`. It used to abort the command with a raw traceback, which
    reads as a tool that crashed rather than as a model that is wrong.
    """
    try:
        return gen.generate(facility_model)
    except PlanningConfigurationError as exc:
        err_console.print(f"[red]error[/red] [dim]{exc.rule}[/dim] {exc.where}")
        err_console.print(f"  {exc.message}")
        err_console.print("\n[red]1 error(s).[/red] The model is not valid.")
        raise typer.Exit(code=1) from exc


def generated_dir(model: Path) -> Path:
    """Where the generated package lives, relative to the model directory.

    `model/` and `workspace/src/` are siblings, so this derives the location
    rather than taking it as an option — one fewer way for a developer and CI to
    point at different trees.
    """
    return model.resolve().parent / "workspace" / "src" / gen.PACKAGE


#: Re-generation runs under a hash seed that differs from this process's. Any
#: fixed value distinct from the parent's will do; the evidence is agreement
#: across two different seeds, not the seeds themselves.
_ALTERNATE_HASH_SEED = "1"
_FALLBACK_HASH_SEED = "2"

#: Executed inside the subprocess. Prints one `path<TAB>digest` line per artifact.
_REGENERATE_SNIPPET = """
import hashlib, sys
from pathlib import Path
from cite_tools import generate as gen
from cite_tools.model.loader import load
for artifact in gen.generate(load(Path(sys.argv[1]))):
    digest = hashlib.sha256(artifact.content.encode()).hexdigest()
    sys.stdout.write(artifact.path + chr(9) + digest + chr(10))
"""


def _determinism_problems(model: Path, artifacts: list[gen.Artifact]) -> list[str]:
    """Generate again in a FRESH interpreter, under a different hash seed.

    ADR-0004 requires byte-identical output because the hand-edit check compares
    against a fresh run. Under non-determinism that check reports false positives
    and gets ignored, which silently disables the mechanism the architecture rests
    on — so the property is asserted on every validation rather than assumed.

    The subprocess is the whole point, and this check used not to have one.
    Generating twice inside one interpreter cannot see the failure mode named
    above: `PYTHONHASHSEED` is fixed for the life of a process, so a generator
    that iterated a set of strings would produce the same wrong order both times
    and the check would pass. Only a second interpreter, seeded differently,
    makes set iteration order differ — and set iteration order is the single most
    likely way this property breaks.
    """
    seed = _ALTERNATE_HASH_SEED
    if os.environ.get("PYTHONHASHSEED") == seed:
        seed = _FALLBACK_HASH_SEED

    completed = subprocess.run(
        [sys.executable, "-c", _REGENERATE_SNIPPET, str(model)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
        check=False,
    )
    if completed.returncode != 0:
        return [
            "the determinism check could not re-generate the model in a subprocess "
            f"(exit {completed.returncode}): {completed.stderr.strip()[-500:]}"
        ]

    second: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        path, _, digest = line.partition("\t")
        second[path] = digest
    first = {a.path: hashlib.sha256(a.content.encode()).hexdigest() for a in artifacts}

    problems: list[str] = []
    for path in sorted(set(first) ^ set(second)):
        where = "this run only" if path in first else f"PYTHONHASHSEED={seed} only"
        problems.append(f"{path}: emitted by {where} — the generator is not deterministic")
    for path in sorted(first.keys() & second.keys()):
        if first[path] != second[path]:
            problems.append(
                f"{path}: differs between two runs under different hash seeds — "
                "the generator is not deterministic"
            )
    return problems


def _report(findings: list[Finding]) -> int:
    """Print findings and return the number of errors."""
    errors = [f for f in findings if f.severity is Severity.ERROR]
    warnings = [f for f in findings if f.severity is Severity.WARNING]

    for finding in warnings + errors:
        stream = err_console if finding.severity is Severity.ERROR else console
        colour = "red" if finding.severity is Severity.ERROR else "yellow"
        stream.print(
            f"[{colour}]{finding.severity.value}[/{colour}] "
            f"[dim]{finding.rule}[/dim] {finding.where}"
        )
        stream.print(f"  {finding.message}")
        if finding.hint:
            stream.print(f"  [dim]{finding.hint}[/dim]")
    return len(errors)


@app.command()
def validate(
    model: ModelOption = Path("model"),
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    write: Annotated[
        bool,
        typer.Option("--write", help="Regenerate the schema export and the generated package."),
    ] = False,
) -> None:
    """Validate the model: schema, then referential integrity.

    Geometric and physical levels, and the generated-artifact diff, are added as
    the generators land; this command is the single place all of them run, so
    that `./scripts/validate-model` never needs to change again.
    """
    try:
        facility_model = load(model)
    except ModelError as exc:
        err_console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Order matters. Referential integrity runs first because the geometric and
    # physical levels resolve poses and types, and resolving against a dangling
    # reference produces a traceback instead of a finding.
    if write:
        export.write(model / "schema")
        gen.write(_generate(facility_model), generated_dir(model))

    findings = referential.check(facility_model)
    # Referential integrity is the ONLY level whose failure may stop another
    # level from running, and this used to read "any error at all".
    #
    # The distinction is not tidiness. Resolving a dangling reference raises
    # rather than reporting, so a referential error genuinely makes the levels
    # below unrunnable. A *physical* error does not: the model still resolves and
    # the generators still run. Gating on the combined set meant one physical
    # error silenced the geometric level **and the committed-vs-fresh diff below**
    # — the hand-edit detector ADR-0021 rests on — and the state a contributor
    # reaches by putting `select: vendor_meshes` back without regenerating is
    # exactly that state: the collision error was reported and three stale
    # descriptions and a stale MODEL_HASH were not. A check that switches itself
    # off in the presence of an unrelated finding is worse than one that is
    # missing, because its silence reads as a pass.
    model_resolves = not any(f.severity is Severity.ERROR for f in findings)
    findings += physical.check(facility_model)

    if model_resolves:
        for zone in facility_model.zones:
            try:
                findings += geometric.check(resolve(facility_model, zone.id))
            except ResolveError as exc:
                err_console.print(f"[red]error[/red] [dim]resolve[/dim] zone {zone.id}: {exc}")
                raise typer.Exit(code=1) from exc

    schema_problems = export.differences(model / "schema")
    for problem in schema_problems:
        err_console.print(f"[red]error[/red] [dim]schema-export[/dim] {problem}")

    # The fifth validation level: the committed artifacts must equal a fresh
    # generator run. This is the hand-edit check, and it only means anything
    # because generation is deterministic (ADR-0004).
    generated_problems: list[str] = []
    if model_resolves and not schema_problems:
        artifacts = _generate(facility_model)
        generated_problems = _determinism_problems(model, artifacts)
        generated_problems += gen.differences(artifacts, generated_dir(model))
        for problem in generated_problems:
            err_console.print(f"[red]error[/red] [dim]generated[/dim] {problem}")

    error_count = _report(findings) + len(schema_problems) + len(generated_problems)
    if strict:
        error_count += sum(1 for f in findings if f.severity is Severity.WARNING)

    if error_count:
        err_console.print(f"\n[red]{error_count} error(s).[/red] The model is not valid.")
        raise typer.Exit(code=1)

    console.print(
        f"[green]ok[/green] model valid — "
        f"{len(facility_model.zones)} zone(s), "
        f"{len(facility_model.types)} type(s), "
        f"{len(facility_model.assets)} asset(s), "
        f"{len(facility_model.stations)} station(s), "
        f"across {len(facility_model.source_files)} file(s)"
    )


@app.command()
def schema(
    model: ModelOption = Path("model"),
    write: Annotated[
        bool, typer.Option("--write", help="Rewrite the exported JSON Schema files.")
    ] = False,
) -> None:
    """Export the pydantic models to ``model/schema/`` as JSON Schema.

    Without ``--write`` this only reports differences, which is the form CI uses.
    """
    out_dir = model / "schema"
    if write:
        written = export.write(out_dir)
        for path in written:
            console.print(f"[green]wrote[/green] {path}")
        return

    problems = export.differences(out_dir)
    for problem in problems:
        err_console.print(f"[red]error[/red] {problem}")
    if problems:
        raise typer.Exit(code=1)
    console.print("[green]ok[/green] exported schema matches the models")


@app.command()
def show(
    model: ModelOption = Path("model"),
    what: Annotated[
        str, typer.Argument(help="assets | zones | types | stations | flow")
    ] = "assets",
) -> None:
    """Render part of the model for a human to read.

    This is a *view*, never a source. It is the answer to ADR-0020's honest cost
    that radians are not how anyone thinks: angles are shown in degrees here and
    nowhere else.
    """
    try:
        facility_model = load(model)
    except ModelError as exc:
        err_console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"{facility_model.facility.name} — {what}")
    if what == "assets":
        table.add_column("id")
        table.add_column("type")
        table.add_column("zone")
        table.add_column("backend")
        table.add_column("pose frame")
        for asset in facility_model.assets:
            table.add_row(
                asset.id, asset.type, asset.zone, asset.hardware.backend, asset.pose.frame
            )
    elif what == "zones":
        table.add_column("id")
        table.add_column("name")
        for zone in facility_model.zones:
            table.add_row(zone.id, zone.name)
    elif what == "types":
        table.add_column("id")
        table.add_column("category")
        table.add_column("backends")
        for asset_type in facility_model.types:
            table.add_row(
                asset_type.id,
                asset_type.category,
                ", ".join(sorted(asset_type.hardware_backends)) or "-",
            )
    elif what == "stations":
        table.add_column("id")
        table.add_column("type")
        table.add_column("actor")
        for station in facility_model.stations:
            table.add_row(station.id, station.type, station.actor or "-")
    elif what == "flow":
        table.add_column("from")
        table.add_column("to")
        table.add_column("via")
        table.add_column("buffer")
        for flow in facility_model.flows:
            for edge in flow.edges:
                table.add_row(edge.from_station, edge.to_station, edge.via or "-", str(edge.buffer))
    else:
        err_console.print(f"[red]error[/red] unknown subject {what!r}")
        raise typer.Exit(code=1)

    console.print(table)


@app.command()
def hulls(
    model: ModelOption = Path("model"),
    write: Annotated[
        bool, typer.Option("--write", help="Rewrite the hull meshes and the manifest region.")
    ] = False,
) -> None:
    """Derive the convex-hull collision meshes the model declares (ADR-0028).

    Not part of ``validate``, and the separation is deliberate.
    ``./scripts/validate-model`` must run anywhere — that is what makes the L0
    layer checkable from a laptop that could never build the simulator — and this
    command reads the **vendor** meshes, which exist only after ``vcs import``.
    Folding it in would make the model unvalidatable on a host without a ROS
    checkout, to gain nothing: the hulls are committed, so nothing regenerates
    them on a normal run.

    Without ``--write`` it checks, which is the form a gate uses: every declared
    mesh is hulled again from the vendor file and compared byte for byte against
    what is committed, and the manifest region is compared against what the same
    inputs produce. A drift here is a stale hull, which is a collision shape that
    does not match the arm — ADR-0028 names that failure as one that looks like a
    planner bug.

    **A skipped set suppresses the region comparison rather than failing it.** A
    set that produced no entry is a set deleted from the region this derives, so
    the comparison would be against something nobody built, and the message it
    used to emit named `--write` as the remedy — an action that would have erased
    the region it was complaining about. The skip's own error stands; the region
    reports as unchecked (ADR-0028, R-09).
    """
    try:
        facility_model = load(model)
    except ModelError as exc:
        err_console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(code=1) from exc

    repo_root = model.resolve().parent
    sets = [
        (asset_type, mesh_set)
        for asset_type in facility_model.types
        if asset_type.description.collision is not None
        for mesh_set in asset_type.description.collision.sets
        if mesh_set.kind == "convex_hull"
    ]
    if not sets:
        console.print("[yellow]SKIP[/yellow] no type declares a derived collision set")
        return

    entries: list[dict] = []
    problems: list[str] = []
    #: Declared sets that produced no entry, for any reason. A skipped set is
    #: absent from `entries`, so the region derived from `entries` is a region
    #: with that set deleted from it — and comparing THAT against the committed
    #: file asks a question nobody was answering. Recorded by name rather than as
    #: a flag so the note below can say which sets, and so the write path can
    #: refuse on the fact itself instead of on the coincidence that every skip
    #: also happens to file a problem.
    skipped: list[str] = []
    for asset_type, mesh_set in sets:
        # Both are guaranteed non-empty by `CollisionMeshSet`'s own validator for
        # a `convex_hull` set; the assertion is for the type checker, and if it
        # ever fires the schema has stopped enforcing what it says it does.
        assert mesh_set.source_package and mesh_set.source_root
        source_root = _vendor_share(repo_root, mesh_set.source_package) / mesh_set.source_root
        if not source_root.is_dir():
            problems.append(
                f"{asset_type.id}/{mesh_set.id}: the vendor meshes are not in this checkout "
                f"({source_root}). Run ./scripts/bootstrap."
            )
            skipped.append(f"{asset_type.id}/{mesh_set.id}")
            continue
        dest_root = repo_root / "assets" / _asset_subdir(mesh_set)
        try:
            entries.append(
                _hull_set(asset_type, mesh_set, source_root, dest_root, repo_root, write, problems)
            )
        except meshes.MeshError as exc:
            # A missing vendor tree is not the only way a set is skipped: a
            # declared mesh absent from the vendor package, an unreadable STL, or
            # scipy missing from the interpreter all arrive here. This was
            # reproduced on a stale checkout where scipy was the cause, with the
            # vendor tree present — same wrong second message, different cause,
            # which is why the guard below is on the skip and not on the tree.
            problems.append(f"{asset_type.id}/{mesh_set.id}: {exc}")
            skipped.append(f"{asset_type.id}/{mesh_set.id}")

    manifest_path = repo_root / "assets" / "manifest.yaml"
    text = manifest_path.read_text()
    try:
        updated = manifest.replace(text, entries)
    except manifest.ManifestError as exc:
        err_console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if write:
        # `skipped` is redundant with `problems` today — every skip files one —
        # and it is named anyway, because what stands between a skipped set and a
        # region rewritten with that set deleted from it must not be a
        # coincidence between two lists.
        if problems or skipped:
            for problem in problems:
                err_console.print(f"[red]error[/red] {problem}")
            raise typer.Exit(code=1)
        manifest_path.write_text(updated)
        console.print(f"[green]wrote[/green] {manifest_path}")
        total = sum(len(e["meshes"]) for e in entries)
        console.print(f"[green]ok[/green] {len(entries)} set(s), {total} mesh(es)")
        return

    # NOT compared when a set was skipped, for any reason. The region derived from
    # a short `entries` is that region with the skipped sets deleted from it, so it
    # can only disagree with the committed file — and the message that disagreement
    # used to produce told the reader to run `--write`, an action that would have
    # erased the region it named (ADR-0028, R-09).
    if not skipped and updated != text:
        problems.append(
            "assets/manifest.yaml's derived region does not match the meshes on disk — "
            "run `./scripts/hulls --write`"
        )
    for problem in problems:
        err_console.print(f"[red]error[/red] {problem}")
    if skipped:
        # After the errors, so it reads as what it is: the skip above has its own
        # message and its own remedy, and this only records that one question went
        # unasked, so that no reader takes silence for a passing region.
        console.print(
            "[yellow]note[/yellow] the manifest's derived region was not checked — "
            f"{len(skipped)} declared set(s) were skipped above ({', '.join(skipped)}). "
            "Fix the skip and run this again; do not run --write to make it agree."
        )
    if problems:
        raise typer.Exit(code=1)
    total = sum(len(e["meshes"]) for e in entries)
    console.print(f"[green]ok[/green] {len(entries)} set(s), {total} mesh(es) match the vendor")


def _asset_subdir(mesh_set) -> str:
    """Where a set lives under ``assets/``, derived from where it is installed from.

    The ament package installs ``assets/meshes`` as ``share/<pkg>/meshes``, so the
    set's ``root`` is its path under ``assets/`` with the leading ``meshes``
    retained. Derived rather than declared twice: a second field naming the source
    directory would be the same path written down again, and it is exactly the
    kind of pair that drifts (P1).
    """
    return mesh_set.root


def _vendor_share(repo_root: Path, package: str) -> Path:
    """The vendor package's source directory in this checkout.

    The SOURCE tree, not the install tree. The hull must be a function of the
    bytes the manifest pins, and an install tree is a build artefact that a
    ``--symlink-install`` may or may not be pointing at those bytes.
    """
    return repo_root / "workspace" / "src" / "external" / "xarm_ros2" / package


def _hull_set(asset_type, mesh_set, source_root, dest_root, repo_root, write, problems) -> dict:
    records = []
    for relative in sorted(mesh_set.meshes):
        source = source_root / relative
        if not source.is_file():
            raise meshes.MeshError(f"declared collision mesh is missing: {relative}")
        payload, source_triangles, triangles = meshes.hull_bytes(source)
        target = dest_root / relative
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        elif not target.is_file():
            problems.append(f"{asset_type.id}/{mesh_set.id}: {relative} has no committed hull")
        elif target.read_bytes() != payload:
            problems.append(
                f"{asset_type.id}/{mesh_set.id}: {relative} does not match a hull of the "
                "vendor mesh it is derived from"
            )
        records.append(
            {
                "path": relative,
                "source_sha256": meshes.sha256_of(source),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_triangles": source_triangles,
                "triangles": triangles,
                "bytes": len(payload),
            }
        )
    return {
        "id": f"{asset_type.id}_{mesh_set.id}",
        "description": (
            f"Convex hulls of the vendor collision meshes for asset type {asset_type.id}"
        ),
        "kind": mesh_set.kind,
        "tool": "cite-model hulls",
        "source": {
            "type": "vcs",
            "repo": "external/xarm_ros2",
            "version": pinned_version(repo_root, "xarm_ros2"),
            "package": mesh_set.source_package,
            "root": mesh_set.source_root,
        },
        "dest": f"assets/{_asset_subdir(mesh_set)}",
        "installed_as": f"package://{mesh_set.package}/{mesh_set.root}",
        "meshes": records,
    }


def pinned_version(repo_root: Path, repo: str) -> str:
    """The commit the vcs manifest pins for a repository.

    Read rather than restated. A hull's provenance is only as good as the version
    it names, and a version copied by hand into the asset manifest would be a
    second place for the pin to live — the thing `external/cite.repos` exists to
    be the only one of (ADR-0008, P1).

    Public because the check that the recorded version is still the pinned one has
    to read the pin the same way this does. A second parser in the test would be a
    second place for the manifest's own format to be understood, and the two would
    agree right up to the day one of them was updated.
    """
    document = yaml.safe_load((repo_root / "external" / "cite.repos").read_text()) or {}
    for name, entry in (document.get("repositories") or {}).items():
        if Path(name).name == repo:
            return str(entry.get("version", "unknown"))
    return "unknown"


def main() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
