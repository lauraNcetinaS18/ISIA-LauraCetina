---

description: "Task list for feature implementation"
---

# Tasks: Ciclo de vida y auditoría de SLA de incidentes

**Input**: Design documents from `/specs/003-incident-lifecycle-sla/`

**Prerequisites**: `plan.md` (requerido), `spec.md` (requerido para historias), `research.md`, `data-model.md`, `contracts/`

**Tests**: Incluidos porque `spec.md` exige en SC-008 una prueba automatizada por escenario de aceptación.

**Organization**: Las tareas se agrupan por historia de usuario para permitir implementación y verificación independientes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias de tareas incompletas)
- **[Story]**: Etiqueta obligatoria solo en las fases de historias de usuario (US1, US2, US3)
- Todas las descripciones incluyen rutas exactas de archivo

## Path Conventions

- **Single project**: `src/` y `tests/` en la raíz del repositorio
- Sin proyectos ni paquetes nuevos; se conserva la topología hexagonal de `docs/adr/003-arquitectura-hexagonal.md`
- `src/incident_repository.py` permanece aislado como benchmark pedagógico

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prerrequisitos de gobernanza y documentación anteriores a cualquier historia

- [ ] T001 Verificar que `pyproject.toml`, `src/domain/`, `src/application/`, `src/adapters/inbound/`, `src/adapters/outbound/` y `tests/` conservan la topología de ADR-003 sin añadir dependencias ni proyectos nuevos
- [ ] T002 Verificar que la enmienda constitucional 2.0.0 está aplicada en `.specify/memory/constitution.md` y `docs/constitution.md`: código de salida CLI 1 en todos los subcomandos, HTTP 422 en REST, versión 2.0.0 y `Last Amended` 2026-11-24
- [ ] T003 [P] Verificar la documentación CLI alineada con la enmienda 2.0.0 en `specs/001-triage-endpoint-manual.md` (códigos 0/1 explícitos) y `specs/002-active-incidents-summary/contracts/cli-summary.md` (exit 1), sin cambiar payloads ni reglas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Núcleo compartido que DEBE estar completo antes de iniciar cualquier historia

**⚠️ CRITICAL**: No iniciar trabajo de historias hasta terminar esta fase

- [ ] T004 [P] Ampliar `Incident` en `src/domain/models.py` con `recommended_team` y `duplicate_group_key` usando `field(default=None, compare=False)`, conservando las definiciones de `data-model.md` para `Incident.incident_id`, `Incident.title`, `Incident.component`, `Incident.severity`, `Incident.status`, `Incident.created_at`, `Incident.resolved_at` e `Incident.raw_text`
- [ ] T005 [P] Añadir en `src/domain/sla_calculator.py` un helper de normalización que rechace marcas aware y devuelva sin transformar las naive, invocándolo antes de comparar `Incident.created_at`, `Incident.resolved_at` y el tiempo de referencia según `data-model.md`, sin alterar los seis resultados deterministas actuales
- [ ] T006 [P] Documentar en `src/application/ports.py` el nuevo contrato de `find_open_duplicates`: igualdad exacta de `Incident.duplicate_group_key` y estados OPEN/IN_PROGRESS/ESCALATION_REQUIRED de `Incident.status`, con RESOLVED excluido y orden ascendente por ID, según `data-model.md` y `contracts/repository-port.md`
- [ ] T007 Extender el esquema y la reconstrucción en `src/adapters/outbound/sqlite_repository.py` con las columnas nullable y el índice `idx_incidents_dup_key` descritos en `data-model.md` para `Incident.raw_text`, `Incident.recommended_team`, `Incident.duplicate_group_key`, `Incident.incident_id`, `Incident.created_at` e `Incident.resolved_at`, manteniendo `incident_duplicates`, `list_active_incidents` y `check_health` sin cambios
- [ ] T008 Preparar en `tests/conftest.py` una fixture de base de datos SQLite temporal que fije `DATABASE_URL` antes de construir la app y la CLI, con incidentes sembrados usando IDs `INC-` + 8 hex según `data-model.md` (`Incident.incident_id`), conforme a la decisión R7 de `research.md`

**Checkpoint**: Base lista; las historias pueden comenzar en paralelo si hay capacidad

---

## Phase 3: User Story 1 - Registrar un incidente y señalar sus duplicados abiertos (Priority: P1) 🎯 MVP

**Goal**: Registrar título y texto original, clasificar reutilizando el dominio y devolver todos los duplicados abiertos.

**Independent Test**: Sembrar incidentes OPEN, IN_PROGRESS, ESCALATION_REQUIRED y RESOLVED, enviar una creación válida por HTTP y comprobar código 201, clasificación y contenido de `duplicate_of`.

### Tests for User Story 1 ⚠️

