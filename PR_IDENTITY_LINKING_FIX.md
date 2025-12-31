# Safe Automatic Identity Linking - Fix for 409 Errors

## Summary

Eliminated 409 "email_already_linked_to_different_account" errors by implementing **safe automatic relinking** when email matches but auth_user_id differs. The system now automatically updates the existing user's `auth_user_id` when the token email matches the database email, making identity linking robust and eliminating login loops.

## Why Relink is Safe

1. **Email is verified in token**: The JWT token contains the email claim from Supabase Auth, which is the source of truth
2. **Case-insensitive matching**: Email matching is case-insensitive and normalized
3. **Row locking**: Uses `WITH FOR UPDATE` to prevent race conditions during relink
4. **Guardrails**: Only relinks when:
   - Email claim is present in token
   - Email matches database email (case-insensitive)
   - No conflicting auth_user_id already exists
5. **Audit trail**: All relinks are logged with structured `[AUTH_RELINK]` messages

## What 409 Now Means

409 errors are now **only raised for truly unsafe conflicts**:

- `auth_user_id_already_linked_to_different_email`: When auth_user_id already exists linked to a different email
- `email_claim_missing_cannot_link`: When email claim is missing and cannot safely relink
- `email_mismatch_cannot_link`: When email in token doesn't match database email (edge case)

**Safe relinks (email matches) no longer raise 409** - they succeed automatically.

## Changes Made

### 1. `backend/app/core/user_helpers.py`

**Main change**: Rewrote `get_or_create_user_by_auth_id()` to implement safe automatic relinking

**Key improvements**:
- Added `endpoint_path` and `email_verified` parameters for logging and guardrails
- Uses `with_for_update()` for row locking during relink operations
- Automatic relink when email matches but auth_user_id differs
- Only raises 409 for truly unsafe conflicts
- Structured audit logging with `[AUTH_RELINK]` messages

**Algorithm**:
1. Query by `auth_user_id` first (primary lookup) → return if found
2. If not found, query by email with `FOR UPDATE` lock
3. If found by email:
   - Legacy user (no auth_user_id) → link to current auth_user_id
   - Different auth_user_id → **SAFE RELINK** (update auth_user_id)
4. If not found, create new user

### 2. `backend/app/core/auth.py`

**Change**: Pass `endpoint_path` and `email_verified` to `get_or_create_user_by_auth_id()`

- Extracts `email_verified` from JWT payload (Supabase includes this claim)
- Passes endpoint path for audit logging
- Updated error logging to handle new error codes

### 3. `frontend/src/api/client.ts`

**Change**: Updated 409 error handling to only logout on unsafe conflicts

- Only triggers logout/redirect for unsafe error codes:
  - `auth_user_id_already_linked_to_different_email`
  - `email_mismatch_cannot_link`
  - `email_claim_missing_cannot_link`
  - Legacy `email_already_linked_to_different_account` (for backward compatibility)
- Safe relinks now succeed without frontend intervention
- Prevents infinite login loops

### 4. `backend/tests/test_user_helpers_identity_linking.py`

**New test file** with comprehensive coverage:

1. ✅ Fresh user creation
2. ✅ Normal login (same identity)
3. ✅ **Safe automatic relink** (the problematic case - now passes)
4. ✅ Unsafe conflict detection
5. ✅ Missing email claim handling
6. ✅ Legacy user linking
7. ✅ Case-insensitive email matching
8. ✅ Concurrent relink attempts

## How to Reproduce Legacy Mismatch and Confirm Fix

### Setup Legacy Mismatch Scenario

```python
# In database, create user with old auth_user_id
from app.models import User, SubscriptionStatus
user = User(
    email="test@example.com",
    auth_user_id="old-auth-user-id-123",
    subscription_status=SubscriptionStatus.FREE
)
db.add(user)
db.commit()
```

### Test Before Fix (Would Fail)

