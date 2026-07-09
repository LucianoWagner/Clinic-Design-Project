import json
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
        # Completa el appointment_id en los datos estructurados
        appt_data = dict(email.appointment_data)
        appt_data["appointment_id"] = appointment_id

        outbox = EmailOutbox(
            appointment_id=appointment_id,
            recipient_email=email.recipient_email,
            recipient_name=email.recipient_name,
            subject=email.subject,
            html_body=email.html_body,
            text_body=email.text_body,
            provider=settings.email_provider,
            appointment_data=json.dumps(appt_data, ensure_ascii=False),
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
            # Deserializar appointment_data si existe
            appt_data: dict = {}
            if item.appointment_data:
                try:
                    appt_data = json.loads(item.appointment_data)
                except Exception:  # noqa: BLE001
                    appt_data = {}

            try:
                result = provider.send(
                    recipient_email=item.recipient_email,
                    recipient_name=item.recipient_name,
                    subject=item.subject,
                    html_body=item.html_body,
                    text_body=item.text_body,
                    appointment_data=appt_data,
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

