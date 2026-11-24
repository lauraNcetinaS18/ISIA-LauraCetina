---

description: "Task list for feature implementation"
---

# Tasks: Resumen de incidentes activos

**Input**: Design documents from `/specs/002-active-incidents-summary/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, `.specify/memory/constitution.md`

**Tests**: Obligatorios por la constitución y SC-007. Cada escenario BDD y cada prueba de criterio de aceptación se escriben primero y deben fallar antes de la implementación correspondiente.

**Organization**: Tareas agrupadas por fase y, dentro de las fases de usuario, por historia para permitir implementación y verificación independientes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias de tareas incompletas ni de escenarios BDD pendientes)
- **[Story]**: Etiqueta US1/US2 solo en fases de historias de usuario
- Todas las tareas incluyen rutas de archivo exactas

## Path Conventions

- Proyecto único: `src/`, `tests/` en la raíz del repositorio
- Rutas relativas a la raíz; ejecución siempre con `uv run`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configurar compuertas de calidad compartidas por todas las historias.

- [X] T001 [P] Configurar `[tool.ruff.lint]` con `select = ["E4", "E7", "E9", "F", "TID"]` y `ban-relative-imports = "parents"` en `pyproject.toml`, según `research.md` R5. Trazabilidad: constitución III; sin FR propio.
- [X] T002 [P] Crear `src/domain/ruff.toml`, `src/application/ruff.toml` y `src/adapters/inbound/ruff.toml` con `extend` relativo y `banned-api` TID251, según `research.md` R5. Trazabilidad: constitución II y III; habilita FR-011.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura obligatoria antes de cualquier historia: pruebas de contrato/rendimiento, puerto, persistencia, factory y caso de uso compartido.

**CRITICAL**: Ninguna historia puede comenzar hasta completar esta fase.

- [X] T003 Crear primero en `tests/test_spec_002_summary.py` las pruebas `test_bdd_sqlite_repository_cumple_puerto` y `test_rendimiento_sc_005_repositorio_10k`, verificando que fallan antes de T004/T005; la prueba de SC-005 debe sembrar 10.000 filas en BD SQLite aislada, descartar calentamiento, ejecutar tres mediciones y exigir mediana < 2 s según `spec.md`, sin usar `src/incident_repository.py`. Trazabilidad: constitución III; SC-005 y SC-007.
- [X] T004 Crear `IncidentRepositoryPort` en `src/application/ports.py` con los cinco métodos de `contracts/repository-port.md` (`save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents`, `check_health`). Trazabilidad: constitución II; habilita FR-001, FR-006, FR-013 y FR-014 sin ser un FR independiente.
- [X] T005 Implementar `SQLiteIncidentRepository` en `src/adapters/outbound/sqlite_repository.py` con esquema, `INNER JOIN sla_policies`, `idx_incidents_component_status`, orden `created_at, incident_id` y mapeo de entidades; citar `data-model.md: Incident.incident_id`, `data-model.md: Incident.title`, `data-model.md: Incident.component`, `data-model.md: Incident.severity`, `data-model.md: Incident.status`, `data-model.md: Incident.created_at`, `data-model.md: Incident.resolved_at`, `data-model.md: incidents.incident_id`, `data-model.md: incidents.title`, `data-model.md: incidents.component`, `data-model.md: incidents.severity`, `data-model.md: incidents.status`, `data-model.md: incidents.created_at`, `data-model.md: incidents.resolved_at`, `data-model.md: sla_policies.severity`, `data-model.md: sla_policies.max_resolution_minutes`, `data-model.md: sla_policies.operates_24x7`, `data-model.md: incident_duplicates.incident_id`, `data-model.md: incident_duplicates.duplicate_group_key`. Trazabilidad: constitución II; FR-002, FR-006, FR-010 y SC-005.
- [X] T006 Implementar `get_incident_repository()` en `src/adapters/outbound/factory.py`, resolviendo `DATABASE_URL` con default `sqlite:///:memory:` y validando prefijo `sqlite:///`, según `research.md` R1. Trazabilidad: constitución II (selección del adaptador outbound); apoya SC-005 sin ser un FR independiente.
- [X] T007 Implementar `get_active_incidents_summary(component_filter, reference_time)` en `src/application/services.py`, inyectando el puerto T004 y reutilizando `evaluate_sla_status` sin redefinir reglas; citar `data-model.md: SLARule.severity`, `data-model.md: SLARule.max_resolution_minutes`, `data-model.md: SLARule.operates_24x7`, `data-model.md: SLARule.escalation_threshold_ratio`, `data-model.md: SLAEvaluation.incident_id`, `data-model.md: SLAEvaluation.severity`, `data-model.md: SLAEvaluation.elapsed_minutes`, `data-model.md: SLAEvaluation.allowed_minutes`, `data-model.md: SLAEvaluation.remaining_minutes`, `data-model.md: SLAEvaluation.is_breached`, `data-model.md: SLAEvaluation.requires_escalation`. Trazabilidad: constitución I y II; FR-001 a FR-008, FR-011 y FR-015.