```bash
# Try to authenticate with new auth_user_id but same email
# OLD BEHAVIOR: Would raise 409 "email_already_linked_to_different_account"
curl -X POST https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer <token-with-new-auth-user-id-and-same-email>" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Test", "business_model": "service", "business_stage": "pre-revenue", "biggest_challenge": "sales"}'

# Expected OLD: 409 Conflict
# Expected NEW: 201 Created (relink occurs automatically)
```

### Test After Fix (Should Pass)

1. **Deploy changes**
2. **Clear site data** (localStorage, cookies)
3. **Login via magic link** with email that has legacy mismatch
4. **Start onboarding** → should be **200/201**, NOT 409
5. **Check logs** for `[AUTH_RELINK]` message:
   ```
   [AUTH_RELINK] endpoint=POST /api/onboarding, email=test@example.com, old_auth_user_id=old-auth-user-id-123, new_auth_user_id=new-auth-user-id-456, user_id=<uuid>, email_verified=True
   ```
6. **Verify database**: User's `auth_user_id` should be updated to new value

## Testing Plan

### Local Testing

```bash
# Run new identity linking tests
cd backend
source .venv/bin/activate
pytest tests/test_user_helpers_identity_linking.py -v

# Run all user helper tests
pytest tests/test_user_helpers.py tests/test_user_helpers_identity_linking.py -v
```

### Production Testing

1. **Deploy to production**
2. **Monitor logs** for `[AUTH_RELINK]` entries (should see relinks happening)
3. **Test with user who had 409 before**:
   - Clear browser data
   - Login via magic link
   - Complete onboarding → should succeed
4. **Verify no 409 errors** in production logs (except for truly unsafe conflicts)

## Migration Notes

- **No database migration required** - this is a code-only change
- **Backward compatible** - existing users continue to work
- **Safe to deploy** - if relink fails, original behavior (409) is preserved for unsafe cases
- **Logging only** - no audit table needed (Option A chosen over Option B)

## Error Code Reference

| Error Code | Status | When Raised | Frontend Action |
|------------|--------|-------------|----------------|
| `auth_user_id_already_linked_to_different_email` | 409 | Auth user ID exists with different email | Logout + redirect to login |
| `email_claim_missing_cannot_link` | 409 | No email in token, cannot relink | Logout + redirect to login |
| `email_mismatch_cannot_link` | 409 | Email in token doesn't match DB email | Logout + redirect to login |
| `email_claim_missing_cannot_create_user` | 400 | No email in token, cannot create user | Show error message |
| ~~`email_already_linked_to_different_account`~~ | ~~409~~ | **REMOVED** - now triggers safe relink | N/A |

## Files Changed

1. `backend/app/core/user_helpers.py` - Main relinking logic
2. `backend/app/core/auth.py` - Pass endpoint and email_verified
3. `frontend/src/api/client.ts` - Updated 409 error handling
4. `backend/tests/test_user_helpers_identity_linking.py` - New comprehensive tests

## Security Considerations

- **Email verification**: Relink only occurs when email in token matches database email
- **Token validation**: JWT is validated before any relink operation
- **Row locking**: Prevents race conditions during relink
- **Audit logging**: All relinks are logged for security monitoring
- **No client trust**: All identity comes from JWT token, never from client payload

## Performance Impact

- **Minimal**: Additional `FOR UPDATE` lock only when relinking (rare case)
- **No impact** on normal login flow (user found by auth_user_id)
- **One-time relink**: Each user only relinks once when auth_user_id changes

## Rollback Plan

If issues occur:
1. Revert code changes (no database changes to rollback)
2. Old behavior (409 on email mismatch) will return
3. Users with mismatches will need manual database fix

## Success Metrics

- ✅ Zero 409 "email_already_linked_to_different_account" errors in production
- ✅ Successful onboarding for users with legacy mismatches
- ✅ `[AUTH_RELINK]` logs appear for users being automatically relinked
- ✅ No infinite login loops in frontend

