# Quickstart: Resumen de incidentes activos

**Feature**: `002-active-incidents-summary` | **Estado**: plan aprobado, implementación pendiente

## 1. Precondiciones

- Python 3.10+ y `uv` disponibles.
- Ejecutar todo desde la raíz del repositorio (no existe `week-1/starter-project`).
- No se necesita contenedor ni servidor externo: el default es SQLite en memoria.

```text
uv sync
```

## 2. Ejecución funcional (una vez implementado)

```text
uv run python -m src.adapters.inbound.cli summary
uv run python -m src.adapters.inbound.cli summary --component payments-gateway
uv run python -m src.adapters.inbound.cli summary --component payments-gateway --reference-time 2026-11-24T12:00:00
```

Para el adaptador REST, usar `TestClient(create_app())` en pruebas o levantar la app con `uv run uvicorn src.adapters.inbound.api.app:create_app --factory --reload` (solo desarrollo).

La variable `DATABASE_URL` permite apuntar a otro archivo SQLite:

```text
DATABASE_URL=sqlite:///./incidentes.db uv run python -m src.adapters.inbound.cli summary
```

Sin esa variable se usa `sqlite:///:memory:`.

## 3. Verificación de H002

```text
uv run pytest -v
uv run ruff check src/
uv run pytest -v tests/test_spec_002_summary.py::test_rendimiento_sc_005_repositorio_10k
```

`uv run pytest -v` debe ejecutar los 5 casos heredados de `tests/test_spec_001_triage.py` más los nuevos de `tests/test_spec_002_summary.py`: 4 escenarios BDD, casos borde de SLA/orden, prueba de cumplimiento del puerto, prueba de paridad con reloj controlado y prueba de rendimiento SC-005.

## 4. Escenarios BDD cubiertos

| Escenario | Prueba prevista | Resultado esperado |
|---|---|---|
| Global excluye `RESOLVED` | `test_bdd_resumen_global_excluye_resueltos` | `total_active` cuenta solo `OPEN`/`IN_PROGRESS`; `breached_count` coincide con `is_breached`. |
| Filtro por componente | `test_bdd_resumen_filtrado_por_componente` | Solo entradas de `payments-gateway`; se conserva el orden `created_at, incident_id`. |
| Sin resultados | `test_bdd_resumen_sin_resultados` | Cuerpo exacto de FR-009. |
| Casos borde y orden | `test_bdd_resumen_casos_borde_sla` | Fin de semana, límite exacto, 75 % y orden determinista (SC-006/SC-008). |
| Paridad CLI | `test_bdd_resumen_paridad_rest_cli` | Mismo JSON estructural con reloj HTTP congelado e igual `--reference-time`. |
| `reference_time` inválido | `test_bdd_resumen_reference_time_invalido` | CLI termina con código 1 y mensaje en `stderr` (constitución 2.0.0). |
| Contrato del puerto | `test_bdd_sqlite_repository_cumple_puerto` | Cinco métodos disponibles y ciclo básico save/get/list/find/health. |
| Rendimiento SC-005 | `test_rendimiento_sc_005_repositorio_10k` | 10.000 filas aisladas; mediana de tres mediciones < 2 s; no usa el benchmark legado. |

## 5. Verificaciones de regresión existentes (no modificadas)

```text
uv run python -m src.domain.sla_calculator
uv run python -m src.domain.triage_rules
uv run python -m src.incident_repository --records 10000 --iterations 20
```

El benchmark sigue siendo informativo y su anti-patrón es intencional; H002 no lo refactoriza ni lo usa en producción.

## 6. Criterios de aceptación rápidos

- [ ] `GET /api/v1/incidents/summary` devuelve 200 con la estructura acordada.
- [ ] `summary` CLI imprime JSON idéntico al REST para el mismo `reference_time`.
- [ ] `RESOLVED` y `ESCALATION_REQUIRED` nunca aparecen en `incidents`.
- [ ] `breached_count` solo cuenta `is_breached = true`.
- [ ] Sin coincidencias devuelve el cuerpo vacío canónico.
- [ ] `uv run ruff check src/` pasa con los `ruff.toml` jerárquicos.
- [ ] `test_rendimiento_sc_005_repositorio_10k` reporta mediana < 2 s sobre 10.000 incidentes aislados.

Ver también: [data-model.md](./data-model.md), [research.md](./research.md) y `contracts/`.
