"""doctor portal roles

Revision ID: 0006_doctor_portal_roles
Revises: 0005_email_outbox
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0006_doctor_portal_roles"
down_revision = "0005_email_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role to users
    op.add_column("users", sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False, server_default="patient"))
    op.create_index("ix_users_role", "users", ["role"])
    
    # Add user_id to doctors
    op.add_column("doctors", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("doctors_user_id_fkey", "doctors", "users", ["user_id"], ["id"])
    op.create_index("ix_doctors_user_id", "doctors", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_doctors_user_id", table_name="doctors")
    op.drop_constraint("doctors_user_id_fkey", "doctors", type_="foreignkey")
    op.drop_column("doctors", "user_id")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
