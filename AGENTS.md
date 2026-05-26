# AGENTS.md

Contexto operativo para agentes/Codex que continúen este proyecto.

## Proyecto

MVP web para gestión de turnos médicos con IA.

El canal principal es una aplicación web con:
- Chatbox escrito (REST).
- Voz en tiempo real: el frontend usa Web Speech API solo para STT del navegador y usa ElevenLabs para TTS via backend. El backend expone WebSocket streaming para la llamada.

## Stack Actualizado

- Python 3.12.
- FastAPI.
- SQLModel/SQLAlchemy.
- PostgreSQL en Docker (Base de negocio + Memoria de IA).
- **LangGraph** (Orquestador de agentes, estado y memoria).
- **LangChain Groq** (Wrapper oficial del LLM).
- Groq (`llama-3.3-70b-versatile`) como proveedor LLM.

## Arquitectura de Carpetas Relevante

```text
app/
  agents/
    graph.py           # Construye el agente ReAct (LangGraph).
    groq_client.py     # Singleton del ChatGroq.
    orchestrator.py    # Orquestador que inyecta estado en el agente.
    prompt.py          # System Prompt del consultorio.
    response_sanitizer.py # Sanitizador defensivo de respuestas del agente.
    tools.py           # Factory de funciones @tool con closures (session/interaction).
  core/
    config.py          # Settings (max_agent_iterations, max_context_messages).
  services/
    tts_service.py     # Proxy async a ElevenLabs TTS.
  api/routes/
    tts.py             # Endpoint POST /api/tts.
    speech.py          # STT backend placeholder + alias legacy /speech/synthesize.
  models/
    interaction.py     # InteractionSession y Logs (Auditoría).
```

## Memoria Dual (Business vs LLM)

El proyecto utiliza un patrón de memoria separada, alojada en la misma base PostgreSQL:

1. **Memoria de Negocio (`interaction_sessions`)**:
   - Manejada por SQLModel.
   - Tiene un `id` numérico.
   - Guarda el estado real: `user_id`, `pending_slot_id`, `current_state`.
   - `user_id` es obligatorio; `Patient` fue eliminado del MVP y `User` representa a la persona que reserva.

2. **Memoria del Agente (`checkpoints`)**:
   - Manejada por `PostgresSaver` de LangGraph (se autoconfigura en el `lifespan` de FastAPI).
   - Guarda el historial de mensajes (`HumanMessage`, `AIMessage`, `ToolMessage`).
   - Se vincula a la sesión de negocio usando `thread_id = str(InteractionSession.id)`.

3. **Historial visible (`conversation_messages`)**:
   - Tabla propia para renderizar el chat en el frontend.
   - Guarda mensajes completos visibles (`user`/`assistant`) por `interaction_session_id`.
   - No reemplaza checkpoints de LangGraph ni `interaction_logs`.

## Tools y Seguridad (Closures)

Las tools están definidas en `app/agents/tools.py` usando una factory `build_tools(session, interaction)`.
- **Por qué**: Para que las funciones `@tool` tengan acceso a la BD y al contexto, pero **sin exponer esos argumentos al LLM**.
- El LLM solo ve argumentos de negocio (`slot_id`, `specialty_name`).
- El acceso a PostgreSQL y la auditoría ocurren dentro de la clausura de la función en Python.

Tools disponibles:
- `list_specialties_and_doctors` (catalogo de especialidades y medicos activos; no busca turnos).
- `search_availability`
- `hold_slot`
- `confirm_appointment` (requiere `explicit_confirmation=True`).

## El Flujo Principal (ReAct vía LangGraph)

1. El usuario envía un mensaje (`POST /api/conversations/{id}/messages`).
2. FastAPI inyecta `session` (BD) y `checkpointer` (Memoria LLM) al `ConversationOrchestrator`.
3. El orquestador carga la sesión de la BD de negocio.
4. Construye el agente llamando a `build_agent_graph()`, inyectando el estado fresco del backend (ej: "el paciente es Juan") en un `SystemMessage` dinámico.
5. Invoca el grafo pasando `thread_id = str(session_id)`.
6. **LangGraph toma el control**:
   - Lee el historial del `checkpointer`.
   - Llama a Groq.
   - Si Groq pide una tool, LangGraph la ejecuta localmente.
   - Guarda la ida y vuelta en su tabla `checkpoints`.
7. El orquestador recibe la respuesta final, la loguea para auditoría en `interaction_logs`, y responde al frontend.

## Mejoras Recientes (Fase 1 Completada)

