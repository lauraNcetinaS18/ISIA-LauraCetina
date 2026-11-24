# Plan técnico — Hito 001: primer corte de Arquitectura Hexagonal

- **Estado**: Aceptado
- **Fecha**: 2026-11-23
- **Alcance**: exponer el triaje por HTTP y CLI sin persistencia, respetando `docs/constitution.md`, `docs/adr/003-arquitectura-hexagonal.md` y `specs/001-triage-endpoint-manual.md`.

## 1. Dependencias

Añadir a `pyproject.toml`:

- Runtime: `fastapi`, `uvicorn`, `pydantic>=2`, `typer`.
- Desarrollo: `pytest`, `httpx`.

Configuración pytest:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

## 2. Migración del dominio

Mover los módulos heredados a:

- `src/domain/models.py`
- `src/domain/triage_rules.py`
- `src/domain/sla_calculator.py`

Ajustes obligatorios:

- Corregir imports hacia `src.domain.*` en los módulos movidos y en `src/incident_repository.py`.
- Corregir `PROJECT_ROOT` en `src/domain/triage_rules.py` de `parent.parent` a `parents[2]` para seguir resolviendo `data/sample_incidents.json`.
- Ampliar los glob de `src/context_audit.py` para incluir `src/**/*.py`, de modo que los nuevos subpaquetes no queden fuera de la auditoría.

## 3. Caso de uso compartido

Crear `src/application/services.py` con:

- `ValidationError`.
- `IncidentService.triage_incident(incident_id, raw_text)`.

El servicio valida entradas y delega en `classify_incident_report`. No importa FastAPI, Pydantic, Typer ni `sqlite3`.

## 4. Adaptadores de entrada

Crear:

- `src/adapters/inbound/api/schemas.py` con modelos Pydantic v2 de request/response, sin `consistency_ratio`.
- `src/adapters/inbound/api/app.py` con `create_app()` y `POST /v1/triage`.
- `src/adapters/inbound/cli.py` con Typer y subcomando `triage`.

Ambos adaptadores delegan en `IncidentService`. La CLI imprime JSON por defecto y mapea `ValidationError` a exit `2`; la API mapea `ValidationError` a HTTP `422`.

## 5. Pruebas BDD

Crear:

- `tests/conftest.py` con fixtures de `fastapi.testclient.TestClient` y `typer.testing.CliRunner`.
- `tests/test_spec_001_triage.py` con los cuatro escenarios de `specs/001-triage-endpoint-manual.md`.

## Notas de arquitectura

- No se crea puerto outbound ni persistencia en H001.
- `incident_repository.py` permanece temporalmente en `src/`; solo se ajustan sus imports.
- `context_audit.py` permanece en `src/`, con globs ampliados.
- Los valores de la spec son normativos: 502 en pasarela de pagos → `P0` y `payments-gateway:http-502-outage`; cuenta bloqueada → `P2` con `Security-IAM`.

## Tareas atómicas ordenadas

1. Actualizar `pyproject.toml`: dependencias, grupo dev y configuración pytest.
2. Crear `__init__.py` en `src/domain/`, `src/application/`, `src/adapters/`, `src/adapters/inbound/`, `src/adapters/inbound/api/`, `src/adapters/outbound/`.
3. Mover `src/models.py` → `src/domain/models.py`.
4. Mover `src/sla_calculator.py` → `src/domain/sla_calculator.py` y ajustar su import de modelos.
5. Mover `src/triage_rules.py` → `src/domain/triage_rules.py`; corregir `PROJECT_ROOT`, imports y texto del demo.
6. Actualizar imports en `src/incident_repository.py` hacia `src.domain.*`.
7. Ampliar `src/context_audit.py` para incluir `src/**/*.py` en sus globs.
8. Crear `src/application/services.py` con `ValidationError` e `IncidentService`.
9. Crear `tests/conftest.py` y `tests/test_spec_001_triage.py` con los 4 escenarios (esperado rojo inicial).
10. Ajustar reglas en `src/domain/triage_rules.py`: 502 en pasarela de pagos → `P0` y `http-502-outage`; cuenta bloqueada → `P2` con `Security-IAM`.
11. Crear `src/adapters/inbound/api/schemas.py` con validación de campos no vacíos.
12. Crear `src/adapters/inbound/api/app.py` con `create_app()` y mapeo `ValidationError` → `422`.
13. Crear `src/adapters/inbound/cli.py` con Typer, subcomando `triage` y salida JSON.
14. Actualizar `AGENTS.md`: nuevos comandos `src.domain.*`, pytest, arquitectura hexagonal, `INC-1002→P2` y `payments-gateway:http-502-outage`.
15. Verificar: `uv run pytest`, demos de dominio, `context_audit` y benchmark rápido del repositorio.

## Decisión de invocación CLI

Se usa `uv run python -m src.adapters.inbound.cli triage --incident-id ... --raw-text ...` para no cambiar `package = false`. Si se requiere el ejecutable literal `triage`, será necesario añadir `[project.scripts]` y pasar `package = true`.
