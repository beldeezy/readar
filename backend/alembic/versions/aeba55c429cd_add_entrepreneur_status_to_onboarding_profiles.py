"""add entrepreneur_status to onboarding_profiles

Revision ID: aeba55c429cd
Revises: d26b8527d18d
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aeba55c429cd"
down_revision: str = "d26b8527d18d"  # Linear chain: comes after d26b8527d18d
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_profiles",
        sa.Column("entrepreneur_status", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("onboarding_profiles", "entrepreneur_status")

