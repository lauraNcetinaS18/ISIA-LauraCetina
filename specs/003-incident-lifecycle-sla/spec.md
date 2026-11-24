# Feature Specification: Ciclo de vida y auditoría de SLA de incidentes

**Feature Branch**: `003-incident-lifecycle-sla`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "El equipo de Operaciones necesita registrar incidentes cuando llegan, identificar si ya existe otro incidente equivalente que continúa abierto y consultar cómo evoluciona el SLA de cada incidente tanto por API REST como por CLI, continuando sobre la arquitectura hexagonal existente y reutilizando el dominio, los puertos, los adaptadores y los servicios actuales."

## Clarifications

### Session 2026-11-24

- Q: ¿Qué código de salida produce la CLI ante datos inválidos? → A: Código 1 para errores de validación en todos los subcomandos (`create`, `sla`, `triage` y `summary`); enmienda aplicada el 2026-11-24 en la constitución 2.0.0, con actualización de los contratos CLI de los hitos 001 y 002.
- Q: ¿La inclusión de `ESCALATION_REQUIRED` cambia la definición de "activos" del hito 002? → A: No; aplica exclusivamente a la detección de duplicados y el resumen del hito 002 se mantiene igual.
- Q: ¿Qué formato tiene el identificador generado y qué ocurre si el `incident_id` provisto ya existe? → A: `INC-` seguido de 8 caracteres hexadecimales en minúsculas; un identificador ya registrado se rechaza como error de validación.
- Q: ¿Se exige formato `INC-[0-9a-f]{8}` al `incident_id` provisto? → A: Sí; cualquier otro valor se rechaza con HTTP 422 / CLI 1, además de la unicidad (P1 aprobado).
- Q: ¿Cómo se comparan las marcas `created_at` y `reference_time` naive y aware? → A: Se rechaza toda marca aware con HTTP 422 / CLI 1 y se opera solo con marcas naive en hora local del servidor (P2 aprobado).

### Revisión de ambigüedades — decisiones confirmadas

- `title` y `raw_text`: se rechazan la cadena vacía y la cadena compuesta solo por espacios en
  ambos canales; los valores no vacíos se conservan tal como llegan (FR-002).
- `incident_id`: el generado es `INC-` + 8 hexadecimales en minúsculas; el provisto debe cumplir
  `INC-[0-9a-f]{8}` y no estar ya registrado (FR-003, FR-021, decisión P1 aprobada).
- Comparación de duplicados: igualdad exacta de `duplicate_group_key`, sin normalización
  adicional, porque el dominio ya entrega la clave normalizada (FR-008).
- Estados: solo OPEN, IN_PROGRESS y ESCALATION_REQUIRED; RESOLVED se ignora y el propio
  identificador se excluye (FR-009, FR-010, FR-011).
- SLA: `reference_time` gobierna la evaluación; `reference_time` igual a `created_at` produce
  0 minutos transcurridos y sin incumplimiento; un ISO 8601 malformado se rechaza (FR-014,
  FR-016, FR-017).
- Errores: HTTP 201/422/404 y CLI 0/1, con el mismo criterio en ambos canales (FR-007,
  FR-016, FR-018).
- Marcas de tiempo naive y aware: se rechaza toda marca aware con HTTP 422 / CLI 1 y se opera
  solo con marcas naive en hora local del servidor, en línea con ADR-002 y `AGENTS.md`
  (FR-022, decisión P2 aprobada).

## Decisiones aprobadas

- **P1 — Validación de formato del `incident_id` proporcionado**: se exige `INC-[0-9a-f]{8}`,
  en coincidencia con el identificador generado; cualquier otro valor se rechaza con HTTP 422 /
  CLI 1, además de la unicidad ya acordada.
- **P2 — Comparación entre marcas naive y aware**: se rechaza toda marca aware con HTTP 422 /
  CLI 1 y se opera solo con marcas naive en hora local del servidor, de modo que la
  comparación sea determinista.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar un incidente y señalar sus duplicados abiertos (Priority: P1)

Como operador de IncidentOps, quiero registrar cada incidente que llega con su título y su
texto original, y que el sistema me indique si ya hay otro incidente equivalente abierto,
para mantener un registro completo sin perder la señal de un problema repetido.

