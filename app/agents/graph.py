"""
Construcción del agente ReAct con LangGraph.

Patrón: build_agent_graph() se llama por request con tools y checkpointer ya preparados.
El LLM (ChatGroq) es un singleton cacheado. El checkpointer viene de app.state (compartido).

¿Por qué por request y no global?
  Las tools son closures con session de DB (scoped por request).
  La compilación de create_react_agent es microsegundos — no es un bottleneck.
  El checkpointer SÍ es global/compartido para que el historial persista entre requests.
"""
from langchain_core.messages import SystemMessage, trim_messages
from langgraph.prebuilt import create_react_agent

from app.agents.groq_client import build_llm
from app.agents.prompt import SYSTEM_PROMPT
from app.core.config import settings
from app.models.interaction import InteractionSession
from app.models.user import User


def build_agent_graph(tools: list, checkpointer, interaction: InteractionSession, user: User):
    """
    Compila y devuelve un agente ReAct listo para invocar.

    Args:
        tools: Lista de @tool funciones con closures sobre session/interaction.
        checkpointer: PostgresSaver o MemorySaver compartido desde app.state.
        interaction: Sesión activa para inyectar estado backend en el system prompt.

    Returns:
        CompiledStateGraph listo para .invoke() o .astream()
    """
    # El state_modifier se ejecuta antes de cada llamada al LLM dentro del loop ReAct.
    # Inyecta el estado backend fresco (user_id, current_state, pending_slot_id)
    # sin que esto quede guardado en el checkpoint como un mensaje más.
    backend_state = (
        f"Estado backend actual: session_id={interaction.id}, "
        f"state={interaction.current_state}, "
        f"user_id={interaction.user_id}, "
        f"usuario_nombre={user.full_name}, "
        f"usuario_dni={user.document_number}, "
        f"usuario_telefono={user.phone}, "
        f"pending_slot_id={interaction.pending_slot_id}. "
        "No le pidas al usuario nombre, DNI ni teléfono para reservar; ya están registrados. "
        "Conversa naturalmente."
    )
    system_message = SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{backend_state}")

    def prompt_with_trimming(state: dict) -> list:
        # Extrae los mensajes del historial que trae el checkpointer de la BD
        messages = state["messages"]
        
        # Recorta el historial dejando los últimos N mensajes (ej: 12).
        # Es inteligente: no rompe los pares de ToolCall/ToolMessage
        # y se asegura de que el chat resultante empiece con un HumanMessage.
        trimmed = trim_messages(
            messages,
            max_tokens=settings.max_context_messages,
            token_counter=len,
            strategy="last",
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
        # El LLM recibe: el System prompt fresco + la cola truncada del historial
        return [system_message] + trimmed

    return create_react_agent(
        model=build_llm(),
        tools=tools,
        prompt=prompt_with_trimming,
        checkpointer=checkpointer,
        # En LangGraph: cada "paso" = 1 nodo del grafo (LLM call o tool call son pasos separados).
        # max_agent_iterations * 2 + 1 cubre N ciclos completos LLM→tool más la respuesta final.
    )
