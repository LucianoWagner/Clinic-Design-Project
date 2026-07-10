from dataclasses import dataclass, field
from html import escape
from typing import Any

from app.models.appointment import AppointmentSlot
from app.models.doctor import Doctor, Specialty
from app.models.user import User


@dataclass(frozen=True)
class AppointmentEmail:
    recipient_email: str
    recipient_name: str
    subject: str
    html_body: str
    text_body: str
    # Campos estructurados para proveedores que construyen su propio HTML (ej. n8n)
    appointment_data: dict[str, Any] = field(default_factory=dict)


class AppointmentEmailBuilder:
    def build(
        self,
        *,
        user: User,
        doctor: Doctor,
        specialty: Specialty,
        slot: AppointmentSlot,
        confirmation_code: str,
        qr_image_base64: str | None = None,
        checkin_token: str | None = None,
    ) -> AppointmentEmail:
        starts_at = slot.starts_at.strftime("%d/%m/%Y %H:%M")
        ends_at = slot.ends_at.strftime("%H:%M")
        subject = f"Confirmacion de turno {confirmation_code}"
        text_body = (
            f"Hola {user.full_name},\n\n"
            "Tu turno fue confirmado.\n\n"
            f"Codigo de confirmacion: {confirmation_code}\n"
            f"Especialidad: {specialty.name}\n"
            f"Profesional: {doctor.full_name}\n"
            f"Fecha y hora: {starts_at} a {ends_at}\n\n"
            "Si necesitás modificarlo o cancelarlo, contactá al consultorio.\n"
        )
        html_body = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.5;color:#0f172a">
          <h2>Turno confirmado</h2>
          <p>Hola {escape(user.full_name)},</p>
          <p>Tu turno fue confirmado correctamente.</p>
          <table cellpadding="6" cellspacing="0" style="border-collapse:collapse">
            <tr><td><strong>Codigo</strong></td><td>{escape(confirmation_code)}</td></tr>
            <tr><td><strong>Especialidad</strong></td><td>{escape(specialty.name)}</td></tr>
            <tr><td><strong>Profesional</strong></td><td>{escape(doctor.full_name)}</td></tr>
            <tr><td><strong>Fecha y hora</strong></td><td>{escape(starts_at)} a {escape(ends_at)}</td></tr>
          </table>
          <p>Si necesitas modificarlo o cancelarlo, contacta al consultorio.</p>
        </div>
        """
        appointment_data: dict = {
            "confirmation_code": confirmation_code,
            "doctor_name": doctor.full_name,
            "specialty": specialty.name,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "appointment_id": None,  # Se completa al encolar en EmailOutboxService
        }
        if qr_image_base64:
            appointment_data["qr_image_base64"] = qr_image_base64
        if checkin_token:
            appointment_data["checkin_token"] = checkin_token

        return AppointmentEmail(
            recipient_email=user.email,
            recipient_name=user.full_name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            appointment_data=appointment_data,
        )

