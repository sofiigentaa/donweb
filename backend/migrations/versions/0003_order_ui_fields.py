"""add UI fields to orders (availability, payment_status, origin, gift_wrap)

Revision ID: 0003_order_ui_fields
Revises: 0002_product_ui_fields
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_order_ui_fields"
down_revision = "0002_product_ui_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("availability", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("payment_status", sa.String(length=30), nullable=True))
    op.add_column("orders", sa.Column("origin", sa.String(length=20), nullable=True))
    op.add_column(
        "orders",
        sa.Column("gift_wrap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("orders", "gift_wrap")
    op.drop_column("orders", "origin")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "availability")