### Frontend UI Rediseñado
- **Tailwind CSS via CDN**: Se reescribió la interfaz usando Tailwind para lograr un diseño "premium" médico con esquema dark mode (Slate/Cyan).
- **UX Robusta**:
  - Indicador animado de "escribiendo..." (typing indicator).
  - Bloqueo de input (`isLoading`) mientras el agente procesa para evitar double-sends.
  - Spinner SVG en el botón de envío y barra de estado con colores por variante.
  - Fallbacks `null-safe` (`?.`) en el JS y **Cache-busting** (`?v=3`) en `index.html` para evitar desajustes (`TypeError: Cannot set properties of null`) cuando el navegador cachea archivos estáticos antiguos.

### Búsqueda de Especialidades (Accent-Insensitive)
- **Problema**: El LLM escribe especialidades correctamente en español (ej. "cardiología") pero en la BD pueden estar sin tildes ("cardiologia"), causando fallos en los `ILIKE` convencionales.
- **Solución Dual**:
  1. **Python**: Se usa `unicodedata.normalize("NFD", ...)` en `appointment_service.py` para remover tildes del input del agente.
  2. **Base de Datos**: Se implementó una migración de Alembic (`0002_unaccent`) que habilita la extensión nativa `unaccent` de Postgres. En SQLAlchemy se wrappea la columna con `func.unaccent(Specialty.name)`, logrando una búsqueda completamente tolerante a acentos.

### Gestión de Contexto y Token Budget (Fase 1.5)
- **Problema**: El `PostgresSaver` de LangGraph acumula el historial infinitamente. En conversaciones muy largas, enviar todo el historial a Groq termina agotando la "ventana de contexto" del modelo o desperdiciando dinero en tokens.
- **Solución**: Se implementó una función `prompt_with_trimming` en `graph.py`. Se usa el utility `trim_messages` de LangChain para truncar el historial y conservar únicamente los últimos N mensajes (configurable en `settings.max_context_messages`). El truncado es inteligente: conserva el SystemMessage inyectado y no rompe los pares de ToolCall/ToolMessage.

### Canal de Voz en Tiempo Real (Fase 2 Completada)
- **Arquitectura Backend**: WebSocket (`/api/ws/conversations/{id}`) + `graph.astream_events(version="v2")`.
- **Async Checkpointer**: Para que `astream_events` no levante `NotImplementedError`, LangGraph requiere memoria asíncrona. Se migró de `PostgresSaver` síncrono a `AsyncPostgresSaver` inyectado en el lifespan de FastAPI. Esto también obligó a volver asíncronos los endpoints REST (`await graph.ainvoke`).
- **Patrón clave**: `stream_message()` en `orchestrator.py` es un **async generator** que emite dicts de eventos. El WS handler solo itera sobre él y reenvía cada evento al browser.
- **Protocolo de eventos** (servidor → cliente):
  - `{type: "token", text}` — fragmento del LLM (texto de respuesta)
  - `{type: "tool_start", name}` — herramienta iniciada
  - `{type: "tool_end", name}` — herramienta terminada
  - `{type: "done", state, full_text}` — respuesta completa
  - `{type: "error", message}` — error
- **Frontend `VoiceCall` (Push-To-Talk)**:
  - **STT Manual**: Para evitar problemas con ruido de fondo y loops de eco, se implementó un botón "Hablar" (Push-To-Talk). El STT se pausa cuando el bot habla.
  - **Sentence-level TTS chunking**: los tokens se acumulan en un buffer y se hablan al completar una oración (`.!?`), logrando voz natural.
  - **ElevenLabs TTS**: Se reemplazo `window.speechSynthesis` por audio MPEG generado en backend con ElevenLabs. El frontend pide audio a `POST /api/tts`, crea Blob URLs y reproduce con `new Audio()` en cola.
  - **Compatibilidad Legacy**: `POST /api/speech/synthesize` sigue existiendo como alias para no romper clientes viejos, pero el frontend nuevo usa `/api/tts`.
  - **Config requerida**: `ELEVENLABS_API_KEY` debe vivir en `.env`, nunca hardcodeada en `config.py`. `ELEVENLABS_VOICE_ID` default validado: `EXAVITQu4vr4xnSDxMaL` (Rachel).
  - **Turn-taking de llamada**: El botón "Hablar" no queda bloqueado durante escucha; en estado listening muestra "Detener" y permite cancelar sin colgar la llamada. `SpeechRecognition` en llamada usa `interimResults=false` porque fue el modo más estable en Chrome para este proyecto.
  - **Limitación conocida**: La calidad de lo que dice el agente al hablar aún puede necesitar ajuste fino de prompt/respuesta para sonar más natural en voz.
  - **Alucinación de JSON**: Se agregó una restricción dura en el `SYSTEM_PROMPT` para evitar que LLMs veloces como Llama 3 70B intenten escupir argumentos JSON directamente al usuario en vez de usar la API de herramientas.

