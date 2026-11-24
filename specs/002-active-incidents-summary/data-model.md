# Data Model: Resumen de incidentes activos

**Feature**: `002-active-incidents-summary` | **Fecha**: 2026-11-24

## 1. Entidades de dominio (existentes, sin cambios)

Definidas en `src/domain/models.py` y `src/domain/sla_calculator.py`.

| Entidad | Campos | Reglas |
|---|---|---|
| `Incident` | `incident_id: str`, `title: str`, `component: str`, `severity: SeverityLevel`, `status: IncidentStatus`, `created_at: datetime`, `resolved_at: datetime \| None` | `status` ∈ `OPEN`, `IN_PROGRESS`, `RESOLVED`, `ESCALATION_REQUIRED`. Para H002 solo se consumen `OPEN`/`IN_PROGRESS`. |
| `SLARule` | `severity`, `max_resolution_minutes`, `operates_24x7`, `escalation_threshold_ratio = 0.75` | `SLA_POLICY_TABLE`: P0=60/24x7, P1=240/24x7, P2=480/hábil, P3=1440/hábil. |
| `SLAEvaluation` | `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation` | `elapsed_minutes ≥ 0`; `allowed_minutes` copia `SLARule.max_resolution_minutes`; breach si `elapsed > allowed`; escalamiento si `status != RESOLVED` y (`is_breached` o `elapsed ≥ 75 %` de `allowed`). `end_time = resolved_at or reference_time`; el dominio rechaza `end_time < created_at`. |

`evaluate_sla_status(incident, reference_time=None)` sigue siendo la única operación que produce `SLAEvaluation`.

## 2. DTOs inbound (nuevos en `src/adapters/inbound/api/schemas.py`)

### `ActiveIncidentItem`

| Campo | Tipo | Origen | Observación |
|---|---|---|---|
| `incident_id` | `str` | `Incident.incident_id` | Se incluye para trazabilidad y para el orden determinista por `created_at, incident_id`. |
| `title` | `str` | `Incident.title` | Texto original del incidente. |
| `component` | `str` | `Incident.component` | Componente exacto. |
| `severity` | `SeverityLevel` | `Incident.severity` | Literal P0–P3. |
| `status` | `IncidentStatus` | `Incident.status` | Solo `OPEN` o `IN_PROGRESS` en respuestas H002. |
| `elapsed_minutes` | `int` | `SLAEvaluation.elapsed_minutes` | Minutos hábiles/24x7 según severidad. |
| `is_breached` | `bool` | `SLAEvaluation.is_breached` | Derivado; hace auditable `breached_count`. |
| `requires_escalation` | `bool` | `SLAEvaluation.requires_escalation` | Campo exigido como "si requiere escalamiento". |

### `ActiveIncidentsSummaryResponse`

| Campo | Tipo | Regla |
|---|---|---|
| `total_active` | `int` | `len(incidents)`; entero ≥ 0. |
| `breached_count` | `int` | Cantidad de `incidents` con `is_breached == True`; `0 ≤ breached_count ≤ total_active`. |
| `incidents` | `list[ActiveIncidentItem]` | Ordenado por `created_at` ascendente y, en empate, por `incident_id` ascendente. Vacío → `[]`. |

Respuesta vacía canónica:

```json
{"total_active": 0, "breached_count": 0, "incidents": []}
```

## 3. Puerto de aplicación (nuevo en `src/application/ports.py`)

`IncidentRepositoryPort` es un `typing.Protocol` con los cinco métodos acordados. La firma completa y su semántica están en [`contracts/repository-port.md`](./contracts/repository-port.md). Resumen:

- `save_incident(incident, duplicate_group_key=None) -> None` — upsert por `incident_id`; si se entrega clave, se registra en `incident_duplicates`.
- `get_incident(incident_id) -> Incident | None` — entidad o `None`.
- `find_open_duplicates(duplicate_group_key) -> list[Incident]` — activos con esa clave, ordenados por `created_at, incident_id`.
- `list_active_incidents(component_filter=None) -> list[Incident]` — solo `OPEN`/`IN_PROGRESS`, con severidad presente en `sla_policies`.
- `check_health() -> bool` — `True` si la conexión responde.

