from sqlmodel import Session, select

from app.models.conversation import ConversationMessage


class ConversationHistoryService:
    def __init__(self, session: Session):
        self.session = session

    def add_message(
        self,
        interaction_session_id: int,
        role: str,
        content: str,
        input_mode: str = "text",
    ) -> ConversationMessage:
        message = ConversationMessage(
            interaction_session_id=interaction_session_id,
            role=role,
            content=content,
            input_mode=input_mode,
        )
        self.session.add(message)
        return message

    def list_messages(self, interaction_session_id: int) -> list[ConversationMessage]:
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.interaction_session_id == interaction_session_id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
        return list(self.session.exec(statement).all())

    def last_messages(self, interaction_session_id: int, limit: int = 2) -> list[ConversationMessage]:
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.interaction_session_id == interaction_session_id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(self.session.exec(statement).all()))

    def first_user_message(self, interaction_session_id: int) -> ConversationMessage | None:
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.interaction_session_id == interaction_session_id)
            .where(ConversationMessage.role == "user")
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
            .limit(1)
        )
        return self.session.exec(statement).first()

    def latest_message(self, interaction_session_id: int) -> ConversationMessage | None:
        statement = (
            select(ConversationMessage)
            .where(ConversationMessage.interaction_session_id == interaction_session_id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(1)
        )
        return self.session.exec(statement).first()
