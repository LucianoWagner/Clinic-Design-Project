"""
Definición de tools del agente usando el decorator @tool de LangChain.

Patrón: factory build_tools(session, interaction) que devuelve funciones @tool
con closures sobre la sesión de DB y la sesión de interacción.
El LLM solo ve los argumentos de negocio; session e interaction son invisibles para él.
"""
import json
from typing import Any

from langchain_core.tools import tool
from sqlmodel import Session

from app.models.interaction import InteractionSession
from app.schemas.appointment import (
    ConfirmAppointmentToolInput,
    HoldSlotToolInput,
    SearchAvailabilityToolInput,
)
from app.services.appointment_service import (
    AppointmentConflictError,
    AppointmentService,
    AppointmentValidationError,
)
from app.services.audit_service import AuditService, redact


def _log_tool(
    audit: AuditService,
    interaction: InteractionSession,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Registra la ejecución de una tool con PII redactada."""
    redacted = dict(arguments)
    for key in ("document_number", "phone"):
        if key in redacted:
            redacted[key] = redact(str(redacted[key]))
    audit.log(
        interaction.id or 0,
        "tool_call",
        "tool",
        tool_name=tool_name,
        tool_args_redacted=redacted,
        tool_result_summary=json.dumps(result, default=str)[:1000],
    )


def build_tools(session: Session, interaction: InteractionSession) -> list:
    """
    Construye la lista de tools del agente con closures sobre session e interaction.
    Llamar una vez por request/turno para obtener tools con el contexto DB correcto.
    """
    appointments = AppointmentService(session)
    audit = AuditService(session)

    @tool
    def list_specialties_and_doctors() -> dict:
        """
        Lista especialidades y medicos activos del consultorio.
        Usar cuando el usuario pregunte que especialidades hay, que medicos atienden,
        o que medicos hay para cada especialidad. No busca horarios ni disponibilidad.
        """
        args: dict[str, Any] = {}
        try:
            catalog = appointments.list_specialties_and_doctors()
            result: dict[str, Any] = {"ok": True, "specialties": catalog}
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": "Error interno al listar médicos y especialidades."}
        _log_tool(audit, interaction, "list_specialties_and_doctors", args, result)
        return result

    @tool
    def search_availability(
        specialty_name: str | None = None,
        doctor_id: int | None = None,
        limit: int = 5,
    ) -> dict:
        """
        Busca turnos disponibles reales en la base de datos.
        Requiere specialty_name o doctor_id. Nunca inventa disponibilidad.
        Devuelve lista de slots con id, médico, especialidad, fecha y hora.
        """
        args = {"specialty_name": specialty_name, "doctor_id": doctor_id, "limit": limit}
        try:
            payload = SearchAvailabilityToolInput(**args)
            slots = appointments.search_availability(
                specialty_name=payload.specialty_name,
                doctor_id=payload.doctor_id,
                limit=payload.limit,
            )
            interaction.current_state = "presenting_options" if slots else "no_availability"
            session.add(interaction)
            result = {"ok": True, "slots": [slot.model_dump(mode="json") for slot in slots]}
        except (AppointmentValidationError, AppointmentConflictError) as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": "Error interno al buscar disponibilidad."}
        _log_tool(audit, interaction, "search_availability", args, result)
        return result

    @tool
    def hold_slot(slot_id: int) -> dict:
        """
        Retiene temporalmente un turno elegido por el usuario antes de confirmar.
        El slot queda reservado por un tiempo limitado para esta sesión.
        Usar antes de pedir confirmación final al usuario.
        """
        args = {"slot_id": slot_id}
        try:
            payload = HoldSlotToolInput(**args)
            slot = appointments.hold_slot(payload.slot_id, interaction.id or 0)
            interaction.current_state = "awaiting_explicit_confirmation"
            session.add(interaction)
            result = {
                "ok": True,
                "slot_id": slot.id,
                "held_until": slot.held_until.isoformat() if slot.held_until else None,
            }
        except (AppointmentValidationError, AppointmentConflictError) as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": "Error interno al retener el turno."}
        _log_tool(audit, interaction, "hold_slot", args, result)
        return result

    @tool
    def confirm_appointment(explicit_confirmation: bool, slot_id: int | None = None) -> dict:
        """
        Confirma definitivamente el turno retenido. Requiere confirmación explícita del usuario.
        No usar sin que el usuario haya dicho explícitamente que confirma.
        Antes de llamar esta tool, resumir al usuario: paciente, especialidad, médico, fecha y hora.
        """
        args = {"explicit_confirmation": explicit_confirmation, "slot_id": slot_id}
        try:
            payload = ConfirmAppointmentToolInput(**args)
            resolved_slot_id = payload.slot_id or interaction.pending_slot_id
            if not resolved_slot_id:
                result: dict[str, Any] = {"ok": False, "error": "No hay un turno retenido para confirmar."}
            else:
                appointment = appointments.confirm_appointment(
                    slot_id=resolved_slot_id,
                    interaction_session_id=interaction.id or 0,
                    explicit_confirmation=payload.explicit_confirmation,
                )
                interaction.current_state = "confirmed"
                session.add(interaction)
                result = {"ok": True, "appointment": appointment.model_dump(mode="json")}
        except (AppointmentValidationError, AppointmentConflictError) as exc:
            result = {"ok": False, "error": str(exc)}
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": "Error interno al confirmar el turno."}
        _log_tool(audit, interaction, "confirm_appointment", args, result)
        return result

    return [
        list_specialties_and_doctors,
        search_availability,
        hold_slot,
        confirm_appointment,
    ]
