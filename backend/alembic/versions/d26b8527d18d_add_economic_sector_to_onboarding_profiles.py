"""add economic_sector to onboarding_profiles

Revision ID: d26b8527d18d
Revises: f1a2b3c4d5e6
Create Date: 2025-12-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d26b8527d18d"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"  # Linear chain: comes after f1a2b3c4d5e6
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_profiles",
        sa.Column("economic_sector", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("onboarding_profiles", "economic_sector")

