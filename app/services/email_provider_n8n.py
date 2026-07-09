"""
Proveedor de email que despacha a n8n vía webhook HTTP.

n8n recibe el payload JSON con los datos del turno y se encarga de:
- Componer el HTML del email (en el nodo Send Email).
- Enviarlo vía SMTP/Gmail.

El backend nunca habla directamente con el servidor SMTP: eso es responsabilidad de n8n.
"""
from typing import Any

import httpx

from app.services.email_provider import EmailSendResult


class N8nWebhookProvider:
    """
    Implementa el protocolo EmailProvider despachando a un webhook de n8n.

    El webhook espera un POST JSON con la siguiente estructura:
    {
        "recipient_email": "paciente@gmail.com",
        "recipient_name": "Luciano Wagner",
        "subject": "Confirmacion de turno TRN-0042",
        "confirmation_code": "TRN-0042",
        "doctor_name": "Dra. Ana Pérez",
        "specialty": "cardiología",
        "starts_at": "27/05/2026 14:00",
        "ends_at": "14:30",
        "appointment_id": 42,
        "html_body": "..."   # fallback: HTML pre-generado por el backend
    }
    """

    TIMEOUT_SECONDS = 10

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(
        self,
        *,
        recipient_email: str,
        recipient_name: str = "",
        subject: str,
        html_body: str,
        text_body: str,
        appointment_data: dict[str, Any] | None = None,
    ) -> EmailSendResult:
        payload: dict[str, Any] = {
            "recipient_email": recipient_email,
            "recipient_name": recipient_name,
            "subject": subject,
            # Campos individuales del turno (para que n8n arme su propio HTML)
            **(appointment_data or {}),
            # html_body como fallback por si n8n lo necesita
            "html_body": html_body,
        }

        response = httpx.post(
            self.webhook_url,
            json=payload,
            timeout=self.TIMEOUT_SECONDS,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"n8n webhook respondió con error {response.status_code}: {response.text[:200]}"
            )

        # n8n puede responder con un body JSON o vacío; ambos son éxito
        try:
            body = response.json()
            message_id = str(body.get("id") or body.get("executionId") or "")
        except Exception:  # noqa: BLE001
            message_id = str(response.status_code)

        return EmailSendResult(provider_message_id=message_id or None)
