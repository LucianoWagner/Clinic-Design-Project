from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.enums import SlotStatus
from app.models.interaction import InteractionSession
from app.models.user import User
from app.services.appointment_service import AppointmentConflictError, AppointmentService


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        specialty = Specialty(name="cardiologia")
        session.add(specialty)
        session.flush()
        doctor = Doctor(full_name="Dra. Test", specialty_id=specialty.id or 0, license_number="MN1")
        session.add(doctor)
        session.flush()
        user = User(
            email="juan@example.com",
            full_name="Juan Perez",
            document_number="12345678",
            phone="1122334455",
            password_hash="hash",
        )
        session.add(user)
        session.flush()
        slot = AppointmentSlot(
            doctor_id=doctor.id or 0,
            starts_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
            ends_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1, minutes=30),
        )
        interaction = InteractionSession(user_id=user.id or 0)
        session.add(slot)
        session.add(interaction)
        session.commit()
        yield session


def test_hold_and_confirm_appointment(session: Session) -> None:
    service = AppointmentService(session)

    held = service.hold_slot(slot_id=1, interaction_session_id=1)
    assert held.status == SlotStatus.held

    appointment = service.confirm_appointment(
        slot_id=1, interaction_session_id=1, explicit_confirmation=True
    )
    assert appointment.confirmation_code == "TUR-1"
    assert appointment.user_id == 1
    assert session.get(AppointmentSlot, 1).status == SlotStatus.booked


def test_cannot_hold_booked_slot(session: Session) -> None:
    service = AppointmentService(session)
    service.hold_slot(slot_id=1, interaction_session_id=1)
    service.confirm_appointment(slot_id=1, interaction_session_id=1, explicit_confirmation=True)

    with pytest.raises(AppointmentConflictError):
        service.hold_slot(slot_id=1, interaction_session_id=1)
