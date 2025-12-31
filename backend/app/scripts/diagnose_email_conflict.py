# backend/app/scripts/diagnose_email_conflict.py

"""
Diagnostic script to check for email conflicts in the database.

This script helps identify whether a 409 "email_already_linked_to_different_account" error
is caused by:
1. A conflicting row in public.users table
2. Multiple users with the same email but different auth_user_id

Usage:
  cd backend
  source .venv/bin/activate  # or venv/bin/activate
  python -m app.scripts.diagnose_email_conflict <email>

Example:
  python -m app.scripts.diagnose_email_conflict test@example.com
"""

import argparse
import sys
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import User, OnboardingProfile, ReadingHistoryEntry, UserBookInteraction
from app.core.config import settings
from urllib.parse import urlparse


def get_database_info() -> dict:
    """Extract safe database connection info (no password)."""
    try:
        parsed = urlparse(settings.DATABASE_URL)
        return {
            "host": parsed.hostname or "unknown",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip('/') if parsed.path else "unknown",
            "user": parsed.username or "unknown",
        }
    except Exception as e:
        return {"error": str(e)}


def get_supabase_info() -> dict:
    """Extract safe Supabase info (no secrets)."""
    info = {}
    if settings.SUPABASE_URL:
        try:
            parsed = urlparse(settings.SUPABASE_URL)
            host = parsed.netloc or parsed.path
            info["url"] = host
            if '.supabase.co' in host:
                project_ref = host.split('.supabase.co')[0]
                info["project_ref"] = project_ref
        except Exception as e:
            info["error"] = str(e)
    else:
        info["url"] = "not_set"
    return info


def count_dependent_rows(db: Session, user_id: str) -> dict:
    """Count dependent rows for a user_id."""
    counts = {
        "onboarding_profiles": 0,
        "reading_history_entries": 0,
        "user_book_interactions": 0,
    }
    
    try:
        from uuid import UUID
        user_uuid = UUID(user_id)
        
        counts["onboarding_profiles"] = db.query(OnboardingProfile).filter(
            OnboardingProfile.user_id == user_uuid
        ).count()
        
        counts["reading_history_entries"] = db.query(ReadingHistoryEntry).filter(
            ReadingHistoryEntry.user_id == user_uuid
        ).count()
        
        counts["user_book_interactions"] = db.query(UserBookInteraction).filter(
            UserBookInteraction.user_id == user_uuid
        ).count()
    except Exception as e:
        counts["error"] = str(e)
    
    return counts


def diagnose_email(email: str):
    """Diagnose email conflict in the database."""
    print("=" * 80)
    print("EMAIL CONFLICT DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Print environment info
    print("Environment Configuration:")
    db_info = get_database_info()
    print(f"  Database: {db_info.get('host')}:{db_info.get('port')}/{db_info.get('database')} (user: {db_info.get('user')})")
    
    supabase_info = get_supabase_info()
    if "project_ref" in supabase_info:
        print(f"  Supabase: {supabase_info['url']} (project_ref: {supabase_info['project_ref']})")
    else:
        print(f"  Supabase: {supabase_info.get('url', 'unknown')}")
    print()
    
    # Normalize email
    normalized_email = email.lower().strip()
    print(f"Searching for email: {email} (normalized: {normalized_email})")
    print()
    
    db: Session = SessionLocal()
    try:
        # Query for all users with this email (case-insensitive)
        users = db.query(User).filter(
            func.lower(User.email) == normalized_email
        ).all()
        
        if not users:
            print("✅ NO CONFLICT FOUND")
            print()
            print(f"No users found with email '{email}' in public.users table.")
            print("This suggests the conflict might be in Supabase Auth (auth.users) or")
            print("the production API is pointing to a different Supabase project.")
            return
        
        print(f"⚠️  FOUND {len(users)} USER(S) WITH THIS EMAIL")
        print()
        
        for idx, user in enumerate(users, 1):
            print(f"User #{idx}:")
            print(f"  id: {user.id}")
            print(f"  auth_user_id: {user.auth_user_id}")
            print(f"  email: {user.email}")
            print(f"  created_at: {user.created_at}")
            print(f"  updated_at: {user.updated_at}")
            
            # Count dependent rows
            counts = count_dependent_rows(db, str(user.id))
            print(f"  Dependent rows:")
            print(f"    - onboarding_profiles: {counts['onboarding_profiles']}")
            print(f"    - reading_history_entries: {counts['reading_history_entries']}")
            print(f"    - user_book_interactions: {counts['user_book_interactions']}")
            print()
        
        # Check for conflicts
        auth_user_ids = [u.auth_user_id for u in users if u.auth_user_id]
        unique_auth_user_ids = set(auth_user_ids)
        
        if len(unique_auth_user_ids) > 1:
            print("🚨 CONFLICT DETECTED")
            print()
            print(f"Multiple users with same email but different auth_user_id:")
            for auth_id in unique_auth_user_ids:
                matching_users = [u for u in users if u.auth_user_id == auth_id]
                print(f"  - auth_user_id={auth_id}: {len(matching_users)} user(s)")
            print()
            print("This is the source of the 409 error.")
            print("Solution: Delete or update one of the conflicting rows in public.users")
        elif len(auth_user_ids) == 1 and len(users) == 1:
            print("✅ NO CONFLICT IN DATABASE")
            print()
            print("Single user found with this email and auth_user_id.")
            print("If you're still getting 409 errors, the conflict might be:")
            print("  1. In Supabase Auth (auth.users) - check Supabase dashboard")
            print("  2. Production API pointing to different Supabase project")
            print("  3. Token contains different auth_user_id than what's in the database")
        elif len(users) > 1 and len(auth_user_ids) == 0:
            print("⚠️  MULTIPLE USERS WITH NULL auth_user_id")
            print()
            print("Multiple users found with this email but no auth_user_id.")
            print("These are likely legacy users that need to be cleaned up.")
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose email conflicts in the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.scripts.diagnose_email_conflict test@example.com
  python -m app.scripts.diagnose_email_conflict "user@domain.com"
        """
    )
    parser.add_argument(
        "email",
        type=str,
        help="Email address to check for conflicts"
    )
    
    args = parser.parse_args()
    
    if not args.email or not args.email.strip():
        print("Error: Email address is required", file=sys.stderr)
        sys.exit(1)
    
    try:
        diagnose_email(args.email)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

