"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("document_type", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("document_number", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=True),
        sa.Column("insurance_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("insurance_member_id", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patients_document_number", "patients", ["document_number"])
    op.create_index("ix_patients_full_name", "patients", ["full_name"])
    op.create_index("ix_patients_phone", "patients", ["phone"])

    op.create_table(
        "specialties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_specialties_name", "specialties", ["name"], unique=True)

    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("specialty_id", sa.Integer(), nullable=False),
        sa.Column("license_number", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["specialty_id"], ["specialties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctors_full_name", "doctors", ["full_name"])
    op.create_index("ix_doctors_specialty_id", "doctors", ["specialty_id"])

    op.create_table(
        "appointment_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("held_until", sa.DateTime(), nullable=True),
        sa.Column("held_by_interaction_session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "starts_at", name="uq_slot_doctor_start"),
    )
    op.create_index("ix_appointment_slots_doctor_id", "appointment_slots", ["doctor_id"])
    op.create_index("ix_appointment_slots_held_by_interaction_session_id", "appointment_slots", ["held_by_interaction_session_id"])
    op.create_index("ix_appointment_slots_held_until", "appointment_slots", ["held_until"])
    op.create_index("ix_appointment_slots_starts_at", "appointment_slots", ["starts_at"])
    op.create_index("ix_appointment_slots_ends_at", "appointment_slots", ["ends_at"])
    op.create_index("ix_appointment_slots_status", "appointment_slots", ["status"])

    op.create_table(
        "interaction_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("current_state", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("pending_slot_id", sa.Integer(), nullable=True),
        sa.Column("collected_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["pending_slot_id"], ["appointment_slots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interaction_sessions_channel", "interaction_sessions", ["channel"])
    op.create_index("ix_interaction_sessions_current_state", "interaction_sessions", ["current_state"])
    op.create_index("ix_interaction_sessions_patient_id", "interaction_sessions", ["patient_id"])
    op.create_index("ix_interaction_sessions_status", "interaction_sessions", ["status"])
    op.create_foreign_key(
        "fk_slot_held_by_interaction",
        "appointment_slots",
        "interaction_sessions",
        ["held_by_interaction_session_id"],
        ["id"],
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("interaction_session_id", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confirmation_source", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["interaction_session_id"], ["interaction_sessions.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["slot_id"], ["appointment_slots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", name="uq_appointment_slot"),
    )
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index("ix_appointments_interaction_session_id", "appointments", ["interaction_session_id"])
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_slot_id", "appointments", ["slot_id"])
    op.create_index("ix_appointments_status", "appointments", ["status"])

    op.create_table(
        "interaction_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("message_summary", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("tool_name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
        sa.Column("tool_args_redacted", sa.JSON(), nullable=True),
        sa.Column("tool_result_summary", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("error_code", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["interaction_session_id"], ["interaction_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interaction_logs_event_type", "interaction_logs", ["event_type"])
    op.create_index("ix_interaction_logs_interaction_session_id", "interaction_logs", ["interaction_session_id"])
    op.create_index("ix_interaction_logs_role", "interaction_logs", ["role"])


def downgrade() -> None:
    op.drop_table("interaction_logs")
    op.drop_table("appointments")
    op.drop_constraint("fk_slot_held_by_interaction", "appointment_slots", type_="foreignkey")
    op.drop_table("interaction_sessions")
    op.drop_table("appointment_slots")
    op.drop_table("doctors")
    op.drop_table("specialties")
    op.drop_table("patients")
