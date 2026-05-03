from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.enums import Channel, InteractionStatus


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class InteractionSession(SQLModel, table=True):
    __tablename__ = "interaction_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    channel: str = Field(default=Channel.web_chat.value, index=True)
    status: str = Field(default=InteractionStatus.started.value, index=True)
    current_state: str = Field(default="greeting", index=True, max_length=80)
    patient_id: Optional[int] = Field(default=None, foreign_key="patients.id", index=True)
    pending_slot_id: Optional[int] = Field(default=None, foreign_key="appointment_slots.id")
    collected_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ended_at: Optional[datetime] = None


class InteractionLog(SQLModel, table=True):
    __tablename__ = "interaction_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    interaction_session_id: int = Field(foreign_key="interaction_sessions.id", index=True)
    event_type: str = Field(index=True, max_length=80)
    role: str = Field(index=True, max_length=40)
    message_summary: Optional[str] = Field(default=None, max_length=1000)
    tool_name: Optional[str] = Field(default=None, max_length=120)
    tool_args_redacted: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    tool_result_summary: Optional[str] = Field(default=None, max_length=1000)
    error_code: Optional[str] = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=utcnow)