## 4. Esquema SQLite del adapter (nuevo en `src/adapters/outbound/sqlite_repository.py`)

### Tablas

```text
sla_policies(severity TEXT PRIMARY KEY,
             max_resolution_minutes INTEGER NOT NULL,
             operates_24x7 INTEGER NOT NULL)

incidents(incident_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          component TEXT NOT NULL,
          severity TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          resolved_at TEXT)

incident_duplicates(incident_id TEXT PRIMARY KEY,
                    duplicate_group_key TEXT NOT NULL)
```

`sla_policies` se puebla desde `SLA_POLICY_TABLE` al inicializar, igual que en el legado. `incident_duplicates` es nueva y no altera las columnas existentes de `incidents`.

### Índice

```text
CREATE INDEX IF NOT EXISTS idx_incidents_component_status
ON incidents (component, status)
```

### Consulta base de `list_active_incidents`

```sql
SELECT i.incident_id, i.title, i.component, i.severity,
       i.status, i.created_at, i.resolved_at
FROM incidents AS i
INNER JOIN sla_policies AS sp ON sp.severity = i.severity
WHERE i.status IN ('OPEN', 'IN_PROGRESS')
  AND (? IS NULL OR i.component = ?)
ORDER BY i.created_at ASC, i.incident_id ASC
```

El `JOIN` evita el N+1 y garantiza política existente; el cálculo de SLA ocurre después, en el servicio. Fechas se guardan en ISO 8601 y se reconstruyen con `datetime.fromisoformat`.

## 5. Reglas de validación y transformación

| Entrada | Validación | Error |
|---|---|---|
| `component` (REST/CLI) | Opcional; si llega, no vacío después de `strip()` | `ValidationError` → HTTP 422 / CLI exit 2 |
| `reference_time` (CLI) | Opcional; ISO 8601 parseable por `datetime.fromisoformat` | `ValidationError` → CLI exit 2 |
| `reference_time` (servicio) | Si es `None`, `datetime.now()` una vez por llamada | — |
| `created_at > reference_time` | Lo rechaza el dominio al evaluar SLA | `ValueError` propagado y mapeado por el adaptador |
| `DATABASE_URL` | Debe empezar con `sqlite:///` en H002 | Error explícito de configuración en la factory |

## 6. Transiciones de estado

No se introducen transiciones nuevas. El resumen es de solo lectura: no cambia `status`, no resuelve incidentes y no dispara escalamientos reales; `requires_escalation` es únicamente una señal derivada del dominio.

## 7. Trazabilidad de requisitos

| Requisito | Elemento del modelo |
|---|---|
| FR-001 / FR-002 / FR-003 | `list_active_incidents` + `ActiveIncidentsSummaryResponse` |
| FR-004 | `ActiveIncidentItem.is_breached` desde `SLAEvaluation.is_breached` y `SLAEvaluation.allowed_minutes` |
| FR-005 | `ActiveIncidentItem` (título, componente, severidad, estado, minutos, escalamiento) |
| FR-006 | `list_active_incidents(component_filter)` + `idx_incidents_component_status` |
| FR-008 | `ActiveIncidentItem.requires_escalation` desde `SLAEvaluation.requires_escalation` |
| FR-013 / FR-014 / FR-015 | DTOs de respuesta y `reference_time` en `IncidentService` |
| SC-005 | `INNER JOIN sla_policies` + `idx_incidents_component_status`; verificado por `test_rendimiento_sc_005_repositorio_10k` con el protocolo de `spec.md` |

`find_open_duplicates` y `incident_duplicates` permanecen en el puerto y el adapter como capacidades definidas en el contrato, pero no son la realización de FR-006.
