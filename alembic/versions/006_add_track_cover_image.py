"""add cover_image_url to tracks

Revision ID: 006
Revises: 005
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("cover_image_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("tracks", "cover_image_url")
