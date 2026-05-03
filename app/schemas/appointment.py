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
    patient_id: int
    doctor_id: int
    slot_id: int
    starts_at: datetime
    confirmation_code: str


class PatientInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    document_number: str = Field(min_length=4, max_length=40)
    phone: str = Field(min_length=6, max_length=40)
    insurance_name: Optional[str] = Field(default=None, max_length=120)


class SearchAvailabilityToolInput(BaseModel):
    specialty_name: Optional[str] = Field(default=None, max_length=120)
    doctor_id: Optional[int] = None
    limit: int = Field(default=5, ge=1, le=10)


class HoldSlotToolInput(BaseModel):
    slot_id: int


class ConfirmAppointmentToolInput(BaseModel):
    slot_id: Optional[int] = None
    explicit_confirmation: bool


class IdentifyPatientToolInput(PatientInput):
    pass
