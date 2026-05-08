"""conversation history retention

Revision ID: 0004_conversation_history
Revises: 0003_users_auth_clean_mvp
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0004_conversation_history"
down_revision = "0003_users_auth_clean_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_session_id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(length=8000), nullable=False),
        sa.Column("input_mode", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["interaction_session_id"], ["interaction_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_created_at", "conversation_messages", ["created_at"]
    )
    op.create_index(
        "ix_conversation_messages_input_mode", "conversation_messages", ["input_mode"]
    )
    op.create_index(
        "ix_conversation_messages_interaction_session_id",
        "conversation_messages",
        ["interaction_session_id"],
    )
    op.create_index("ix_conversation_messages_role", "conversation_messages", ["role"])

    op.drop_constraint("appointments_interaction_session_id_fkey", "appointments", type_="foreignkey")
    op.drop_index("ix_appointments_interaction_session_id", table_name="appointments")
    op.drop_column("appointments", "interaction_session_id")


def downgrade() -> None:
    op.add_column("appointments", sa.Column("interaction_session_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "appointments_interaction_session_id_fkey",
        "appointments",
        "interaction_sessions",
        ["interaction_session_id"],
        ["id"],
    )
    op.create_index(
        "ix_appointments_interaction_session_id",
        "appointments",
        ["interaction_session_id"],
    )
    op.drop_index("ix_conversation_messages_role", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_interaction_session_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_input_mode", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_created_at", table_name="conversation_messages")
    op.drop_table("conversation_messages")