**Why this priority**: Es la entrada de datos de todo el ciclo de vida; sin ella no existen
los incidentes que consumen las funcionalidades 001 y 002.

**Independent Test**: Se puede validar de forma aislada sembrando incidentes previos en los
estados OPEN, IN_PROGRESS, ESCALATION_REQUIRED y RESOLVED, enviando una creación válida y
comprobando el código de respuesta, la clasificación y el contenido de `duplicate_of`.

**Acceptance Scenarios**:

1. **Given** que no existe ningún incidente abierto con la misma clave de duplicado,
   **When** se registra un incidente con `title` y `raw_text` válidos y sin `incident_id`,
   **Then** se devuelve HTTP 201 con un identificador `INC-` seguido de 8 caracteres
   hexadecimales, `status` OPEN, la clasificación completa, `is_duplicate=false` y
   `duplicate_of=[]`.
2. **Given** un incidente previo en estado OPEN con la misma clave de duplicado, **When** se
   registra un nuevo incidente con un texto equivalente, **Then** se devuelve HTTP 201,
   `is_duplicate=true`, `duplicate_of` contiene el identificador previo y ambos incidentes
   quedan registrados.
3. **Given** un incidente RESOLVED con la misma clave y otro en estado ESCALATION_REQUIRED,
   **When** se registra un nuevo incidente equivalente, **Then** `duplicate_of` contiene solo
   el identificador en ESCALATION_REQUIRED y el incidente RESOLVED se ignora.
4. **Given** un `title` o un `raw_text` vacío o compuesto únicamente por espacios, **When** se
   intenta registrar el incidente, **Then** se devuelve HTTP 422 y no se crea ningún
   incidente.
5. **Given** que se omite `status`, **When** se registra el incidente, **Then** el nuevo
   incidente queda con `status` OPEN.
6. **Given** que se omite `created_at`, **When** se registra el incidente, **Then** su
   `created_at` es el instante de la creación.
7. **Given** un `incident_id` provisto que no cumple `INC-[0-9a-f]{8}` o que ya está registrado,
   **When** se intenta registrar, **Then** se devuelve HTTP 422 y no se crea ningún incidente.

---

### User Story 2 - Auditar el SLA de un incidente concreto (Priority: P1)

Como operador de IncidentOps, quiero consultar la evolución del SLA de un incidente,
fijando si hace falta una hora de referencia, para saber si se incumplió o si debe escalarse
sin depender del momento en que realizo la consulta.

**Why this priority**: Es la segunda forma de consulta diaria y permite evaluaciones
reproducibles; sin ella no se puede auditar el cumplimiento de cada incidente.

**Independent Test**: Se puede validar de forma aislada con un incidente P2 creado el viernes
2026-11-06 a las 17:00 y una consulta con `reference_time` del lunes 2026-11-09 a las 09:00,
comprobando los cinco valores de la evaluación.

**Acceptance Scenarios**:

