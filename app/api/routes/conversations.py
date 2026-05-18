from collections.abc import Generator
from contextlib import contextmanager

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi_limiter.depends import RateLimiter
from sqlmodel import Session, select

from app.agents.orchestrator import ConversationOrchestrator
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.interaction import InteractionSession
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationMessageRead,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from app.services.conversation_history_service import ConversationHistoryService
from app.services.conversation_retention_service import ConversationRetentionService

router = APIRouter(tags=["conversations"])


def get_checkpointer(request: Request):
    return request.app.state.checkpointer


@router.post("/conversations", response_model=ConversationRead)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> ConversationRead:
    orchestrator = ConversationOrchestrator(session, checkpointer, current_user)
    interaction = orchestrator.create_session(payload.channel)
    await ConversationRetentionService(session, checkpointer).enforce_for_user(current_user.id or 0)
    session.commit()
    session.refresh(interaction)
    return _conversation_read(session, interaction)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ConversationRead]:
    statement = (
        select(InteractionSession)
        .where(InteractionSession.user_id == current_user.id)
        .where(InteractionSession.ended_at.is_(None))
        .order_by(InteractionSession.updated_at.desc(), InteractionSession.id.desc())
        .limit(settings.max_conversations_per_user)
    )
    return [_conversation_read(session, interaction) for interaction in session.exec(statement).all()]


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageRead])
def list_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ConversationMessageRead]:
    _get_owned_interaction(session, conversation_id, current_user)
    messages = ConversationHistoryService(session).list_messages(conversation_id)
    return [_message_read(message) for message in messages]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    checkpointer=Depends(get_checkpointer),
) -> None:
    interaction = _get_owned_interaction(session, conversation_id, current_user)
    await ConversationRetentionService(session, checkpointer).delete_conversation(interaction)
    session.commit()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))]
)
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
            await websocket.send_json({"type": "error", "message": "Autenticacion requerida."})
            await websocket.close(code=1008)
            return

        token = auth_payload.get("token", "")
        with _websocket_session(websocket.app) as session:
            current_user = _user_from_token(session, token)
            if not current_user:
                await websocket.send_json({"type": "error", "message": "Token invalido o expirado."})
                await websocket.close(code=1008)
                return
            try:
                _get_owned_interaction(session, conversation_id, current_user)
            except HTTPException:
                await websocket.send_json({"type": "error", "message": "Conversacion no encontrada."})
                await websocket.close(code=1008)
                return

        message_count = 0
        while True:
            payload = await websocket.receive_json()
            message_count += 1
            if message_count > 100:
                await websocket.send_json({"type": "error", "message": "Limite de mensajes alcanzado en esta sesion."})
                await websocket.close(code=1008)
                return

            text = payload.get("text", "")
            input_mode = payload.get("input_mode", "voice")

            with _websocket_session(websocket.app) as session:
                current_user = _user_from_token(session, token)
                if not current_user:
                    await websocket.send_json({"type": "error", "message": "Token invalido o expirado."})
                    await websocket.close(code=1008)
                    return
                try:
                    _get_owned_interaction(session, conversation_id, current_user)
                except HTTPException:
                    await websocket.send_json({"type": "error", "message": "Conversacion no encontrada."})
                    await websocket.close(code=1008)
                    return
                orchestrator = ConversationOrchestrator(session, checkpointer, current_user)
                async for event in orchestrator.stream_message(conversation_id, text, input_mode):
                    await websocket.send_json(event)

    except WebSocketDisconnect:
        return


def _conversation_read(session: Session, interaction: InteractionSession) -> ConversationRead:
    history = ConversationHistoryService(session)
    first_user_message = history.first_user_message(interaction.id or 0)
    latest_message = history.latest_message(interaction.id or 0)
    return ConversationRead(
        id=interaction.id or 0,
        user_id=interaction.user_id,
        channel=interaction.channel,
        status=interaction.status,
        current_state=interaction.current_state,
        title=_title_from_message(first_user_message.content if first_user_message else None),
        preview=latest_message.content if latest_message else None,
        created_at=interaction.created_at,
        updated_at=interaction.updated_at,
        last_messages=[
            _message_read(message) for message in history.last_messages(interaction.id or 0, limit=2)
        ],
    )


def _message_read(message) -> ConversationMessageRead:
    return ConversationMessageRead(
        id=message.id or 0,
        conversation_id=message.interaction_session_id,
        role=message.role,
        content=message.content,
        input_mode=message.input_mode,
        created_at=message.created_at,
    )


def _title_from_message(message: str | None) -> str:
    if not message:
        return "Nueva consulta"
    clean = " ".join(message.split())
    return clean[:44] + ("..." if len(clean) > 44 else "")


def _get_owned_interaction(
    session: Session, conversation_id: int, current_user: User
) -> InteractionSession:
    interaction = session.get(InteractionSession, conversation_id)
    if not interaction or interaction.user_id != current_user.id or interaction.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversacion no encontrada.")
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
