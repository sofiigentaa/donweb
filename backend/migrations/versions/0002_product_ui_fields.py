"""add UI fields to products (min_age, stock_trust, color)

Revision ID: 0002_product_ui_fields
Revises: 0001_initial
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_product_ui_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None



def _add_column(table: str, column: sa.Column) -> None:
    """Idempotente: 0001 crea las tablas con los modelos actuales, así que en una
    base nueva la columna puede existir ya."""
    existing = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column("products", sa.Column("min_age", sa.Integer(), nullable=True))
    _add_column(
        "products",
        sa.Column(
            "stock_trust",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'al día'"),
        ),
    )
    _add_column("products", sa.Column("color", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "color")
    op.drop_column("products", "stock_trust")
    op.drop_column("products", "min_age")
