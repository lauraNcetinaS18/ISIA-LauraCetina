# Research: Ciclo de vida y auditoría de SLA de incidentes

**Feature**: `003-incident-lifecycle-sla` | **Fecha**: 2026-11-24

## R1 — Normalización consistente de marcas naive y aware

- **Decision**: Añadir en `src/domain/sla_calculator.py` una función de normalización que validate
  que la marca sea naive (`utcoffset() is None`) y la devuelva sin transformarla; una marca aware
  produce `ValueError`. `evaluate_sla_status` invoca la normalización sobre `created_at`,
  `resolved_at` y `reference_time` antes de cualquier comparación. Los adaptadores parsean el ISO
  8601 y pasan `datetime` al servicio, que vuelve a normalizar de forma idempotente.
- **Rationale**: La decisión P2 aprobada exige rechazar marcas aware con HTTP 422 / CLI 1 y operar
  solo en hora local naive del servidor. ADR-002 descarta zonas horarias y `AGENTS.md` confirma
  "No holidays/timezones". Las 6 marcas naive de la verificación determinista actual conservan
  sus resultados porque la función no transforma valores naive.
- **Alternatives considered**: (a) convertir aware a naive local — descartada porque cambiaría
  resultados de marcas aware hoy aceptadas y contradice P2; (b) normalizar todo a UTC —
  descartada porque ADR-002 fija la ventana 08:00–18:00 en hora del servidor; (c) dejar la
  comprobación en cada adaptador — descartada porque duplicaría la regla y rompería la paridad.

## R2 — Generación y validación de `INC-HEX8`

- **Decision**: Generar el identificador ausente en `src/application/services.py` con
  `f"INC-{secrets.token_hex(4)}"` (8 hexadecimales en minúsculas) y validar tanto el formato
  `^INC-[0-9a-f]{8}$` como la unicidad antes de persistir. Los esquemas Pydantic aplican el mismo
  patrón y la CLI delega la validación al servicio. Ante una colisión, se genera otro valor.
- **Rationale**: `secrets` es stdlib y su uso pertenece a aplicación, no al dominio, cuya lista
  permitida es `dataclasses`, `typing` y `datetime`. La validación centralizada en el servicio
  garantiza que REST y CLI apliquen exactamente la misma regla (FR-019). P1 aprobó exigir el
  formato al identificador provisto.
- **Alternatives considered**: (a) `uuid4().hex[:8]` — funciona pero es menos directo; (b)
  validar solo en Pydantic — descartado porque la CLI quedaría sin la misma validación; (c)
  aceptar los IDs históricos `INC-1001` — descartado porque contradice P1, aunque obliga a
  actualizar fixtures de H003 con IDs de 8 hexadecimales.

## R3 — Extensión de `Incident`

- **Decision**: Añadir `recommended_team: Optional[TeamName] = None` y
  `duplicate_group_key: Optional[str] = None` al final de `Incident` usando
  `dataclasses.field(default=None, compare=False)`, y ampliar la reconstrucción del repositorio
  para poblarlos.
- **Rationale**: Los campos son metadatos de clasificación, no entradas de las reglas de SLA ni de
  triaje; `compare=False` preserva la igualdad observada por las pruebas de H002, que construyen
  incidentes sin estos campos y comparan con `get_incident`. `TeamName` ya existe en el dominio.
- **Alternatives considered**: (a) campos con comparación normal — descartado por romper la
  igualdad de H002; (b) un dataclass separado — descartado porque añade indirección sin beneficio
  y la spec pide extender `Incident`; (c) guardar los metadatos solo en el DTO — descartado porque
  el repositorio debe reconstruir la entidad completa.

## R4 — Detección de duplicados

- **Decision**: `find_open_duplicates` filtra por igualdad exacta de `duplicate_group_key` y por
  `status IN ('OPEN','IN_PROGRESS','ESCALATION_REQUIRED')`, con `ORDER BY incident_id ASC`.
  `create_incident` llama al puerto antes de guardar, excluye explícitamente su propio
  identificador y devuelve `is_duplicate = bool(duplicate_of)`; la existencia de duplicados no
  impide el registro.
