"""Add published_at to tracks table

Revision ID: 003
Revises: 002
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracks", "published_at")
