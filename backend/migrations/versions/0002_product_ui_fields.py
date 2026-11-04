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


def upgrade() -> None:
    op.add_column("products", sa.Column("min_age", sa.Integer(), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "stock_trust",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'al día'"),
        ),
    )
    op.add_column("products", sa.Column("color", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "color")
    op.drop_column("products", "stock_trust")
    op.drop_column("products", "min_age")
