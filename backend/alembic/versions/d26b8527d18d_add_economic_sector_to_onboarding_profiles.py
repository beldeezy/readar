"""add economic_sector to onboarding_profiles

Revision ID: d26b8527d18d
Revises: ee4e43888fe6
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d26b8527d18d"
down_revision: str = "ee4e43888fe6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_profiles",
        sa.Column("economic_sector", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("onboarding_profiles", "economic_sector")

