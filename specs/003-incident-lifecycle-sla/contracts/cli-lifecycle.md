# Contrato CLI: subcomandos `create` y `sla`

**Feature**: `003-incident-lifecycle-sla` | **Versión**: 1.0 | **Ubicación**: `src/adapters/inbound/cli.py`

## Invocación

```text
uv run python -m src.adapters.inbound.cli create --title TEXTO --raw-text TEXTO [--incident-id ID] [--created-at ISO8601] [--status ESTADO]
uv run python -m src.adapters.inbound.cli sla --incident-id ID [--reference-time ISO8601]
```

| Opción | Tipo | Requerida | Descripción |
|---|---|---|---|
| `--title` | `str` | Sí* | No vacío ni solo espacios. |
| `--raw-text` | `str` | Sí* | No vacío ni solo espacios. |
| `--incident-id` | `str` | No | `INC-[0-9a-f]{8}`; ausente → generado. |
| `--created-at` | `str` | No | ISO 8601 naive; ausente → instante actual. |
| `--status` | `str` | No | Uno de los estados vigentes; default `OPEN`. |
| `--reference-time` | `str` | No | ISO 8601 naive; ausente → instante actual. |

\* Se declara como opción opcional en Typer y se valida en `IncidentService`, de modo que una
omisión produzca código de salida 1 y no el código 2 del framework.

## Salida

Una sola línea JSON en `stdout`, con el mismo orden de campos que el contrato HTTP:

```json
{"incident_id": "inc-a1b2c3d4", "title": "...", "component": "payments-gateway", "severity": "P0", "recommended_team": "Backend-Core", "rationale": "...", "duplicate_group_key": "payments-gateway:http-502-outage", "status": "OPEN", "created_at": "2026-11-06T17:00:00", "is_duplicate": false, "duplicate_of": []}
```

```json
{"incident_id": "inc-a1b2c3d4", "severity": "P2", "elapsed_minutes": 120, "allowed_minutes": 480, "remaining_minutes": 360, "is_breached": false, "requires_escalation": false}
```

Se usa `json.dumps(payload, ensure_ascii=False)`; no se imprimen mensajes adicionales en `stdout`.

## Códigos de salida

| Código | Situación |
|---|---|
| `0` | Creación o auditoría válida. |
| `1` | `ValidationError`, `ValueError` de dominio, ID inexistente o error de parseo de fecha, en cualquier subcomando. El mensaje va a `stderr` con prefijo `Error: `. |

La adopción del código `1` en `triage` y `summary` sustituye al `2` original por la enmienda
constitucional 2.0.0 derivada de Q1; sus payloads y reglas de negocio no cambian. Queda fuera de
este contrato el error de framework «opción desconocida», gobernado por Click.

## Paridad REST/CLI

Ambos canales construyen `IncidentService(get_incident_repository())` y delegan en
`create_incident` / `evaluate_incident_sla`. Con la misma entrada y el mismo `reference_time`, los
payloads son estructuralmente idénticos (FR-019).

## Trazabilidad

FR-001, FR-007, FR-015, FR-018, FR-019 y escenarios BDD 1–5 de US3.
