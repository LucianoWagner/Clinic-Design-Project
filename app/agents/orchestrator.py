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
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage
from sqlmodel import Session

from app.agents.graph import build_agent_graph
from app.agents.tools import build_tools
from app.core.config import settings
from app.models.enums import Channel, InteractionStatus
from app.models.interaction import InteractionSession
from app.schemas.conversation import AgentAction, MessageRead
from app.services.appointment_service import AppointmentValidationError
from app.services.audit_service import AuditService


EMERGENCY_TERMS = ("infarto", "no puedo respirar", "convuls", "desmayo", "hemorragia")


class ConversationOrchestrator:
    def __init__(self, session: Session, checkpointer) -> None:
        self.session = session
        self.checkpointer = checkpointer
        self.audit = AuditService(session)

    # ------------------------------------------------------------------
    # Gestión de sesión
    # ------------------------------------------------------------------

    def create_session(self, channel: Channel | str) -> InteractionSession:
        channel_value = channel.value if isinstance(channel, Channel) else channel
        interaction = InteractionSession(
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

    def handle_message(
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

        return self._handle_with_langgraph(interaction, message)

    def _handle_with_langgraph(self, interaction: InteractionSession, message: str) -> MessageRead:
        # Tools con closures sobre la sesión DB y la interacción actuales
        tools = build_tools(self.session, interaction)

        # El grafo se compila por request (microsegundos); el checkpointer es compartido
        graph = build_agent_graph(tools, self.checkpointer, interaction)

        # thread_id identifica la conversación en el checkpoint de LangGraph
        config = {
            "configurable": {"thread_id": str(interaction.id)},
            "recursion_limit": settings.max_agent_iterations * 2 + 1,
        }

        try:
            state = graph.invoke(
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _finish_turn(
        self,
        interaction: InteractionSession,
        response: str,
        actions: list[AgentAction] | None = None,
    ) -> MessageRead:
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

    @staticmethod
    def _is_emergency(message: str) -> bool:
        lowered = message.lower()
        return any(term in lowered for term in EMERGENCY_TERMS)
