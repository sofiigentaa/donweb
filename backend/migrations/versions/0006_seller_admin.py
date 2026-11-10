"""add is_admin to sellers

Revision ID: 0006_seller_admin
Revises: 0005_totp_sellers
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_seller_admin"
down_revision = "0005_totp_sellers"


def _add_column(table: str, column: sa.Column) -> None:
    """Idempotente: 0001 crea las tablas con los modelos actuales, así que en una
    base nueva la columna puede existir ya."""
    existing = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column(
        "sellers",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("sellers", "is_admin")
