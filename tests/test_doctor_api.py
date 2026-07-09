import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from datetime import datetime, UTC, timedelta

from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.models.doctor import Doctor, Specialty
from app.models.appointment import AppointmentSlot, Appointment
from app.models.enums import UserRole, SlotStatus, AppointmentStatus


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _setup_doctor_and_patient(client: TestClient) -> dict:
    session = next(app.dependency_overrides[get_session]())
    
    # 1. Create Specialty
    specialty = Specialty(name="Pediatría")
    session.add(specialty)
    session.flush()
    session.commit()
    
    # 2. Register Doctor via API (hashes password correctly)
    doc_reg = client.post("/api/auth/register", json={
        "email": "doctor@test.com",
        "full_name": "Dr. House",
        "document_number": "88888888",
        "phone": "11223344",
        "password": "doctorpassword"
    })
    assert doc_reg.status_code == 200
    doc_user_id = doc_reg.json()["user"]["id"]
    
    # 3. Create Doctor profile and update role
    from sqlmodel import select
    doc_user = session.exec(select(User).where(User.id == doc_user_id)).one()
    doc_user.role = UserRole.doctor.value
    
    doctor = Doctor(
        user_id=doc_user.id,
        specialty_id=specialty.id or 0,
        full_name=doc_user.full_name,
        license_number="MN999"
    )
    session.add(doc_user)
    session.add(doctor)
    session.commit()
    
    # 4. Register Patient via API
    pat_reg = client.post("/api/auth/register", json={
        "email": "patient@test.com",
        "full_name": "John Doe",
        "document_number": "11111111",
        "phone": "55555555",
        "password": "patientpassword"
    })
    assert pat_reg.status_code == 200
    pat_user_id = pat_reg.json()["user"]["id"]
    
    # 5. Login to get tokens
    doc_login = client.post("/api/auth/login", json={
        "email": "doctor@test.com",
        "password": "doctorpassword"
    })
    assert doc_login.status_code == 200
    
    pat_login = client.post("/api/auth/login", json={
        "email": "patient@test.com",
        "password": "patientpassword"
    })
    assert pat_login.status_code == 200
    
    return {
        "doctor_token": doc_login.json()["access_token"],
        "patient_token": pat_login.json()["access_token"],
        "doctor_id": doctor.id,
        "doctor_user_id": doc_user_id,
        "patient_user_id": pat_user_id
    }


def test_doctor_slots_crud(client: TestClient) -> None:
    data = _setup_doctor_and_patient(client)
    doc_headers = {"Authorization": f"Bearer {data['doctor_token']}"}
    pat_headers = {"Authorization": f"Bearer {data['patient_token']}"}
    
    # 1. Create slot
    starts = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = client.post(
        "/api/doctor/slots",
        json={"starts_at": starts, "duration_minutes": 30},
        headers=doc_headers
    )
    assert response.status_code == 200
    slot_id = response.json()["id"]
    assert response.json()["status"] == SlotStatus.available.value
    
    # Patient should NOT be allowed to create slots
    bad_res = client.post(
        "/api/doctor/slots",
        json={"starts_at": starts, "duration_minutes": 30},
        headers=pat_headers
    )
    assert bad_res.status_code == 403
    
    # 2. Get slots
    response = client.get("/api/doctor/slots", headers=doc_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # 3. Update slot
    new_starts = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    response = client.put(
        f"/api/doctor/slots/{slot_id}",
        json={"starts_at": new_starts, "duration_minutes": 45},
        headers=doc_headers
    )
    assert response.status_code == 200
    res_data = response.json()
    starts_dt = datetime.fromisoformat(res_data["starts_at"].replace("Z", "+00:00"))
    ends_dt = datetime.fromisoformat(res_data["ends_at"].replace("Z", "+00:00"))
    duration = (ends_dt - starts_dt).total_seconds() / 60
    assert duration == 45
    
    # 4. Delete slot
    response = client.delete(f"/api/doctor/slots/{slot_id}", headers=doc_headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Horario eliminado correctamente."
    
    # Check slots list is now empty
    response = client.get("/api/doctor/slots", headers=doc_headers)
    assert len(response.json()) == 0


def test_doctor_appointments_flow(client: TestClient) -> None:
    data = _setup_doctor_and_patient(client)
    doc_headers = {"Authorization": f"Bearer {data['doctor_token']}"}
    
    # Direct session inserts to setup a booked slot and appointment
    session = next(app.dependency_overrides[get_session]())
    
    slot = AppointmentSlot(
        doctor_id=data["doctor_id"],
        starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, minutes=30),
        status=SlotStatus.booked.value
    )
    session.add(slot)
    session.flush()
    
    appt = Appointment(
        user_id=data["patient_user_id"],
        doctor_id=data["doctor_id"],
        slot_id=slot.id,
        status=AppointmentStatus.confirmed.value
    )
    session.add(appt)
    session.commit()
    
    # 0. Get slots and verify the booked slot is filtered out
    response_slots = client.get("/api/doctor/slots", headers=doc_headers)
    assert response_slots.status_code == 200
    assert len(response_slots.json()) == 0
    
    # 1. Get doctor's appointments
    response = client.get("/api/doctor/appointments", headers=doc_headers)
    assert response.status_code == 200
    appts = response.json()
    assert len(appts) == 1
    assert appts[0]["patient_name"] == "John Doe"
    assert appts[0]["status"] == AppointmentStatus.confirmed.value
    
    # 2. Cancel appointment
    response = client.patch(
        f"/api/doctor/appointments/{appt.id}/status",
        json={"status": "cancelled"},
        headers=doc_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == AppointmentStatus.cancelled.value
    
    # Verify slot is also cancelled
    session.expire_all()
    slot_db = session.get(AppointmentSlot, slot.id)
    assert slot_db.status == SlotStatus.cancelled.value
