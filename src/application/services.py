"""Casos de uso compartidos de IncidentOps."""

from datetime import datetime
from typing import Any

from src.application.ports import IncidentRepositoryPort
from src.domain.models import TriageResult
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Error de validación de entrada compartido por los adaptadores."""


class IncidentService:
    """Orquesta los casos de uso de incidentes sin depender de adaptadores."""

    def __init__(self, repository: IncidentRepositoryPort | None = None) -> None:
        self._repository = repository

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Valida la entrada y clasifica el reporte usando el dominio."""
        if not incident_id or not incident_id.strip():
            raise ValidationError("incident_id no puede estar vacío")
        if not raw_text or not raw_text.strip():
            raise ValidationError("raw_text no puede estar vacío")
        return classify_incident_report(incident_id.strip(), raw_text)

    def get_active_incidents_summary(
        self,
        component_filter: str | None = None,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Devuelve el resumen de activos usando solo reglas del dominio."""
        if self._repository is None:
            raise ValidationError("Repositorio de incidentes no configurado")

        filtro = component_filter.strip() if component_filter is not None else None
        if filtro == "":
            raise ValidationError("component no puede estar vacío")

        momento = reference_time if reference_time is not None else datetime.now()
        incidentes = self._repository.list_active_incidents(filtro)
        detalles = []

        for incidente in incidentes:
            evaluacion = evaluate_sla_status(incidente, momento)
            detalles.append(
                {
                    "incident_id": incidente.incident_id,
                    "title": incidente.title,
                    "component": incidente.component,
                    "severity": evaluacion.severity,
                    "status": incidente.status,
                    "elapsed_minutes": evaluacion.elapsed_minutes,
                    "is_breached": evaluacion.is_breached,
                    "requires_escalation": evaluacion.requires_escalation,
                }
            )

        return {
            "total_active": len(detalles),
            "breached_count": sum(1 for detalle in detalles if detalle["is_breached"]),
            "incidents": detalles,
        }
