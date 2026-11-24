# Contrato HTTP: GET /api/v1/incidents/summary

**Feature**: `002-active-incidents-summary` | **Versión**: 1.0 | **Base**: `create_app()` en `src/adapters/inbound/api/app.py`

## Request

```http
GET /api/v1/incidents/summary HTTP/1.1
GET /api/v1/incidents/summary?component=payments-gateway HTTP/1.1
```

| Parámetro | Ubicación | Tipo | Requerido | Descripción |
|---|---|---|---|---|
| `component` | query | `str` | No | Filtro exacto por componente. Si se omite, se devuelven todos los activos. |

No se expone `reference_time` en HTTP; el servicio usa `datetime.now()` una vez por petición.

## Response 200

`Content-Type: application/json`. Modelo: `ActiveIncidentsSummaryResponse`.

| Campo | Tipo | Regla |
|---|---|---|
| `total_active` | `integer` | `len(incidents)` |
| `breached_count` | `integer` | Número de entradas con `is_breached = true` |
| `incidents` | `array<ActiveIncidentItem>` | Ordenado por `created_at`, luego `incident_id` |

`ActiveIncidentItem`: `incident_id`, `title`, `component`, `severity`, `status`, `elapsed_minutes`, `is_breached`, `requires_escalation`.

Ejemplo con datos:

```json
{
  "total_active": 1,
  "breached_count": 1,
  "incidents": [
    {
      "incident_id": "INC-1001",
      "title": "HTTP 502 Bad Gateway en pasarela de pagos",
      "component": "payments-gateway",
      "severity": "P0",
      "status": "OPEN",
      "elapsed_minutes": 75,
      "is_breached": true,
      "requires_escalation": true
    }
  ]
}
```

Ejemplo vacío (FR-009, exacto):

```json
{"total_active": 0, "breached_count": 0, "incidents": []}
```

## Errores

| Situación | Código | Cuerpo |
|---|---|---|
| `component` vacío o solo espacios | 422 | `{"detail": "component no puede estar vacío"}` |
| `reference_time` del dominio anterior a `created_at` | 422 | `{"detail": "<mensaje de ValueError del dominio>"}` |

La capa HTTP no implementa reglas de severidad, escalamiento ni duplicados: solo mapea `ValidationError`/`ValueError` a 422 y devuelve el DTO que produjo `IncidentService`.

## Trazabilidad

FR-001, FR-002, FR-003, FR-004, FR-005, FR-009, FR-010, FR-013 y escenarios BDD 1–3 de `spec.md`.
