<!--
Sync Impact Report
- Validación 2026-11-23: los tres principios solicitados ya están formalizados y son conformes
  con `docs/constitution.md` y `docs/adr/003-arquitectura-hexagonal.md`.
- Enmienda 2026-11-24 (Q1, feature 003): el principio II pasa a fijar el código de salida CLI 1
  en errores de validación de todos los subcomandos, manteniendo HTTP 422. Motivación: paridad
  REST/CLI y aclaración aprobada en la sesión de 2026-11-24. Impacto: cambia el contrato CLI de
  H001/H002 y sus aserciones de exit code; no cambia payloads ni reglas de dominio.
- Cambio de versión: 1.0.0 → 2.0.0.
- Principios modificados: II. Arquitectura Hexagonal estricta (mapeo de errores CLI).
- Secciones agregadas: ninguna en esta revisión.
- Secciones eliminadas: ninguna.
- TODOs de seguimiento:
  - Declarar la configuración de Ruff que haga cumplir las fronteras arquitectónicas; el paquete
    ya está en el grupo `dev` de `pyproject.toml`, pero no hay reglas de lint configuradas
    (fuera del alcance de este archivo).
  - Ubicar o redactar el ADR-001 citado para la decisión SQLite3; no está en `docs/adr/`.
-->

# Constitución de IncidentOps

Esta constitución define las reglas técnicas no negociables de IncidentOps. `AGENTS.md` conserva la guía operativa; `docs/adr/` registra las decisiones puntuales. En caso de conflicto, prevalece esta constitución y después los ADR aceptados.

## Core Principles

### I. Núcleo determinista único en `src/domain/`

`src/domain/` es la única fuente de verdad para triaje, severidades, SLA, estados y duplicados, y contiene `models.py`, `triage_rules.py` y `sla_calculator.py`.

- Las entidades, uniones `Literal` y reglas puras residen exclusivamente en esos tres módulos.
- P0/P1 usan calendario 24/7; P2/P3 solo horario hábil L–V 08:00–18:00 (600 min/día, fines de semana 0). `is_breached` es `elapsed > max`; el escalamiento requiere `status != RESOLVED` y (`is_breached` o `elapsed >= 75%`), y permanece activo tras el breach.
- La severidad se decide por impacto real, nunca por palabras como `hoy` u `urgente`. Equipos válidos: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`. Estados válidos: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`. Clave de duplicados: `<component>:<symptom_category>`.
- Ningún endpoint, DTO, comando CLI, adaptador MCP ni repositorio reimplementa estas reglas; todos delegan en el dominio o en `IncidentService`.
- Las reglas DEBEN permanecer verificables sin servidor web ni base de datos, y los resultados deterministas existentes NO DEBEN cambiar en refactorizaciones.

**Rationale:** Una sola implementación evita divergencias entre REST, CLI y MCP, y permite verificar el comportamiento con pruebas puras y reproducibles.

### II. Arquitectura Hexagonal estricta

La topología aceptada en ADR-003 es obligatoria: las dependencias apuntan hacia el dominio y ninguna flecha sale de él.

- `src/domain/` NO DEBE importar FastAPI, Pydantic, Typer, `sqlite3` ni adaptadores; solo lo indispensable de la biblioteca estándar para reglas puras (`dataclasses`, `typing`, `datetime`).
- `src/application/` contiene `ports.py` con puertos `typing.Protocol` y `services.py` con `IncidentService`, único orquestador de casos de uso.
- `src/adapters/inbound/` aloja FastAPI y Typer como adaptadores delgados que validan, serializan y delegan en `IncidentService`; la estructura DEBE admitir un futuro adaptador MCP sin duplicar lógica ni modificar el servicio. Los errores de validación se mapean a HTTP 422 en REST y a código de salida 1 en CLI, en todos los subcomandos; el mensaje de error va a `stderr`.
- `src/adapters/outbound/` implementa los puertos de aplicación y se selecciona mediante `DATABASE_URL`. El motor inicial es SQLite3 de la biblioteca estándar; sustituirlo exige un ADR específico aprobado previamente.

**Rationale:** La frontera alrededor del dominio, y no alrededor de un framework o motor, permite añadir interfaces y cambiar de persistencia sin reescribir reglas de negocio.