### Calidad de Respuestas del Agente (Fase 2.5 Completada)
- **Tool de catálogo**: `list_specialties_and_doctors` responde preguntas como "que medicos tenes" o "que especialidades hay" consultando `specialties` y `doctors` activos. No reemplaza `search_availability`; solo lista catálogo.
- **Prompt reforzado**: `SYSTEM_PROMPT` prohíbe mostrar JSON, nombres de tools, argumentos internos o bloques tipo `<function=...>`. Para síntomas no urgentes, el agente no debe listar causas ni sugerir tratamientos; debe aclarar límites y ofrecer sacar turno.
- **Sanitización defensiva**: `app/agents/response_sanitizer.py` remueve pseudo tool calls (`<function=...>{...}</function>`) y JSON residual antes de responder/loguear.
- **REST + Streaming**: `ConversationOrchestrator` sanitiza respuestas REST antes de `message_sent` y filtra tokens del WebSocket con `StreamingFunctionCallSanitizer` para evitar fugas en vivo.
- **Auditoría**: si se modifica una respuesta, se registra `response_sanitized` en `interaction_logs` antes del `message_sent` limpio.
- **Tests**: `tests/test_response_sanitizer.py` cubre sanitización normal/multilinea/streaming. `tests/test_conversation.py` cubre la tool de catálogo y que `_finish_turn` loguee la respuesta limpia.

