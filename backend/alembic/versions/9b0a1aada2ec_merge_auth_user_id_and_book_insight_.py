"""merge auth_user_id and book_insight_fields

Revision ID: 9b0a1aada2ec
Revises: add_auth_user_id, cb17facfbf15
Create Date: 2025-12-18 16:47:43.773947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b0a1aada2ec'
down_revision: Union[str, None] = ('add_auth_user_id', 'cb17facfbf15')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

