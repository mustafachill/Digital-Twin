"""``cite-model`` — validate the L0 facility model and generate from it.

The entry point name and the ``validate --model <dir>`` signature are a fixed
contract: ``scripts/validate-model`` invokes exactly that, and CI invokes the
script. Renaming either breaks the toolchain contract that CLAUDE.md §7 exists
to keep stable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

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
    findings = referential.check(facility_model)
    findings += physical.check(facility_model)

    if not any(f.severity is Severity.ERROR for f in findings):
        for zone in facility_model.zones:
            try:
                findings += geometric.check(resolve(facility_model, zone.id))
            except ResolveError as exc:
                err_console.print(f"[red]error[/red] [dim]resolve[/dim] zone {zone.id}: {exc}")
                raise typer.Exit(code=1) from exc

    schema_problems = export.differences(model / "schema")
    for problem in schema_problems:
        err_console.print(f"[red]error[/red] [dim]schema-export[/dim] {problem}")

    error_count = _report(findings) + len(schema_problems)
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


def main() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
