# Contrato del puerto de repositorio: H003

**Feature**: `003-incident-lifecycle-sla` | **Puerto**: `src/application/ports.py`

## Métodos utilizados por `IncidentService`

| Método | Uso en H003 | Cambio respecto a H002 |
|---|---|---|
| `save_incident(incident, duplicate_group_key=None)` | Persiste el incidente nuevo con su clave. | Ahora escribe `raw_text`, `recommended_team` y `duplicate_group_key` en `incidents`. |
| `get_incident(incident_id)` | Recupera para auditoría y valida unicidad del ID. | Reconstruye los campos nuevos; `None` si no existe. |
| `find_open_duplicates(duplicate_group_key)` | Devuelve equivalentes abiertos. | Incluye `ESCALATION_REQUIRED` y ordena por `incident_id ASC`. |
| `list_active_incidents(component_filter=None)` | Sin uso en H003. | **Sin cambios**: solo OPEN e IN_PROGRESS. |
| `check_health()` | Sin uso en H003. | Sin cambios. |

## `find_open_duplicates`

- Entrada: `duplicate_group_key: str` exacto, sin normalización adicional.
- Filtro de estados: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`.
- Orden: `incident_id` ascendente.
- Salida: `list[Incident]` con los campos ampliados reconstruidos.
- La exclusión del propio incidente recién creado es responsabilidad de `create_incident`, que
  consulta antes de guardar y filtra además por ID.

## Invariantes

- El puerto no expone SQL ni tipos de SQLite.
- Ninguna regla de severidad, equipo, duplicados ni SLA se implementa en el adaptador; el SQL solo
  filtra estados y aplica igualdad de cadena.
- `INSERT OR REPLACE` sigue vigente; la validación de unicidad ocurre en el servicio antes de
  guardar para no sobrescribir un registro existente.
- La selección del adaptador sigue dependiendo exclusivamente de `DATABASE_URL` a través de
  `src/adapters/outbound/factory.py`.

## Trazabilidad

FR-006, FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-020, decisión P1 y `data-model.md`.
