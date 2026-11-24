"""Puertos de aplicación de IncidentOps."""

from typing import Protocol

from src.domain.models import Incident


class IncidentRepositoryPort(Protocol):
    """Contrato de persistencia consumido por los casos de uso."""

    def save_incident(
        self, incident: Incident, duplicate_group_key: str | None = None
    ) -> None: ...

    def get_incident(self, incident_id: str) -> Incident | None: ...

    def find_open_duplicates(self, duplicate_group_key: str) -> list[Incident]: ...

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]: ...

    def check_health(self) -> bool: ...
