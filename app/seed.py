from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.db.session import engine
from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty


def run() -> None:
    with Session(engine) as session:
        if session.exec(select(Specialty)).first():
            print("Seed already exists")
            return

        cardiology = Specialty(name="cardiologia")
        clinic = Specialty(name="clinica")
        dermatology = Specialty(name="dermatologia")
        session.add(cardiology)
        session.add(clinic)
        session.add(dermatology)
        session.flush()

        doctors = [
            Doctor(full_name="Dra. Ana Pérez", specialty_id=cardiology.id or 0, license_number="MN1001"),
            Doctor(full_name="Dr. Juan Gómez", specialty_id=clinic.id or 0, license_number="MN1002"),
            Doctor(full_name="Dra. Laura Díaz", specialty_id=dermatology.id or 0, license_number="MN1003"),
        ]
        session.add_all(doctors)
        session.flush()

        start = datetime.now(UTC).replace(tzinfo=None, minute=0, second=0, microsecond=0) + timedelta(days=1)
        for doctor in doctors:
            for day in range(5):
                for hour in (9, 10, 11, 15, 16):
                    starts_at = (start + timedelta(days=day)).replace(hour=hour)
                    session.add(
                        AppointmentSlot(
                            doctor_id=doctor.id or 0,
                            starts_at=starts_at,
                            ends_at=starts_at + timedelta(minutes=30),
                        )
                    )
        session.commit()
        print("Seed completed")


if __name__ == "__main__":
    run()
