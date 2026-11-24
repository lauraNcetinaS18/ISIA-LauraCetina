# Implementation Plan: Resumen de incidentes activos

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-active-incidents-summary/spec.md`

## Summary

Habilitar una vista agregada y determinista de incidentes activos (`OPEN`/`IN_PROGRESS`) con filtro opcional por componente, expuesta simultáneamente por `GET /api/v1/incidents/summary` y por el subcomando `summary` de Typer. El caso de uso `get_active_incidents_summary(component_filter, reference_time)` vivirá en `src/application/services.py`, obtendrá los incidentes crudos mediante el nuevo `IncidentRepositoryPort` (`src/application/ports.py`) y delegará todo cálculo de SLA/escalamiento a `src/domain/sla_calculator.py`. La persistencia se aislará en `src/adapters/outbound/sqlite_repository.py`, seleccionada por `src/adapters/outbound/factory.py` desde `DATABASE_URL` (default `sqlite:///:memory:`), usando `INNER JOIN sla_policies` e índice compuesto `(component, status)` para eliminar el full scan y el N+1 del benchmark heredado sin reimplementar reglas de negocio en adaptadores. SC-005 se verifica con una prueba automatizada sobre 10.000 filas del nuevo adapter, no sobre el benchmark legado.

## Technical Context

**Language/Version**: Python 3.10+ (ejecución siempre vía `uv`)

**Primary Dependencies**: FastAPI, Pydantic v2, Typer, `sqlite3` (stdlib); desarrollo: `pytest`, `httpx`, Ruff

**Storage**: SQLite3 embebido; `DATABASE_URL` con default `sqlite:///:memory:`; cambio de motor exige ADR previo

**Testing**: `uv run pytest -v` con BDD Given/When/Then, `TestClient` para REST, `CliRunner` para CLI y BD temporal aislada por prueba

**Target Platform**: Runtime local/CI de Python (sin contenedores; `docs/ROADMAP.md` es aspiracional)

**Project Type**: Servicio HTTP + CLI sobre un núcleo de dominio puro (arquitectura hexagonal)

**Performance Goals**: 10.000 incidentes con consulta < 2 s (SC-005), verificado por `test_rendimiento_sc_005_repositorio_10k` con el protocolo de `spec.md`; cálculo SLA O(D) según ADR-002

**Constraints**: Dominio sin frameworks/BD/HTTP; aplicación sin adaptadores concretos; inbound nunca importa `sqlite3` ni el repositorio legado; sin ORMs pesados; mapeo `ValidationError` → HTTP 422 / CLI exit 1 (constitución 2.0.0); salidas y docstrings en español

**Scale/Scope**: 10.000 registros sintéticos, 2 canales de entrada (REST + CLI), 1 adaptador outbound SQLite inicial

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requisito constitucional | Evaluación | Evidencia en el diseño |
|---|---|---|
| Núcleo determinista en `src/domain/` | PASS | `evaluate_sla_status` sigue siendo la única fuente de `elapsed_minutes`, `is_breached` y escalamiento; `models.py` no se modifica. |
| Aplicación sin frameworks ni persistencia | PASS | `IncidentService` importa solo dominio y `IncidentRepositoryPort` (`typing.Protocol`); la inyección llega desde `factory.py`. |
| Inbound delega y mapea errores | PASS | REST y CLI construyen el servicio con el repositorio de la factory, delegando a `get_active_incidents_summary`; `ValidationError` → 422 / exit 1 (constitución 2.0.0). |
| Outbound intercambiable por `DATABASE_URL` | PASS | `factory.py` selecciona `SQLiteIncidentRepository`; default `sqlite:///:memory:`; la firma del puerto no expone SQL. |
| SQLite3 sin ORMs; cambio de motor con ADR | PASS | No se introduce SQLAlchemy ni nuevo motor; no se requiere ADR adicional. |
| Calidad: Ruff + BDD con `uv` | PASS | Se planifican `[tool.ruff.lint]`, `ruff.toml` jerárquicos y `tests/test_spec_002_summary.py` con `test_bdd_*`, `TestClient`, `CliRunner`, `test_bdd_sqlite_repository_cumple_puerto` y `test_rendimiento_sc_005_repositorio_10k`; los escenarios BDD se escriben antes de su implementación. |
| Especificación y checklist sin clarificaciones abiertas | PASS | `checklists/requirements.md` 16/16; 4 escenarios BDD acordados en `## Clarifications`. |

Re-evaluación posterior a Phase 1: **PASS** sin cambios; el diseño no introduce dependencias hacia capas internas ni reglas de negocio fuera del dominio.

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── plan.md              # Este archivo (/speckit.plan)
├── research.md          # Decisión técnica de Phase 0
├── data-model.md        # Entidades, DTOs, puerto y esquema SQLite
├── quickstart.md        # Arranque y verificación de H002
├── contracts/           # Contratos HTTP, CLI y puerto de repositorio
│   ├── http-summary.md
│   ├── cli-summary.md
│   └── repository-port.md
└── tasks.md             # Phase 2 (/speckit.tasks) - NO creado por /speckit.plan
```

### Source Code (repository root)

```text
pyproject.toml                         # MODIFICADO: [tool.ruff.lint] + TID252

src/
├── domain/
│   ├── models.py                      # existente, sin cambios
│   ├── triage_rules.py                # existente, sin cambios
│   ├── sla_calculator.py              # existente, sin cambios
│   └── ruff.toml                      # NUEVO: TID251 (sin frameworks/BD/adapters)
├── application/
│   ├── ports.py                       # NUEVO: IncidentRepositoryPort
│   ├── services.py                    # MODIFICADO: get_active_incidents_summary
│   └── ruff.toml                      # NUEVO: TID251 (sin frameworks/drivers/adapters)
└── adapters/
    ├── inbound/
    │   ├── api/
    │   │   ├── app.py                 # MODIFICADO: GET /api/v1/incidents/summary
    │   │   └── schemas.py             # MODIFICADO: ActiveIncidentItem, ActiveIncidentsSummaryResponse
    │   ├── cli.py                     # MODIFICADO: comando summary
    │   └── ruff.toml                  # NUEVO: TID251 (sin drivers ni repo legado)
    └── outbound/
        ├── __init__.py                # existente, sin cambios
        ├── factory.py                 # NUEVO: get_incident_repository() desde DATABASE_URL
        └── sqlite_repository.py       # NUEVO: SQLiteIncidentRepository

tests/
├── conftest.py                        # MODIFICADO: fixtures de BD temporal/servicio
├── test_spec_001_triage.py            # existente, sin cambios
└── test_spec_002_summary.py           # NUEVO: 4 BDD + casos borde + SC-005 + cumplimiento del puerto
```

**Structure Decision**: Se conserva la estructura hexagonal ya aceptada en ADR-003. `src/incident_repository.py` permanece únicamente como benchmark pedagógico de Semana 1 y no es importado por el flujo H002; la persistencia en producción pasa a `src/adapters/outbound/`. No se crean proyectos ni paquetes nuevos fuera de `src/` y `tests/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `src/incident_repository.py` mantiene SQL fuera de `src/adapters/outbound/` | Es el benchmark intencional de H001; `AGENTS.md` indica no refactorizarlo salvo petición explícita y sigue siendo referencia didáctica de full scan + N+1. | Eliminarlo rompería la verificación histórica `uv run python -m src.incident_repository`; dejar que el nuevo flujo lo importe violaría ADR-003, por lo que se aísla mediante factory y TID251. |
