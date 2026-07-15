from datetime import UTC, datetime, timedelta
from sqlmodel import Session, delete, select
from sqlalchemy import text

from app.db.session import engine
from app.models.appointment import Appointment, AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.user import User
from app.models.interaction import InteractionSession, InteractionLog
from app.models.conversation import ConversationMessage
from app.models.email import EmailOutbox
from app.models.enums import SlotStatus, UserRole
from app.core.security import hash_password


def clean_database(session: Session) -> None:
    print("Limpiando base de datos...")
    
    # Romper referencias circulares temporales
    try:
        with session.begin_nested():
            session.execute(text("UPDATE appointment_slots SET held_by_interaction_session_id = NULL"))
            session.execute(text("UPDATE interaction_sessions SET pending_slot_id = NULL"))
            session.flush()
    except Exception as e:
        print(f"Advertencia al romper referencias circulares: {e}")
        
    # 1. Eliminar mensajes y logs
    session.exec(delete(ConversationMessage))
    session.exec(delete(InteractionLog))
    
    # 2. Eliminar emails
    session.exec(delete(EmailOutbox))
    
    # 3. Eliminar turnos (appointments)
    session.exec(delete(Appointment))
    
    # 4. Eliminar sesiones (después de logs/mensajes/turnos)
    session.exec(delete(InteractionSession))
    
    # 5. Eliminar slots (después de sesiones y turnos)
    session.exec(delete(AppointmentSlot))
    
    # 6. Eliminar doctores
    session.exec(delete(Doctor))
    
    # 7. Eliminar especialidades y usuarios
    session.exec(delete(Specialty))
    session.exec(delete(User))
    
    # 8. Limpiar checkpoints de LangGraph (tablas internas)
    try:
        with session.begin_nested():
            session.execute(text("DELETE FROM checkpoint_writes"))
            session.execute(text("DELETE FROM checkpoint_blobs"))
            session.execute(text("DELETE FROM checkpoints"))
            session.flush()
        print("Tablas de checkpoints de LangGraph limpiadas.")
    except Exception as e:
        print(f"No se pudieron limpiar las tablas de checkpoints (quizás no existan aún): {e}")
        
    session.flush()
    print("Base de datos limpia.")



def is_already_seeded(session: Session) -> bool:
    """Devuelve True si ya hay al menos un usuario en la BD (seed ya fue ejecutado)."""
    return session.exec(select(User)).first() is not None


def run() -> None:
    with Session(engine) as session:
        if is_already_seeded(session):
            print("Base de datos ya inicializada, omitiendo seed.")
            return

        clean_database(session)
        
        # 1. Crear Especialidades
        cardiology = Specialty(name="cardiologia")
        clinic = Specialty(name="clinica")
        dermatology = Specialty(name="dermatologia")
        pediatrics = Specialty(name="pediatria")
        session.add_all([cardiology, clinic, dermatology, pediatrics])
        session.flush()
        
        # 2. Crear Usuarios (Admin y Paciente)
        admin_user = User(
            email="admin@consultorio.com",
            full_name="Administrador Consultorio",
            document_number="99999999",
            phone="1122334455",
            password_hash=hash_password("admin1234"),
            role=UserRole.admin.value,
        )
        patient_user = User(
            email="paciente@consultorio.com",
            full_name="Luciano Wagner",
            document_number="88888888",
            phone="1155667788",
            password_hash=hash_password("paciente1234"),
            role=UserRole.patient.value,
        )
        session.add_all([admin_user, patient_user])
        session.flush()
        
        # 3. Crear Usuarios de Médicos
        doctor_users = [
            User(
                email="ana@consultorio.com",
                full_name="Dra. Ana Pérez",
                document_number="11111111",
                phone="1111111111",
                password_hash=hash_password("doctor1234"),
                role=UserRole.doctor.value,
            ),
            User(
                email="juan@consultorio.com",
                full_name="Dr. Juan Gómez",
                document_number="22222222",
                phone="2222222222",
                password_hash=hash_password("doctor1234"),
                role=UserRole.doctor.value,
            ),
            User(
                email="laura@consultorio.com",
                full_name="Dra. Laura Díaz",
                document_number="33333333",
                phone="3333333333",
                password_hash=hash_password("doctor1234"),
                role=UserRole.doctor.value,
            ),
            User(
                email="maria@consultorio.com",
                full_name="Dra. María Torres",
                document_number="44444444",
                phone="4444444444",
                password_hash=hash_password("doctor1234"),
                role=UserRole.doctor.value,
            ),
        ]
        session.add_all(doctor_users)
        session.flush()
        
        # 4. Crear Perfiles de Médicos en la tabla `doctors` vinculados a sus usuarios
        doctors = [
            Doctor(
                full_name="Dra. Ana Pérez",
                specialty_id=cardiology.id or 0,
                license_number="MN1001",
                user_id=doctor_users[0].id,
            ),
            Doctor(
                full_name="Dr. Juan Gómez",
                specialty_id=clinic.id or 0,
                license_number="MN1002",
                user_id=doctor_users[1].id,
            ),
            Doctor(
                full_name="Dra. Laura Díaz",
                specialty_id=dermatology.id or 0,
                license_number="MN1003",
                user_id=doctor_users[2].id,
            ),
            Doctor(
                full_name="Dra. María Torres",
                specialty_id=pediatrics.id or 0,
                license_number="MN1004",
                user_id=doctor_users[3].id,
            ),
        ]
        session.add_all(doctors)
        session.flush()
        
        # 5. Generar slots para los próximos 14 días laborables
        now = (datetime.now(UTC) - timedelta(hours=3)).replace(tzinfo=None)
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
                    
        session.commit()
        print("Base de datos reseteada e inicializada correctamente.")
        print(f"Admin: admin@consultorio.com / admin1234")
        print(f"Paciente: paciente@consultorio.com / paciente1234")
        print(f"Médicos: [ana, juan, laura, maria]@consultorio.com / doctor1234")
        print(f"Slots creados: {slots_created}")


if __name__ == "__main__":
    import sys
    if "--force" in sys.argv:
        # Reseteo forzado: limpia la BD aunque ya tenga datos
        with Session(engine) as session:
            clean_database(session)
        # Remueve el guard de idempotencia para que run() siembre de cero
        _original = is_already_seeded
        globals()["is_already_seeded"] = lambda s: False
        run()
        globals()["is_already_seeded"] = _original
    else:
        run()