### Auth JWT y Usuario como Persona de Turno (Fase 3 Completada)
- **Modelo de identidad**: `User` reemplaza a `Patient`. El registro pide `full_name`, `email`, `document_number`, `phone` y password. Login por email/password.
- **Migración destructiva MVP**: `0003_users_auth_clean_mvp` limpia conversaciones, logs, checkpoints, appointments y patients; crea `users`; cambia `interaction_sessions.user_id` y `appointments.user_id` a obligatorios.
- **Auth modular**: `app/core/security.py`, `app/api/deps.py`, `app/services/auth_service.py`, `app/api/routes/auth.py`.
- **Endpoints auth**: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`.
- **Conversaciones por usuario**: `POST/GET/DELETE /api/conversations` requieren JWT y filtran por owner. `POST /api/conversations/{id}/messages` valida ownership.
- **WebSocket con auth**: `/api/ws/conversations/{id}` exige primer mensaje `{type: "auth", token}` antes de aceptar `user_message`.
- **Agente sin paciente**: se removió `identify_or_create_patient`. El prompt no debe pedir nombre/DNI/teléfono para reservar; esos datos se inyectan desde `User`.
- **Frontend actual**: login/register/logout mínimo en `app/static`, token en `localStorage`, REST con Bearer token y WS con mensaje auth inicial.

### Sidebar e Historial de Conversaciones (Fase 3.5 Completada)
- **Panel lateral tipo ChatGPT**: el frontend muestra hasta 2 conversaciones recientes del usuario y permite cargar sus mensajes visibles.
- **Retención backend**: `settings.max_conversations_per_user = 2`. Al crear una sesión nueva, `ConversationRetentionService` elimina físicamente las conversaciones excedentes del mismo usuario.
- **Historial visible**: `conversation_messages` es la fuente para renderizar chats. `interaction_logs` sigue siendo auditoría y puede estar truncado.
- **Limpieza de memoria LangGraph**: `ConversationCheckpointService` borra checkpoints por `thread_id = str(interaction_session.id)` usando API pública si existe, o fallback SQL por `thread_id` en tablas `checkpoint_writes`, `checkpoint_blobs`, `checkpoints`.
- **Appointments desacoplados de sesión**: `Appointment` queda asociado a `user_id`, `doctor_id` y `slot_id`. La sesión de chat solo se usa para holds temporales y contexto del agente, no como parte del dominio del turno confirmado.
- **Frontend actual**: “Nueva consulta” limpia la UI local y no crea sesión hasta que el usuario escribe o inicia llamada. Al crearse una nueva sesión, el sidebar se refresca y la más vieja se elimina por backend.

### Emails Transaccionales con Resend (Fase 3.6 Completada)
- **Proveedor**: Resend, configurado con `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_ENABLED` y `EMAIL_PROVIDER=resend`.
- **Outbox transaccional**: `email_outbox` guarda emails pendientes, enviados o fallidos. El turno se confirma aunque el proveedor de email falle.
- **Confirmación de turno**: `AppointmentService.confirm_appointment()` crea el `Appointment` y encola un email de confirmación para `User.email` con profesional, especialidad, fecha/hora y código.
- **Despacho post-commit**: `ConversationOrchestrator` llama `EmailOutboxService.dispatch_pending()` después del commit del turno/respuesta. Nunca enviar email antes de confirmar la transacción.
- **Privacidad**: los emails de turno no deben incluir síntomas, diagnóstico ni contenido de conversación.

## Siguientes Pasos (Roadmap)

### Fase 4 - Roles/Admin y Frontend Next.js
- Proteger endpoints administrativos (`/appointment-slots`, `/appointments`) con roles.
- Migrar frontend a Next.js + shadcn cuando el flujo de auth/conversaciones esté estabilizado.
- Evaluar cookies HttpOnly/Secure y refresh tokens para producción.

## Convenciones Para Agentes
- Nunca mezclar llamadas directas a Groq SDK con LangChain. Usar siempre `ChatGroq`.
- Toda nueva tool debe agregarse en `build_tools()` y ser una función decorada con `@tool`.
- Nunca pasar la `Session` de SQLModel como parámetro visible para el LLM.
- Evitar modificar la tabla `checkpoints` a mano; usar los métodos del `PostgresSaver`.
- Nunca devolver al usuario ni guardar como `message_sent` sintaxis interna de tools. Si se toca el flujo del agente, preservar `response_sanitizer.py` en REST y streaming.
- No reintroducir `Patient` en este MVP. Turnos, conversaciones y agente deben usar `User`.
- No usar checkpoints de LangGraph ni `interaction_logs` para renderizar el historial visible. Usar `conversation_messages`.
- No volver a asociar `Appointment` a `interaction_session_id`; los turnos confirmados pertenecen al `User`.
- Nunca enviar emails directamente desde tools o antes del commit. Usar `email_outbox` y despachar post-commit.

### Fase 4 (Completada) - Refinamiento de Voz y UI
- **Codificación en Frontend (Mojibake):** Se resolvieron problemas de doble codificación UTF-8 en `app.js` mediante limpieza manual y versionado forzado en `index.html` (`?v=X`) para evitar problemas de caché del navegador.
- **Doble Capa para Listas en Voz:** Para evitar que el agente dicte en audio listas largas (como turnos u horarios disponibles):
  1. **Prompt preventivo:** El LLM siempre antepone un resumen verbal de máximo 2 oraciones antes de enlistar.
  2. **Barrera de backend (`tts_text`):** Durante el modo llamada, el websocket solo envía al frontend el texto resumido (`extract_spoken_text` en `tts_service.py`), filtrando el contenido estructurado (listas, markdown).
  - El resultado es que **el chat muestra el texto completo**, pero **el TTS solo reproduce la introducción conversacional**.

### Fase 4.5 (Completada) - Rate Limiting y UX del Historial
- **Borrado manual de conversaciones**: Se agregó un ícono de eliminar en cada ítem del historial del sidebar del frontend (`app.js`). Esto invoca el endpoint `DELETE /api/conversations/{id}` (protegido por JWT) y limpia la UI localmente.
- **Control de Costos (Rate Limiting)**: Para proteger la facturación de la API del LLM (Groq) y TTS (ElevenLabs) frente a abusos o bots:
  - Se agregó **Redis** (`redis:7-alpine`) al `docker-compose.yml` para gestionar en memoria los contadores.
  - **REST API**: Se integró `fastapi-limiter`. Se aplicó `@RateLimiter` como dependencia:
    - `POST /api/conversations/{id}/messages`: Límite de 10 requests por minuto.
    - `POST /api/tts`: Límite de 20 requests por minuto.
  - **WebSocket**: Como el limiter HTTP no se aplica a conexiones persistentes, se implementó un limitador in-memory (`message_count`) dentro del loop del `conversation_ws` que cierra el socket (código `1008`) si el usuario supera los 100 mensajes por sesión.

### Fase 5 (Completada) - Portal Médico, Zona Horaria y Mejoras del Agente

#### Portal del Médico (`/api/doctor/`)
- Los usuarios con `role=doctor` ven una interfaz diferente al hacer login: panel con dos secciones separadas:
  1. **Turnos con pacientes** (`appointments`): tabla interactiva con turnos `confirmed`, `cancelled` y `finished`. El doctor puede cambiar el estado de cada turno. Un turno `confirmed` cuya fecha ya pasó se presenta como `finished` en runtime (sin modificar la BD).
  2. **Horarios disponibles** (`appointment_slots`): tabla con slots `available`. El doctor puede agregar, editar fecha/hora y eliminar slots.
- Un slot que tiene un `Appointment` asociado (status=`booked`) **no aparece** en la tabla de horarios disponibles — figura en turnos con paciente.
- Endpoints relevantes:
  - `GET /api/doctor/appointments` — turnos del doctor autenticado.
  - `PATCH /api/doctor/appointments/{id}/status` — actualiza estado (`confirmed`/`cancelled`/`finished`).
  - `GET /api/doctor/slots` — slots disponibles del doctor autenticado.
  - `POST /api/doctor/slots` — crea un nuevo slot.
  - `PUT /api/doctor/slots/{id}` — edita fecha/hora de un slot existente.
  - `DELETE /api/doctor/slots/{id}` — elimina un slot (solo si no tiene turno asociado).

#### Zona Horaria (UTC-3 / Argentina)
- **Problema raíz**: La BD almacena `TIMESTAMP WITHOUT TIME ZONE`. El backend corre en UTC (Docker). El frontend envía fechas locales. Sin corrección, un slot creado a las 14:00 hora local se guardaba como 17:00 UTC.
- **Solución adoptada (naive local)**: Todo el stack maneja datetimes "naive" en hora local Argentina (UTC-3).
  - El frontend envía la cadena `datetime-local` directamente (ej. `"2026-06-10T14:00"`) **sin** convertir a ISO UTC (`.toISOString()` fue removido del submit).
  - El backend, al comparar "ahora" contra slots pasados, usa `datetime.now(UTC) - timedelta(hours=3)` en lugar de `datetime.now(UTC)` a secas. Afecta: `appointment_service.py`, `doctor.py` (status `finished`), `seed.py`.
  - `parseApiDate()` en `app.js` parsea los datetimes devueltos por la API como hora local (sin forzar `Z`) para que la visualización sea consistente.
- **Limitación conocida**: el offset `-3` está hardcodeado. Si el servidor se despliega en otra zona horaria o se necesita DST, se debe migrar a una solución con `pytz`/`zoneinfo` y timestamps WITH TIME ZONE en Postgres.

#### Búsqueda de Disponibilidad con Filtro de Fecha
- `search_availability` tool ahora acepta `date_from: str | None` y `date_to: str | None` (formato `YYYY-MM-DD`).
- Para buscar un día exacto: `date_from=date_to="2026-06-09"`.
- El LLM está instruido en `prompt.py` a usar estos parámetros cuando el usuario pide turnos para una fecha específica. **Nunca debe decir "no puedo buscar por fecha"**.
- Límite por defecto subido de 5 a 20 (máximo 50). El LLM muestra todos los slots devueltos agrupados por día.
- Los parámetros se parsean a `date` en Python dentro de la tool antes de pasarlos al servicio.

#### Seed Idempotente
- `app/seed.py` ya **no borra ni recrea datos** si la BD tiene usuarios.
- El `docker-compose.yml` corre `python -m app.seed` en cada arranque, pero la función `is_already_seeded()` lo cortocircuita si ya hay datos — los checkpoints de LangGraph, conversaciones e historial sobreviven entre reinicios.
- Para **forzar un reset completo** (borrar todo y sembrar desde cero):
  ```bash
  docker compose exec api env PYTHONPATH=/app python /app/app/seed.py --force
  ```

#### Usuarios del Sistema (seed)
| Rol | Email | Contraseña |
|-----|-------|-----------|
| Admin | `admin@consultorio.com` | `admin1234` |
| Paciente | `paciente@consultorio.com` | `paciente1234` |
| Médico | `ana@consultorio.com` | `doctor1234` |
| Médico | `juan@consultorio.com` | `doctor1234` |
| Médico | `laura@consultorio.com` | `doctor1234` |
| Médico | `maria@consultorio.com` | `doctor1234` |

- `ana` → Dra. Ana Pérez (cardiología, MN1001)
- `juan` → Dr. Juan Gómez (clínica, MN1002)
- `laura` → Dra. Laura Díaz (dermatología, MN1003)
- `maria` → Dra. María Torres (pediatría, MN1004)

#### Convenciones Adicionales Para Agentes
- No usar `.toISOString()` al enviar fechas de slots desde el frontend: enviar la cadena `datetime-local` (`YYYY-MM-DDTHH:mm`) directamente.
- No comparar datetimes contra `datetime.now(UTC)` sin el ajuste `-timedelta(hours=3)` en servicios que involucren slots o appointments.
- No ejecutar `seed.run()` directamente sin verificar `is_already_seeded()` — hacerlo desde CLI con `--force` si se necesita reset.
- El frontend diferencia el rol del usuario post-login: `role === "doctor"` → vista portal médico; cualquier otro rol → vista chatbot.
