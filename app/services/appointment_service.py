import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models.appointment import Appointment, AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.enums import SlotStatus
from app.models.interaction import InteractionSession
from app.models.patient import Patient
from app.schemas.appointment import AppointmentRead, PatientInput, SlotRead


class AppointmentConflictError(Exception):
    pass


class AppointmentValidationError(Exception):
    pass


class AppointmentService:
    def __init__(self, session: Session):
        self.session = session

    def list_specialties_and_doctors(self) -> list[dict]:
        statement = (
            select(Specialty, Doctor)
            .join(Doctor, Doctor.specialty_id == Specialty.id)
            .where(Specialty.is_active == True)  # noqa: E712
            .where(Doctor.is_active == True)  # noqa: E712
            .order_by(Specialty.name, Doctor.full_name)
        )
        rows = self.session.exec(statement).all()

        grouped: dict[int, dict] = {}
        for specialty, doctor in rows:
            specialty_id = specialty.id or 0
            if specialty_id not in grouped:
                grouped[specialty_id] = {
                    "specialty_id": specialty_id,
                    "specialty_name": specialty.name,
                    "doctors": [],
                }
            grouped[specialty_id]["doctors"].append(
                {
                    "doctor_id": doctor.id or 0,
                    "doctor_name": doctor.full_name,
                }
            )
        return list(grouped.values())

    def search_availability(
        self, specialty_name: str | None = None, doctor_id: int | None = None, limit: int = 5
    ) -> list[SlotRead]:
        now = datetime.now(UTC).replace(tzinfo=None)
        statement = (
            select(AppointmentSlot, Doctor, Specialty)
            .join(Doctor, AppointmentSlot.doctor_id == Doctor.id)
            .join(Specialty, Doctor.specialty_id == Specialty.id)
            .where(AppointmentSlot.starts_at > now)
            .where(AppointmentSlot.status == SlotStatus.available.value)
            .where(Doctor.is_active == True)  # noqa: E712
            .where(Specialty.is_active == True)  # noqa: E712
            .order_by(AppointmentSlot.starts_at)
            .limit(limit)
        )
        if specialty_name:
            # Normaliza el input: quita tildes para que "cardiologia" == "cardiología".
            # func.unaccent() hace lo mismo en el lado de la BD (requiere extensión unaccent).
            normalized = (
                unicodedata.normalize("NFD", specialty_name)
                .encode("ascii", "ignore")
                .decode("ascii")
                .strip()
            )
            if self.session.get_bind().dialect.name == "sqlite":
                statement = statement.where(Specialty.name.ilike(f"%{normalized}%"))
            else:
                statement = statement.where(func.unaccent(Specialty.name).ilike(f"%{normalized}%"))
        if doctor_id:
            statement = statement.where(Doctor.id == doctor_id)

        rows = self.session.exec(statement).all()
        return [
            SlotRead(
                id=slot.id or 0,
                doctor_id=doctor.id or 0,
                doctor_name=doctor.full_name,
                specialty_name=specialty.name,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
            )
            for slot, doctor, specialty in rows
        ]

    def identify_or_create_patient(self, data: PatientInput) -> Patient:
        patient = self.session.exec(
            select(Patient).where(Patient.document_number == data.document_number)
        ).first()
        if patient:
            patient.full_name = data.full_name
            patient.phone = data.phone
            patient.insurance_name = data.insurance_name
            self.session.add(patient)
            return patient
        patient = Patient(
            full_name=data.full_name,
            document_number=data.document_number,
            phone=data.phone,
            insurance_name=data.insurance_name,
        )
        self.session.add(patient)
        self.session.flush()
        return patient

    def hold_slot(self, slot_id: int, interaction_session_id: int) -> AppointmentSlot:
        slot = self.session.get(AppointmentSlot, slot_id)
        if not slot:
            raise AppointmentValidationError("El turno seleccionado no existe.")

        now = datetime.now(UTC).replace(tzinfo=None)
        if slot.status == SlotStatus.booked.value:
            raise AppointmentConflictError("Ese turno ya fue reservado.")
        if slot.status == SlotStatus.held.value and slot.held_until and slot.held_until > now:
            if slot.held_by_interaction_session_id != interaction_session_id:
                raise AppointmentConflictError("Ese turno está retenido temporalmente.")

        slot.status = SlotStatus.held.value
        slot.held_by_interaction_session_id = interaction_session_id
        slot.held_until = now + timedelta(seconds=settings.hold_ttl_seconds)
        self.session.add(slot)

        interaction = self.session.get(InteractionSession, interaction_session_id)
        if interaction:
            interaction.pending_slot_id = slot.id
            self.session.add(interaction)
        return slot

    def confirm_appointment(
        self, slot_id: int, interaction_session_id: int, explicit_confirmation: bool
    ) -> AppointmentRead:
        if not explicit_confirmation:
            raise AppointmentValidationError("Falta confirmación explícita.")

        interaction = self.session.get(InteractionSession, interaction_session_id)
        if not interaction or not interaction.patient_id:
            raise AppointmentValidationError("Faltan datos del paciente.")

        slot = self.session.get(AppointmentSlot, slot_id)
        now = datetime.now(UTC).replace(tzinfo=None)
        if not slot:
            raise AppointmentValidationError("El turno seleccionado no existe.")
        if (
            slot.status != SlotStatus.held.value
            or slot.held_by_interaction_session_id != interaction_session_id
            or not slot.held_until
            or slot.held_until <= now
        ):
            raise AppointmentConflictError("La reserva temporal venció o no pertenece a esta sesión.")

        appointment = Appointment(
            patient_id=interaction.patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id or 0,
            interaction_session_id=interaction_session_id,
        )
        slot.status = SlotStatus.booked.value
        slot.held_until = None
        self.session.add(slot)
        self.session.add(appointment)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise AppointmentConflictError("Ese turno ya fue confirmado.") from exc

        return AppointmentRead(
            id=appointment.id or 0,
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            slot_id=appointment.slot_id,
            starts_at=slot.starts_at,
            confirmation_code=f"TUR-{appointment.id}",
        )
