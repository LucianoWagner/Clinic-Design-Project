"""users auth clean mvp

Revision ID: 0003_users_auth_clean_mvp
Revises: 0002_unaccent
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0003_users_auth_clean_mvp"
down_revision = "0002_unaccent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM interaction_logs")
    op.execute("DELETE FROM appointments")
    op.execute(
        "UPDATE appointment_slots SET held_by_interaction_session_id = NULL, "
        "held_until = NULL, status = 'available'"
    )
    op.execute("DELETE FROM interaction_sessions")
    op.execute("DELETE FROM patients")
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.checkpoint_writes') IS NOT NULL THEN
                DELETE FROM checkpoint_writes;
            END IF;
            IF to_regclass('public.checkpoint_blobs') IS NOT NULL THEN
                DELETE FROM checkpoint_blobs;
            END IF;
            IF to_regclass('public.checkpoints') IS NOT NULL THEN
                DELETE FROM checkpoints;
            END IF;
        END $$;
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("document_number", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_document_number", "users", ["document_number"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_full_name", "users", ["full_name"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_phone", "users", ["phone"])

    op.add_column("interaction_sessions", sa.Column("user_id", sa.Integer(), nullable=False))
    op.drop_constraint(
        "interaction_sessions_patient_id_fkey", "interaction_sessions", type_="foreignkey"
    )
    op.drop_index("ix_interaction_sessions_patient_id", table_name="interaction_sessions")
    op.create_index("ix_interaction_sessions_user_id", "interaction_sessions", ["user_id"])
    op.create_foreign_key(
        "interaction_sessions_user_id_fkey", "interaction_sessions", "users", ["user_id"], ["id"]
    )
    op.drop_column("interaction_sessions", "patient_id")

    op.add_column("appointments", sa.Column("user_id", sa.Integer(), nullable=False))
    op.drop_constraint("appointments_patient_id_fkey", "appointments", type_="foreignkey")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.create_index("ix_appointments_user_id", "appointments", ["user_id"])
    op.create_foreign_key("appointments_user_id_fkey", "appointments", "users", ["user_id"], ["id"])
    op.drop_column("appointments", "patient_id")

    op.drop_table("patients")


def downgrade() -> None:
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

    op.add_column("appointments", sa.Column("patient_id", sa.Integer(), nullable=True))
    op.drop_constraint("appointments_user_id_fkey", "appointments", type_="foreignkey")
    op.drop_index("ix_appointments_user_id", table_name="appointments")
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_foreign_key(
        "appointments_patient_id_fkey", "appointments", "patients", ["patient_id"], ["id"]
    )
    op.drop_column("appointments", "user_id")

    op.add_column("interaction_sessions", sa.Column("patient_id", sa.Integer(), nullable=True))
    op.drop_constraint(
        "interaction_sessions_user_id_fkey", "interaction_sessions", type_="foreignkey"
    )
    op.drop_index("ix_interaction_sessions_user_id", table_name="interaction_sessions")
    op.create_index("ix_interaction_sessions_patient_id", "interaction_sessions", ["patient_id"])
    op.create_foreign_key(
        "interaction_sessions_patient_id_fkey",
        "interaction_sessions",
        "patients",
        ["patient_id"],
        ["id"],
    )
    op.drop_column("interaction_sessions", "user_id")

    op.drop_table("users")
