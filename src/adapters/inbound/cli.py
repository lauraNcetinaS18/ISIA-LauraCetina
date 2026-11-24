"""Adaptador CLI para el triaje y el resumen de incidentes."""

import json
from datetime import datetime

import typer

from src.adapters.outbound.factory import get_incident_repository
from src.application.services import IncidentService, ValidationError

app = typer.Typer()


@app.callback()
def main() -> None:
    """Expone los comandos de IncidentOps."""


@app.command("triage")
def triage(
    incident_id: str = typer.Option(..., "--incident-id"),
    raw_text: str = typer.Option(..., "--raw-text"),
) -> None:
    """Clasifica un reporte desde terminal y emite JSON."""
    service = IncidentService()
    try:
        result = service.triage_incident(incident_id, raw_text)
    except ValidationError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    payload = {
        "incident_id": result.incident_id,
        "severity": result.severity,
        "component": result.component,
        "recommended_team": result.recommended_team,
        "rationale": result.rationale,
        "duplicate_group_key": result.duplicate_group_key,
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("summary")
def summary(
    component: str | None = typer.Option(None, "--component"),
    reference_time: str | None = typer.Option(None, "--reference-time"),
) -> None:
    """Muestra el resumen de incidentes activos en JSON."""
    momento = None
    if reference_time is not None:
        try:
            momento = datetime.fromisoformat(reference_time)
        except ValueError as exc:
            typer.echo("Error: reference_time no es ISO 8601 válido", err=True)
            raise typer.Exit(code=2) from exc

    service = IncidentService(get_incident_repository())
    try:
        resultado = service.get_active_incidents_summary(component, momento)
    except (ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    app()
