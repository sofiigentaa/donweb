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

def upgrade() -> None:
    op.add_column("customers", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("sellers", sa.Column("password_hash", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("sellers", "password_hash")
    op.drop_column("customers", "password_hash")
