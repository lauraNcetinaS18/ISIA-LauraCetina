# Especificación Funcional — Hito 001: Triaje HTTP y CLI

## Objetivo

Exponer el motor determinista de triaje como servicio HTTP y como comando de terminal sin persistencia, reutilizando una única implementación del dominio.

## Alcance

- Incluye: contrato de entrada/salida, endpoint HTTP, comando CLI y errores de validación.
- Excluye: persistencia, alertas de duplicados, autenticación, procesamiento por lote y adaptador MCP.

## Contrato compartido

- Entrada: `incident_id` (string no vacío) y `raw_text` (string no vacío).
- HTTP: `POST /v1/triage`, `Content-Type: application/json`. Respuesta exitosa `200` con:
  - `incident_id`
  - `severity`
  - `component`
  - `recommended_team`
  - `rationale`
  - `duplicate_group_key`
- Validación fallida: HTTP `422 Unprocessable Entity`.
- CLI: comando `triage` con `--incident-id` y `--raw-text`; imprime JSON válido en stdout.
- Los valores esperados de los escenarios son normativos para H001.

---

## ESCENARIO 1 – Caída crítica de pasarela de pagos

**Given** que se recibe un reporte de caída crítica HTTP 502 en la pasarela de pagos.

**When** se solicita su clasificación mediante el endpoint HTTP.

**Then** debe devolver:
- HTTP 200.
- `severity="P0"`.
- `component="payments-gateway"`.
- `recommended_team="Backend-Core"`.
- `duplicate_group_key="payments-gateway:http-502-outage"`.

---

## ESCENARIO 2 – Cuenta individual bloqueada

**Given** que se recibe un reporte de una cuenta individual bloqueada que menciona "hoy".

**When** se ejecuta el triaje.

**Then** debe devolver:
- HTTP 200.
- `severity="P2"`.
- `recommended_team="Security-IAM"`.

No debe producir un falso positivo P0.

---

## ESCENARIO 3 – Entradas inválidas

**Given** que se envía `raw_text` compuesto solo por espacios en blanco o `incident_id` vacío.

**When** se solicita el triaje HTTP.

**Then** debe devolver HTTP 422 Unprocessable Entity.

---

## ESCENARIO 4 – Paridad del CLI

**Given** que se ejecuta el comando:

```bash
triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"
```

**When** se procesa el incidente desde terminal.

**Then** debe generar una salida JSON válida con `severity="P0"` y `recommended_team="Backend-Core"`.

```json
{
  "incident_id": "INC-1001",
  "severity": "P0",
  "component": "payments-gateway",
  "recommended_team": "Backend-Core",
  "duplicate_group_key": "payments-gateway:http-502-outage"
}
```

---

## Criterios transversales

- Una misma tupla (`incident_id`, `raw_text`) produce la misma clasificación por HTTP y por CLI.
- El triaje no escribe en base de datos ni calcula duplicados persistentes; `duplicate_group_key` es solo resultado de la clasificación.
- Ningún adaptador reimplementa reglas de severidad, equipo o duplicados; delega en el dominio a través del caso de uso compartido.
