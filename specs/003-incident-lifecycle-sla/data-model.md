# Modelo de datos: Ciclo de vida y auditoría de SLA de incidentes

**Feature**: `003-incident-lifecycle-sla` | **Especificación**: [spec.md](./spec.md)

## Entidades de dominio

### `Incident` (`src/domain/models.py`, ampliado)

| Campo | Tipo | Origen | Regla |
|---|---|---|---|
| `incident_id` | `str` | Provisto o generado | Generado: `INC-` + 8 hexadecimales en minúsculas. Provisto: `^INC-[0-9a-f]{8}$` y único. |
| `title` | `str` | Obligatorio | No vacío ni solo espacios; se conserva tal como llega. |
| `component` | `str` | `TriageResult` | Lo determina el dominio, nunca el adaptador. |
| `severity` | `SeverityLevel` | `TriageResult` | P0–P3 por impacto real. |
| `recommended_team` | `Optional[TeamName]` nuevo | `TriageResult` | Uno de los cuatro equipos válidos; `None` en incidentes sembrados por H002. |
| `status` | `IncidentStatus` | Provisto o `OPEN` | OPEN, IN_PROGRESS, ESCALATION_REQUIRED, RESOLVED. |
| `created_at` | `datetime` | Provisto o instante actual | Naive, hora local del servidor; aware se rechaza. |
| `resolved_at` | `Optional[datetime]` | Existente | Naive; no se modifica en H003. |
| `duplicate_group_key` | `Optional[str]` nuevo | `TriageResult` | `<component>:<symptom_category>`, comparación exacta; `None` en filas antiguas. |
| `raw_text` | `str` (persistido) | Obligatorio | No vacío ni solo espacios; se conserva tal como llega. |

Los dos campos nuevos se declaran con `field(default=None, compare=False)` para preservar la
igualdad de `Incident` verificada por H002. No participan en el cálculo de SLA ni de triaje.

### `SLAEvaluation` (`src/domain/models.py`, sin cambios)

`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`,
`is_breached`, `requires_escalation`. El cálculo sigue en `evaluate_sla_status` (ADR-002).

### Not-found

`IncidentNotFoundError(LookupError)` en `src/application/services.py`: distinto de
`ValidationError` para que REST pueda responder 404 sin confundirlo con validación.

## Reglas de validación

| Dato | Regla | Error |
|---|---|---|
| `title`, `raw_text` | Cadena no vacía y con algún carácter que no sea espacio | `ValidationError` → 422 / CLI 1 |
| `incident_id` provisto | `^INC-[0-9a-f]{8}$` | `ValidationError` → 422 / CLI 1 |
| `incident_id` duplicado | No existe previamente en el repositorio | `ValidationError` → 422 / CLI 1 |
| `incident_id` ausente | `INC-` + `secrets.token_hex(4)`; reintentar si colisiona | — |
| `created_at`, `reference_time` | ISO 8601 naive; aware rechazada | `ValidationError` → 422 / CLI 1 |
| `status` | `Literal` vigente; omisión = `OPEN` | Rechazo por esquema → 422 / CLI 1 |
| `reference_time < created_at` | Se rechaza | `ValueError` de dominio → 422 / CLI 1 |
| Incidente inexistente en SLA | `get_incident` devuelve `None` | `IncidentNotFoundError` → 404 / CLI 1 |

## Duplicados

- Clave: igualdad exacta de `duplicate_group_key` (ya normalizada por el dominio).
- Estados candidatos: OPEN, IN_PROGRESS y ESCALATION_REQUIRED.
- Excluidos: RESOLVED y el propio `incident_id` recién creado.
- Resultado: `duplicate_of` con todos los identificadores coincidentes, ordenados por
  `incident_id` ascendente; `is_duplicate = bool(duplicate_of)`.
- Un duplicado abierto no impide la creación; ambos incidentes se persisten.

## Transiciones de estado

No se introduce automata nuevo. Se conservan los estados y las reglas de escalamiento de ADR-002:
el escalamiento depende de `status != RESOLVED` y de los umbrales de SLA, pero H003 no cambia el
`status` almacenado. La inclusión de ESCALATION_REQUIRED en la búsqueda de duplicados **no** la
incorpora al resumen de H002.

## DTOs de los adaptadores

### `CreateIncidentRequest`

`title: str`, `raw_text: str`, `incident_id: str | None = None`,
`created_at: datetime | None = None`, `status: IncidentStatus = "OPEN"`.

### `IncidentCreatedResponse`

`incident_id`, `title`, `component`, `severity`, `recommended_team`, `rationale`,
`duplicate_group_key`, `status`, `created_at`, `is_duplicate`, `duplicate_of`. Se usa el mismo
orden de campos en REST y CLI.

### `SLAEvaluationResponse`

`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`,
`is_breached`, `requires_escalation`.

## Contrato del repositorio (`src/application/ports.py`)

La interfaz existente se conserva; cambia el comportamiento documentado de un método:

- `save_incident(incident, duplicate_group_key=None)`: persiste los campos ampliados.
- `get_incident(incident_id)`: reconstruye `Incident` con los campos ampliados o devuelve `None`.
- `find_open_duplicates(duplicate_group_key)`: devuelve los incidentes OPEN, IN_PROGRESS y
  ESCALATION_REQUIRED con esa clave exacta, ordenados por `incident_id`.
- `list_active_incidents(component_filter=None)`: **sin cambios**, solo OPEN e IN_PROGRESS.
- `check_health()`: sin cambios.

## Esquema SQLite (`src/adapters/outbound/sqlite_repository.py`)

```text
incidents (
  incident_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  raw_text TEXT,                    -- NUEVO, nullable por compatibilidad con H002
  component TEXT NOT NULL,
  severity TEXT NOT NULL,
  recommended_team TEXT,            -- NUEVO, nullable
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  duplicate_group_key TEXT          -- NUEVO, nullable
)

CREATE INDEX IF NOT EXISTS idx_incidents_dup_key
  ON incidents (duplicate_group_key, status);
```

`incident_duplicates` y `sla_policies` permanecen intactas. Las fechas se guardan en ISO 8601 y se
reconstruyen con `datetime.fromisoformat`, conservando el contrato de H002.