**Checkpoint**: Fundación lista, con pruebas de puerto y SC-005 ya definidas. US1 y US2 pueden comenzar.

---

## Phase 3: User Story 1 - Consultar el resumen global y filtrado por HTTP (Priority: P1)

**Goal**: Exponer `GET /api/v1/incidents/summary` con filtro opcional `component`, devolviendo totales y detalle determinista sin incluir `RESOLVED` ni `ESCALATION_REQUIRED`.

**Independent Test**: Sobre un conjunto fijo de incidentes `OPEN`, `IN_PROGRESS`, `RESOLVED` y `ESCALATION_REQUIRED`, la respuesta HTTP debe contener solo los activos, con `total_active` y `breached_count` derivados de `incidents`, orden `created_at, incident_id` y el cuerpo vacío canónico de FR-009 cuando no haya coincidencias.

### Tests for User Story 1

> Escribir primero y verificar que fallan antes de T009/T010.

- [X] T008 [US1] Crear en `tests/test_spec_002_summary.py` las pruebas BDD `test_bdd_resumen_global_excluye_resueltos`, `test_bdd_resumen_filtrado_por_componente`, `test_bdd_resumen_sin_resultados` y `test_bdd_resumen_casos_borde_sla` (fin de semana, límite exacto, 75 %, breach estricto y orden `created_at, incident_id`), validando los campos citados en `data-model.md: ActiveIncidentItem.incident_id`, `data-model.md: ActiveIncidentItem.title`, `data-model.md: ActiveIncidentItem.component`, `data-model.md: ActiveIncidentItem.severity`, `data-model.md: ActiveIncidentItem.status`, `data-model.md: ActiveIncidentItem.elapsed_minutes`, `data-model.md: ActiveIncidentItem.is_breached`, `data-model.md: ActiveIncidentItem.requires_escalation`, `data-model.md: ActiveIncidentsSummaryResponse.total_active`, `data-model.md: ActiveIncidentsSummaryResponse.breached_count`, `data-model.md: ActiveIncidentsSummaryResponse.incidents`. Trazabilidad: FR-002 a FR-011, FR-013, SC-001, SC-002, SC-004, SC-006, SC-007 y SC-008.

### Implementation for User Story 1

- [X] T009 [US1] Definir `ActiveIncidentItem` y `ActiveIncidentsSummaryResponse` en `src/adapters/inbound/api/schemas.py` con los campos y reglas de `data-model.md: ActiveIncidentItem.incident_id`, `data-model.md: ActiveIncidentItem.title`, `data-model.md: ActiveIncidentItem.component`, `data-model.md: ActiveIncidentItem.severity`, `data-model.md: ActiveIncidentItem.status`, `data-model.md: ActiveIncidentItem.elapsed_minutes`, `data-model.md: ActiveIncidentItem.is_breached`, `data-model.md: ActiveIncidentItem.requires_escalation`, `data-model.md: ActiveIncidentsSummaryResponse.total_active`, `data-model.md: ActiveIncidentsSummaryResponse.breached_count`, `data-model.md: ActiveIncidentsSummaryResponse.incidents`. Sin marcador [P]: depende de que T008 ya haya definido los escenarios BDD. Trazabilidad: FR-001, FR-005, FR-009, FR-012 y SC-002.
- [X] T010 [US1] Agregar la ruta `GET /api/v1/incidents/summary` en `src/adapters/inbound/api/app.py`, obteniendo el repositorio desde `src/adapters/outbound/factory.py`, delegando en `IncidentService` y mapeando errores a HTTP 422 según `contracts/http-summary.md`. Trazabilidad: FR-001, FR-006, FR-009, FR-010, FR-013 y SC-001 a SC-004.

**Checkpoint**: US1 funciona de forma aislada con `uv run pytest -v`.

---

## Phase 4: User Story 2 - Consultar el resumen equivalente desde la terminal (Priority: P1)

**Goal**: Ofrecer el subcomando `summary` con `--component` y `--reference-time` opcionales, devolviendo exactamente la misma estructura JSON que HTTP.

**Independent Test**: Con el mismo conjunto de incidentes y el mismo instante de referencia, comparar campo por campo la salida de `CliRunner` con la respuesta de `TestClient`. La prueba congela el reloj del servicio en HTTP mediante una fixture determinista y pasa el mismo ISO a `--reference-time`; incluye el caso vacío y un `--reference-time` inválido (exit 2).

### Tests for User Story 2

> Escribir primero y verificar que fallan antes de T012.

