"""
Rutas de conversaciones: creación de sesión y envío de mensajes.
El checkpointer de LangGraph se inyecta desde app.state vía dependency.
"""
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.agents.orchestrator import ConversationOrchestrator
from app.db.session import get_session
from app.schemas.conversation import ConversationCreate, ConversationRead, MessageCreate, MessageRead

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
def post_message(
    conversation_id: int,
    payload: MessageCreate,
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> MessageRead:
    return ConversationOrchestrator(session, checkpointer).handle_message(
        conversation_id, payload.message, payload.input_mode
    )


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_ws(websocket: WebSocket, conversation_id: int) -> None:
    """
    Canal WebSocket para conversación en tiempo real.
    Preparado para streaming en Fase 2 (canal de voz).
    Actualmente procesa mensajes completos igual que el endpoint REST.
    """
    checkpointer = websocket.app.state.checkpointer
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            message = MessageCreate(**payload)
            with next(get_session()) as session:
                response = ConversationOrchestrator(session, checkpointer).handle_message(
                    conversation_id, message.message, message.input_mode
                )
            await websocket.send_json(response.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
