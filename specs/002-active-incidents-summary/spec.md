# Feature Specification: Resumen de incidentes activos

**Feature Branch**: `002-active-incidents-summary`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Necesitamos consultar el resumen de incidentes actualmente activos (OPEN e IN_PROGRESS) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente."

## Clarifications

### Session 2026-11-24

- Q: ¿Qué estados se consideran incidentes activos? → A: Exclusivamente OPEN e IN_PROGRESS; RESOLVED y ESCALATION_REQUIRED se excluyen.
- Q: ¿Cómo se expone el resumen por HTTP? → A: `GET /api/v1/incidents/summary` con parámetro query opcional `component`.
- Q: ¿Cómo se expone el resumen por CLI? → A: Subcomando `summary` con parámetros opcionales `--component` y `--reference-time`.
- Q: ¿Qué devuelve una consulta sin incidentes activos o sin coincidencias con el filtro? → A: HTTP 200 con el cuerpo vacío canónico definido en FR-009; mismo resultado en la terminal.
- Q: ¿Cómo se fija la hora de referencia para evaluar el SLA? → A: `reference_time` permite evaluaciones deterministas; si se omite, se usa el instante actual.
- Q: ¿Qué escenarios BDD debe cubrir la especificación? → A: Cuatro: resumen global excluyendo RESOLVED, resumen filtrado por componente, consulta sin resultados y consulta equivalente por CLI.
- Q: ¿Cómo se mide SC-005? → A: Con 10.000 incidentes en una BD SQLite aislada, una ejecución de calentamiento descartada y tres ejecuciones consecutivas; la mediana debe ser menor que 2 segundos. El benchmark legado no se usa como medición.
- Q: ¿Cómo se fija el reloj en la prueba de paridad si HTTP no expone `reference_time`? → A: La prueba congela el reloj del servicio en HTTP mediante una fixture determinista y pasa el mismo instante a `--reference-time` en la CLI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar el resumen global y filtrado por HTTP (Priority: P1)

Como operador de IncidentOps, quiero solicitar el resumen de los incidentes activos
para ver de un vistazo cuántos hay abiertos o en atención, cuántos incumplieron su
SLA y qué incidentes requieren atención inmediata, sin revisarlos uno por uno.

**Why this priority**: Es la forma principal de consulta para quien monitoriza la
operación; sin ella no existe visibilidad consolidada del estado actual.

**Independent Test**: Se puede validar de forma aislada con un conjunto conocido de
incidentes OPEN, IN_PROGRESS, RESOLVED y ESCALATION_REQUIRED, comprobando que solo
aparecen los dos primeros y que los totales coinciden con el detalle.

**Acceptance Scenarios**:

1. **Given** que existen incidentes OPEN e IN_PROGRESS y también incidentes RESOLVED,
   **When** se solicita `GET /api/v1/incidents/summary` sin filtro, **Then** se devuelve
   HTTP 200 con `total_active`, `breached_count` e `incidents`, y los incidentes
   RESOLVED no aparecen ni se contabilizan.
2. **Given** incidentes activos de varios componentes, **When** se solicita
   `GET /api/v1/incidents/summary?component=<componente>`, **Then** `incidents` contiene
   solo los incidentes de ese componente y `total_active` y `breached_count` se
   recalculan sobre ese subconjunto.
3. **Given** que no hay incidentes activos o que el filtro no coincide con ninguno,
   **When** se solicita el resumen por HTTP, **Then** se devuelve HTTP 200 con el
   cuerpo vacío canónico definido en FR-009.

---

### User Story 2 - Consultar el resumen equivalente desde la terminal (Priority: P1)

Como ingeniero de guardia, quiero obtener desde la terminal exactamente el mismo
resumen que por HTTP para revisar la situación sin cambiar de herramienta ni
reinterpretar los datos.

**Why this priority**: La terminal es el segundo canal de uso diario y debe ser
equivalente al HTTP; una divergencia generaría decisiones distintas con los mismos
incidentes.

