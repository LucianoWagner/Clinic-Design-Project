from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.enums import AppointmentStatus, SlotStatus


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AppointmentSlot(SQLModel, table=True):
    __tablename__ = "appointment_slots"
    __table_args__ = (UniqueConstraint("doctor_id", "starts_at", name="uq_slot_doctor_start"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    status: str = Field(default=SlotStatus.available.value, index=True)
    held_until: Optional[datetime] = Field(default=None, index=True)
    held_by_interaction_session_id: Optional[int] = Field(
        default=None, foreign_key="interaction_sessions.id", index=True
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_appointment_slot"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    slot_id: int = Field(foreign_key="appointment_slots.id", index=True)
    status: str = Field(default=AppointmentStatus.confirmed.value, index=True)
    confirmation_source: str = Field(default="web_agent", max_length=80)
    confirmed_at: datetime = Field(default_factory=utcnow)
    checkin_token: Optional[str] = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
