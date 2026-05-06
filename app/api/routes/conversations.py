from datetime import UTC, datetime
from contextlib import contextmanager
from collections.abc import Generator

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session, select

from app.agents.orchestrator import ConversationOrchestrator
from app.api.deps import get_current_user
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.enums import InteractionStatus
from app.models.interaction import InteractionSession
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationRead, MessageCreate, MessageRead

router = APIRouter(tags=["conversations"])


def get_checkpointer(request: Request):
    return request.app.state.checkpointer


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> ConversationRead:
    orchestrator = ConversationOrchestrator(session, checkpointer, current_user)
    interaction = orchestrator.create_session(payload.channel)
    return _conversation_read(interaction)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ConversationRead]:
    statement = (
        select(InteractionSession)
        .where(InteractionSession.user_id == current_user.id)
        .where(InteractionSession.ended_at.is_(None))
        .order_by(InteractionSession.updated_at.desc())
    )
    return [_conversation_read(interaction) for interaction in session.exec(statement).all()]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    interaction = _get_owned_interaction(session, conversation_id, current_user)
    interaction.status = InteractionStatus.abandoned.value
    interaction.ended_at = datetime.now(UTC).replace(tzinfo=None)
    interaction.updated_at = interaction.ended_at
    session.add(interaction)
    session.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=MessageRead)
async def post_message(
    conversation_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> MessageRead:
    _get_owned_interaction(session, conversation_id, current_user)
    return await ConversationOrchestrator(session, checkpointer, current_user).handle_message(
        conversation_id, payload.message, payload.input_mode
    )


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_ws(websocket: WebSocket, conversation_id: int) -> None:
    checkpointer = websocket.app.state.checkpointer
    await websocket.accept()
    try:
        auth_payload = await websocket.receive_json()
        if auth_payload.get("type") != "auth":
            await websocket.send_json({"type": "error", "message": "Autenticación requerida."})
            await websocket.close(code=1008)
            return

        token = auth_payload.get("token", "")
        with _websocket_session(websocket.app) as session:
            current_user = _user_from_token(session, token)
            if not current_user:
                await websocket.send_json({"type": "error", "message": "Token inválido o expirado."})
                await websocket.close(code=1008)
                return
            try:
                _get_owned_interaction(session, conversation_id, current_user)
            except HTTPException:
                await websocket.send_json({"type": "error", "message": "Conversación no encontrada."})
                await websocket.close(code=1008)
                return

        while True:
            payload = await websocket.receive_json()
            text = payload.get("text", "")
            input_mode = payload.get("input_mode", "voice")

            with _websocket_session(websocket.app) as session:
                current_user = _user_from_token(session, token)
                if not current_user:
                    await websocket.send_json({"type": "error", "message": "Token inválido o expirado."})
                    await websocket.close(code=1008)
                    return
                try:
                    _get_owned_interaction(session, conversation_id, current_user)
                except HTTPException:
                    await websocket.send_json({"type": "error", "message": "Conversación no encontrada."})
                    await websocket.close(code=1008)
                    return
                orchestrator = ConversationOrchestrator(session, checkpointer, current_user)
                async for event in orchestrator.stream_message(conversation_id, text, input_mode):
                    await websocket.send_json(event)

    except WebSocketDisconnect:
        return


def _conversation_read(interaction: InteractionSession) -> ConversationRead:
    return ConversationRead(
        id=interaction.id or 0,
        user_id=interaction.user_id,
        channel=interaction.channel,
        status=interaction.status,
        current_state=interaction.current_state,
    )


def _get_owned_interaction(
    session: Session, conversation_id: int, current_user: User
) -> InteractionSession:
    interaction = session.get(InteractionSession, conversation_id)
    if not interaction or interaction.user_id != current_user.id or interaction.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
    return interaction


def _user_from_token(session: Session, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", ""))
    except (jwt.PyJWTError, TypeError, ValueError):
        return None

    user = session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


@contextmanager
def _websocket_session(app) -> Generator[Session, None, None]:
    session_dependency = app.dependency_overrides.get(get_session, get_session)
    generator = session_dependency()
    session = next(generator)
    try:
        yield session
    finally:
        generator.close()
