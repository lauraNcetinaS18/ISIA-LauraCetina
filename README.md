# IncidentOps — Proyecto Semilla (Semana 1)

**IncidentOps** es un sistema backend en Python gestionado con [`uv`](https://docs.astral.sh/uv/) que administra reportes de incidentes de software, evalúa acuerdos de nivel de servicio (**SLA**) sobre SQLite y ejecuta reglas de **triaje y enrutamiento de tickets**.

Este repositorio sirve como banco de pruebas práctico para la **Semana 1** de *Ingeniería de Software Asistida por Inteligencia Artificial (ISIA)* bajo un enfoque **100% *AI for Software Engineering***.

---

## Requisitos e Instalación con `uv`

- **Python 3.10+** y **[`uv`](https://docs.astral.sh/uv/)**.
- Dependencias declaradas en [`pyproject.toml`](pyproject.toml):
  - `tiktoken`: Para medir con precisión matemática el consumo de tokens BPE (`o200k_base` / `cl100k_base`) en las distintas estrategias de recolección de contexto.

Para inicializar el entorno virtual e instalar `tiktoken`:

```bash
cd week-1/starter-project
uv sync
```

---

## Comandos Principales para la Práctica

Ejecuta todos los comandos desde `week-1/starter-project/` usando `uv run`:

### 1. Fase 1 — Auditoría de Tokens con `tiktoken`: Fuerza Bruta vs. `grep` vs. LSP
Compara cuántos tokens reales consume leer todos los archivos del repositorio (`glob` + `read`), leer los archivos `.py` coincidentes (`grep` + `read`) o extraer únicamente la definición, firmas de tipos y referencias de un símbolo como lo hace un servidor **LSP**:

```bash
uv run python -m src.context_audit --symbol evaluate_sla_status
uv run python -m src.context_audit --symbol get_active_incidents_summary
uv run python -m src.context_audit --symbol classify_incident_report
```

Para comparar el impacto en tokens de distintos formatos de serialización de datos (JSON indentado, JSON compacto, YAML, CSV):

```bash
uv run python -m src.context_audit --compare-formats
```

### 2. Fase 2 — Benchmark del Repositorio de Incidentes (10,000 registros)
Ejecuta el escenario con deuda técnica (escaneo completo en memoria y problema de consultas N+1 sobre 10,000 incidentes en SQLite):

```bash
uv run python -m src.incident_repository
```

### 3. Fase 3 — Auditoría del Motor de Triaje (`src/triage_rules.py`)
Evalúa cómo el motor heurístico actual clasifica los 10 incidentes de [`data/sample_incidents.json`](data/sample_incidents.json) e identifica sus fallos de diseño:

```bash
uv run python -m src.triage_rules
```

### 4. Verificación del Cálculo Determinista de SLA (`src/sla_calculator.py`)
Ejecuta la demostración del cálculo de SLA actual (donde se evidencia el bug de horario hábil en tickets `P2`/`P3`):

```bash
uv run python -m src.sla_calculator
```
