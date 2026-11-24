"""Esquemas Pydantic del adaptador REST."""

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.models import IncidentStatus, SeverityLevel, TeamName


class TriageRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)

    @field_validator("incident_id", "raw_text")
    @classmethod
    def no_vacio(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El campo no puede contener solo espacios en blanco")
        return value


class TriageResponse(BaseModel):
    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: TeamName
    rationale: str
    duplicate_group_key: str


class ActiveIncidentItem(BaseModel):
    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int = Field(ge=0)
    is_breached: bool
    requires_escalation: bool

    @field_validator("status")
    @classmethod
    def solo_activos(cls, value: IncidentStatus) -> IncidentStatus:
        if value not in ("OPEN", "IN_PROGRESS"):
            raise ValueError("El resumen solo admite incidentes OPEN o IN_PROGRESS")
        return value


class ActiveIncidentsSummaryResponse(BaseModel):
    total_active: int = Field(ge=0)
    breached_count: int = Field(ge=0)
    incidents: list[ActiveIncidentItem]

    @model_validator(mode="after")
    def validar_totales(self) -> "ActiveIncidentsSummaryResponse":
        if self.total_active != len(self.incidents):
            raise ValueError("total_active no coincide con incidents")
        if self.breached_count > self.total_active:
            raise ValueError("breached_count no puede superar total_active")
        return self
