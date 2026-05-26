from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Specialty(SQLModel, table=True):
    __tablename__ = "specialties"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=120)
    is_active: bool = Field(default=True)
    doctors: list["Doctor"] = Relationship(back_populates="specialty")


class Doctor(SQLModel, table=True):
    __tablename__ = "doctors"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True, max_length=160)
    specialty_id: int = Field(foreign_key="specialties.id", index=True)
    license_number: str = Field(max_length=80)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", unique=True, index=True)
    is_active: bool = Field(default=True)
    specialty: Specialty = Relationship(back_populates="doctors")
