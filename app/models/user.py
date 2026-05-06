from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=160)
    full_name: str = Field(index=True, min_length=2, max_length=160)
    document_number: str = Field(index=True, unique=True, max_length=40)
    phone: str = Field(index=True, max_length=40)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
