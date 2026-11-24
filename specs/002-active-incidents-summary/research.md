# Research: Resumen de incidentes activos

**Feature**: `002-active-incidents-summary` | **Fecha**: 2026-11-24

## R1. Selección de almacenamiento y factory

**Decision**: `src/adapters/outbound/factory.py` expondrá `get_incident_repository() -> IncidentRepositoryPort`, leyendo `DATABASE_URL` con default `sqlite:///:memory:`. Solo se admitirá el esquema `sqlite:///` en H002; cualquier otro valor deberá fallar con un error explícito en español hasta existir un ADR que autorice otro motor.

**Rationale**: Cumple el principio de persistencia intercambiable sin acoplar los adaptadores inbound al driver. El default en memoria permite ejecutar REST, CLI y pruebas sin archivos ni contenedores.

**Alternatives considered**: (1) instanciar `SQLiteIncidentRepository` directamente en `app.py`/`cli.py` — rechazado porque rompe la inversión de dependencias; (2) usar una variable `DB_PATH` — rechazado porque el usuario especificó `DATABASE_URL`; (3) agregar SQLAlchemy — rechazado por la constitución y ADR-001.

## R2. Forma del puerto y método `find_open_duplicates`

**Decision**: `IncidentRepositoryPort` será un `typing.Protocol` con:

- `save_incident(incident: Incident, duplicate_group_key: str | None = None) -> None`
- `get_incident(incident_id: str) -> Incident | None`
- `find_open_duplicates(duplicate_group_key: str) -> list[Incident]`
- `list_active_incidents(component_filter: str | None = None) -> list[Incident]`
- `check_health() -> bool`

`list_active_incidents` devuelve entidades de dominio crudas; no recibe `reference_time` ni calcula campos derivados. Para `find_open_duplicates` se creará la tabla auxiliar `incident_duplicates(incident_id TEXT PRIMARY KEY, duplicate_group_key TEXT NOT NULL)`, alimentada por el argumento opcional de `save_incident`. El adapter solo persiste la clave que ya calculó el dominio; no decide duplicados.

**Rationale**: `Incident` no tiene campo `duplicate_group_key` y `TriageResult` sí lo produce; un argumento opcional evita ensuciar el modelo de dominio y mantiene la regla de duplicados fuera del adapter. H002 no invoca `find_open_duplicates`, pero el puerto debe quedar completo y verificable.

**Alternatives considered**: (1) buscar duplicados por `component` + `severity` en el adapter — rechazado porque reimplementaría reglas de negocio; (2) agregar `duplicate_group_key` a `Incident` — rechazado porque amplía el contrato de dominio sin una historia de usuario que lo pida; (3) omitir el método — rechazado por requisito explícito del usuario.

## R3. Cálculo de SLA y uso de `INNER JOIN sla_policies`

**Decision**: La consulta de `list_active_incidents` hará `INNER JOIN sla_policies sp ON sp.severity = i.severity`, filtrará `i.status IN ('OPEN','IN_PROGRESS')`, aplicará `i.component = ?` solo cuando `component_filter` no sea `None`, y ordenará por `i.created_at, i.incident_id`. El servicio convertirá cada fila en `Incident` y llamará a `evaluate_sla_status(incident, reference_time=reference_time)`; el `JOIN` garantiza que solo se devuelvan severidades con política vigente y evita el N+1, pero no calcula SLA.

**Rationale**: El usuario exige conservar el `INNER JOIN`; el dominio sigue siendo la única fuente de verdad de brechas y escalamiento (ADR-002). Seleccionar la política en la misma consulta elimina el `SELECT` por fila del legado.

**Alternatives considered**: (1) calcular minutos en SQL — rechazado porque duplicaría la lógica de horario hábil; (2) `LEFT JOIN` — rechazado porque admitiría severidades sin política y contradice el `INNER JOIN` solicitado; (3) traer `max_resolution_minutes` y usarlo en el servicio — rechazado porque crearía una segunda fuente de verdad frente a `SLA_POLICY_TABLE`.

