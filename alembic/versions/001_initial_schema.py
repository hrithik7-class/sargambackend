"""Initial schema — users and oauth_accounts tables

Revision ID: 001
Revises:
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── users ───────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    # ─── oauth_accounts ──────────────────────────────────────────────────────
    # Create the enum type first (PostgreSQL requires explicit enum creation)
    oauth_provider_enum = postgresql.ENUM("google", "facebook", name="oauthprovider", create_type=False)
    oauth_provider_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("google", "facebook", name="oauthprovider"),
            nullable=False,
        ),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("access_token", sa.String(length=512), nullable=True),
        sa.Column("refresh_token", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_accounts_id"), "oauth_accounts", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oauth_accounts_id"), table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    # Drop the enum type
    sa.Enum(name="oauthprovider").drop(op.get_bind(), checkfirst=True)
