from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_session, require_role
from app.models.appointment import Appointment, AppointmentSlot
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, SlotStatus, UserRole
from app.models.user import User
from app.schemas.appointment import (
    DoctorAppointmentRead,
    DoctorAppointmentStatusUpdate,
    DoctorSlotCreate,
    DoctorSlotRead,
)

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _get_doctor_profile(user_id: int, session: Session) -> Doctor:
    doctor = session.exec(select(Doctor).where(Doctor.user_id == user_id)).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un perfil de médico para este usuario.",
        )
    return doctor


@router.get("/appointments", response_model=list[DoctorAppointmentRead])
def get_doctor_appointments(
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    statement = (
        select(Appointment, AppointmentSlot, User)
        .join(AppointmentSlot, Appointment.slot_id == AppointmentSlot.id)
        .join(User, Appointment.user_id == User.id)
        .where(Appointment.doctor_id == doctor.id)
        .order_by(AppointmentSlot.starts_at.desc())
    )
    results = session.exec(statement).all()
    
    now = (datetime.now(UTC) - timedelta(hours=3)).replace(tzinfo=None)
    appointments = []
    
    for app, slot, patient in results:
        # Calcular estado finalizado si ya pasó y estaba confirmado
        app_status = app.status
        if app_status == AppointmentStatus.confirmed.value and slot.ends_at < now:
            app_status = AppointmentStatus.finished.value
            
        appointments.append(
            DoctorAppointmentRead(
                id=app.id or 0,
                patient_name=patient.full_name,
                patient_email=patient.email,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                status=app_status,
                confirmed_at=app.confirmed_at,
            )
        )
    return appointments


@router.patch("/appointments/{id}/status", response_model=DoctorAppointmentRead)
def update_appointment_status(
    id: int,
    data: DoctorAppointmentStatusUpdate,
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    app = session.get(Appointment, id)
    if not app or app.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno no encontrado.",
        )
        
    new_status = data.status.lower()
    if new_status not in [AppointmentStatus.confirmed.value, AppointmentStatus.cancelled.value, AppointmentStatus.finished.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado inválido. Debe ser 'confirmed', 'cancelled' o 'finished'.",
        )
        
    app.status = new_status
    session.add(app)
    
    # Actualizar estado de la ranura asociada (slot)
    slot = session.get(AppointmentSlot, app.slot_id)
    if slot:
        if new_status == AppointmentStatus.cancelled.value:
            slot.status = SlotStatus.cancelled.value
        elif new_status == AppointmentStatus.confirmed.value:
            slot.status = SlotStatus.booked.value
        elif new_status == AppointmentStatus.finished.value:
            slot.status = SlotStatus.booked.value  # se mantiene booked
        session.add(slot)
        
    session.commit()
    session.refresh(app)
    
    patient = session.get(User, app.user_id)
    slot = session.get(AppointmentSlot, app.slot_id)
    
    return DoctorAppointmentRead(
        id=app.id or 0,
        patient_name=patient.full_name if patient else "Paciente",
        patient_email=patient.email if patient else "",
        starts_at=slot.starts_at if slot else datetime.now(),
        ends_at=slot.ends_at if slot else datetime.now(),
        status=app.status,
        confirmed_at=app.confirmed_at,
    )


@router.get("/slots", response_model=list[DoctorSlotRead])
def get_doctor_slots(
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    statement = (
        select(AppointmentSlot)
        .where(AppointmentSlot.doctor_id == doctor.id)
        .where(AppointmentSlot.status != SlotStatus.booked.value)
        .order_by(AppointmentSlot.starts_at.desc())
    )
    slots = session.exec(statement).all()
    return [
        DoctorSlotRead(
            id=slot.id or 0,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            status=slot.status,
        )
        for slot in slots
    ]


@router.post("/slots", response_model=DoctorSlotRead)
def create_doctor_slot(
    data: DoctorSlotCreate,
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    starts_at = data.starts_at
    ends_at = starts_at + timedelta(minutes=data.duration_minutes)
    
    # Validar solapamiento
    statement = (
        select(AppointmentSlot)
        .where(AppointmentSlot.doctor_id == doctor.id)
        .where(
            (AppointmentSlot.starts_at < ends_at) & (AppointmentSlot.ends_at > starts_at)
        )
    )
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un turno configurado que se solapa con este horario.",
        )
        
    slot = AppointmentSlot(
        doctor_id=doctor.id or 0,
        starts_at=starts_at,
        ends_at=ends_at,
        status=SlotStatus.available.value,
    )
    session.add(slot)
    session.commit()
    session.refresh(slot)
    
    return DoctorSlotRead(
        id=slot.id or 0,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=slot.status,
    )


@router.put("/slots/{id}", response_model=DoctorSlotRead)
def update_doctor_slot(
    id: int,
    data: DoctorSlotCreate,
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    slot = session.get(AppointmentSlot, id)
    if not slot or slot.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horario no encontrado.",
        )
        
    if slot.status == SlotStatus.booked.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar un horario que ya tiene un turno confirmado reservado.",
        )
        
    starts_at = data.starts_at
    ends_at = starts_at + timedelta(minutes=data.duration_minutes)
    
    # Validar solapamiento con otros slots excluyendo el actual
    statement = (
        select(AppointmentSlot)
        .where(AppointmentSlot.doctor_id == doctor.id)
        .where(AppointmentSlot.id != id)
        .where(
            (AppointmentSlot.starts_at < ends_at) & (AppointmentSlot.ends_at > starts_at)
        )
    )
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe otro turno que se solapa con el nuevo horario propuesto.",
        )
        
    slot.starts_at = starts_at
    slot.ends_at = ends_at
    session.add(slot)
    session.commit()
    session.refresh(slot)
    
    return DoctorSlotRead(
        id=slot.id or 0,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=slot.status,
    )


@router.delete("/slots/{id}")
def delete_doctor_slot(
    id: int,
    current_user: User = Depends(require_role(UserRole.doctor)),
    session: Session = Depends(get_session),
):
    doctor = _get_doctor_profile(current_user.id, session)
    
    slot = session.get(AppointmentSlot, id)
    if not slot or slot.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horario no encontrado.",
        )
        
    if slot.status == SlotStatus.booked.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar un horario que tiene un turno confirmado reservado.",
        )
        
    session.delete(slot)
    session.commit()
    return {"detail": "Horario eliminado correctamente."}
