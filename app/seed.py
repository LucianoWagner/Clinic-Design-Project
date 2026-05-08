from datetime import UTC, datetime, timedelta

from sqlmodel import Session, delete, select

from app.db.session import engine
from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty


def _seed_catalog(session: Session) -> list[Doctor]:
    """Crea especialidades y doctores solo si no existen. Retorna los doctores activos."""
    if not session.exec(select(Specialty)).first():
        cardiology = Specialty(name="cardiologia")
        clinic = Specialty(name="clinica")
        dermatology = Specialty(name="dermatologia")
        pediatrics = Specialty(name="pediatria")
        session.add_all([cardiology, clinic, dermatology, pediatrics])
        session.flush()

        doctors = [
            Doctor(full_name="Dra. Ana Pérez", specialty_id=cardiology.id or 0, license_number="MN1001"),
            Doctor(full_name="Dr. Juan Gómez", specialty_id=clinic.id or 0, license_number="MN1002"),
            Doctor(full_name="Dra. Laura Díaz", specialty_id=dermatology.id or 0, license_number="MN1003"),
            Doctor(full_name="Dra. María Torres", specialty_id=pediatrics.id or 0, license_number="MN1004"),
        ]
        session.add_all(doctors)
        session.flush()
        print("Catálogo de especialidades y médicos creado")
    else:
        print("Catálogo ya existe, omitiendo")

    return list(session.exec(select(Doctor).where(Doctor.is_active == True)).all())  # noqa: E712


def _refresh_slots(session: Session, doctors: list[Doctor]) -> None:
    """
    Elimina los slots disponibles vencidos y regenera slots futuros para todos los
    doctores activos. Los slots ya reservados (booked) se conservan.
    """
    now = datetime.now(UTC).replace(tzinfo=None)

    # Eliminar solo slots que ya pasaron y no están reservados
    session.exec(
        delete(AppointmentSlot).where(
            AppointmentSlot.starts_at <= now,
            AppointmentSlot.status != "booked",
        )
    )
    session.flush()

    # Revisar si ya hay slots futuros suficientes (más de 5 días de cobertura)
    future_count = session.exec(
        select(AppointmentSlot).where(AppointmentSlot.starts_at > now)
    ).first()

    if future_count:
        print("Slots futuros ya existen, omitiendo regeneración")
        return

    # Generar slots para los próximos 14 días laborables
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    slots_created = 0
    for doctor in doctors:
        for day in range(14):
            candidate = start + timedelta(days=day)
            # Saltar fines de semana
            if candidate.weekday() >= 5:
                continue
            for hour in (9, 10, 11, 14, 15, 16):
                starts_at = candidate.replace(hour=hour)
                session.add(
                    AppointmentSlot(
                        doctor_id=doctor.id or 0,
                        starts_at=starts_at,
                        ends_at=starts_at + timedelta(minutes=30),
                    )
                )
                slots_created += 1

    print(f"Slots regenerados: {slots_created} turnos para los próximos 14 días")


def run() -> None:
    with Session(engine) as session:
        doctors = _seed_catalog(session)
        _refresh_slots(session, doctors)
        session.commit()


if __name__ == "__main__":
    run()
