from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    interaction_session_id: int = Field(foreign_key="interaction_sessions.id", index=True)
    role: str = Field(index=True, max_length=40)
    content: str = Field(max_length=8000)
    input_mode: str = Field(default="text", index=True, max_length=20)
    created_at: datetime = Field(default_factory=utcnow, index=True)
