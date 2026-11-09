"""add totp_secret to sellers

Revision ID: 0005_totp_sellers
Revises: 0004_auth_passwords
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_totp_sellers"
down_revision = "0004_auth_passwords"

def upgrade() -> None:
    op.add_column("sellers", sa.Column("totp_secret", sa.String(length=32), nullable=True))

def downgrade() -> None:
    op.drop_column("sellers", "totp_secret")
