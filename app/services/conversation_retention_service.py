from sqlmodel import Session, select

from app.core.config import settings
from app.models.appointment import AppointmentSlot
from app.models.conversation import ConversationMessage
from app.models.enums import SlotStatus
from app.models.interaction import InteractionLog, InteractionSession
from app.services.conversation_checkpoint_service import ConversationCheckpointService


class ConversationRetentionService:
    def __init__(self, session: Session, checkpointer=None):
        self.session = session
        self.checkpoints = ConversationCheckpointService(session, checkpointer)

    async def enforce_for_user(self, user_id: int, keep: int | None = None) -> list[int]:
        limit = keep or settings.max_conversations_per_user
        if limit < 1:
            limit = 1

        statement = (
            select(InteractionSession)
            .where(InteractionSession.user_id == user_id)
            .order_by(InteractionSession.updated_at.desc(), InteractionSession.id.desc())
        )
        conversations = list(self.session.exec(statement).all())
        stale = conversations[limit:]
        deleted_ids: list[int] = []

        for interaction in stale:
            if not interaction.id:
                continue
            await self.delete_conversation(interaction)
            deleted_ids.append(interaction.id)

        return deleted_ids

    async def delete_conversation(self, interaction: InteractionSession) -> None:
        interaction_id = interaction.id
        if not interaction_id:
            return

        await self.checkpoints.delete_thread(str(interaction_id))
        self._release_held_slots(interaction_id)
        self._delete_messages(interaction_id)
        self._delete_logs(interaction_id)
        self.session.delete(interaction)

    def _release_held_slots(self, interaction_id: int) -> None:
        slots = self.session.exec(
            select(AppointmentSlot).where(
                AppointmentSlot.held_by_interaction_session_id == interaction_id
            )
        ).all()
        for slot in slots:
            if slot.status == SlotStatus.held.value:
                slot.status = SlotStatus.available.value
            slot.held_by_interaction_session_id = None
            slot.held_until = None
            self.session.add(slot)

    def _delete_messages(self, interaction_id: int) -> None:
        messages = self.session.exec(
            select(ConversationMessage).where(
                ConversationMessage.interaction_session_id == interaction_id
            )
        ).all()
        for message in messages:
            self.session.delete(message)

    def _delete_logs(self, interaction_id: int) -> None:
        logs = self.session.exec(
            select(InteractionLog).where(InteractionLog.interaction_session_id == interaction_id)
        ).all()
        for log in logs:
            self.session.delete(log)
