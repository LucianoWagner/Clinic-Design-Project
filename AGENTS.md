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
   - Guarda el estado real: `patient_id`, `pending_slot_id`, `current_state`.

2. **Memoria del Agente (`checkpoints`)**:
   - Manejada por `PostgresSaver` de LangGraph (se autoconfigura en el `lifespan` de FastAPI).
   - Guarda el historial de mensajes (`HumanMessage`, `AIMessage`, `ToolMessage`).
   - Se vincula a la sesión de negocio usando `thread_id = str(InteractionSession.id)`.

## Tools y Seguridad (Closures)

Las tools están definidas en `app/agents/tools.py` usando una factory `build_tools(session, interaction)`.
- **Por qué**: Para que las funciones `@tool` tengan acceso a la BD y al contexto, pero **sin exponer esos argumentos al LLM**.
- El LLM solo ve argumentos de negocio (`slot_id`, `specialty_name`).
- El acceso a PostgreSQL y la auditoría ocurren dentro de la clausura de la función en Python.

Tools disponibles:
- `identify_or_create_patient`
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
## Siguientes Pasos (Roadmap)

### Fase 3 - Login y Multi-paciente
- Sistema de autenticación (JWT).
- Endpoint `GET /api/conversations` para listar historial de chats por usuario.
- Endpoint `DELETE /api/conversations/{id}` para borrar conversaciones.

## Convenciones Para Agentes
- Nunca mezclar llamadas directas a Groq SDK con LangChain. Usar siempre `ChatGroq`.
- Toda nueva tool debe agregarse en `build_tools()` y ser una función decorada con `@tool`.
- Nunca pasar la `Session` de SQLModel como parámetro visible para el LLM.
- Evitar modificar la tabla `checkpoints` a mano; usar los métodos del `PostgresSaver`.
