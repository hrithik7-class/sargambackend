"""Add subscriptions table

Revision ID: 005
Revises: 004
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    paymentprovider_enum = postgresql.ENUM(
        "lemonsqueezy", "razorpay",
        name="paymentprovider",
        create_type=False,
    )
    paymentprovider_enum.create(op.get_bind(), checkfirst=True)

    subscriptionstatus_enum = postgresql.ENUM(
        "active", "cancelled", "expired", "past_due",
        name="subscriptionstatus",
        create_type=False,
    )
    subscriptionstatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("lemonsqueezy", "razorpay", name="paymentprovider"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("plan_slug", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", "expired", "past_due", name="subscriptionstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("current_period_ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscriptions_id"), "subscriptions", ["id"], unique=False)
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_external_id"), "subscriptions", ["external_id"], unique=False)
    op.create_unique_constraint(
        "uq_subscriptions_provider_external_id",
        "subscriptions",
        ["provider", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_subscriptions_provider_external_id", "subscriptions", type_="unique")
    op.drop_index(op.f("ix_subscriptions_external_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    sa.Enum(name="subscriptionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="paymentprovider").drop(op.get_bind(), checkfirst=True)
