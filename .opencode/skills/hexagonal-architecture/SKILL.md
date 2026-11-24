---
name: hexagonal-architecture
description: Instrucciones para diseñar, implementar y verificar código respetando la Arquitectura Hexagonal de IncidentOps.
---

# Arquitectura Hexagonal (IncidentOps)

Usa esta skill al diseñar, implementar o revisar código bajo `src/`. Las reglas son
obligatorias y derivan de `.specify/memory/constitution.md` y ADR-003.

## Fronteras de dependencias

### `src/domain/`

- Solo `models.py`, `triage_rules.py` y `sla_calculator.py` contienen reglas de negocio.
- Prohibido importar frameworks (FastAPI, Pydantic, Typer), componentes HTTP
  (`fastapi`, `starlette`, `httpx`, `requests`), bases de datos u ORMs (`sqlite3`,
  SQLAlchemy) y cualquier módulo de `src.application` o `src.adapters`.
- Permitido únicamente lo indispensable de la biblioteca estándar: `dataclasses`,
  `typing`, `datetime`.

### `src/application/`

- Puede usar biblioteca estándar y `src.domain`; nada más.
- Contiene los casos de uso en `services.py`: `IncidentService` y `ValidationError`.
- Define puertos en `ports.py` mediante `typing.Protocol`, en particular
  `IncidentRepositoryPort`.
- No importa adaptadores, frameworks ni motores de persistencia.

### `src/adapters/inbound/`

- REST (FastAPI) y CLI (Typer) delegan siempre en `IncidentService`; no reimplementan
  severidad, equipo ni duplicados.
- Prohibido importar drivers de base de datos ni repositorios concretos
  (`sqlite3`, SQLAlchemy, `src.incident_repository`, implementaciones outbound).
- Obtén las dependencias desde `src.adapters.outbound.factory` (inyección por
  constructor); ese es el único punto de acceso permitido al outbound.
- Garantiza paridad REST/CLI: mismos casos de uso, misma salida JSON y mismos errores
  (`ValidationError` → HTTP 422 en REST, código de salida 1 en CLI, constitución 2.0.0).
- Un futuro adaptador MCP sigue exactamente la misma regla.

### `src/adapters/outbound/`

- Implementa los puertos secundarios definidos en `src.application.ports`, en especial
  `IncidentRepositoryPort`.
- Expone `factory` para seleccionar el mecanismo activo según `DATABASE_URL`.
- SQLite3 de la stdlib es el motor inicial; sustituirlo no debe tocar dominio ni
  aplicación y requiere un ADR específico previo.

## Verificación con Ruff

Configuración base en `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "TID"]

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "parents"
```

Configuraciones jerárquicas (Ruff usa la más cercana; `extend` hereda la raíz):

```toml
# src/domain/ruff.toml
extend = "../../pyproject.toml"

[lint.flake8-tidy-imports.banned-api]
"fastapi".msg = "El dominio no importa frameworks HTTP."
"pydantic".msg = "El dominio no importa frameworks de validación."
"typer".msg = "El dominio no importa frameworks de CLI."
"httpx".msg = "El dominio no importa clientes HTTP."
"requests".msg = "El dominio no importa clientes HTTP."
"sqlite3".msg = "El dominio no importa bases de datos."
"sqlalchemy".msg = "El dominio no importa ORMs."
"src.application".msg = "Las dependencias apuntan hacia el dominio."
"src.adapters".msg = "El dominio no conoce adaptadores."
```

```toml
# src/application/ruff.toml
extend = "../../pyproject.toml"

[lint.flake8-tidy-imports.banned-api]
"fastapi".msg = "La aplicación no importa frameworks HTTP."
"pydantic".msg = "La aplicación no importa frameworks de validación."
"typer".msg = "La aplicación no importa frameworks de CLI."
"sqlite3".msg = "La aplicación no importa motores de base de datos."
"sqlalchemy".msg = "La aplicación no importa ORMs."
"src.adapters".msg = "La aplicación no conoce adaptadores concretos."
```

```toml
# src/adapters/inbound/ruff.toml
extend = "../../../pyproject.toml"

[lint.flake8-tidy-imports.banned-api]
"sqlite3".msg = "Usa src.adapters.outbound.factory; no importes drivers."
"sqlalchemy".msg = "Usa src.adapters.outbound.factory; no importes ORMs."
"src.incident_repository".msg = "Usa src.adapters.outbound.factory."
```

Comando de validación obligatorio antes de fusionar:

```bash
uv run ruff check src/
```

No añadas `# noqa` ni excepciones sin justificación en la revisión; cualquier
violación de TID251/TID252 bloquea el cambio.