**Hallazgo a registrar**: en el estado actual de `src/incident_repository.py:30-62` no existe `INNER JOIN` ni `CREATE INDEX`; solo hay un `SELECT max_resolution_minutes ...` por fila en `src/incident_repository.py:129-133`. Por tanto, el Hito 002 **introduce** el `INNER JOIN` y el índice en el nuevo adapter en lugar de "heredarlos" literalmente. Esta incorporación es deliberada y está cubierta por SC-005.

## R4. Persistencia optimizada frente al benchmark heredado

**Decision**: Crear `SQLiteIncidentRepository` con el esquema actual de `incidents`/`sla_policies`, agregar `CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)` y la consulta con `JOIN` de R3. `src/incident_repository.py` se conserva sin cambios como herramienta de diagnóstico; ningún módulo H002 lo importa y la regla TID251 de inbound lo prohíbe explícitamente.

**Rationale**: El usuario pidió extraer la persistencia optimizada y conservar índice/JOIN; `AGENTS.md` marca el anti-patrón como intencional y solo advierte no refactorizarlo sin solicitud. Mantener el benchmark preserva la lección pedagógica mientras el flujo productivo usa el adapter correcto.

**Alternatives considered**: (1) modificar `src/incident_repository.py` in place — rechazado porque destruiría el benchmark "Antes de Refactorizar"; (2) eliminarlo — rechazado por el mismo motivo y por el comando de verificación documentado en `AGENTS.md`; (3) dejar que ambos escriban en la misma BD — rechazado por riesgo de esquemas divergentes.

## R5. Configuración Ruff jerárquica

**Decision**: Agregar a `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "TID"]

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "parents"
```

Y crear tres `ruff.toml` con `extend` relativo (`../../pyproject.toml` en `src/domain/` y `src/application/`; `../../../pyproject.toml` en `src/adapters/inbound/`) y `banned-api` (TID251) según la skill `hexagonal-architecture`: dominio sin `fastapi`/`pydantic`/`typer`/`httpx`/`requests`/`sqlite3`/`sqlalchemy`/`src.application`/`src.adapters`; aplicación sin frameworks, drivers ni `src.adapters`; inbound sin `sqlite3`, `sqlalchemy` ni `src.incident_repository`.

**Rationale**: Ruff aplica la configuración más cercana y no propaga automáticamente; `extend` conserva la selección raíz. `ban-relative-imports = "parents"` refuerza imports absolutos `src.*`. El validador será `uv run ruff check src/` desde la raíz (sin `--config`, para que se apliquen los archivos hijos).

**Alternatives considered**: (1) un único `pyproject.toml` con `per-file-ignores` — rechazado porque la skill exige configuración jerárquica; (2) `TID252` con `ban-relative-imports = "all"` — rechazado porque prohibiría imports relativos intra-paquecito no solicitados; (3) ejecutar Ruff desde cada subdirectorio — rechazado porque `testpaths`/`pythonpath` y la verificación documentada parten de la raíz.

## R6. Aislamiento, reloj y paridad REST/CLI

**Decision**: Cada prueba de `tests/test_spec_002_summary.py` recibirá una BD SQLite temporal mediante `DATABASE_URL` y construirá el servicio/factory dentro de la prueba. `IncidentService.get_active_incidents_summary` aceptará `reference_time: datetime | None = None`; si es `None`, usará `datetime.now()` una sola vez por petición. REST no expone `reference_time` y usa ese valor implícito; CLI expone `--reference-time` en ISO 8601 (`datetime.fromisoformat`) y un valor inválido se mapea a `ValidationError` → exit 1 (constitución 2.0.0). Para el escenario de paridad, la prueba fijará el reloj del lado REST y pasará el mismo ISO al CLI, o sembrará datos con margen temporal suficiente y comparará la estructura completa.

**Rationale**: El requisito de paridad exige que ambos canales devuelvan el mismo JSON; sin un reloj controlado la comparación sería frágil. La BD temporal evita contaminar el benchmark de 10k filas.

**Alternatives considered**: (1) `reference_time` como query param de HTTP — rechazado porque el contrato acordado solo incluye `component`; (2) comparar solo `total_active` — rechazado porque SC-003 exige misma estructura; (3) BD global compartida — rechazado por no determinista y por riesgo entre pruebas.