- [X] T011 [US2] Agregar en `tests/test_spec_002_summary.py` las pruebas `test_bdd_resumen_paridad_rest_cli` y `test_bdd_resumen_reference_time_invalido`, comparando `data-model.md: ActiveIncidentsSummaryResponse.total_active`, `data-model.md: ActiveIncidentsSummaryResponse.breached_count`, `data-model.md: ActiveIncidentsSummaryResponse.incidents` y los campos de `ActiveIncidentItem` definidos en T009, con reloj HTTP congelado según `spec.md`. Trazabilidad: FR-001, FR-009, FR-012, FR-014, FR-015, SC-003, SC-007 y SC-008.

### Implementation for User Story 2

- [X] T012 [US2] Implementar el subcomando `summary` en `src/adapters/inbound/cli.py` con `--component` y `--reference-time`, delegando en `IncidentService`, parseando ISO 8601, mapeando `ValidationError` a exit 2 y emitiendo `json.dumps(..., ensure_ascii=False)` según `contracts/cli-summary.md`. Sin marcador [P]: depende de que T011 ya haya definido los escenarios BDD. Trazabilidad: FR-001, FR-006, FR-009, FR-012, FR-014, FR-015, SC-003 y SC-007.

**Checkpoint**: US1 y US2 devuelven estructuras idénticas y son verificables por separado.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Compuertas finales y verificación de regresión.

- [X] T013 [P] Verificar fronteras arquitectónicas con `uv run ruff check src/` y ajustar `src/domain/ruff.toml`, `src/application/ruff.toml` o `src/adapters/inbound/ruff.toml` si aparece TID251/TID252. Trazabilidad: constitución II y III; FR-011 y SC-007.
- [X] T014 Ejecutar la validación completa descrita en `quickstart.md` (`uv run pytest -v`, `uv run ruff check src/`, `test_rendimiento_sc_005_repositorio_10k`, módulos de dominio y benchmark legado `src/incident_repository.py` solo como regresión informativa) y confirmar SC-001 a SC-008. Trazabilidad: constitución III; SC-001 a SC-008.

---

## Constitution Traceability

| Task | Principio constitucional | Requisito/criterio relacionado | Observación |
|---|---|---|---|
| T001 | III Gobernanza técnica y calidad | Ninguno directo | Obligación de gobernanza; habilita todas las compuertas. |
| T002 | II Hexagonal estricta + III Calidad | FR-011 (indirecto) | No crea FR nuevo; hace cumplir fronteras con Ruff. |
| T003 | III Calidad (BDD y prueba por criterio) | SC-005, SC-007 | Define primero pruebas de puerto y rendimiento. |
| T004 | II Puertos en `src/application/` | FR-001, FR-006, FR-013, FR-014 | Habilitador técnico, no FR independiente. |
| T005 | II Outbound intercambiable | FR-002, FR-006, FR-010, SC-005 | Implementación del adaptador optimizado. |
| T006 | II `DATABASE_URL` selecciona adaptador | SC-005 (apoyo) | Sin FR propio; decide el repositorio activo. |
| T007 | I Dominio único + II Aplicación | FR-001–FR-008, FR-011, FR-015 | Orquesta; no reimplementa reglas. |
| T008–T010 | III BDD + II Inbound delgado | FR-002–FR-011, FR-013, SC-001–SC-008 | Historia HTTP. |
| T011–T012 | III BDD + II Inbound delgado | FR-001, FR-006, FR-009, FR-012, FR-014, FR-015, SC-003, SC-007, SC-008 | Historia CLI. |
| T013 | II y III | FR-011, SC-007 | Verificación de fronteras. |
| T014 | III | SC-001–SC-008 | Compuerta final de calidad. |

---

## Requirement → Task → Test Matrix

