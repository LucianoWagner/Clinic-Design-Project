"""
Construcción del agente ReAct con LangGraph.

Patrón: build_agent_graph() se llama por request con tools y checkpointer ya preparados.
El LLM (ChatGroq) es un singleton cacheado. El checkpointer viene de app.state (compartido).

¿Por qué por request y no global?
  Las tools son closures con session de DB (scoped por request).
  La compilación de create_react_agent es microsegundos — no es un bottleneck.
  El checkpointer SÍ es global/compartido para que el historial persista entre requests.
"""
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from app.agents.groq_client import build_llm
from app.agents.prompt import SYSTEM_PROMPT
from app.core.config import settings
from app.models.interaction import InteractionSession


def build_agent_graph(tools: list, checkpointer, interaction: InteractionSession):
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
    # Inyecta el estado backend fresco (patient_id, current_state, pending_slot_id)
    # sin que esto quede guardado en el checkpoint como un mensaje más.
    backend_state = (
        f"Estado backend actual: session_id={interaction.id}, "
        f"state={interaction.current_state}, "
        f"patient_id={interaction.patient_id}, "
        f"pending_slot_id={interaction.pending_slot_id}. "
        "No le pidas al usuario llenar un formulario; conversa naturalmente."
    )
    system_message = SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{backend_state}")

    return create_react_agent(
        model=build_llm(),
        tools=tools,
        # prompt: reemplaza o prepend el system message antes de cada LLM call.
        prompt=system_message,
        checkpointer=checkpointer,
        # En LangGraph: cada "paso" = 1 nodo del grafo (LLM call o tool call son pasos separados).
        # max_agent_iterations * 2 + 1 cubre N ciclos completos LLM→tool más la respuesta final.
    )
