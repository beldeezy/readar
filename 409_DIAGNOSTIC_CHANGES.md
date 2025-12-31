# 409 Error Diagnostic Changes

## Summary

Added diagnostic logging and a diagnostic script to identify the source of 409 "email_already_linked_to_different_account" errors in production.

## Changes Made

### 1. Enhanced Diagnostic Logging in `user_helpers.py`

**File**: `backend/app/core/user_helpers.py`

**Change**: Added detailed diagnostic logging right before raising 409 error

```python
# TEMP DIAGNOSTIC: Log detailed info before raising 409
endpoint = getattr(db, '_endpoint_context', 'unknown_endpoint')

logger.error(
    f"[409_DIAGNOSTIC] endpoint={endpoint}, "
    f"token_auth_user_id={auth_user_id}, "
    f"token_email={normalized_email}, "
    f"db_user_id={existing_by_email.id}, "
    f"db_auth_user_id={existing_by_email.auth_user_id}, "
    f"db_email={existing_by_email.email}"
)
```

**What it logs**:
- Endpoint path (method + path)
- Token's auth_user_id (from JWT sub claim)
- Token's email (from JWT email claim)
- Database row that was found: id, auth_user_id, email

**Location**: Lines 153-161 (right before the 409 exception is raised)

### 2. Pass Endpoint Context to Database Session

**File**: `backend/app/core/auth.py`

**Change**: Store endpoint info in database session for diagnostic logging

```python
# Store endpoint in db session for diagnostic logging
db._endpoint_context = endpoint
```

**Location**: Line 107 (in `get_current_user` function)

### 3. Startup Configuration Logging

**File**: `backend/app/main.py`

**Change**: Log Supabase URL and database host at startup (safe, no secrets)

```python
# Log Supabase URL (safe - just hostname/project ref)
if settings.SUPABASE_URL:
    # Extract project ref if it's a supabase.co URL
    # Log: hostname and project_ref

# Log database host (safe - no password)
# Log: host, port, database name
```

**What it logs**:
- Supabase URL hostname and project_ref (if applicable)
- Database host, port, and database name (no password)

**Location**: Lines 153-186 (in `on_startup` function)

### 4. Diagnostic Script

**File**: `backend/app/scripts/diagnose_email_conflict.py`

**Purpose**: One-off admin script to check for email conflicts in the database

**Features**:
- Queries `public.users` table for email (case-insensitive)
- Shows all matching users with their id, auth_user_id, email
- Counts dependent rows (onboarding_profiles, reading_history_entries, user_book_interactions)
- Identifies conflicts (multiple users with same email but different auth_user_id)
- Shows environment configuration (database host, Supabase project ref)

## Usage

### Running the Diagnostic Script

**In production environment** (e.g., Render shell):

```bash
# SSH into production or use Render shell
cd backend
source .venv/bin/activate  # or venv/bin/activate depending on your setup
python -m app.scripts.diagnose_email_conflict <email>
```

**Example**:
```bash
python -m app.scripts.diagnose_email_conflict test@example.com
```

### Expected Outputs

#### Scenario 1: No Conflict Found
```
================================================================================
EMAIL CONFLICT DIAGNOSTIC
================================================================================

Environment Configuration:
  Database: db.example.com:5432/readar (user: postgres)
  Supabase: xyz123.supabase.co (project_ref: xyz123)

Searching for email: test@example.com (normalized: test@example.com)

✅ NO CONFLICT FOUND

No users found with email 'test@example.com' in public.users table.
This suggests the conflict might be in Supabase Auth (auth.users) or
the production API is pointing to a different Supabase project.
```

