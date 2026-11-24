# Contrato CLI: subcomando `summary`

**Feature**: `002-active-incidents-summary` | **Versión**: 1.0 | **Ubicación**: `src/adapters/inbound/cli.py`

## Invocación

```text
uv run python -m src.adapters.inbound.cli summary [--component TEXTO] [--reference-time ISO8601]
```

| Opción | Tipo | Requerida | Descripción |
|---|---|---|---|
| `--component` | `str` | No | Filtro exacto por componente; se aplica `strip()` antes de delegar. |
| `--reference-time` | `str` | No | ISO 8601 parseable por `datetime.fromisoformat`, p. ej. `2026-11-24T12:00:00`. Si se omite, el servicio usa el instante actual. |

## Salida

Una sola línea JSON en `stdout`, con la misma estructura y el mismo orden de campos que el contrato HTTP:

```json
{"total_active": 0, "breached_count": 0, "incidents": []}
```

Se usa `json.dumps(payload, ensure_ascii=False)`, igual que en el comando `triage`. No se imprimen mensajes adicionales en `stdout`.

## Códigos de salida

| Código | Situación |
|---|---|
| `0` | Resumen generado correctamente (incluso sin incidentes). |
| `2` | `ValidationError` por `component` vacío, `--reference-time` inválido o error de dominio al evaluar SLA; el mensaje va a `stderr` con prefijo `Error: `. |

## Paridad REST/CLI

El payload debe ser estructuralmente idéntico al de `GET /api/v1/incidents/summary` cuando ambos comparten el mismo instante de referencia (SC-003). El CLI solo cambia la forma de entrega del reloj: `--reference-time` explícito frente a `datetime.now()` implícito del HTTP. En la prueba de paridad se congela el reloj del servicio en HTTP mediante una fixture y se pasa el mismo instante a `--reference-time`, conforme a la aclaración de `spec.md`.

## Trazabilidad

FR-001, FR-002, FR-003, FR-004, FR-005, FR-009, FR-012, FR-014, FR-015 y escenario BDD 4 de `spec.md`.
