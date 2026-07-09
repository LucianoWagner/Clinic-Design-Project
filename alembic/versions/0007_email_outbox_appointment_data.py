"""email outbox appointment_data json column

Revision ID: 0007_email_outbox_appt_data
Revises: 0006_doctor_portal_roles
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_email_outbox_appt_data"
down_revision = "0006_doctor_portal_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columna nullable: no afecta filas existentes
    op.add_column(
        "email_outbox",
        sa.Column("appointment_data", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_outbox", "appointment_data")
