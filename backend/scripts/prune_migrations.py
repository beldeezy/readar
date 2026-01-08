#!/usr/bin/env python3
"""
Migration Pruning Script

This script:
1. Captures the current database schema
2. Deletes all old migration files
3. Creates a single baseline migration
4. Resets alembic_version table to the new baseline

IMPORTANT: Run this ONLY after backing up your database!

Usage:
    python scripts/prune_migrations.py
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


def backup_migrations():
    """Backup existing migrations to a backup folder."""
    versions_dir = Path("alembic/versions")
    backup_dir = Path("alembic/versions_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))

    print(f"📦 Backing up migrations to {backup_dir}")
    shutil.copytree(versions_dir, backup_dir)
    print(f"✓ Backup created")
    return backup_dir


def get_current_alembic_versions(engine):
    """Get current version(s) from alembic_version table."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = [row[0] for row in result]
    return versions


def delete_old_migrations():
    """Delete all old migration files."""
    versions_dir = Path("alembic/versions")
    migration_files = list(versions_dir.glob("*.py"))

    print(f"\n🗑️  Deleting {len(migration_files)} old migration files...")
    for file in migration_files:
        if file.name != "__init__.py":
            file.unlink()
            print(f"  Deleted: {file.name}")

    print("✓ Old migrations deleted")


def create_baseline_migration():
    """Create a new baseline migration with current schema."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    revision_id = f"baseline_{timestamp}"

    migration_content = f'''"""baseline migration - pruned from {timestamp}

Revision ID: {revision_id}
Revises:
Create Date: {datetime.now()}

This is a baseline migration created by pruning all previous migrations.
All schema is assumed to already exist in the database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '{revision_id}'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline migration - schema already exists.

    This migration assumes all tables, columns, indexes, and constraints
    already exist in the database. No schema changes are applied.
    """
    pass


def downgrade() -> None:
    """Cannot downgrade from baseline."""
    raise NotImplementedError("Cannot downgrade from baseline migration")
'''

    baseline_file = Path(f"alembic/versions/{revision_id}.py")
    baseline_file.write_text(migration_content)

    print(f"\n📝 Created baseline migration: {revision_id}")
    return revision_id


def update_alembic_version(engine, new_revision):
    """Update alembic_version table to new baseline."""
    with engine.connect() as conn:
        # Delete all existing versions
        conn.execute(text("DELETE FROM alembic_version"))
        conn.commit()

        # Insert new baseline version
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": new_revision}
        )
        conn.commit()

    print(f"\n✓ Updated alembic_version to: {new_revision}")


def main():
    print("=" * 60)
    print("MIGRATION PRUNING SCRIPT")
    print("=" * 60)

    # Check database connection
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. .env file has correct DATABASE_URL")
        print("3. Database exists and is accessible")
        return 1

    # Get current versions
    current_versions = get_current_alembic_versions(engine)
    print(f"\n📊 Current alembic versions: {current_versions}")
    print(f"   Total: {len(current_versions)} version(s)")

    if len(current_versions) > 1:
        print("   ⚠️  Multiple heads detected!")

    # Confirm with user
    print("\n⚠️  WARNING: This will:")
    print("   1. Backup all migration files")
    print("   2. Delete all migration files")
    print("   3. Create a single baseline migration")
    print("   4. Update alembic_version table")
    print("\n   Your database schema will NOT be changed.")
    print("   Only the migration tracking will be reset.")

    response = input("\n❓ Continue? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Aborted")
        return 0

    # Execute pruning steps
    try:
        # Step 1: Backup
        backup_dir = backup_migrations()

        # Step 2: Delete old migrations
        delete_old_migrations()

        # Step 3: Create baseline
        new_revision = create_baseline_migration()

        # Step 4: Update database
        update_alembic_version(engine, new_revision)

        print("\n" + "=" * 60)
        print("✅ MIGRATION PRUNING COMPLETE!")
        print("=" * 60)
        print(f"\nBackup location: {backup_dir}")
        print(f"New baseline: {new_revision}")
        print("\nNext steps:")
        print("1. Run: alembic current")
        print("2. Verify: alembic heads")
        print("3. Future migrations: alembic revision -m 'description'")

        return 0

    except Exception as e:
        print(f"\n❌ Error during pruning: {e}")
        print("\nYour backup is safe in: alembic/versions_backup_*")
        print("You can restore by copying files back to alembic/versions/")
        return 1


if __name__ == "__main__":
    sys.exit(main())
