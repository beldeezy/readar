"""merge_all_heads_final_deploy

Revision ID: c7bbe6aea939
Revises: 77f670469d60, c7d8e9f0a1b2, d8e9f0a1b2c3
Create Date: 2026-03-19 17:45:24.074924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7bbe6aea939'
down_revision: Union[str, None] = ('77f670469d60', 'c7d8e9f0a1b2', 'd8e9f0a1b2c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

