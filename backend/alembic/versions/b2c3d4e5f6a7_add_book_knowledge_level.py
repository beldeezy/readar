"""add knowledge_level to books

Adds an integer altitude score (1-5) per book — how foundational vs tactical
the book is — powering the depth indicator on the Founder Knowledge Map.

Revision ID: b2c3d4e5f6a7
Revises: 7a8b9c0d1e2f
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("books", sa.Column("knowledge_level", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "knowledge_level")
