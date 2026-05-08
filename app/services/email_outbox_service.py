from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.config import settings
from app.models.email import EmailOutbox
from app.services.appointment_email_builder import AppointmentEmail
from app.services.email_provider import EmailProvider, build_email_provider


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EmailOutboxService:
    def __init__(self, session: Session, provider: EmailProvider | None = None):
        self.session = session
        self.provider = provider

    def enqueue_appointment_confirmation(
        self, *, appointment_id: int, email: AppointmentEmail
    ) -> EmailOutbox:
        outbox = EmailOutbox(
            appointment_id=appointment_id,
            recipient_email=email.recipient_email,
            recipient_name=email.recipient_name,
            subject=email.subject,
            html_body=email.html_body,
            text_body=email.text_body,
            provider=settings.email_provider,
        )
        self.session.add(outbox)
        return outbox

    def dispatch_pending(self, limit: int = 10) -> list[EmailOutbox]:
        if not settings.email_enabled:
            return []

        provider = self.provider or build_email_provider()
        if not provider:
            return []

        statement = (
            select(EmailOutbox)
            .where(EmailOutbox.status == "pending")
            .order_by(EmailOutbox.created_at, EmailOutbox.id)
            .limit(limit)
        )
        pending = list(self.session.exec(statement).all())
        dispatched: list[EmailOutbox] = []
        for item in pending:
            try:
                result = provider.send(
                    recipient_email=item.recipient_email,
                    subject=item.subject,
                    html_body=item.html_body,
                    text_body=item.text_body,
                )
            except Exception as exc:  # noqa: BLE001
                item.status = "failed"
                item.attempt_count += 1
                item.last_error = str(exc)[:1000]
                item.updated_at = utcnow()
                self.session.add(item)
                dispatched.append(item)
                continue

            item.status = "sent"
            item.attempt_count += 1
            item.provider_message_id = result.provider_message_id
            item.last_error = None
            item.sent_at = utcnow()
            item.updated_at = item.sent_at
            self.session.add(item)
            dispatched.append(item)

        if dispatched:
            self.session.commit()
        return dispatched
