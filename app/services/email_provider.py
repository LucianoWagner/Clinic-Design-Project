from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str | None = None


class EmailProvider(Protocol):
    def send(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        text_body: str,
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
        subject: str,
        html_body: str,
        text_body: str,
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
    if settings.email_provider != "resend":
        return None
    if not settings.resend_api_key:
        return None
    return ResendEmailProvider(settings.resend_api_key, settings.email_from)
