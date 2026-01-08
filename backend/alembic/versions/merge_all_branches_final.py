"""merge all branches - final consolidation

Merges the 4 actual migration heads that exist at this point:
- 1a2b3c4d5e6f (widen_alembic_version - independent branch)
- 8a9b0c1d2e3f (ensure_auth_user_id_unique_constraint - auth chain)
- fix_subscription_status_enum (subscription enum fix chain)
- merge_onboarding_schema_changes (onboarding merge - dead-end branch)

Note: Other revisions from the original merge have already been
consolidated by intermediate merge migrations in their respective chains.

Revision ID: merge_all_branches_final
Revises: 1a2b3c4d5e6f, 8a9b0c1d2e3f, fix_subscription_status_enum, merge_onboarding_schema_changes
Create Date: 2025-01-07

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'merge_all_branches_final'
down_revision: Union[str, Sequence[str]] = (
    '1a2b3c4d5e6f',
    '8a9b0c1d2e3f',
    'fix_subscription_status_enum',
    'merge_onboarding_schema_changes',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes needed.

    All parent migrations have already been applied.
    This just consolidates the migration tree into a single head.
    """
    pass


def downgrade() -> None:
    """Merge migration - no schema changes to revert."""
    pass
