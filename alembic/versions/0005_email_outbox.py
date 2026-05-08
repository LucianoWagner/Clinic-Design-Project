"""email outbox

Revision ID: 0005_email_outbox
Revises: 0004_conversation_history
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0005_email_outbox"
down_revision = "0004_conversation_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("recipient_name", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=False),
        sa.Column("subject", sqlmodel.sql.sqltypes.AutoString(length=240), nullable=False),
        sa.Column("html_body", sqlmodel.sql.sqltypes.AutoString(length=12000), nullable=False),
        sa.Column("text_body", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("provider_message_id", sqlmodel.sql.sqltypes.AutoString(length=160), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_outbox_appointment_id", "email_outbox", ["appointment_id"])
    op.create_index("ix_email_outbox_created_at", "email_outbox", ["created_at"])
    op.create_index("ix_email_outbox_provider", "email_outbox", ["provider"])
    op.create_index("ix_email_outbox_recipient_email", "email_outbox", ["recipient_email"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_index("ix_email_outbox_recipient_email", table_name="email_outbox")
    op.drop_index("ix_email_outbox_provider", table_name="email_outbox")
    op.drop_index("ix_email_outbox_created_at", table_name="email_outbox")
    op.drop_index("ix_email_outbox_appointment_id", table_name="email_outbox")
    op.drop_table("email_outbox")