| Key | Tasks | Prueba asociada |
|---|---|---|
| FR-001 | T004,T007,T009,T010,T011,T012 | `test_bdd_resumen_global_excluye_resueltos`, `test_bdd_resumen_paridad_rest_cli` |
| FR-002 | T005,T007,T008 | `test_bdd_resumen_global_excluye_resueltos` |
| FR-003 | T007,T008,T009 | `test_bdd_resumen_global_excluye_resueltos` |
| FR-004 | T007,T008 | `test_bdd_resumen_casos_borde_sla` |
| FR-005 | T007,T008,T009 | `test_bdd_resumen_global_excluye_resueltos` |
| FR-006 | T004,T005,T007,T008,T010,T012 | `test_bdd_resumen_filtrado_por_componente` |
| FR-007 | T007,T008 | `test_bdd_resumen_casos_borde_sla` |
| FR-008 | T007,T008 | `test_bdd_resumen_casos_borde_sla` |
| FR-009 | T008,T010,T011,T012 | `test_bdd_resumen_sin_resultados` |
| FR-010 | T005,T008 | `test_bdd_resumen_casos_borde_sla` |
| FR-011 | T002,T007,T013,T014 | `uv run python -m src.domain.sla_calculator`, `uv run python -m src.domain.triage_rules`, `uv run ruff check src/` |
| FR-012 | T009,T011,T012 | `test_bdd_resumen_paridad_rest_cli` |
| FR-013 | T004,T007,T010 | Escenarios BDD 1–3 vía `TestClient` |
| FR-014 | T004,T007,T011,T012 | `test_bdd_resumen_paridad_rest_cli`, `test_bdd_resumen_reference_time_invalido` |
| FR-015 | T007,T011,T012 | `test_bdd_resumen_paridad_rest_cli`, `test_bdd_resumen_reference_time_invalido` |
| SC-001 | T005,T007,T008,T014 | `test_bdd_resumen_global_excluye_resueltos` |
| SC-002 | T008,T009,T014 | `test_bdd_resumen_global_excluye_resueltos` |
| SC-003 | T009,T011,T012,T014 | `test_bdd_resumen_paridad_rest_cli` |
| SC-004 | T005,T008,T014 | `test_bdd_resumen_filtrado_por_componente` |
| SC-005 | T003,T005,T006,T014 | `test_rendimiento_sc_005_repositorio_10k` |
| SC-006 | T007,T008,T014 | `test_bdd_resumen_casos_borde_sla` |
| SC-007 | T003,T008,T011,T013,T014 | Todas las pruebas `test_bdd_*` y `test_rendimiento_sc_005_repositorio_10k` |
| SC-008 | T008,T011,T014 | `test_bdd_resumen_casos_borde_sla`, `test_bdd_resumen_paridad_rest_cli` |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias; T001 y T002 pueden ejecutarse en paralelo.
- **Foundational (Phase 2)**: Depende de Setup; bloquea ambas historias.
  - T003 va primero: define pruebas de puerto y SC-005 antes de T004/T005.
  - T004 precede a T005 y T007.
  - T005 precede a T006.
- **User Stories (Phase 3–4)**: Dependen de Foundational.
  - US1: T008 → T009 → T010.
  - US2: T011 → T012.
  - Tras completar T008 y T011, T009 y T012 pueden ejecutarse en paralelo por personas distintas; no se usan marcadores [P] porque ambas tareas dependen de que sus escenarios BDD ya estén definidos.
- **Polish (Phase 5)**: Depende de US1 y US2 completas.

### BDD-first Guarantee

- T003 (puerto/rendimiento) se escriba antes de T004/T005.
- T008 (US1) se escriba antes de T009/T010.
- T011 (US2) se escriba antes de T012.
- Ninguna tarea de implementación de historia lleva [P], para impedir que se ejecute antes de su escenario BDD.

### Parallel Opportunities

- T001 + T002 (Setup)
- Tras T008 y T011: T009 (schemas) + T012 (CLI) en archivos distintos
- US1 y US2 pueden avanzar en paralelo una vez completas sus pruebas BDD
- T013 en paralelo con la revisión final de T014

---

## Parallel Example: BDD-safe

```bash
# Primero, escenarios BDD (sin paralelismo con implementación):
Task: "T008 Crear pruebas BDD de US1 en tests/test_spec_002_summary.py"
Task: "T011 Agregar pruebas de paridad en tests/test_spec_002_summary.py"

# Después, implementaciones en archivos distintos:
Task: "T009 Definir DTOs en src/adapters/inbound/api/schemas.py"
Task: "T012 Implementar comando summary en src/adapters/inbound/cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational, con T003 primero.
3. Completar Phase 3: US1 en orden T008 → T009 → T010.
4. Detener y validar US1 de forma independiente con `uv run pytest -v`.
5. Demo del endpoint HTTP.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar → MVP.
3. US2 → validar paridad → release completo.
4. Polish → compuertas finales, incluida SC-005.

### Parallel Team Strategy

1. Equipo completo: Setup + Foundational.
2. Tras T008 y T011:
   - Desarrollador A: T009 → T010.
   - Desarrollador B: T012.
3. Integrar y ejecutar Phase 5.

---

## Notes

- [P] = archivos distintos y sin dependencias de escenarios BDD pendientes.
- [US1]/[US2] = trazabilidad con `spec.md`.
- Todas las citas `data-model.md: Entidad.campo` son la fuente canónica de restricciones; se usaron los nombres reales de `SLAEvaluation` (`allowed_minutes`, `requires_escalation`).
- Verificar que las pruebas fallan antes de implementar cada historia.
- No refactorizar `src/incident_repository.py`: es el benchmark intencional de H001 y no se usa para medir SC-005.
- No confirmar ni fusionar; sede de cambios bajo control del usuario.
