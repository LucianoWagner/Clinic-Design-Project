"""add_checkin_token_to_appointments

Revision ID: 28fcb542505e
Revises: 0007_email_outbox_appt_data
Create Date: 2026-07-10 14:32:33.603753
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = '28fcb542505e'
down_revision = '0007_email_outbox_appt_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'appointments',
        sa.Column('checkin_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        'ix_appointments_checkin_token',
        'appointments',
        ['checkin_token'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_appointments_checkin_token', table_name='appointments')
    op.drop_column('appointments', 'checkin_token')
