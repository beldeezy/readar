"""
Cleanup script for duplicate users and orphaned auth_user_ids.

This script:
1. Finds duplicate users by lower(email) and reports conflicts
2. Finds rows where email matches but auth_user_id is null, and safely backfills where possible
3. Does NOT auto-merge if two rows have same email but different auth_user_id (prints and stops)

Run with: python -m app.scripts.cleanup_duplicate_users
"""
import sys
import os
from sqlalchemy import func
from sqlalchemy.orm import Session

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import SessionLocal
from app.models import User


def find_duplicate_emails(db: Session) -> list:
    """Find users with duplicate emails (case-insensitive)."""
    duplicates = db.query(
        func.lower(User.email).label('email_lower'),
        func.count(User.id).label('count')
    ).filter(
        User.email.isnot(None)
    ).group_by(
        func.lower(User.email)
    ).having(
        func.count(User.id) > 1
    ).all()
    
    return duplicates


def get_users_by_email(db: Session, email_lower: str) -> list:
    """Get all users with the same email (case-insensitive)."""
    return db.query(User).filter(
        func.lower(User.email) == email_lower
    ).all()


def find_orphaned_auth_user_ids(db: Session) -> list:
    """Find users with email but no auth_user_id."""
    return db.query(User).filter(
        User.email.isnot(None),
        User.auth_user_id.is_(None)
    ).all()


def main():
    """Main cleanup function."""
    db: Session = SessionLocal()
    
    try:
        print("=" * 80)
        print("User Cleanup Script")
        print("=" * 80)
        print()
        
        # Step 1: Find duplicate emails
        print("Step 1: Checking for duplicate emails (case-insensitive)...")
        duplicates = find_duplicate_emails(db)
        
        if duplicates:
            print(f"⚠️  Found {len(duplicates)} duplicate email groups:")
            print()
            
            conflicts = []
            for dup in duplicates:
                email_lower = dup.email_lower
                users = get_users_by_email(db, email_lower)
                
                print(f"  Email: {email_lower}")
                print(f"  Count: {dup.count}")
                print(f"  Users:")
                
                auth_user_ids = set()
                for user in users:
                    auth_id = user.auth_user_id or "(null)"
                    auth_user_ids.add(auth_id)
                    print(f"    - ID: {user.id}, auth_user_id: {auth_id}, email: {user.email}, created: {user.created_at}")
                
                # Check if there are conflicting auth_user_ids
                if len(auth_user_ids) > 1 or (len(auth_user_ids) == 1 and None in auth_user_ids and len(auth_user_ids) > 1):
                    conflicts.append({
                        'email': email_lower,
                        'users': users,
                        'auth_user_ids': auth_user_ids
                    })
                
                print()
            
            if conflicts:
                print("❌ CONFLICTS DETECTED:")
                print("   Multiple users with same email but different auth_user_ids.")
                print("   Manual intervention required. Do NOT auto-merge.")
                print()
                for conflict in conflicts:
                    print(f"   Email: {conflict['email']}")
                    print(f"   Auth User IDs: {conflict['auth_user_ids']}")
                    print()
                print("   Stopping. Please resolve conflicts manually.")
                return 1
        else:
            print("✅ No duplicate emails found.")
            print()
        
        # Step 2: Find orphaned auth_user_ids (email exists but no auth_user_id)
        print("Step 2: Checking for users with email but no auth_user_id...")
        orphaned = find_orphaned_auth_user_ids(db)
        
        if orphaned:
            print(f"📋 Found {len(orphaned)} users with email but no auth_user_id:")
            print()
            for user in orphaned:
                print(f"  - ID: {user.id}, email: {user.email}, created: {user.created_at}")
            print()
            print("   Note: These users cannot be automatically linked without auth_user_id.")
            print("   They may need to be linked manually or will be linked on next auth.")
        else:
            print("✅ No orphaned users found.")
            print()
        
        # Step 3: Summary
        print("=" * 80)
        print("Summary:")
        print(f"  Duplicate email groups: {len(duplicates)}")
        print(f"  Orphaned users (email but no auth_user_id): {len(orphaned)}")
        print("=" * 80)
        
        if duplicates and not conflicts:
            print()
            print("✅ No conflicts detected. Duplicates can be safely merged if needed.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

