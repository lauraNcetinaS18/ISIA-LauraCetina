---
name: bdd-acceptance
description: Instrucciones para redactar especificaciones BDD y crear pruebas de aceptación automatizadas para IncidentOps.
---

# BDD y pruebas de aceptación (IncidentOps)

Usa esta skill al escribir `specs/*.md` o `tests/*.py`. Toda regla nueva nace de un
escenario y su prueba; el código llega después.

## 1. Redacción BDD

- Escribe escenarios **Given / When / Then** al estilo Dan North: contexto, acción,
  resultado observable. Un escenario = una regla de negocio.
- Usa vocabulario ubicuo: «reporte de incidente», «pasarela de pagos», «clasificación»,
  «severidad», «equipo recomendado», «SLA», «escalamiento».
- Prohibido en el escenario: nombres de clases o funciones Python, tablas SQL, consultas,
  rutas de archivos, parámetros internos ni detalle de implementación.
- Permitido: contratos observables (`POST /v1/triage`, HTTP 200/422, JSON de respuesta,
  `incident_id`, texto del reporte, códigos de salida de la CLI).
- Formato: `## ESCENARIO N – Título de negocio`, separado con `---`.

## 2. Mapeo de escenarios a pruebas

- Cada escenario BDD corresponde a exactamente una función `test_bdd_*` en `tests/`
  con el mismo orden y el mismo nombre conceptual.
  - `ESCENARIO 1 – Caída crítica de pasarela de pagos` → `test_bdd_caida_critica_pasarela`.
  - `ESCENARIO 3 – Entradas inválidas` → `test_bdd_entradas_invalidas`.
- Paramétriza solo variantes del mismo escenario (`@pytest.mark.parametrize`).
- Conserva las pruebas heredadas `test_escenario_*`; las nuevas usan siempre `test_bdd_*`.

## 3. Herramientas de prueba

- Usa las fixtures de `tests/conftest.py`: `client` (`TestClient` de FastAPI) y
  `cli_runner` (`CliRunner` de Typer).
- REST: `client.post("/v1/triage", json=...)`; verifica `status_code` y el cuerpo JSON.
- CLI: `cli_runner.invoke(cli_app, ["triage", ...])`; verifica `exit_code` y
  `json.loads(result.output)`.
- Una misma tupla `(incident_id, raw_text)` debe producir la misma clasificación por
  HTTP y por CLI (paridad).
- Errores de validación: REST `422`, CLI código de salida `2`.

## 4. Aislamiento

- Ningún escenario depende de otro ni del orden de ejecución; cada prueba construye
  sus propios datos de entrada.
- Si hay persistencia, usa `tmp_path` con una `DATABASE_URL` única por escenario y
  crea el adaptador outbound desde `src.adapters.outbound.factory`; cierra la conexión
  al terminar.
- Prohibido compartir una base de datos global en memoria, cachés ni contadores entre
  escenarios.
- En H001 (triaje sin persistencia) basta con `client` y `cli_runner`: la prueba no
  debe escribir en base de datos.

Verificación obligatoria: `uv run pytest -v`.
