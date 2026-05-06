"""
Orquestador de conversaciones médicas.

Flujo por request:
  1. Carga/valida InteractionSession de la DB.
  2. Detecta emergencias antes de invocar el LLM.
  3. Construye tools con closures (session + interaction).
  4. Compila el agente ReAct con build_agent_graph().
  5. Invoca el grafo con thread_id = str(interaction.id) para checkpointing.
  6. Loguea y devuelve la respuesta.

El historial de la conversación es gestionado por LangGraph (PostgresSaver/MemorySaver).
AuditService se mantiene para logs de negocio y auditoría (no para historial del LLM).
"""
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage
from sqlmodel import Session

from app.agents.graph import build_agent_graph
from app.agents.response_sanitizer import StreamingFunctionCallSanitizer, sanitize_agent_response
from app.agents.tools import build_tools
from app.core.config import settings
from app.models.enums import Channel, InteractionStatus
from app.models.interaction import InteractionSession
from app.models.user import User
from app.schemas.conversation import AgentAction, MessageRead
from app.services.appointment_service import AppointmentValidationError
from app.services.audit_service import AuditService


EMERGENCY_TERMS = ("infarto", "no puedo respirar", "convuls", "desmayo", "hemorragia")


class ConversationOrchestrator:
    def __init__(self, session: Session, checkpointer, current_user: User | None = None) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.current_user = current_user
        self.audit = AuditService(session)

    # ------------------------------------------------------------------
    # Gestión de sesión
    # ------------------------------------------------------------------

    def create_session(self, channel: Channel | str, user_id: int | None = None) -> InteractionSession:
        resolved_user_id = user_id or self.current_user_id
        channel_value = channel.value if isinstance(channel, Channel) else channel
        interaction = InteractionSession(
            user_id=resolved_user_id,
            channel=channel_value,
            status=InteractionStatus.in_progress.value,
            current_state="intent_detection",
        )
        self.session.add(interaction)
        self.session.commit()
        self.session.refresh(interaction)
        self.audit.log(interaction.id or 0, "session_created", "backend", f"channel={channel_value}")
        self.session.commit()
        return interaction

    # ------------------------------------------------------------------
    # Manejo de mensajes
    # ------------------------------------------------------------------

    async def handle_message(
        self, interaction_id: int, message: str, input_mode: str = "text"
    ) -> MessageRead:
        interaction = self.session.get(InteractionSession, interaction_id)
        if not interaction:
            raise AppointmentValidationError("La conversacion no existe.")

        if input_mode == "voice":
            interaction.channel = Channel.web_voice.value
        interaction.status = InteractionStatus.in_progress.value
        self.audit.log(interaction.id or 0, "message_received", "user", message[:500])

        # Detección de emergencias: se responde antes de invocar el LLM
        if self._is_emergency(message):
            interaction.current_state = "emergency_redirect"
            return self._finish_turn(
                interaction,
                "Por lo que describís, podría tratarse de una urgencia. "
                "Contactá emergencias o acercate a una guardia. No puedo dar diagnóstico médico.",
            )

        if not settings.groq_api_key:
            return self._finish_turn(
                interaction,
                "Para interpretar pedidos en lenguaje natural necesito Groq habilitado. "
                "Configurá GROQ_API_KEY en .env.",
            )

        return await self._handle_with_langgraph(interaction, message)

    async def _handle_with_langgraph(self, interaction: InteractionSession, message: str) -> MessageRead:
        # Tools con closures sobre la sesión DB y la interacción actuales
        user = self._get_interaction_user(interaction)
        tools = build_tools(self.session, interaction)

        # El grafo se compila por request (microsegundos); el checkpointer es compartido
        graph = build_agent_graph(tools, self.checkpointer, interaction, user)

        # thread_id identifica la conversación en el checkpoint de LangGraph
        config = {
            "configurable": {"thread_id": str(interaction.id)},
            "recursion_limit": settings.max_agent_iterations * 2 + 1,
        }

        try:
            state = await graph.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
            # El último mensaje del estado es siempre la respuesta final del asistente
            last_message = state["messages"][-1]
            response = last_message.content or "No pude completar la respuesta."
        except Exception as exc:  # noqa: BLE001
            self.audit.log(interaction.id or 0, "agent_error", "backend", str(exc)[:500])
            response = "Hubo un error procesando tu mensaje. Por favor intentá de nuevo."

        return self._finish_turn(interaction, response)

    async def stream_message(
        self,
        conversation_id: int,
        message: str,
        input_mode: str = "voice",
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator que emite eventos del agente para streaming vía WebSocket.

        Protocol de eventos emitidos:
          {type: "token",      text: str}           ← fragmento de texto del LLM
          {type: "tool_start", name: str}           ← herramienta iniciada
          {type: "tool_end",   name: str}           ← herramienta terminada
          {type: "done",       state: str, full_text: str}
          {type: "error",      message: str}

        El WS handler solo necesita: async for event in orchestrator.stream_message(...)
        """
        interaction = self.session.get(InteractionSession, conversation_id)
        if not interaction:
            yield {"type": "error", "message": "Conversación no encontrada."}
            return

        if input_mode == "voice":
            interaction.channel = Channel.web_voice.value
        interaction.status = InteractionStatus.in_progress.value
        self.audit.log(interaction.id or 0, "message_received", "user", message[:500])

        # Emergencias: emitir y salir sin invocar el LLM
        if self._is_emergency(message):
            interaction.current_state = "emergency_redirect"
            text = (
                "Por lo que describís, podría tratarse de una urgencia. "
                "Contactá emergencias o acercate a una guardia."
            )
            self._do_finish_turn(interaction, text)
            yield {"type": "token", "text": text}
            yield {"type": "done", "state": interaction.current_state, "full_text": text}
            return

        if not settings.groq_api_key:
            text = "Groq API key no configurada. Revisá el .env."
            self._do_finish_turn(interaction, text)
            yield {"type": "token", "text": text}
            yield {"type": "done", "state": interaction.current_state, "full_text": text}
            return

        user = self._get_interaction_user(interaction)
        tools = build_tools(self.session, interaction)
        graph = build_agent_graph(tools, self.checkpointer, interaction, user)
        config = {
            "configurable": {"thread_id": str(interaction.id)},
            "recursion_limit": settings.max_agent_iterations * 2 + 1,
        }

        full_response = ""
        stream_sanitizer = StreamingFunctionCallSanitizer()
        try:
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    # content es texto de respuesta final; tool_call_chunks tienen content=""
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        full_response += chunk
                        safe_chunk = stream_sanitizer.push(chunk)
                        if safe_chunk:
                            yield {"type": "token", "text": safe_chunk}
                elif kind == "on_tool_start":
                    yield {"type": "tool_start", "name": event.get("name", "tool")}
                elif kind == "on_tool_end":
                    yield {"type": "tool_end", "name": event.get("name", "tool")}
            safe_tail = stream_sanitizer.flush()
            if safe_tail:
                yield {"type": "token", "text": safe_tail}

        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            self.audit.log(interaction.id or 0, "agent_error", "backend", repr(exc)[:500])
            error_text = "Hubo un error procesando tu mensaje. Intentá de nuevo."
            full_response = full_response or error_text
            yield {"type": "error", "message": error_text}

        final_response = self._do_finish_turn(interaction, full_response or "Sin respuesta.")
        yield {"type": "done", "state": interaction.current_state, "full_text": final_response}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _finish_turn(
        self,
        interaction: InteractionSession,
        response: str,
        actions: list[AgentAction] | None = None,
    ) -> MessageRead:
        response = self._sanitize_response(interaction, response)
        interaction.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(interaction)
        self.audit.log(interaction.id or 0, "message_sent", "assistant", response[:500])
        self.session.commit()
        return MessageRead(
            conversation_id=interaction.id or 0,
            response=response,
            state=interaction.current_state,
            actions=actions or [],
        )

    def _do_finish_turn(self, interaction: InteractionSession, response: str) -> str:
        """Versión void de _finish_turn para el modo streaming (no construye MessageRead)."""
        response = self._sanitize_response(interaction, response)
        interaction.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(interaction)
        self.audit.log(interaction.id or 0, "message_sent", "assistant", response[:500])
        self.session.commit()
        return response

    def _sanitize_response(self, interaction: InteractionSession, response: str) -> str:
        sanitized = sanitize_agent_response(response)
        if sanitized.was_sanitized:
            self.audit.log(
                interaction.id or 0,
                "response_sanitized",
                "backend",
                "Se removio sintaxis interna de tool calling de la respuesta del agente.",
            )
        return (
            sanitized.text
            or "Puedo ayudarte a buscar especialidades, médicos o turnos disponibles."
        )

    @property
    def current_user_id(self) -> int:
        if not self.current_user or not self.current_user.id:
            raise AppointmentValidationError("Falta usuario autenticado.")
        return self.current_user.id

    def _get_interaction_user(self, interaction: InteractionSession) -> User:
        if self.current_user and self.current_user.id == interaction.user_id:
            return self.current_user
        user = self.session.get(User, interaction.user_id)
        if not user:
            raise AppointmentValidationError("La conversación no tiene usuario válido.")
        return user

    @staticmethod
    def _is_emergency(message: str) -> bool:
        lowered = message.lower()
        return any(term in lowered for term in EMERGENCY_TERMS)