- [ ] T009 [US1] Escribir primero en `tests/test_spec_003_lifecycle_sla.py` los BDD de US1 para creación sin duplicado, con duplicado OPEN, con RESOLVED + ESCALATION_REQUIRED, múltiples equivalentes con IDs desordenados y aserción de orden ascendente en `duplicate_of`, campos vacíos, omisión de `status`/`created_at`, ID inválido o duplicado, y marca aware; verificar que fallan antes de T010

### Implementation for User Story 1

- [ ] T010 [P] [US1] Implementar `create_incident`, `ValidationError` y `IncidentNotFoundError` en `src/application/services.py`, generando IDs con `secrets.token_hex(4)`, validando y normalizando según `data-model.md` los campos `Incident.title`, `Incident.raw_text`, `Incident.incident_id`, `Incident.created_at`, `Incident.status`, `Incident.component`, `Incident.severity`, `Incident.recommended_team` e `Incident.duplicate_group_key`, reutilizando `classify_incident_report` y `find_open_duplicates` sin redefinir reglas
- [ ] T011 [P] [US1] Crear en `src/adapters/inbound/api/schemas.py` los modelos `CreateIncidentRequest` e `IncidentCreatedResponse` con los campos y el orden de `data-model.md`: `CreateIncidentRequest.title`, `CreateIncidentRequest.raw_text`, `CreateIncidentRequest.incident_id`, `CreateIncidentRequest.created_at`, `CreateIncidentRequest.status`, e `IncidentCreatedResponse.incident_id`, `IncidentCreatedResponse.title`, `IncidentCreatedResponse.component`, `IncidentCreatedResponse.severity`, `IncidentCreatedResponse.recommended_team`, `IncidentCreatedResponse.rationale`, `IncidentCreatedResponse.duplicate_group_key`, `IncidentCreatedResponse.status`, `IncidentCreatedResponse.created_at`, `IncidentCreatedResponse.is_duplicate`, `IncidentCreatedResponse.duplicate_of`
- [ ] T012 [US1] Añadir `POST /api/v1/incidents` en `src/adapters/inbound/api/app.py`, delegando en `IncidentService.create_incident`, mapeando `ValidationError`/`ValueError` a HTTP 422 y serializando con el orden definido en `src/adapters/inbound/api/schemas.py` y `contracts/http-lifecycle.md`
- [ ] T013 [US1] Ejecutar `uv run pytest -v tests/test_spec_003_lifecycle_sla.py tests/test_spec_001_triage.py` y confirmar que los BDD de US1 pasan y que `src/adapters/inbound/api/app.py` no altera la ruta `POST /v1/triage` verificada en `tests/test_spec_001_triage.py`

**Checkpoint**: US1 funciona y es verificable de forma independiente

---

## Phase 4: User Story 2 - Auditar el SLA de un incidente concreto (Priority: P1)

**Goal**: Consultar la evolución del SLA con una hora de referencia opcional y resultados reproducibles.

**Independent Test**: Crear un P2 el viernes 2026-11-06 a las 17:00 y consultar con `reference_time=2026-11-09T09:00:00`, verificando los cinco valores de la evaluación.

### Tests for User Story 2 ⚠️

- [ ] T014 [US2] Escribir primero en `tests/test_spec_003_lifecycle_sla.py` los BDD de US2 para el caso de referencia 120/480/360, ID inexistente (404), `reference_time` anterior, igual y omisión, escalamiento al 75 %, y `reference_time` aware o malformado; verificar que fallan antes de T015

### Implementation for User Story 2

- [ ] T015 [US2] Implementar `evaluate_incident_sla` en `src/application/services.py`, recuperando con `get_incident`, normalizando `Incident.created_at` según `data-model.md`, delegando en `evaluate_sla_status` y devolviendo `SLAEvaluation.incident_id`, `SLAEvaluation.severity`, `SLAEvaluation.elapsed_minutes`, `SLAEvaluation.allowed_minutes`, `SLAEvaluation.remaining_minutes`, `SLAEvaluation.is_breached` y `SLAEvaluation.requires_escalation` definidos en `data-model.md`, con `IncidentNotFoundError` para IDs inexistentes
- [ ] T016 [P] [US2] Crear `SLAEvaluationResponse` en `src/adapters/inbound/api/schemas.py` con `SLAEvaluationResponse.incident_id`, `SLAEvaluationResponse.severity`, `SLAEvaluationResponse.elapsed_minutes`, `SLAEvaluationResponse.allowed_minutes`, `SLAEvaluationResponse.remaining_minutes`, `SLAEvaluationResponse.is_breached` y `SLAEvaluationResponse.requires_escalation`, según `data-model.md` y `contracts/http-lifecycle.md`
- [ ] T017 [US2] Añadir `GET /api/v1/incidents/{incident_id}/sla` en `src/adapters/inbound/api/app.py`, leyendo el parámetro opcional `reference_time`, mapeando `IncidentNotFoundError` a 404 y `ValidationError`/`ValueError` a 422, sin reimplementar SLA
- [ ] T018 [US2] Ejecutar `uv run python -m src.domain.sla_calculator` y `uv run pytest -v tests/test_spec_003_lifecycle_sla.py`, confirmando que `src/domain/sla_calculator.py` conserva `RESULTADO: TODOS LOS CASOS PASAN` y que el escenario de referencia devuelve 120, 480 y 360 minutos

