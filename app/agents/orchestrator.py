"""
Orquestador de conversaciones medicas.

El historial visible del frontend vive en conversation_messages. El contexto del
agente sigue en LangGraph, vinculado por thread_id = str(interaction.id).
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
from app.services.conversation_history_service import ConversationHistoryService
from app.services.email_outbox_service import EmailOutboxService
from app.services.tts_service import extract_spoken_text


EMERGENCY_TERMS = ("infarto", "no puedo respirar", "convuls", "desmayo", "hemorragia")


class ConversationOrchestrator:
    def __init__(self, session: Session, checkpointer, current_user: User | None = None) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.current_user = current_user
        self.audit = AuditService(session)
        self.history = ConversationHistoryService(session)
        self.email_outbox = EmailOutboxService(session)

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

    async def handle_message(
        self, interaction_id: int, message: str, input_mode: str = "text"
    ) -> MessageRead:
        interaction = self.session.get(InteractionSession, interaction_id)
        if not interaction:
            raise AppointmentValidationError("La conversacion no existe.")

        self._start_turn(interaction, message, input_mode)

        if self._is_emergency(message):
            interaction.current_state = "emergency_redirect"
            return self._finish_turn(
                interaction,
                "Por lo que describis, podria tratarse de una urgencia. "
                "Contacta emergencias o acercate a una guardia. No puedo dar diagnostico medico.",
                input_mode=input_mode,
            )

        if not settings.groq_api_key:
            return self._finish_turn(
                interaction,
                "Para interpretar pedidos en lenguaje natural necesito Groq habilitado. "
                "Configura GROQ_API_KEY en .env.",
                input_mode=input_mode,
            )

        return await self._handle_with_langgraph(interaction, message, input_mode)

    async def _handle_with_langgraph(
        self, interaction: InteractionSession, message: str, input_mode: str = "text"
    ) -> MessageRead:
        user = self._get_interaction_user(interaction)
        tools = build_tools(self.session, interaction)
        graph = build_agent_graph(tools, self.checkpointer, interaction, user)
        config = {
            "configurable": {"thread_id": str(interaction.id)},
            "recursion_limit": settings.max_agent_iterations * 2 + 1,
        }

        try:
            state = await graph.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config=config,
            )
            last_message = state["messages"][-1]
            response = last_message.content or "No pude completar la respuesta."
        except Exception as exc:  # noqa: BLE001
            self.audit.log(interaction.id or 0, "agent_error", "backend", str(exc)[:500])
            response = "Hubo un error procesando tu mensaje. Por favor intenta de nuevo."

        return self._finish_turn(interaction, response, input_mode=input_mode)

    async def stream_message(
        self,
        conversation_id: int,
        message: str,
        input_mode: str = "voice",
    ) -> AsyncGenerator[dict, None]:
        interaction = self.session.get(InteractionSession, conversation_id)
        if not interaction:
            yield {"type": "error", "message": "Conversacion no encontrada."}
            return

        self._start_turn(interaction, message, input_mode)

        if self._is_emergency(message):
            interaction.current_state = "emergency_redirect"
            text = (
                "Por lo que describis, podria tratarse de una urgencia. "
                "Contacta emergencias o acercate a una guardia."
            )
            final_text = self._do_finish_turn(interaction, text, input_mode=input_mode)
            yield {"type": "token", "text": final_text}
            yield {"type": "done", "state": interaction.current_state, "full_text": final_text}
            return

        if not settings.groq_api_key:
            text = "Groq API key no configurada. Revisa el .env."
            final_text = self._do_finish_turn(interaction, text, input_mode=input_mode)
            yield {"type": "token", "text": final_text}
            yield {"type": "done", "state": interaction.current_state, "full_text": final_text}
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
            self.audit.log(interaction.id or 0, "agent_error", "backend", repr(exc)[:500])
            error_text = "Hubo un error procesando tu mensaje. Intenta de nuevo."
            full_response = full_response or error_text
            yield {"type": "error", "message": error_text}

        final_response = self._do_finish_turn(
            interaction, full_response or "Sin respuesta.", input_mode=input_mode
        )
        # Emitir el texto resumido solo para síntesis de voz.
        # La detección de listas/datos estructurados ocurre aquí sobre el texto completo,
        # no sobre tokens individuales (más fiable que hacer regex sobre streaming).
        spoken_text = extract_spoken_text(final_response)
        if spoken_text:
            yield {"type": "tts_text", "text": spoken_text}
        yield {"type": "done", "state": interaction.current_state, "full_text": final_response}

    def _start_turn(self, interaction: InteractionSession, message: str, input_mode: str) -> None:
        if input_mode == "voice":
            interaction.channel = Channel.web_voice.value
        interaction.status = InteractionStatus.in_progress.value
        self.audit.log(interaction.id or 0, "message_received", "user", message[:500])
        self.history.add_message(interaction.id or 0, "user", message, input_mode)

    def _finish_turn(
        self,
        interaction: InteractionSession,
        response: str,
        actions: list[AgentAction] | None = None,
        input_mode: str = "text",
    ) -> MessageRead:
        response = self._sanitize_response(interaction, response)
        self._persist_assistant_turn(interaction, response, input_mode)
        self.session.commit()
        self._dispatch_email_outbox(interaction)
        return MessageRead(
            conversation_id=interaction.id or 0,
            response=response,
            state=interaction.current_state,
            actions=actions or [],
        )

    def _do_finish_turn(
        self, interaction: InteractionSession, response: str, input_mode: str = "voice"
    ) -> str:
        response = self._sanitize_response(interaction, response)
        self._persist_assistant_turn(interaction, response, input_mode)
        self.session.commit()
        self._dispatch_email_outbox(interaction)
        return response

    def _persist_assistant_turn(
        self, interaction: InteractionSession, response: str, input_mode: str
    ) -> None:
        interaction.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(interaction)
        self.audit.log(interaction.id or 0, "message_sent", "assistant", response[:500])
        self.history.add_message(interaction.id or 0, "assistant", response, input_mode)

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
            or "Puedo ayudarte a buscar especialidades, medicos o turnos disponibles."
        )

    def _dispatch_email_outbox(self, interaction: InteractionSession) -> None:
        try:
            dispatched = self.email_outbox.dispatch_pending()
        except Exception as exc:  # noqa: BLE001
            self.audit.log(
                interaction.id or 0,
                "appointment_email_dispatch_error",
                "backend",
                str(exc)[:500],
            )
            self.session.commit()
            return

        for email in dispatched:
            event_type = (
                "appointment_email_sent"
                if email.status == "sent"
                else "appointment_email_failed"
            )
            self.audit.log(
                interaction.id or 0,
                event_type,
                "backend",
                f"appointment_id={email.appointment_id}, email_outbox_id={email.id}",
            )
        if dispatched:
            self.session.commit()

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
            raise AppointmentValidationError("La conversacion no tiene usuario valido.")
        return user

    @staticmethod
    def _is_emergency(message: str) -> bool:
        lowered = message.lower()
        return any(term in lowered for term in EMERGENCY_TERMS)
