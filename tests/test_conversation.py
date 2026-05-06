from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import MemorySaver
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.orchestrator import ConversationOrchestrator
from app.agents.tools import build_tools
from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.interaction import InteractionLog
from app.models.user import User


def _make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _create_user(session: Session, email: str = "user@example.com") -> User:
    user = User(
        email=email,
        full_name="Usuario Test",
        document_number=email.split("@")[0],
        phone="1122334455",
        password_hash="hash",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed(session: Session) -> User:
    specialty = Specialty(name="cardiologia")
    session.add(specialty)
    session.flush()
    doctor = Doctor(full_name="Dra. Test", specialty_id=specialty.id or 0, license_number="MN1")
    session.add(doctor)
    session.flush()
    slot = AppointmentSlot(
        doctor_id=doctor.id or 0,
        starts_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        ends_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1, minutes=30),
    )
    session.add(slot)
    user = _create_user(session, "juan@example.com")
    session.commit()
    return user


def test_tool_executor_books_real_slot() -> None:
    session = _make_session()
    user = _seed(session)

    checkpointer = MemorySaver()
    interaction = ConversationOrchestrator(session, checkpointer, user).create_session(
        channel="web_chat"
    )

    tools_list = build_tools(session, interaction)
    tools = {tool.name: tool for tool in tools_list}
    assert "identify_or_create_patient" not in tools

    avail_result = tools["search_availability"].invoke({"specialty_name": "cardiologia"})
    assert avail_result["ok"] is True
    assert len(avail_result["slots"]) >= 1
    slot_id = avail_result["slots"][0]["id"]

    hold_result = tools["hold_slot"].invoke({"slot_id": slot_id})
    assert hold_result["ok"] is True
    assert hold_result["held_until"] is not None

    confirm_result = tools["confirm_appointment"].invoke({"explicit_confirmation": True})
    assert confirm_result["ok"] is True
    assert confirm_result["appointment"]["user_id"] == user.id
    assert confirm_result["appointment"]["confirmation_code"].startswith("TUR-")


def test_confirm_fails_without_valid_user() -> None:
    session = _make_session()
    user = _seed(session)

    interaction = ConversationOrchestrator(session, MemorySaver(), user).create_session(
        channel="web_chat"
    )
    interaction.user_id = 999
    session.add(interaction)
    session.commit()
    tools = {tool.name: tool for tool in build_tools(session, interaction)}

    hold_result = tools["hold_slot"].invoke({"slot_id": 1})
    assert hold_result["ok"] is True

    confirm_result = tools["confirm_appointment"].invoke({"explicit_confirmation": True})
    assert confirm_result["ok"] is False


def test_catalog_tool_lists_active_specialties_and_doctors() -> None:
    session = _make_session()
    cardio = Specialty(name="cardiologia")
    clinic = Specialty(name="clinica")
    inactive_specialty = Specialty(name="traumatologia", is_active=False)
    session.add_all([cardio, clinic, inactive_specialty])
    session.flush()
    session.add_all(
        [
            Doctor(full_name="Dra. Ana Perez", specialty_id=cardio.id or 0, license_number="MN1"),
            Doctor(full_name="Dr. Juan Gomez", specialty_id=clinic.id or 0, license_number="MN2"),
            Doctor(
                full_name="Dr. Inactivo",
                specialty_id=clinic.id or 0,
                license_number="MN3",
                is_active=False,
            ),
            Doctor(
                full_name="Dra. Oculta",
                specialty_id=inactive_specialty.id or 0,
                license_number="MN4",
            ),
        ]
    )
    session.commit()

    user = _create_user(session)
    orchestrator = ConversationOrchestrator(session, MemorySaver(), user)
    interaction = orchestrator.create_session(channel="web_chat")
    tools = {tool.name: tool for tool in build_tools(session, interaction)}

    result = tools["list_specialties_and_doctors"].invoke({})

    assert result["ok"] is True
    assert result["specialties"] == [
        {
            "specialty_id": cardio.id,
            "specialty_name": "cardiologia",
            "doctors": [{"doctor_id": 1, "doctor_name": "Dra. Ana Perez"}],
        },
        {
            "specialty_id": clinic.id,
            "specialty_name": "clinica",
            "doctors": [{"doctor_id": 2, "doctor_name": "Dr. Juan Gomez"}],
        },
    ]


def test_finish_turn_sanitizes_before_logging() -> None:
    session = _make_session()
    user = _create_user(session)
    orchestrator = ConversationOrchestrator(session, MemorySaver(), user)
    interaction = orchestrator.create_session(channel="web_chat")

    result = orchestrator._finish_turn(
        interaction,
        'Respuesta humana. <function=search_availability>{"specialty_name":"x"}</function>',
    )

    logs = session.exec(
        select(InteractionLog).where(InteractionLog.interaction_session_id == interaction.id)
    ).all()
    sent_logs = [log for log in logs if log.event_type == "message_sent"]
    sanitized_logs = [log for log in logs if log.event_type == "response_sanitized"]
    assert result.response == "Respuesta humana."
    assert sent_logs[-1].message_summary == "Respuesta humana."
    assert len(sanitized_logs) == 1
