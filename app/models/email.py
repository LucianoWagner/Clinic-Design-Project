from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EmailOutbox(SQLModel, table=True):
    __tablename__ = "email_outbox"

    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointments.id", index=True)
    recipient_email: str = Field(index=True, max_length=160)
    recipient_name: str = Field(max_length=160)
    subject: str = Field(max_length=240)
    html_body: str = Field(max_length=12000)
    text_body: str = Field(max_length=4000)
    status: str = Field(default="pending", index=True, max_length=40)
    provider: str = Field(default="resend", index=True, max_length=40)
    provider_message_id: Optional[str] = Field(default=None, max_length=160)
    attempt_count: int = Field(default=0)
    last_error: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
    sent_at: Optional[datetime] = None
