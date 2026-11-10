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



def _add_column(table: str, column: sa.Column) -> None:
    """Idempotente: 0001 crea las tablas con los modelos actuales, así que en una
    base nueva la columna puede existir ya."""
    existing = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column("orders", sa.Column("availability", sa.String(length=20), nullable=True))
    _add_column("orders", sa.Column("payment_status", sa.String(length=30), nullable=True))
    _add_column("orders", sa.Column("origin", sa.String(length=20), nullable=True))
    _add_column(
        "orders",
        sa.Column("gift_wrap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("orders", "gift_wrap")
    op.drop_column("orders", "origin")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "availability")