### III. Gobernanza técnica y calidad (NON-NEGOTIABLE)

El stack y las compuertas de calidad quedan fijados; cualquier desviación requiere enmienda o ADR previo.

- Python >=3.10 gestionado con `uv`: dependencias y ejecución se resuelven con `uv sync`/`uv run`. Ningún comando del proyecto se ejecuta fuera de `uv run`.
- REST con FastAPI y Pydantic v2; CLI con Typer. Estos frameworks quedan fuera de `src/domain/` y no redefinen reglas de negocio.
- Persistencia con `sqlite3` de la stdlib, sin ORMs pesados, conforme a ADR-001. Cualquier cambio de motor de base de datos exige un ADR específico previo.
- Cada comportamiento se especifica en BDD (`Given / When / Then`) y cada criterio de aceptación DEBE tener una prueba automatizada. Las fronteras arquitectónicas DEBEN validarse con `uv run ruff check src/`.
- Las pruebas BDD son obligatorias y se ejecutan con `uv run pytest -v`; toda nueva regla de dominio entra primero con su escenario BDD y su prueba.

**Rationale:** Herramientas y compuertas uniformes hacen que la conformidad sea verificable en revisión y que las reglas deterministas no se degraden silenciosamente.

## Restricciones técnicas

- Lenguaje y entorno: Python >=3.10; `uv` es el único gestor de dependencias y ejecutor. Dependencias de ejecución: `tiktoken`, `fastapi`, `uvicorn`, `pydantic>=2`, `typer`. Dependencias de desarrollo: `pytest`, `httpx` y Ruff.
- `src/domain/` depende únicamente de la biblioteca estándar; `src/application/` define puertos sin conocer frameworks; los adaptadores inbound y outbound son los únicos que pueden importarlos.
- `DATABASE_URL` selecciona el adaptador outbound activo. Mientras no se apruebe otro motor, el único valor operativo es SQLite3 de la stdlib y las consultas, incluido el escaneo completo y el patrón N+1, permanecen confinadas al adaptador outbound.
- Un futuro adaptador MCP DEBE traducir sus solicitudes a `IncidentService` y reutilizar las entidades del dominio; no introduce reglas de severidad, equipo o duplicados propias.
- Código, docstrings y salida de consola se escriben en español. `AGENTS.md` conserva los comandos operativos vigentes y `docs/adr/` las decisiones puntuales.

## Flujo de desarrollo y compuertas de calidad

- Toda historia DEBE partir de una especificación BDD con criterios de aceptación (`Given / When / Then`) y sus pruebas correspondientes antes de la implementación de la regla.
- Todo cambio DEBE pasar `uv run pytest -v` y `uv run ruff check src/` sin errores. La verificación determinista del dominio incluye `uv run python -m src.domain.sla_calculator` y `uv run python -m src.domain.triage_rules`.
- La revisión DEBE comprobar que las reglas siguen solo en `src/domain/`, que los adaptadores delegan en `IncidentService` y que no se agregó dependencia de framework ni de motor en el núcleo.
- La complejidad adicional (capas, mapeos, indirección) DEBE estar justificada por el cumplimiento de estos principios; las refactorizaciones NO DEBEN alterar resultados deterministas ya cubiertos.
- Un cambio de motor de base de datos, de framework estructural o de una regla de dominio aprobada DEBE proponerse primero como ADR y aprobarse antes de implementarse.

## Governance

Esta constitución prevalece sobre otras prácticas del repositorio. Solo puede modificarse mediante una enmienda documentada que identifique el principio afectado, explique la motivación, incluya el análisis de impacto y sea aprobada por el equipo del proyecto; los cambios de motor o de arquitectura requieren además un ADR específico previo.

El versionado sigue Semantic Versioning: MAJOR para eliminación o redefinición incompatible de principios; MINOR para principios o secciones nuevas y para ampliaciones materiales de la guía; PATCH para aclaraciones, correcciones y refinamientos sin cambio semántico. Toda enmienda actualiza la fecha `Last Amended` y el número de versión.

El cumplimiento se revisa en cada pull request con las compuertas descritas; el incumplimiento DEBE corregirse antes de fusionar. Las excepciones temporales DEBEN registrarse con alcance y fecha de expiración en el registro de decisiones.

**Version**: 2.0.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-24