- **Rationale**: FR-008 a FR-013 y P2 de la aclaración: la inclusión de ESCALATION_REQUIRED se
  limita a duplicados. Como el incidente nuevo aún no está persistido al consultar, la exclusión
  del propio ID es automática y se refuerza con un filtro explícito. El orden por `incident_id`
  hace `duplicate_of` determinista.
- **Alternatives considered**: (a) consultar después de guardar y filtrar — descartado por riesgo
  de incluir el propio registro; (b) ampliar `list_active_incidents` — descartado porque cambiaría
  el resumen de H002; (c) comparar por título o texto — prohibido por FR-008.

## R5 — Persistencia SQLite

- **Decision**: Añadir a `incidents` las columnas nullable `raw_text TEXT`,
  `recommended_team TEXT` y `duplicate_group_key TEXT`, crear
  `CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status)`,
  extender los `SELECT` y `_fila_a_incidente`, y escribir la clave de duplicado en la propia tabla
  de incidentes (manteniendo `incident_duplicates` solo por compatibilidad con H002).
- **Rationale**: La spec define al incidente registrado con texto original, equipo y clave; el
  índice exigido solo es útil si la clave está en `incidents`. Las columnas son nullable porque
  las pruebas de 10.000 filas de H002 insertan las 7 columnas originales; no se introduce ORM.
- **Alternatives considered**: (a) columnas `NOT NULL` — rompe la siembra de H002; (b) migración
  destructiva — descartada porque el default es `sqlite:///:memory:`; (c) eliminar
  `incident_duplicates` — descartado para no reemplazar el contrato de H002.

## R6 — Errores HTTP y códigos de salida

- **Decision**: `IncidentNotFoundError(LookupError)` se mapea a HTTP 404 y a CLI 1;
  `ValidationError`, `ValueError` de normalización y errores de parseo se mapean a HTTP 422 y CLI
  1. Los tres `typer.Exit(code=2)` actuales pasan a `code=1` y la única prueba de H002 que afirma
  el código 2 se ajusta a 1. Las opciones obligatorias de `create` se declaran opcionales y se
  validan en el servicio para que una omisión también termine con código 1.
- **Rationale**: Q1 aprobó el código 1 en todos los subcomandos y la enmienda constitucional 2.0.0
  ya lo formalizó. La funcionalidad y los payloads de triage y summary permanecen intactos; solo
  cambia el código acordado. Lo anterior evita que Typer devuelva 2 por
  una opción ausente antes de llegar al servicio.
- **Alternatives considered**: (a) código 1 solo en H003 — genera dos convenciones; (b) dejar
  opciones obligatorias de Typer — produce código 2 del framework ante omisiones; (c) usar
  excepciones HTTP en el servicio — violaría ADR-003. Queda fuera del conjunto acordado el error
  de framework «opción desconocida», que sigue con el código propio de Click.

## R7 — Pruebas y paridad REST/CLI

- **Decision**: `tests/test_spec_003_lifecycle_sla.py` usa `TestClient` y `CliRunner` sobre un
  `DATABASE_URL` de archivo temporal fijado antes de construir la app, sembrando incidentes con
  IDs `INC-` + 8 hex. Cubre los 18 escenarios BDD, casos borde, paridad campo por campo y
  regresión de H001/H002; la hora se fija con el mismo patrón de monkeypatch de H002 y el ID
  generado se verifica por patrón o se parchea.
- **Rationale**: La memoria SQLite produce bases distintas por conexión y la fixture `client`
  actual construye la app antes de que la prueba pueda cambiar `DATABASE_URL`; un archivo temporal
  garantiza que REST y CLI vean los mismos datos. SC-005 exige paridad del 100 % y SC-009 cero
  regresiones.
- **Alternatives considered**: (a) reutilizar la BD en memoria — rompe la paridad entre
  conexiones; (b) probar solo el servicio — no cubre FR-001/FR-014 ni el mapeo de errores; (c)
  moquear el repositorio — no verificaría el índice ni la consulta de duplicados.
