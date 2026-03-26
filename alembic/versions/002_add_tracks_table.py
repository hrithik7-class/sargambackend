"""Add tracks table

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the TrackStatus enum type
    trackstatus_enum = postgresql.ENUM(
        "pending", "generating_audio", "completed", "failed",
        name="trackstatus",
        create_type=False,
    )
    trackstatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("input_prompt", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False, server_default="english"),
        sa.Column("genre", sa.String(length=100), nullable=False, server_default="Pop"),
        sa.Column("generated_lyrics", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "generating_audio", "completed", "failed", name="trackstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("copyright_safe", sa.Boolean(), nullable=True),
        sa.Column("copyright_score", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tracks_id"), "tracks", ["id"], unique=False)
    op.create_index(op.f("ix_tracks_user_id"), "tracks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tracks_user_id"), table_name="tracks")
    op.drop_index(op.f("ix_tracks_id"), table_name="tracks")
    op.drop_table("tracks")
    sa.Enum(name="trackstatus").drop(op.get_bind(), checkfirst=True)