**Checkpoint**: US1 y US2 funcionan de forma independiente

---

## Phase 5: User Story 3 - Registrar y auditar desde la terminal con resultados equivalentes (Priority: P2)

**Goal**: Exponer `create` y `sla` por CLI con la misma estructura JSON que HTTP y un único código de error.

**Independent Test**: Ejecutar `create` y `sla` sobre los mismos datos y `reference_time` usados por HTTP y comparar campo por campo, comprobando código 0; forzar errores y comprobar código 1.

### Tests for User Story 3 ⚠️

- [ ] T019 [US3] Escribir primero en `tests/test_spec_003_lifecycle_sla.py` los BDD de US3 para paridad de `create` y `sla`, omisión de `--reference-time`, errores de `create`/`sla` con código 1 y errores de `triage`/`summary` con código 1; verificar que fallan antes de T020

### Implementation for User Story 3

- [ ] T020 [US3] Implementar en `src/adapters/inbound/cli.py` los subcomandos `create` y `sla` invocables desde `CliRunner`, con opciones opcionales validadas en el servicio, `json.dumps(..., ensure_ascii=False)` y el orden de campos de `contracts/cli-lifecycle.md`; unificar los `typer.Exit` de `triage` y `summary` a código 1 sin cambiar payloads
- [ ] T021 [P] [US3] Ajustar en `tests/test_spec_002_summary.py` la única aserción de código de salida de 2 a 1, conservando las comprobaciones de payload y reglas de `get_active_incidents_summary`
- [ ] T022 [US3] Ejecutar `uv run pytest -v tests/test_spec_003_lifecycle_sla.py tests/test_spec_002_summary.py` y verificar campo por campo la paridad REST/CLI de `create` y `sla` descrita en `contracts/cli-lifecycle.md` y `contracts/http-lifecycle.md`

**Checkpoint**: Las tres historias son independientes y la paridad REST/CLI está verificada

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Compuertas de calidad y comprobación final de invariantes

- [ ] T023 [P] Ejecutar `uv run ruff check src/` y corregir cualquier violación TID251/TID252 en `src/domain/models.py`, `src/domain/sla_calculator.py`, `src/application/services.py`, `src/adapters/inbound/api/app.py`, `src/adapters/inbound/api/schemas.py`, `src/adapters/inbound/cli.py` y `src/adapters/outbound/sqlite_repository.py`
- [ ] T024 [P] Verificar en `pyproject.toml` y `src/incident_repository.py` que no se añadieron dependencias ni imports desde H003 al benchmark, y que `src/adapters/outbound/factory.py` sigue siendo el único selector de `DATABASE_URL`
- [ ] T025 Ejecutar la validación completa de `specs/003-incident-lifecycle-sla/quickstart.md`: `uv run pytest -v`, `uv run ruff check src/`, `uv run python -m src.domain.sla_calculator` y `uv run python -m src.domain.triage_rules`, confirmando cero regresiones de H001/H002 y `RESULTADO: TODOS LOS CASOS PASAN`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias; T002 y T003 son prerrequisitos de gobernanza antes de tocar código
- **Foundational (Phase 2)**: Depende de Setup; BLOCKS todas las historias
- **User Stories (Phase 3+)**: Dependen de Foundational; pueden ejecutarse en paralelo si hay capacidad
- **Polish (Phase 6)**: Depende de todas las historias deseadas

### User Story Dependencies

- **User Story 1 (P1)**: Comienza tras Foundational; sin dependencias de US2/US3; es el MVP
- **User Story 2 (P1)**: Comienza tras Foundational; reutiliza `get_incident` pero es verificable por separado
- **User Story 3 (P2)**: Comienza tras Foundational; para la prueba de paridad necesita US1 y US2 implementadas, pero sus comandos y errores son verificables de forma aislada
- **Dentro de cada historia**: Las pruebas se escriben primero y deben fallar; modelos/contratos antes que servicios; servicios antes que endpoints; integración al final

### Parallel Opportunities

