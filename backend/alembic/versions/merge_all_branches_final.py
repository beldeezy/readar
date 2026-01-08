"""merge all branches - final consolidation

Merges all 9 migration heads into a single head:
- 1a2b3c4d5e6f (widen_alembic_version)
- 6fb58de6fce8 (update_user_book_status_enum_to_4_states)
- 80a813719b89 (merge_heads book status + auth)
- 9b0a1aada2ec (merge auth_user_id and book_insight)
- add_event_logs_table (event logs feature)
- aeba55c429cd (add_entrepreneur_status_to_onboarding)
- 8a9b0c1d2e3f (ensure_auth_user_id_unique_constraint - auth constraint)
- fix_subscription_status_enum (subscription enum fix)
- merge_onboarding_schema_changes (onboarding merge)

Revision ID: merge_all_branches_final
Revises: 1a2b3c4d5e6f, 6fb58de6fce8, 80a813719b89, 9b0a1aada2ec, add_event_logs_table, aeba55c429cd, 8a9b0c1d2e3f, fix_subscription_status_enum, merge_onboarding_schema_changes
Create Date: 2025-01-07

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'merge_all_branches_final'
down_revision: Union[str, Sequence[str]] = (
    '1a2b3c4d5e6f',
    '6fb58de6fce8',
    '80a813719b89',
    '9b0a1aada2ec',
    'add_event_logs_table',
    'aeba55c429cd',
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
