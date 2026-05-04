# AGENTS.md

Contexto operativo para agentes/Codex que continúen este proyecto.

## Proyecto

MVP web para gestión de turnos médicos con IA.

El canal principal es una aplicación web con:
- Chatbox escrito (REST).
- Preparado para Voz: El frontend usa Web Speech API (STT/TTS del navegador) y el backend tiene un WebSocket configurado y listo para ser adaptado a streaming (Fase 2 pendiente).

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

## Siguientes Pasos (Roadmap)

### Fase 2 - Canal de Voz "Llamada" (Streaming)
- El endpoint WebSocket (`/ws/conversations/{conversation_id}`) ya existe pero procesa mensajes bloqueantes.
- Tarea: Modificar el frontend para enviar fragmentos de audio o texto en tiempo real (`continuous=true`).
- Tarea: Modificar el backend para usar `graph.astream()` (o `astream_events`) y devolver fragmentos del LLM a medida que se generan, permitiendo que el TTS del navegador hable más rápido.

## Convenciones Para Agentes
- Nunca mezclar llamadas directas a Groq SDK con LangChain. Usar siempre `ChatGroq`.
- Toda nueva tool debe agregarse en `build_tools()` y ser una función decorada con `@tool`.
- Nunca pasar la `Session` de SQLModel como parámetro visible para el LLM.
- Evitar modificar la tabla `checkpoints` a mano; usar los métodos del `PostgresSaver`.
