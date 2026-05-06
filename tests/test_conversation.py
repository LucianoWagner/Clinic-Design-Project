from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import MemorySaver
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.orchestrator import ConversationOrchestrator
from app.agents.tools import build_tools
from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.interaction import InteractionLog



def _make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session) -> None:
    """Crea datos mínimos para tests: especialidad, médico y slot futuro."""
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
    session.commit()


def test_tool_executor_books_real_slot() -> None:
    """Flujo completo: identificar paciente → buscar disponibilidad → hold → confirm."""
    session = _make_session()
    _seed(session)

    checkpointer = MemorySaver()
    interaction = ConversationOrchestrator(session, checkpointer).create_session(channel="web_chat")

    # Construir tools con closures sobre la sesión y la interacción
    tools_list = build_tools(session, interaction)
    tools = {t.name: t for t in tools_list}

    # identify_or_create_patient
    patient_result = tools["identify_or_create_patient"].invoke({
        "full_name": "Juan Perez",
        "document_number": "12345678",
        "phone": "1122334455",
    })
    assert patient_result["ok"] is True
    assert patient_result["patient_id"] is not None

    # search_availability
    avail_result = tools["search_availability"].invoke({"specialty_name": "cardiologia"})
    assert avail_result["ok"] is True
    assert len(avail_result["slots"]) >= 1
    slot_id = avail_result["slots"][0]["id"]

    # hold_slot
    hold_result = tools["hold_slot"].invoke({"slot_id": slot_id})
    assert hold_result["ok"] is True
    assert hold_result["held_until"] is not None

    # confirm_appointment
    confirm_result = tools["confirm_appointment"].invoke({"explicit_confirmation": True})
    assert confirm_result["ok"] is True
    assert confirm_result["appointment"]["confirmation_code"].startswith("TUR-")


def test_cannot_hold_without_patient() -> None:
    """Hold sin paciente identificado no debe confirmar — falla en confirm, no en hold."""
    session = _make_session()
    _seed(session)

    checkpointer = MemorySaver()
    interaction = ConversationOrchestrator(session, checkpointer).create_session(channel="web_chat")
    tools_list = build_tools(session, interaction)
    tools = {t.name: t for t in tools_list}

    hold_result = tools["hold_slot"].invoke({"slot_id": 1})
    assert hold_result["ok"] is True  # hold no requiere paciente

    # confirm SÍ requiere paciente → falla
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

    orchestrator = ConversationOrchestrator(session, MemorySaver())
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
    orchestrator = ConversationOrchestrator(session, MemorySaver())
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
