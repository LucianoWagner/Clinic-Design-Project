from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.email import EmailOutbox
from app.models.enums import SlotStatus
from app.models.interaction import InteractionSession
from app.models.user import User
from app.services.appointment_service import AppointmentConflictError, AppointmentService
from app.services.email_outbox_service import EmailOutboxService
from app.services.email_provider import EmailSendResult


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
    session.flush()
    email = session.get(EmailOutbox, 1)
    assert appointment.confirmation_code == "TUR-1"
    assert appointment.user_id == 1
    assert session.get(AppointmentSlot, 1).status == SlotStatus.booked
    assert email is not None
    assert email.status == "pending"
    assert email.recipient_email == "juan@example.com"
    assert "Dra. Test" in email.text_body
    assert "cardiologia" in email.text_body
    assert "TUR-1" in email.text_body
    assert "me duele" not in email.text_body.lower()
    assert "sintoma" not in email.text_body.lower()


def test_cannot_hold_booked_slot(session: Session) -> None:
    service = AppointmentService(session)
    service.hold_slot(slot_id=1, interaction_session_id=1)
    service.confirm_appointment(slot_id=1, interaction_session_id=1, explicit_confirmation=True)

    with pytest.raises(AppointmentConflictError):
        service.hold_slot(slot_id=1, interaction_session_id=1)


def test_email_outbox_dispatch_success(session: Session, monkeypatch) -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def send(self, **kwargs):
            self.calls += 1
            assert kwargs["recipient_email"] == "juan@example.com"
            return EmailSendResult(provider_message_id="email_123")

    monkeypatch.setattr("app.services.email_outbox_service.settings.email_enabled", True)
    service = AppointmentService(session)
    service.hold_slot(slot_id=1, interaction_session_id=1)
    service.confirm_appointment(slot_id=1, interaction_session_id=1, explicit_confirmation=True)
    session.commit()

    provider = Provider()
    dispatched = EmailOutboxService(session, provider).dispatch_pending()

    assert provider.calls == 1
    assert dispatched[0].status == "sent"
    assert dispatched[0].provider_message_id == "email_123"


def test_email_outbox_dispatch_failure_does_not_delete_appointment(
    session: Session, monkeypatch
) -> None:
    class Provider:
        def send(self, **kwargs):
            raise RuntimeError("resend down")

    monkeypatch.setattr("app.services.email_outbox_service.settings.email_enabled", True)
    service = AppointmentService(session)
    service.hold_slot(slot_id=1, interaction_session_id=1)
    appointment = service.confirm_appointment(
        slot_id=1, interaction_session_id=1, explicit_confirmation=True
    )
    session.commit()

    dispatched = EmailOutboxService(session, Provider()).dispatch_pending()

    assert appointment.id == 1
    assert dispatched[0].status == "failed"
    assert dispatched[0].attempt_count == 1
    assert "resend down" in dispatched[0].last_error


def test_email_disabled_does_not_call_provider(session: Session, monkeypatch) -> None:
    class Provider:
        def send(self, **kwargs):
            raise AssertionError("provider should not be called")

    monkeypatch.setattr("app.services.email_outbox_service.settings.email_enabled", False)
    service = AppointmentService(session)
    service.hold_slot(slot_id=1, interaction_session_id=1)
    service.confirm_appointment(slot_id=1, interaction_session_id=1, explicit_confirmation=True)
    session.commit()

    assert EmailOutboxService(session, Provider()).dispatch_pending() == []
    assert session.get(EmailOutbox, 1).status == "pending"
