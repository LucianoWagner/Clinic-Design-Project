"""
Rutas de conversaciones: creación de sesión y envío de mensajes.
El checkpointer de LangGraph se inyecta desde app.state vía dependency.
"""
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.agents.orchestrator import ConversationOrchestrator
from app.db.session import get_session
from app.schemas.conversation import ConversationCreate, ConversationRead, MessageCreate, MessageRead  # MessageCreate/Read usados en REST

router = APIRouter(tags=["conversations"])


def get_checkpointer(request: Request):
    """Dependency que expone el checkpointer inicializado en el lifespan."""
    return request.app.state.checkpointer


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(
    payload: ConversationCreate,
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> ConversationRead:
    interaction = ConversationOrchestrator(session, checkpointer).create_session(payload.channel)
    return ConversationRead(
        id=interaction.id or 0,
        channel=interaction.channel,
        status=interaction.status,
        current_state=interaction.current_state,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageRead)
async def post_message(
    conversation_id: int,
    payload: MessageCreate,
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> MessageRead:
    return await ConversationOrchestrator(session, checkpointer).handle_message(
        conversation_id, payload.message, payload.input_mode
    )


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_ws(websocket: WebSocket, conversation_id: int) -> None:
    """
    Canal WebSocket para streaming en tiempo real (Fase 2 — Canal de Voz).

    Protocolo (servidor → cliente):
      {type: "token",      text: str}           ← fragmento del LLM
      {type: "tool_start", name: str}           ← herramienta iniciada
      {type: "tool_end",   name: str}           ← herramienta terminada
      {type: "done",       state: str, full_text: str}
      {type: "error",      message: str}

    Protocolo (cliente → servidor):
      {type: "user_message", text: str, input_mode: "voice" | "text"}
    """
    checkpointer = websocket.app.state.checkpointer
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            text       = payload.get("text", "")
            input_mode = payload.get("input_mode", "voice")

            with next(get_session()) as session:
                orchestrator = ConversationOrchestrator(session, checkpointer)
                # stream_message es un async generator: itera y reenvía cada evento al WS
                async for event in orchestrator.stream_message(
                    conversation_id, text, input_mode
                ):
                    await websocket.send_json(event)

    except WebSocketDisconnect:
        return
