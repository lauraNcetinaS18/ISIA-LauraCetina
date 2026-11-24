# Implementation Plan: Ciclo de vida y auditoría de SLA de incidentes

**Branch**: `003-incident-lifecycle-sla` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-incident-lifecycle-sla/spec.md`

## Summary

Ampliar IncidentOps con registro de incidentes y auditoría determinista de SLA sin sustituir los
hitos 001 y 002. `IncidentService` incorpora `create_incident` y `evaluate_incident_sla` como
únicos casos de uso: el primero clasifica con `classify_incident_report`, detecta duplicados por
`duplicate_group_key` entre los estados OPEN/IN_PROGRESS/ESCALATION_REQUIRED y persiste el nuevo
incidente; el segundo recupera la entidad y delega el cálculo en `evaluate_sla_status`. El dominio
se enriquece con dos campos opcionales en `Incident` y con una normalización de marcas temporales
que, según la decisión P2 aprobada, rechaza toda marca aware y conserva sin cambios el
comportamiento naive ya verificado. El adaptador SQLite añade columnas y el índice
`idx_incidents_dup_key`; REST y CLI exponen los mismos casos de uso y la misma estructura JSON.
El código de salida CLI 1 adoptado por Q1 quedó formalizado en la enmienda constitucional 2.0.0,
por lo que no hay violación pendiente.

## Technical Context

**Language/Version**: Python 3.10+; ejecución siempre mediante `uv run`

**Primary Dependencies**: FastAPI, Pydantic v2, Typer, `sqlite3` (stdlib), `tiktoken`; desarrollo:
`pytest`, `httpx`, Ruff

**Storage**: SQLite3 embebido seleccionado por `DATABASE_URL` (default `sqlite:///:memory:`); sin
ORM; el esquema existente se amplía con columnas nullable y un índice compuesto

**Testing**: `uv run pytest -v`, escenarios BDD Given/When/Then con `TestClient` (REST) y
`CliRunner` (CLI), base de datos aislada por prueba mediante `DATABASE_URL` apuntando a un archivo
temporal; regresión de H001/H002 y verificación determinista del dominio

**Target Platform**: Runtime local/CI de Python; sin contenedores (`docs/ROADMAP.md` es
aspiracional)

**Project Type**: Servicio HTTP + CLI sobre un núcleo de dominio puro (arquitectura hexagonal,
ADR-003)

**Performance Goals**: Sin objetivo numérico nuevo en la especificación; se conserva el cálculo
de SLA O(D) de ADR-002 y la consulta de duplicados usa `idx_incidents_dup_key` para evitar un
escaneo completo; no se introduce N+1 en el caso de uso

**Constraints**: `src/domain/` solo biblioteca estándar (`dataclasses`, `typing`, `datetime`) y sin
frameworks, HTTP, BD ni imports de aplicación/adaptadores; `src/application/` sin adaptadores ni
frameworks; inbound sin `sqlite3`, sin repositorio legado y sin reglas de negocio propias; un solo
`IncidentService` para ambos canales; mapeo de errores 422/404 en REST y código 1 en CLI según la
decisión aprobada; sin ORM; código, docstrings y salidas en español

**Scale/Scope**: 22 requisitos funcionales, 18 escenarios de aceptación, 2 canales inbound, 1
adaptador outbound SQLite, esquema ampliado sin migraciones disruptivas; alcance limitado a
creación y consulta de SLA

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requisito constitucional | Evaluación | Evidencia en el diseño |
|---|---|---|
| I. Núcleo determinista único en `src/domain/` | PASS | La clasificación sigue en `triage_rules.py` y el SLA en `sla_calculator.py`; la normalización de marcas se añade en el dominio y no cambia resultados naive; los dos campos nuevos de `Incident` son opcionales y `compare=False` para no alterar igualdades de H002. |
| I. Reglas de severidad/equipo/duplicados no se reimplementan | PASS | `create_incident` llama a `classify_incident_report` y compara la clave devuelta con igualdad exacta; REST y CLI solo serializan. |
| II. Aplicación sin frameworks ni persistencia concreta | PASS | `IncidentService` importa solo dominio, `IncidentRepositoryPort` y módulos stdlib (`re`, `secrets`); la inyección llega desde `factory.py`. |
| II. Inbound delega en `IncidentService` | PASS | Los cuatro handlers/callbacks nuevos construyen el servicio con la factory y no contienen reglas de triaje, equipo, duplicados ni SLA. |
| II. Outbound intercambiable por `DATABASE_URL` | PASS | `factory.py` sigue siendo el único punto de selección; la firma del puerto no expone SQL. |
| III. SQLite3 sin ORMs; cambio de motor con ADR | PASS | No se introduce SQLAlchemy ni otro motor; no se requiere ADR nuevo. |
| III. Calidad: Ruff + BDD con `uv` | PASS | Se planifican `tests/test_spec_003_lifecycle_sla.py` con `test_bdd_*`, `TestClient`, `CliRunner`, casos borde y regresión; validación con `uv run ruff check src/` y `uv run pytest -v`. |
| Especificación sin clarificaciones abiertas | PASS | `checklists/requirements.md` 16/16; P1 y P2 aprobados y registrados en `spec.md`. |
| III. Errores de validación CLI → código 1 (enmienda 2.0.0) | PASS | La constitución 2.0.0 (`constitution.md:42`, `docs/constitution.md`) fija código 1 en todos los subcomandos y HTTP 422 en REST. Los contratos CLI de H001/H002 y la aserción de H002 quedan alineados; triage y summary conservan payloads y reglas. |

