"""add daily refresh metering to users

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: str = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("daily_refresh_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("daily_refresh_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "daily_refresh_date")
    op.drop_column("users", "daily_refresh_count")