**Independent Test**: Se puede validar de forma aislada sobre el mismo conjunto de
incidentes y la misma hora de referencia, comparando campo por campo con la respuesta
HTTP. La prueba congela el reloj del servicio en HTTP mediante una fixture determinista
y pasa el mismo instante a `--reference-time`; HTTP no expone `reference_time`.

**Acceptance Scenarios**:

1. **Given** el mismo conjunto de incidentes y la misma hora de referencia, **When** se
   ejecuta el subcomando `summary` con `--component` y `--reference-time` opcionales,
   **Then** la terminal muestra la misma información que el canal HTTP, con idénticos
   `total_active`, `breached_count` e `incidents`.

---

### Edge Cases

- Sin incidentes activos o sin coincidencias con el filtro: se aplica el cuerpo vacío
   canónico de FR-009 en ambos canales.
- Un incidente OPEN o IN_PROGRESS que requiere escalamiento: permanece incluido en el
  resumen; el indicador de escalamiento no cambia su estado.
- Incidentes P2/P3 que abarcan fines de semana: los minutos transcurridos no incluyen
  sábados ni domingos, conforme a la política de SLA vigente.
- Incidente exactamente en el límite de tiempo permitido: no se cuenta como
  incumplimiento; solo se incumple cuando el tiempo transcurrido supera el límite.
- Incidente exactamente en el 75 % del tiempo permitido: se marca como que requiere
  escalamiento sin necesidad de haber incumplido.
- Estados RESOLVED y ESCALATION_REQUIRED: se excluyen del resumen por definición de
  "activos" de esta feature.
- Sin `--reference-time`: se usa el instante de la consulta; con `--reference-time`,
  la evaluación de SLA es determinista para ese instante.
- Resultados deterministas: el detalle se presenta siempre en el mismo orden para la
  misma consulta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE ofrecer el resumen de incidentes activos por los canales
  HTTP y terminal, reutilizando el mismo caso de uso y las mismas reglas de dominio
  en ambos.
- **FR-002**: El sistema DEBE incluir exclusivamente incidentes cuyo estado sea OPEN o
  IN_PROGRESS; RESOLVED y ESCALATION_REQUIRED quedan fuera del resumen.
- **FR-003**: El sistema DEBE reportar `total_active`, el número de incidentes activos
  incluidos en la consulta.
- **FR-004**: El sistema DEBE reportar `breached_count`, cuántos de esos incidentes
  incumplieron su SLA, entendiéndose por incumplimiento un tiempo transcurrido
  estrictamente mayor que el tiempo permitido.
- **FR-005**: El sistema DEBE incluir en `incidents`, para cada incidente, título,
  componente, severidad, estado, minutos transcurridos e indicador de si requiere
  escalamiento.
- **FR-006**: El sistema DEBE aceptar un filtro opcional por componente y aplicarlo
  antes de calcular `total_active`, `breached_count` e `incidents`.
- **FR-007**: El sistema DEBE calcular los minutos transcurridos según la política de
  SLA vigente: calendario continuo para P0/P1 y horario hábil de lunes a viernes de
  08:00 a 18:00, sin fines de semana, para P2/P3.
- **FR-008**: El sistema DEBE marcar que un incidente requiere escalamiento cuando su
  SLA se incumplió o cuando se consumió al menos el 75 % del tiempo permitido.
- **FR-009**: Si no hay incidentes activos o no hay coincidencias con el filtro, el
  canal HTTP DEBE devolver HTTP 200 con `{"total_active": 0, "breached_count": 0, "incidents": []}` y la terminal DEBE mostrar el mismo resultado vacío.
- **FR-010**: El sistema DEBE presentar `incidents` en un orden determinista.
- **FR-011**: El sistema NO DEBE modificar las reglas de triaje, severidad ni SLA ya
  aprobadas; DEBE reutilizar su definición existente.
- **FR-012**: La consulta por terminal DEBE entregar la misma estructura JSON que la
  consulta HTTP (nombres de campos, tipos y orden de campos), de modo que un mismo
  conjunto de incidentes produzca idénticos valores en ambos canales.
