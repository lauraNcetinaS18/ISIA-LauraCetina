# Contrato: `IncidentRepositoryPort`

**Feature**: `002-active-incidents-summary` | **Ubicación**: `src/application/ports.py` | **Implementación H002**: `src/adapters/outbound/sqlite_repository.py`

## Declaración prevista

```python
from datetime import datetime
from typing import Protocol

from src.domain.models import Incident


class IncidentRepositoryPort(Protocol):
    def save_incident(
        self, incident: Incident, duplicate_group_key: str | None = None
    ) -> None: ...

    def get_incident(self, incident_id: str) -> Incident | None: ...

    def find_open_duplicates(self, duplicate_group_key: str) -> list[Incident]: ...

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]: ...

    def check_health(self) -> bool: ...
```

## Semántica

| Método | Comportamiento |
|---|---|
| `save_incident` | Upsert por `incident_id`. Si `duplicate_group_key` no es `None`, se persiste en `incident_duplicates`. No calcula duplicados ni severidades. |
| `get_incident` | Devuelve la entidad reconstruida o `None` si no existe. |
| `find_open_duplicates` | Devuelve incidentes `OPEN`/`IN_PROGRESS` con la clave indicada, ordenados por `created_at, incident_id`. |
| `list_active_incidents` | Devuelve entidades `OPEN`/`IN_PROGRESS`, con `INNER JOIN sla_policies`, filtro opcional exacto por `component` y orden `created_at, incident_id`. Sin cálculo de SLA. |
| `check_health` | `True` si la conexión responde (p. ej. `SELECT 1`). |

## Requisitos de implementación

- El adapter debe reconstruir `Incident` usando `datetime.fromisoformat` para `created_at`/`resolved_at`.
- Debe respetar `DATABASE_URL` resuelto por `src/adapters.outbound.factory`; default `sqlite:///:memory:`.
- No debe importar dominio desde capas superiores ni frameworks HTTP/CLI.
- Debe crear el índice `idx_incidents_component_status ON incidents (component, status)` y la tabla `incident_duplicates` al inicializarse.
- No debe realizar full scan ni consultas N+1: una sola consulta con `JOIN` para `list_active_incidents`.

## Verificación de cumplimiento

`tests/test_spec_002_summary.py` incluirá una prueba de contrato que construya `SQLiteIncidentRepository` sobre BD temporal y verifique que expone los cinco métodos con las firmas y tipos esperados, además de un caso de humo para `save_incident` → `get_incident` → `list_active_incidents` → `find_open_duplicates` → `check_health`. Esta prueba complementa, no sustituye, los cuatro escenarios BDD. La misma implementación se mide con `test_rendimiento_sc_005_repositorio_10k` según el protocolo de SC-005 en `spec.md`.
