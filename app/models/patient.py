from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True, min_length=2, max_length=160)
    document_type: str = Field(default="DNI", max_length=20)
    document_number: str = Field(index=True, max_length=40)
    phone: str = Field(index=True, max_length=40)
    email: Optional[str] = Field(default=None, max_length=160)
    insurance_name: Optional[str] = Field(default=None, max_length=120)
    insurance_member_id: Optional[str] = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