- **FR-013**: El sistema DEBE exponer el resumen por HTTP mediante
  `GET /api/v1/incidents/summary`, con parámetro query opcional `component`.
- **FR-014**: El sistema DEBE exponer el resumen por terminal mediante el subcomando
  `summary`, con parámetros opcionales `--component` y `--reference-time`.
- **FR-015**: El parámetro `reference_time` DEBE permitir evaluaciones deterministas
  del SLA; si se omite, el sistema DEBE usar el instante actual como referencia.

### Key Entities *(include if feature involves data)*

- **Resumen de incidentes activos**: Resultado de una consulta; contiene `total_active`,
  `breached_count` e `incidents`, después de aplicar el filtro opcional `component` y
  usando la hora de referencia indicada o la actual.
- **Detalle de incidente activo**: Informe de un incidente dentro de `incidents`;
  incluye título, componente, severidad, estado, minutos transcurridos e indicador de
  escalamiento requerido.
- **Política de SLA**: Regla de negocio ya aprobada que define el tiempo permitido, el
  calendario aplicable según severidad y el umbral de escalamiento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los incidentes OPEN e IN_PROGRESS de un conjunto de prueba
  aparece en `incidents` exactamente una vez.
- **SC-002**: En el 100 % de las consultas, `total_active` y `breached_count` coinciden
  con los valores derivados de `incidents`.
- **SC-003**: Para una misma consulta, los canales HTTP y terminal devuelven valores
  idénticos en el 100 % de los casos evaluados.
- **SC-004**: Con filtro por componente, el 100 % de los elementos de `incidents`
  pertenece a ese componente y los totales se recalculan en consecuencia.
- **SC-005**: Una consulta sobre 10 000 incidentes almacenados devuelve el resumen en
  menos de 2 segundos en condiciones normales de prueba.
- **SC-006**: Cero falsos positivos de incumplimiento en los casos borde de fin de
  semana y límite exacto de SLA.
- **SC-007**: El 100 % de los escenarios de aceptación de esta especificación tiene una
  prueba automatizada correspondiente que pasa.
- **SC-008**: El 100 % de las consultas que usan el mismo `reference_time` produce
   resultados idénticos.

### Medición de SC-005

La verificación de SC-005 se realiza con el siguiente protocolo reproducible:

1. Crear una BD SQLite aislada por la prueba y sembrar exactamente 10.000 incidentes.
2. Descartar una ejecución de calentamiento de `list_active_incidents` + servicio.
3. Ejecutar tres mediciones consecutivas sobre los mismos datos y reportar la mediana.
4. Exigir que la mediana sea menor que 2 segundos; el umbral proviene de SC-005 y no se sustituye por otro.
5. No usar `src/incident_repository.py` como medición: es el benchmark legado con full scan + N+1 intencionales.

## Assumptions

- Los usuarios de la feature son operadores o ingenieros de guardia con permisos de
  solo lectura; autorización y autenticación quedan fuera de alcance.
- "Actualmente activos" significa exclusivamente OPEN e IN_PROGRESS, evaluados en el
  momento de la consulta.
- El filtro por componente es de coincidencia exacta con el valor registrado; no admite
  coincidencias parciales ni normalización de mayúsculas.
- Los totales se calculan siempre sobre el conjunto resultante después de aplicar el
  filtro, no sobre todos los incidentes almacenados.
- No se incluye paginación, orden configurable ni agregación por severidad en esta
   versión; `incidents` se ordena por `created_at` ascendente y, en empate, por
   `incident_id` ascendente, según `data-model.md`.
- Las reglas de SLA, severidad y escalamiento son las ya aprobadas en ADR-002 y la
  constitución del proyecto; esta feature solo las consume.
- Cuando se proporciona `--reference-time` en la terminal, ese instante gobierna la
  evaluación del SLA; si se omite, y en el canal HTTP, se usa el instante actual.
- La terminal muestra la misma estructura JSON definida en FR-012, para conservar
   coherencia y permitir su procesamiento.
