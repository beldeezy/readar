"""add last_recommendations_email_at to users

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: str = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_recommendations_email_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_recommendations_email_at")
