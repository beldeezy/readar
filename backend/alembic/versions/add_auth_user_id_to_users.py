"""add_auth_user_id_to_users

Revision ID: add_auth_user_id
Revises: f1a2b3c4d5e6
Create Date: 2025-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "add_auth_user_id"
down_revision: str = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auth_user_id column
    op.add_column('users', sa.Column('auth_user_id', sa.String(), nullable=True))
    
    # Create unique index on auth_user_id
    op.create_index(op.f('ix_users_auth_user_id'), 'users', ['auth_user_id'], unique=True)
    
    # Make email and password_hash nullable (for Supabase users who don't have passwords)
    op.alter_column('users', 'email',
                    existing_type=sa.String(),
                    nullable=True)
    op.alter_column('users', 'password_hash',
                    existing_type=sa.String(),
                    nullable=True)


def downgrade() -> None:
    # Remove index
    op.drop_index(op.f('ix_users_auth_user_id'), table_name='users')
    
    # Remove column
    op.drop_column('users', 'auth_user_id')
    
    # Restore NOT NULL constraints (if needed)
    op.alter_column('users', 'email',
                    existing_type=sa.String(),
                    nullable=False)
    op.alter_column('users', 'password_hash',
                    existing_type=sa.String(),
                    nullable=False)

