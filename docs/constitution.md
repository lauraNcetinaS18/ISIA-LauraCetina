# Constitución del Proyecto IncidentOps

Esta constitución define las reglas técnicas no negociables de IncidentOps. `AGENTS.md` conserva la guía operativa y los comandos; `docs/adr/` registra las decisiones puntuales.

## 1. Dominio determinista único

- El dominio es la única fuente de verdad para triaje, severidades, SLA, estados y duplicados.
- Severidades P0–P3: P0/P1 usan calendario 24/7; P2/P3 solo horario hábil L–V 08:00–18:00 (600 min/día; fines de semana 0). Breach es `elapsed > max`; escalamiento requiere `status != RESOLVED` y (`is_breached` o `elapsed >= 75%`), y permanece activo tras el breach.
- La severidad se decide por impacto real, nunca por palabras como `hoy` u `urgente`. Equipos válidos: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`. Estados válidos: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`. Clave de duplicados: `<component>:<symptom_category>`.
- Ningún endpoint, DTO, comando CLI, adaptador MCP ni repositorio puede reimplementar estas reglas: solo delegan en el dominio o en casos de uso.

## 2. Arquitectura Hexagonal (ADR-003)

- Se adopta la topología de ADR-003: `src/domain/` con entidades y reglas puras; `src/application/` con `IncidentService` y puertos `typing.Protocol`; `src/adapters/inbound/` con API REST y CLI, preparado para un futuro adaptador MCP; `src/adapters/outbound/` con persistencia intercambiable.
- Las dependencias apuntan hacia el dominio. El núcleo no importa FastAPI, Pydantic, Typer, `sqlite3` ni adaptadores.
- REST y CLI son adaptadores primarios delgados: validan, serializan y delegan en `IncidentService`. Un futuro adaptador MCP debe reutilizar el mismo servicio sin duplicar lógica.
- Los errores de validación se mapean a HTTP 422 en REST y a código de salida 1 en CLI, en todos los subcomandos; el mensaje de error va a `stderr`.
- Los adaptadores secundarios implementan puertos definidos en aplicación. SQLite3 es el motor inicial; cambiar de motor requiere un ADR previo.

## 3. Gobernanza técnica y calidad

- Python >=3.10 gestionado con `uv`; dependencias y ejecución se resuelven con `uv sync`/`uv run`.
- REST con FastAPI y Pydantic v2; CLI con Typer. Estos frameworks quedan fuera del dominio.
- Persistencia con `sqlite3` de la stdlib, sin ORMs pesados. Cualquier cambio de motor de base de datos exige ADR previo.
- Cada comportamiento se especifica en BDD (`Given / When / Then`) y cada criterio de aceptación debe tener una prueba automatizada con `pytest`.
- Toda nueva regla de dominio entra primero con su escenario BDD y su prueba; las refactorizaciones no deben alterar los resultados deterministas existentes.

**Versión**: 2.0.0 | **Ratificada**: 2026-11-23 | **Última enmienda**: 2026-11-24
