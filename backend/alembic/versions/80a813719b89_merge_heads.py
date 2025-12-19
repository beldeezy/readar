"""merge heads

Revision ID: 80a813719b89
Revises: 9b0a1aada2ec, add_event_logs_table
Create Date: 2025-12-19 13:25:39.069657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80a813719b89'
down_revision: Union[str, None] = ('9b0a1aada2ec', 'add_event_logs_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