Re-evaluación posterior a Phase 1: **PASS sin excepciones**. El diseño no añade dependencias hacia
capas internas, no mueve reglas fuera del dominio y mantiene el resumen de H002 restringido a
OPEN/IN_PROGRESS.

## Project Structure

### Documentation (this feature)

```text
specs/003-incident-lifecycle-sla/
├── plan.md              # Este archivo (/speckit.plan)
├── research.md          # Decisiones técnicas de Phase 0
├── data-model.md        # Entidades, DTOs, puerto y esquema SQLite
├── quickstart.md        # Verificación de extremo a extremo de H003
├── contracts/           # Contratos HTTP, CLI y puerto de repositorio
│   ├── http-lifecycle.md
│   ├── cli-lifecycle.md
│   └── repository-port.md
└── tasks.md             # Generado por /speckit.tasks
```

### Source Code (repository root)

```text
src/
├── domain/
│   ├── models.py                      # MODIFICADO: Incident + recommended_team, duplicate_group_key
│   ├── triage_rules.py                # existente, sin cambios
│   ├── sla_calculator.py              # MODIFICADO: normalización de marcas naive/aware
│   └── ruff.toml                      # existente, sin cambios
├── application/
│   ├── ports.py                       # existente; se documenta el nuevo contrato de find_open_duplicates
│   ├── services.py                    # MODIFICADO: create_incident, evaluate_incident_sla, IncidentNotFoundError
│   └── ruff.toml                      # existente, sin cambios
└── adapters/
    ├── inbound/
    │   ├── api/
    │   │   ├── app.py                 # MODIFICADO: POST /api/v1/incidents, GET .../sla, 404/422
    │   │   └── schemas.py             # MODIFICADO: CreateIncidentRequest, IncidentCreatedResponse, SLAEvaluationResponse
    │   ├── cli.py                     # MODIFICADO: comandos create y sla; exit 1 en errores
    │   └── ruff.toml                  # existente, sin cambios
    └── outbound/
        ├── factory.py                 # existente, sin cambios
        └── sqlite_repository.py       # MODIFICADO: columnas, índice idx_incidents_dup_key, consulta de duplicados

tests/
├── conftest.py                        # existente; se reutilizan client/cli_runner
├── test_spec_001_triage.py            # existente, sin cambios funcionales
├── test_spec_002_summary.py           # MODIFICADO: único ajuste de aserción de exit code 2 → 1
└── test_spec_003_lifecycle_sla.py     # NUEVO: 18 escenarios BDD + borde + paridad + regresión
```

**Structure Decision**: Se conserva la topología hexagonal aceptada en ADR-003 y la skill
`hexagonal-architecture`. No se crean proyectos ni paquetes nuevos; `src/incident_repository.py`
sigue siendo solo el benchmark pedagógico y no es importado por H003. La persistencia continúa en
`src/adapters/outbound/`, seleccionada por `DATABASE_URL`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Código de salida 1 en CLI frente al código 2 original (RESUELTO por enmienda 2.0.0) | La aclaración Q1 aprobada en la sesión de 2026-11-24 exige un único criterio de error en todos los subcomandos (`create`, `sla`, `triage`, `summary`) para conservar la paridad REST/CLI. | Mantener el código 2 contradiría la especificación aprobada; aplicar el 1 solo a H003 dejaría dos convenciones en la misma CLI. La alternativa elegida minimizó el cambio: el único ajuste en H001/H002 fue la aserción/contrato del código de salida, sin tocar sus reglas ni payloads. |
| Columnas adicionales con valor `NULL` en `incidents` (`raw_text`, `recommended_team`, `duplicate_group_key`) | El esquema actual no persiste equipo ni clave de duplicado en la tabla de incidentes y el índice exigido `idx_incidents_dup_key` debe apoyarse en esas columnas; las filas sembradas por H002 insertan solo las columnas originales. | Hacer las columnas `NOT NULL` rompería las pruebas de 10.000 filas de H002; mantener la clave solo en `incident_duplicates` crearía dos fuentes de verdad y dejaría el índice sin uso. |
