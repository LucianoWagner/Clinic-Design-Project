from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str | None = None


class EmailProvider(Protocol):
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
        ...


class ResendEmailProvider:
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(
        self,
        *,
        recipient_email: str,
        recipient_name: str = "",
        subject: str,
        html_body: str,
        text_body: str,
        appointment_data: dict[str, Any] | None = None,  # ignorado por Resend
    ) -> EmailSendResult:
        import resend

        resend.api_key = self.api_key
        response = resend.Emails.send(
            {
                "from": self.sender,
                "to": [recipient_email],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }
        )
        if isinstance(response, dict):
            return EmailSendResult(provider_message_id=response.get("id"))
        return EmailSendResult(provider_message_id=getattr(response, "id", None))


def build_email_provider() -> EmailProvider | None:
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            return None
        return ResendEmailProvider(settings.resend_api_key, settings.email_from)
    if settings.email_provider == "n8n":
        from app.services.email_provider_n8n import N8nWebhookProvider
        if not settings.n8n_webhook_url:
            return None
        return N8nWebhookProvider(settings.n8n_webhook_url)
    return None

