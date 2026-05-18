from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AvailabilityQuery(BaseModel):
    specialty_name: Optional[str] = None
    doctor_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class SlotRead(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    specialty_name: str
    starts_at: datetime
    ends_at: datetime


class HoldSlotRequest(BaseModel):
    slot_id: int
    interaction_session_id: int


class HoldSlotRead(BaseModel):
    slot_id: int
    held_until: datetime


class ConfirmAppointmentRequest(BaseModel):
    slot_id: int
    interaction_session_id: int
    explicit_confirmation: bool


class AppointmentRead(BaseModel):
    id: int
    user_id: int
    doctor_id: int
    slot_id: int
    starts_at: datetime
    confirmation_code: str


class SearchAvailabilityToolInput(BaseModel):
    specialty_name: Optional[str] = Field(default=None, max_length=120)
    doctor_id: Optional[int] = None
    limit: int = Field(default=5, ge=1, le=10)


class HoldSlotToolInput(BaseModel):
    slot_id: int


class ConfirmAppointmentToolInput(BaseModel):
    slot_id: Optional[int] = None
    explicit_confirmation: bool


class UserAppointmentRead(BaseModel):
    id: int
    doctor_name: str
    specialty_name: str
    starts_at: datetime
    ends_at: datetime
    status: str
    confirmed_at: datetime
