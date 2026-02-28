# src/spec2dv/cli.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from .ingest import load_spec_bundle
from .db import init_db, connect_db, upsert_spec_bundle, write_spec_version
from .validate import validate_db
from .export_json import export_registers_json
from .export_xml import export_registers_xml
from .export_dv import export_dv_constraints_json, export_uvm_regmodel

app = typer.Typer(add_completion=False)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@app.command()
def init(
    db: Path = typer.Option(Path("spec2dv.sqlite"), help="SQLite DB file path."),
):
    """Initialize the database schema."""
    init_db(db)
    typer.echo(f"Initialized DB at: {db}")


@app.command()
def ingest(
    spec: Path = typer.Argument(..., help="Base spec YAML path."),
    variant: Optional[Path] = typer.Option(None, help="Variant overlay YAML path."),
    db: Path = typer.Option(Path("spec2dv.sqlite"), help="SQLite DB file path."),
    git_commit: Optional[str] = typer.Option(None, help="Git commit hash for traceability."),
):
    """Parse YAML spec (+ optional variant overlay) and write to DB."""
    init_db(db)
    bundle = load_spec_bundle(spec_path=spec, variant_path=variant)
    with connect_db(db) as conn:
        upsert_spec_bundle(conn, bundle)
        write_spec_version(conn, bundle.spec_version, bundle.variant_name, git_commit)
    typer.echo(f"Ingested spec_version={bundle.spec_version} variant={bundle.variant_name or 'base'} into {db}")


@app.command()
def validate(
    db: Path = typer.Option(Path("spec2dv.sqlite"), help="SQLite DB file path."),
    fail_on_error: bool = typer.Option(True, help="Exit non-zero if errors found."),
    report: Optional[Path] = typer.Option(None, help="Write a Markdown validation report."),
):
    """Run hardware-aware validations against the DB."""
    with connect_db(db) as conn:
        result = validate_db(conn)

    if report:
        _ensure_parent(report)
        report.write_text(result.to_markdown(), encoding="utf-8")
        typer.echo(f"Wrote report: {report}")

    typer.echo(result.summary())

    if fail_on_error and result.error_count > 0:
        raise typer.Exit(code=2)


@app.command()
def export(
    db: Path = typer.Option(Path("spec2dv.sqlite"), help="SQLite DB file path."),
    out_dir: Path = typer.Option(Path("exports"), help="Output directory."),
    xml: bool = typer.Option(True, help="Export registers.xml"),
    json_out: bool = typer.Option(True, help="Export registers.json"),
):
    """Export structured outputs (XML/JSON) from the DB."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with connect_db(db) as conn:
        if json_out:
            p = out_dir / "json" / "registers.json"
            _ensure_parent(p)
            export_registers_json(conn, p)
            typer.echo(f"Wrote {p}")
        if xml:
            p = out_dir / "xml" / "registers.xml"
            _ensure_parent(p)
            export_registers_xml(conn, p)
            typer.echo(f"Wrote {p}")


@app.command("export-dv")
def export_dv(
    db: Path = typer.Option(Path("spec2dv.sqlite"), help="SQLite DB file path."),
    out_dir: Path = typer.Option(Path("exports/dv"), help="DV output directory."),
    constraints: bool = typer.Option(True, help="Export DV constraint config JSON."),
    uvm: bool = typer.Option(True, help="Export UVM register model stubs (SystemVerilog)."),
):
    """Export DV-facing artifacts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with connect_db(db) as conn:
        if constraints:
            p = out_dir / "constraints.json"
            _ensure_parent(p)
            export_dv_constraints_json(conn, p)
            typer.echo(f"Wrote {p}")
        if uvm:
            p = out_dir / "uvm_regmodel.sv"
            _ensure_parent(p)
            export_uvm_regmodel(conn, p)
            typer.echo(f"Wrote {p}")


if __name__ == "__main__":
    app()