# Quickstart: verificación de `003-incident-lifecycle-sla`

**Feature**: `003-incident-lifecycle-sla` | **Especificación**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Prerrequisitos

- Python 3.10+ y `uv`; dependencias resueltas con `uv sync`.
- Ejecutar siempre desde la raíz del repositorio y dentro de `uv run`.
- Enmienda constitucional 2.0.0 aplicada para el código de salida 1 en CLI (decisión Q1) y
  contratos CLI de H001/H002 actualizados; sin ella, la verificación de exit codes fallaría.

## Puesta en marcha

```bash
uv sync
export DATABASE_URL="sqlite:///:memory:"
```

Para paridad REST/CLI usar un archivo temporal en `DATABASE_URL`, porque `:memory:` crea una base
distinta por conexión (ver [research.md](./research.md#r7--pruebas-y-paridad-restcli)).

## Verificación automatizada

```bash
uv run pytest -v
uv run ruff check src/
uv run python -m src.domain.sla_calculator
uv run python -m src.domain.triage_rules
```

Esperado: todos los escenarios de `tests/test_spec_003_lifecycle_sla.py` y las pruebas de H001/H002
pasan; `RESULTADO: TODOS LOS CASOS PASAN` en el dominio; Ruff sin violaciones TID251/TID252.
Los formatos de petición/respuesta y los códigos se detallan en
[contracts/http-lifecycle.md](./contracts/http-lifecycle.md) y
[contracts/cli-lifecycle.md](./contracts/cli-lifecycle.md).

## Escenarios de extremo a extremo

### 1. Registro sin duplicados

```bash
uv run python -m src.adapters.inbound.cli create --title "Pasarela caída" --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"
```

Esperado: JSON con `is_duplicate=false`, `duplicate_of=[]`, `severity="P0"`,
`recommended_team="Backend-Core"` y código de salida `0`.

### 2. Registro con duplicado abierto

Registrar después un segundo texto equivalente con la misma clave. Esperado: `is_duplicate=true` y
el identificador previo dentro de `duplicate_of`; un incidente `RESOLVED` con la misma clave no
aparece. Detalles en [data-model.md](./data-model.md#duplicados).

### 3. Auditoría determinista de SLA

```bash
uv run python -m src.adapters.inbound.cli sla --incident-id <ID> --reference-time "2026-11-09T09:00:00"
```

Con un P2 creado el viernes 2026-11-06 a las 17:00, esperado: `elapsed_minutes=120`,
`allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`,
`requires_escalation=false` y código `0`.

### 4. Errores

- ID inexistente en `sla`: HTTP 404 / CLI 1.
- `reference_time` anterior a `created_at`, aware o malformado: HTTP 422 / CLI 1.
- `title` o `raw_text` vacíos, ID con formato inválido o duplicado: HTTP 422 / CLI 1.
- `triage` y `summary` con datos inválidos: CLI 1 (cambio acordado en Q1).

### 5. Paridad REST/CLI

Repetir el registro y la auditoría por `POST /api/v1/incidents` y
`GET /api/v1/incidents/{incident_id}/sla` con los mismos datos y `reference_time`; comparar campo
por campo con la salida de la CLI. Esperado: estructuras idénticas (SC-005).

## Salida de esta fase

Este quickstart valida el diseño; la implementación y la división en tareas se generan después con
`/speckit.tasks`. No se ha modificado código fuente en esta fase.
