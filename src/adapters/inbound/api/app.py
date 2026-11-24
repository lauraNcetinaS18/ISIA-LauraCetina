"""Adaptador REST para el triaje y el resumen de incidentes."""

from fastapi import FastAPI, HTTPException, status

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import get_incident_repository
from src.application.services import IncidentService, ValidationError


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI con el caso de uso de triaje."""
    app = FastAPI(title="IncidentOps Triage", version="1.0.0")
    service = IncidentService(get_incident_repository())

    @app.post("/v1/triage", response_model=TriageResponse)
    def triage(request: TriageRequest) -> TriageResponse:
        try:
            result = service.triage_incident(request.incident_id, request.raw_text)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return TriageResponse(
            incident_id=result.incident_id,
            severity=result.severity,
            component=result.component,
            recommended_team=result.recommended_team,
            rationale=result.rationale,
            duplicate_group_key=result.duplicate_group_key,
        )

    @app.get("/api/v1/incidents/summary", response_model=ActiveIncidentsSummaryResponse)
    def resumen_activos(component: str | None = None) -> ActiveIncidentsSummaryResponse:
        try:
            resultado = service.get_active_incidents_summary(component_filter=component)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return ActiveIncidentsSummaryResponse(**resultado)

    return app