#### Scenario 2: Conflict Found
```
================================================================================
EMAIL CONFLICT DIAGNOSTIC
================================================================================

Environment Configuration:
  Database: db.example.com:5432/readar (user: postgres)
  Supabase: xyz123.supabase.co (project_ref: xyz123)

Searching for email: test@example.com (normalized: test@example.com)

⚠️  FOUND 2 USER(S) WITH THIS EMAIL

User #1:
  id: 123e4567-e89b-12d3-a456-426614174000
  auth_user_id: auth-user-id-1
  email: test@example.com
  created_at: 2025-01-15 10:00:00
  updated_at: 2025-01-15 10:00:00
  Dependent rows:
    - onboarding_profiles: 1
    - reading_history_entries: 5
    - user_book_interactions: 10

User #2:
  id: 223e4567-e89b-12d3-a456-426614174001
  auth_user_id: auth-user-id-2
  email: test@example.com
  created_at: 2025-01-20 15:00:00
  updated_at: 2025-01-20 15:00:00
  Dependent rows:
    - onboarding_profiles: 0
    - reading_history_entries: 0
    - user_book_interactions: 0

🚨 CONFLICT DETECTED

Multiple users with same email but different auth_user_id:
  - auth_user_id=auth-user-id-1: 1 user(s)
  - auth_user_id=auth-user-id-2: 1 user(s)

This is the source of the 409 error.
Solution: Delete or update one of the conflicting rows in public.users
```

#### Scenario 3: Single User (No Conflict in DB)
```
================================================================================
EMAIL CONFLICT DIAGNOSTIC
================================================================================

Environment Configuration:
  Database: db.example.com:5432/readar (user: postgres)
  Supabase: xyz123.supabase.co (project_ref: xyz123)

Searching for email: test@example.com (normalized: test@example.com)

⚠️  FOUND 1 USER(S) WITH THIS EMAIL

User #1:
  id: 123e4567-e89b-12d3-a456-426614174000
  auth_user_id: auth-user-id-1
  email: test@example.com
  created_at: 2025-01-15 10:00:00
  updated_at: 2025-01-15 10:00:00
  Dependent rows:
    - onboarding_profiles: 1
    - reading_history_entries: 5
    - user_book_interactions: 10

✅ NO CONFLICT IN DATABASE

Single user found with this email and auth_user_id.
If you're still getting 409 errors, the conflict might be:
  1. In Supabase Auth (auth.users) - check Supabase dashboard
  2. Production API pointing to different Supabase project
  3. Token contains different auth_user_id than what's in the database
```

## Log Analysis

### When 409 Error Occurs

Check production logs for the diagnostic log entry:

```
[409_DIAGNOSTIC] endpoint=POST /api/onboarding, token_auth_user_id=<uuid-from-token>, token_email=test@example.com, db_user_id=<uuid>, db_auth_user_id=<different-uuid>, db_email=test@example.com
```

**What to look for**:
1. **token_auth_user_id** vs **db_auth_user_id**: If different, this confirms the conflict
2. **endpoint**: Which endpoint triggered the error
3. **token_email** vs **db_email**: Should match (case-insensitive)

### Startup Logs

Check production startup logs for:

```
[CONFIG] SUPABASE_URL hostname=xyz123.supabase.co, project_ref=xyz123
[CONFIG] DATABASE_URL host=db.example.com, port=5432, database=readar
```

**What to verify**:
1. Supabase project_ref matches the project you're editing
2. Database host matches the expected production database

## Troubleshooting Steps

1. **Check startup logs** to verify Supabase project and database host
2. **Run diagnostic script** with the conflicting email
3. **Check diagnostic logs** when 409 occurs to see token vs DB values
4. **Compare results**:
   - If script finds conflict → Delete/update conflicting row in `public.users`
   - If script finds no conflict → Check Supabase Auth (auth.users) dashboard
   - If script finds single user → Check if token's auth_user_id matches DB

## Files Changed

1. `backend/app/core/user_helpers.py` - Added diagnostic logging
2. `backend/app/core/auth.py` - Pass endpoint context to DB session
3. `backend/app/main.py` - Added startup configuration logging
4. `backend/app/scripts/diagnose_email_conflict.py` - New diagnostic script

## Next Steps

1. Deploy these changes to production
2. Monitor logs for `[409_DIAGNOSTIC]` entries
3. Run diagnostic script when 409 errors occur
4. Use results to identify and fix the root cause

