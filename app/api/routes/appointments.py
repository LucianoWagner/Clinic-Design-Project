from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.appointment import Appointment, AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.schemas.appointment import AvailabilityQuery, SlotRead
from app.services.appointment_service import AppointmentService

router = APIRouter(tags=["appointments"])


@router.get("/specialties")
def list_specialties(session: Session = Depends(get_session)) -> list[Specialty]:
    return session.exec(select(Specialty).where(Specialty.is_active == True)).all()  # noqa: E712


@router.get("/doctors")
def list_doctors(session: Session = Depends(get_session)) -> list[Doctor]:
    return session.exec(select(Doctor).where(Doctor.is_active == True)).all()  # noqa: E712


@router.get("/availability", response_model=list[SlotRead])
def get_availability(
    specialty_name: str | None = None,
    doctor_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[SlotRead]:
    return AppointmentService(session).search_availability(specialty_name, doctor_id)


@router.post("/appointment-slots")
def create_slot(
    doctor_id: int,
    starts_at: datetime,
    minutes: int = 30,
    session: Session = Depends(get_session),
) -> AppointmentSlot:
    slot = AppointmentSlot(
        doctor_id=doctor_id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=minutes),
    )
    session.add(slot)
    session.commit()
    session.refresh(slot)
    return slot


@router.get("/appointments")
def list_appointments(session: Session = Depends(get_session)) -> list[Appointment]:
    return session.exec(select(Appointment).order_by(Appointment.created_at.desc())).all()
