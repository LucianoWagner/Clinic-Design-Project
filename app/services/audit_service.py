from sqlmodel import Session

from app.models.interaction import InteractionLog


def redact(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


class AuditService:
    def __init__(self, session: Session):
        self.session = session

    def log(
        self,
        interaction_session_id: int,
        event_type: str,
        role: str,
        message_summary: str | None = None,
        tool_name: str | None = None,
        tool_args_redacted: dict | None = None,
        tool_result_summary: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.session.add(
            InteractionLog(
                interaction_session_id=interaction_session_id,
                event_type=event_type,
                role=role,
                message_summary=message_summary,
                tool_name=tool_name,
                tool_args_redacted=tool_args_redacted,
                tool_result_summary=tool_result_summary,
                error_code=error_code,
            )
        )
