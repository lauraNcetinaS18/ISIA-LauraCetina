# Contrato HTTP: ciclo de vida y SLA

**Feature**: `003-incident-lifecycle-sla` | **Versión**: 1.0

## `POST /api/v1/incidents`

### Entrada

```json
{
  "title": "Pasarela de pagos devuelve HTTP 502",
  "raw_text": "HTTP 502 Bad Gateway en pasarela de pagos en todas las transacciones",
  "incident_id": "inc-a1b2c3d4",
  "created_at": "2026-11-06T17:00:00",
  "status": "OPEN"
}
```

| Campo | Tipo | Requerido | Regla |
|---|---|---|---|
| `title` | `str` | Sí | No vacío ni solo espacios. |
| `raw_text` | `str` | Sí | No vacío ni solo espacios. |
| `incident_id` | `str` | No | `INC-[0-9a-f]{8}`; ausente → generado; duplicado → rechazo. |
| `created_at` | `datetime` ISO 8601 | No | Naive; ausente → instante actual. |
| `status` | `IncidentStatus` | No | Default `OPEN`. |

### Salida: HTTP 201

```json
{
  "incident_id": "inc-a1b2c3d4",
  "title": "Pasarela de pagos devuelve HTTP 502",
  "component": "payments-gateway",
  "severity": "P0",
  "recommended_team": "Backend-Core",
  "rationale": "Impacto evaluado antes que palabras clave ...",
  "duplicate_group_key": "payments-gateway:http-502-outage",
  "status": "OPEN",
  "created_at": "2026-11-06T17:00:00",
  "is_duplicate": false,
  "duplicate_of": []
}
```

El orden de campos mostrado es el contrato de paridad con la CLI (FR-019).

## `GET /api/v1/incidents/{incident_id}/sla`

### Parámetro opcional

`reference_time`: marca ISO 8601 naive, p. ej. `2026-11-09T09:00:00`. Ausente → instante actual.

### Salida: HTTP 200

```json
{
  "incident_id": "inc-a1b2c3d4",
  "severity": "P2",
  "elapsed_minutes": 120,
  "allowed_minutes": 480,
  "remaining_minutes": 360,
  "is_breached": false,
  "requires_escalation": false
}
```

## Códigos de estado

| Código | Situación |
|---|---|
| `201` | Creación válida. |
| `200` | Auditoría de SLA válida. |
| `404` | `incident_id` inexistente en la auditoría. |
| `422` | Datos inválidos: campos vacíos, ID con formato inválido o duplicado, `reference_time` malformado, aware o anterior a `created_at`. |

Las rutas y payloads existentes de H001 (`POST /v1/triage`) y H002
(`GET /api/v1/incidents/summary`) no se modifican.

## Trazabilidad

FR-001, FR-002, FR-003, FR-004, FR-005, FR-007, FR-014, FR-016, FR-017, FR-018, FR-019, FR-021,
FR-022 y escenarios BDD 1–6 de US1 y 1–6 de US2.
