"""Agrega la extensión unaccent de PostgreSQL para búsquedas sin acento.

Revision ID: 0002_unaccent
Revises: 0001_initial
Create Date: 2026-05-04
"""
from alembic import op

revision = "0002_unaccent"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # unaccent es una extensión incluida por defecto en postgres-alpine.
    # Permite usar func.unaccent() en queries SQLAlchemy para hacer
    # búsquedas insensibles a tildes (ej: "cardiologia" == "cardiología").
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent")
