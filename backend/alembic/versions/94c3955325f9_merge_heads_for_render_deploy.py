"""merge heads for render deploy

Revision ID: 94c3955325f9
Revises: merge_heads_book_status_auth
Create Date: 2025-12-20 09:01:53.183963

Note: This was originally a merge migration, but we've linearized the chain.
This now just follows merge_heads_book_status_auth.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94c3955325f9'
down_revision: Union[str, None] = 'merge_heads_book_status_auth'  # Linear chain: comes after merge_heads_book_status_auth
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

