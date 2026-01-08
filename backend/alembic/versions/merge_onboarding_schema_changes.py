"""merge onboarding schema changes

Merges:
- d26b8527d18d (add_economic_sector_to_onboarding_profiles)
- make_onboarding_full_name_nullable

Revision ID: merge_onboarding_schema_changes
Revises: d26b8527d18d, make_onboarding_full_name_nullable
Create Date: 2025-01-07

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'merge_onboarding_schema_changes'
down_revision: Union[str, Sequence[str]] = ('d26b8527d18d', 'make_onboarding_full_name_nullable')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes needed, just merges branches."""
    pass


def downgrade() -> None:
    """Merge migration - no schema changes to revert."""
    pass
