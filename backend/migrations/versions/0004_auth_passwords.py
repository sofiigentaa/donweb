"""add password_hash to customers and sellers

Revision ID: 0004_auth_passwords
Revises: 0003_order_ui_fields
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_auth_passwords"
down_revision = "0003_order_ui_fields"
branch_labels = None
depends_on = None


def _add_column(table: str, column: sa.Column) -> None:
    """Idempotente: 0001 crea las tablas con los modelos actuales, así que en una
    base nueva la columna puede existir ya."""
    existing = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column("customers", sa.Column("password_hash", sa.String(length=255), nullable=True))
    _add_column("sellers", sa.Column("password_hash", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("sellers", "password_hash")
    op.drop_column("customers", "password_hash")