1. **Given** un incidente P2 creado el viernes 2026-11-06 a las 17:00, **When** se solicita
   `GET /api/v1/incidents/{incident_id}/sla` con `reference_time=2026-11-09T09:00:00`,
   **Then** se devuelve HTTP 200 con `elapsed_minutes=120`, `allowed_minutes=480`,
   `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.
2. **Given** un identificador que no corresponde a ningún incidente, **When** se consulta su
   SLA, **Then** se devuelve HTTP 404.
3. **Given** un `reference_time` anterior a `created_at`, **When** se consulta el SLA,
   **Then** se devuelve HTTP 422.
4. **Given** que se omite `reference_time`, **When** se consulta el SLA, **Then** la evaluación
   usa el instante de la consulta.
5. **Given** un incidente OPEN que ha consumido al menos el 75 % del tiempo permitido sin
   incumplirlo, **When** se consulta su SLA, **Then** `requires_escalation=true` e
   `is_breached=false`.
6. **Given** un `reference_time` aware o con formato ISO 8601 inválido, **When** se consulta el
   SLA, **Then** se devuelve HTTP 422.

---

### User Story 3 - Registrar y auditar desde la terminal con resultados equivalentes (Priority: P2)

Como ingeniero de guardia, quiero registrar incidentes y auditar su SLA desde la terminal con
los mismos resultados que por HTTP, para cambiar de canal sin reinterpretar la información.

**Why this priority**: La terminal es el segundo canal de uso diario; una divergencia
generaría decisiones distintas con los mismos datos.

**Independent Test**: Se puede validar de forma aislada ejecutando `create` y `sla` sobre los
mismos datos y el mismo `reference_time` que el canal HTTP y comparando campo por campo.

**Acceptance Scenarios**:

1. **Given** los mismos datos válidos, **When** se ejecuta el subcomando `create`, **Then** la
   terminal emite un JSON con la misma clasificación, `is_duplicate` y `duplicate_of` que la
   respuesta HTTP y termina con código 0.
2. **Given** el mismo incidente y el mismo `reference_time`, **When** se ejecuta el subcomando
   `sla`, **Then** la terminal emite el mismo JSON de evaluación que el canal HTTP y termina
   con código 0.
3. **Given** datos inválidos en `create` (incluye identificador con formato inválido o
   duplicado), o un identificador inexistente o un `reference_time` inválido, aware o anterior a
   la creación en `sla`, **When** se ejecuta el comando, **Then** termina con código de salida 1
   y muestra el error por la salida de error.
4. **Given** que se omite `reference_time` en `sla`, **When** se ejecuta el comando, **Then**
   la evaluación usa el instante actual, igual que en el canal HTTP.
5. **Given** datos inválidos en `triage` o `summary`, **When** se ejecuta cualquiera de esos
   subcomandos, **Then** termina con código de salida 1, conforme a la aclaración de la sesión
   2026-11-24.

---

### Edge Cases

- `title` o `raw_text` iguales a `""` o compuestos solo por espacios: se rechazan en ambos
  canales sin crear registro ni consumir un identificador o una fecha; los valores no vacíos se
  conservan tal como llegan.
- `incident_id` proporcionado: se conserva tal cual, debe cumplir `INC-[0-9a-f]{8}` y no estar
  ya registrado; el generado solo se usa cuando se omite y siempre en minúsculas. Otro formato o
  un duplicado se rechaza como dato inválido (P1 aprobado).
- Igualdad de duplicados: se basa exclusivamente en `duplicate_group_key`; textos distintos
  con la misma clave cuentan como duplicados y textos iguales con clave distinta no.
- Incidentes RESOLVED: se ignoran siempre en la búsqueda de duplicados.
- Incidentes ESCALATION_REQUIRED: se consideran abiertos a efectos de duplicados.
- Propio identificador: nunca aparece en `duplicate_of`.
- Múltiples equivalentes abiertos: `duplicate_of` contiene todos ellos, no solo el primero,
  en orden determinista ascendente por identificador.
- Duplicado existente: no impide registrar el nuevo incidente; ambos quedan registrados.
- SLA P2/P3 que abarca fin de semana: los fines de semana y las horas fuera de 08:00–18:00 no
  suman minutos transcurridos.
- Límite exacto de SLA: `is_breached` es verdadero solo cuando el tiempo transcurrido supera
  el permitido; el 75 % exacto activa el escalamiento.
- `reference_time` anterior a `created_at`: se rechaza en ambos canales. Un `reference_time`
  igual a `created_at` produce 0 minutos transcurridos y sin incumplimiento.
- `reference_time` con formato ISO 8601 inválido: se rechaza en ambos canales.
- Cualquier marca `created_at` o `reference_time` aware: se rechaza con HTTP 422 / CLI 1 y solo
  se admiten marcas naive en hora local del servidor (P2 aprobado).
- Sin `reference_time`: se usa el instante de la consulta, por lo que dos consultas en
  instantes distintos pueden dar valores diferentes.
- Regresión: la clasificación de la funcionalidad 001 y el resumen de la 002 conservan sus
  resultados actuales.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE ofrecer el registro de incidentes por HTTP mediante
  `POST /api/v1/incidents` y por terminal mediante el subcomando `create`, invocando en ambos
  canales el mismo caso de uso.
- **FR-002**: El registro DEBE exigir `title` y `raw_text` en ambos canales. DEBE rechazar la
  cadena vacía y la cadena compuesta únicamente por espacios en blanco, sin crear el incidente.
  Los valores no vacíos se conservan tal como llegan.
- **FR-003**: `incident_id` es opcional; si se omite, el sistema DEBE generar un identificador
  con formato `INC-` seguido de 8 caracteres hexadecimales en minúsculas. Si se proporciona,
  DEBE cumplir `INC-[0-9a-f]{8}` y no estar ya registrado; cualquier otro valor se rechaza como
  dato inválido.
- **FR-004**: `created_at` es opcional; si se omite, el sistema DEBE usar el instante de la
  creación.
- **FR-005**: `status` es opcional y DEBE tener `OPEN` como valor predeterminado.
- **FR-006**: El registro DEBE clasificar el incidente reutilizando las reglas de triaje ya
  aprobadas, sin redefinir severidad, componente, equipo recomendado ni clave de duplicado.
- **FR-007**: La creación DEBE responder HTTP 201 en el canal HTTP y emitir JSON en la
  terminal, e incluir la clasificación completa, `is_duplicate` (booleano) y `duplicate_of`
  (lista de identificadores).
- **FR-008**: La detección de duplicados DEBE comparar exclusivamente por
  `duplicate_group_key`, con igualdad exacta de la cadena y sin normalización adicional, porque
  el dominio ya entrega esa clave normalizada.
- **FR-009**: El sistema DEBE considerar como posibles duplicados únicamente los incidentes
  en estados OPEN, IN_PROGRESS y ESCALATION_REQUIRED. Esta ampliación se limita a la búsqueda
  de duplicados y NO modifica la definición de "activos" del resumen de la funcionalidad 002.
- **FR-010**: El sistema DEBE ignorar los incidentes RESOLVED al buscar duplicados.
- **FR-011**: El sistema DEBE excluir el identificador del incidente recién creado de
  `duplicate_of`.
- **FR-012**: La existencia de un duplicado abierto NO DEBE impedir el registro; el nuevo
  incidente DEBE registrarse igualmente.
- **FR-013**: `duplicate_of` DEBE contener todos los identificadores equivalentes abiertos y
  presentarlos en orden determinista.
- **FR-014**: El sistema DEBE exponer la auditoría de SLA por HTTP mediante
  `GET /api/v1/incidents/{incident_id}/sla`, con parámetro opcional `reference_time` en
  formato ISO 8601.
- **FR-015**: El sistema DEBE exponer la misma auditoría por terminal mediante el subcomando
  `sla`, con la opción opcional `--reference-time`.
- **FR-016**: La consulta de SLA DEBE responder HTTP 404 cuando el incidente no exista y HTTP
  422 cuando `reference_time` sea anterior a `created_at` o no sea un ISO 8601 válido. Un
  `reference_time` igual a `created_at` es válido y produce 0 minutos transcurridos.
- **FR-017**: La evaluación de SLA DEBE reutilizar la política vigente y devolver
  `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached` y
  `requires_escalation`.
- **FR-018**: El canal HTTP DEBE responder 201 en una creación válida, 422 ante datos
  inválidos (incluye `title` o `raw_text` vacíos, identificador con formato inválido o duplicado,
  `reference_time` malformado, anterior a `created_at` o aware) y 404 ante un identificador
  inexistente. La terminal DEBE terminar con código 0 en éxito y con código 1 ante cualquiera de
  esos errores, en todos los subcomandos, incluidos `triage` y `summary`; el mensaje de error va
  a la salida de error.
- **FR-019**: Para las mismas entradas y el mismo `reference_time`, el canal HTTP y la
  terminal DEBEN devolver la misma estructura JSON, con idénticos nombres de campos, tipos y
  valores.
- **FR-020**: Esta funcionalidad NO DEBE modificar las reglas de triaje ni de SLA aprobadas,
  ni las funcionalidades 001 y 002 existentes.
- **FR-021**: El formato canónico `INC-[0-9a-f]{8}` se aplica tanto al identificador generado
  como al provisto (FR-003); un valor con otro formato produce HTTP 422 / CLI 1 y conserva la
  decisión P1 aprobada.
- **FR-022**: El sistema DEBE rechazar con HTTP 422 / CLI 1 toda marca `created_at` o
  `reference_time` aware (con desplazamiento horario) y operar únicamente con marcas naive en
  hora local del servidor, de modo que la comparación sea determinista.

### Key Entities *(include if feature involves data)*

- **Incidente registrado**: Reporte almacenado con título, texto original, identificador,
  componente, severidad, equipo recomendado, estado, fecha de creación y clave de duplicado.
- **Clasificación**: Resultado del triaje del incidente; incluye severidad, componente,
  equipo recomendado, justificación y clave de duplicado.
- **Resultado de duplicados**: Indicador de si el nuevo incidente tiene equivalentes abiertos
  y la lista de identificadores de esos incidentes.
- **Evaluación de SLA**: Resultado de auditar un incidente; incluye minutos transcurridos,
  minutos permitidos, minutos restantes, indicador de incumplimiento e indicador de
  escalamiento requerido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las creaciones válidas devuelve confirmación de creación con
  `status` OPEN y la clasificación completa.
- **SC-002**: El 100 % de los incidentes equivalentes abiertos se identifica como duplicado y
  se producen cero falsos positivos con incidentes RESOLVED.
- **SC-003**: Con el mismo `reference_time`, el 100 % de las auditorías devuelve valores
  idénticos.
- **SC-004**: La auditoría del caso de referencia (P2, viernes 17:00 a lunes 09:00) devuelve
  exactamente 120, 480 y 360 minutos, con ambas banderas en falso.
- **SC-005**: El 100 % de las operaciones realizadas por HTTP y por terminal devuelve la
  misma estructura y los mismos valores para las mismas entradas.
- **SC-006**: El 100 % de las entradas inválidas se rechaza sin dejar un incidente creado.
- **SC-007**: El 100 % de las consultas con un identificador inexistente se reporta como no
  encontrado y el 100 % de las consultas con `reference_time` anterior a la creación se
  rechaza.
- **SC-008**: El 100 % de los escenarios de aceptación de esta especificación tiene una prueba
  automatizada correspondiente que pasa.
- **SC-009**: Cero regresiones: el 100 % de las pruebas y resultados deterministas de los
  hitos 001 y 002 sigue pasando.

## Assumptions

- Los usuarios de esta funcionalidad son operadores o ingenieros de guardia con permisos de
  registro y consulta; autenticación y autorización quedan fuera de alcance.
- La adopción del código de salida 1 en todos los subcomandos quedó formalizada mediante la
  enmienda constitucional 2.0.0 de 2026-11-24 y la actualización de los contratos CLI de los
  hitos 001 y 002; no es un prerrequisito pendiente.
- Por "clasificación completa" se entiende el conjunto ya producido por el triaje vigente:
  identificador, severidad, componente, equipo recomendado, justificación y clave de
  duplicado.
- En el canal HTTP, `reference_time` se envía como parámetro de consulta; en la terminal, como
  opción `--reference-time`. Ambos aceptan marcas ISO 8601.
- La ventana horaria y la comparación de fechas usan la hora local del servidor, sin zonas
  horarias, conforme a ADR-002 y `AGENTS.md`; toda marca aware se rechaza y solo se admiten
  marcas naive (P2 aprobado).
- La igualdad de `duplicate_group_key` se evalúa sobre la cadena exacta porque el dominio ya
  produce claves normalizadas; no se aplica otra normalización en esta funcionalidad.
- El `incident_id` provisto debe cumplir `INC-[0-9a-f]{8}` y ser único; otro formato se rechaza
  como dato inválido (P1 aprobado).
- `duplicate_of` se ordena de forma ascendente por identificador y no incluye el identificador
  del incidente recién creado.
- El cambio de estados considerados para duplicados se limita a esa búsqueda; la definición de
  "incidentes activos" del resumen de la funcionalidad 002 no se modifica.
- Se reutiliza la persistencia y la configuración ya existentes; no se introduce otro motor ni
  otra fuente de verdad para los datos.
- La política de SLA, los horarios hábiles y el umbral de escalamiento son los ya aprobados;
  esta funcionalidad solo los consume.
- No se incluyen actualización, cierre ni eliminación de incidentes: el alcance se limita a
  creación y auditoría de SLA.
- La terminal emite una sola estructura JSON, con los mismos nombres de campos y orden que el
  canal HTTP, para conservar la paridad entre canales.
