"""add totp_secret to sellers

Revision ID: 0005_totp_sellers
Revises: 0004_auth_passwords
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_totp_sellers"
down_revision = "0004_auth_passwords"


def _add_column(table: str, column: sa.Column) -> None:
    """Idempotente: 0001 crea las tablas con los modelos actuales, así que en una
    base nueva la columna puede existir ya."""
    existing = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column("sellers", sa.Column("totp_secret", sa.String(length=32), nullable=True))

def downgrade() -> None:
    op.drop_column("sellers", "totp_secret")