- Setup: T003 en paralelo con T001/T002
- Foundational: T004, T005 y T006 en paralelo (archivos distintos); T007 y T008 después de esas decisiones
- US1: T009 (tests) en paralelo con T010 (servicio) y T011 (schemas); T012 y T013 después
- US2: T014 (tests) en paralelo con T016 (schemas); T015 y T017 después
- US3: T019 (tests) en paralelo con T021 (assertion de H002); T020 y T022 después
- Polish: T023 y T024 en paralelo; T025 al final
- Las tareas de `tests/test_spec_003_lifecycle_sla.py` (T009, T014, T019, T022) son secuenciales porque comparten archivo

---

## Parallel Example: User Story 1

```bash
# Lanzar juntas las tareas paralelas de US1 tras el checkpoint de Foundational:
Task: "Escribir BDD de US1 en tests/test_spec_003_lifecycle_sla.py"
Task: "Implementar create_incident en src/application/services.py"
Task: "Crear esquemas en src/adapters/inbound/api/schemas.py"
```

## Parallel Example: User Story 2

```bash
# Lanzar juntas las tareas paralelas de US2:
Task: "Escribir BDD de US2 en tests/test_spec_003_lifecycle_sla.py"
Task: "Crear SLAEvaluationResponse en src/adapters/inbound/api/schemas.py"
```

## Parallel Example: User Story 3

```bash
# Lanzar juntas las tareas paralelas de US3:
Task: "Escribir BDD de US3 en tests/test_spec_003_lifecycle_sla.py"
Task: "Ajustar aserción de exit code en tests/test_spec_002_summary.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2 (CRITICAL: bloquea todas las historias)
2. Completar Phase 3 (US1)
3. **STOP and VALIDATE**: ejecutar T013 y demostrar creación + duplicados por HTTP
4. Entregar o demostrar el MVP antes de continuar

### Incremental Delivery

1. Setup + Foundational → base lista
2. US1 → prueba independiente → MVP
3. US2 → prueba independiente → auditoría por HTTP
4. US3 → prueba de paridad → CLI equivalente
5. Cada historia añade valor sin romper H001/H002

### Parallel Team Strategy

1. El equipo completa Setup + Foundational junto
2. Tras el checkpoint: Desarrollador A en US1, Desarrollador B en US2, Desarrollador C en US3
3. Cada historia se integra y valida de forma independiente antes del Polish final

---

## Traceability

Los escenarios BDD `Given / When / Then` están en `spec.md:64-87` (US1), `spec.md:103-120` (US2) y `spec.md:134-150` (US3); T009, T014 y T019 los implementan en `tests/test_spec_003_lifecycle_sla.py`.

| Requisito | Tareas de implementación | Tareas de prueba / verificación |
|---|---|---|
| FR-001 | T010, T012, T020 | T013, T022 |
| FR-002 | T010, T011 | T009 |
| FR-003 | T008, T010, T011 | T009 |
| FR-004 | T010, T011 | T009 |
| FR-005 | T010, T011 | T009 |
| FR-006 | T010 | T009, T013 |
| FR-007 | T011, T012, T020 | T009, T022 |
| FR-008 | T006, T007, T010 | T009 |
| FR-009 | T006, T007, T010, T021 | T009, T021, T025 |
| FR-010 | T006, T007, T010 | T009 |
| FR-011 | T010 | T009 |
| FR-012 | T010 | T009 |
| FR-013 | T006, T007, T010 | T009 |
| FR-014 | T015, T016, T017 | T014, T018 |
| FR-015 | T020 | T019, T022 |
| FR-016 | T015, T017 | T014, T018 |
| FR-017 | T005, T015, T016 | T014, T018 |
| FR-018 | T012, T017, T020 | T019, T021, T022 |
| FR-019 | T011, T016, T020 | T022 |
| FR-020 | T001, T013, T018, T021, T024, T025 | T013, T018, T021, T025 |
| FR-021 | T008, T010, T011 | T009 |
| FR-022 | T005, T010, T015, T017, T020 | T009, T014, T019 |
| SC-001 | T011, T012 | T009, T013 |
| SC-002 | T010 | T009, T013 |
| SC-003 | T015 | T014, T018 |
| SC-004 | T015 | T014, T018 |
| SC-005 | T020 | T022 |
| SC-006 | T010, T011, T012 | T009, T013 |
| SC-007 | T015, T017 | T014, T018 |
| SC-008 | T009, T014, T019 | T013, T018, T022 |
| SC-009 | T021, T024 | T013, T018, T025 |

---

## Notes

- `[P]` = archivos distintos y sin dependencias de tareas incompletas
- `[Story]` garantiza trazabilidad hacia `spec.md`
- Los campos restringidos se derivan de `data-model.md`; las tareas los citan explícitamente como `Entity.field`
- Todas las verificaciones se ejecutan con `uv run` desde la raíz del repositorio
- No se realizan commits salvo solicitud explícita
