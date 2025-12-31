# Fix for 409 "email_already_linked_to_different_account" Error

## Summary

Fixed production 409 errors during onboarding save and reading history CSV upload by:
1. Adding proper 409 error handling in `get_or_create_user_by_auth_id` with `ALLOW_EMAIL_RELINK` check
2. Ensuring endpoints use `auth_user_id` as primary key (already implemented)
3. Making endpoints idempotent (already implemented)
4. Adding enhanced logging for 409 errors
5. Updating frontend to handle 409 errors with logout and redirect

## Changes Made

### Backend Changes

#### 1. `backend/app/core/user_helpers.py`
- **Added 409 error handling**: When email is already linked to a different `auth_user_id`, the function now:
  - Checks `ALLOW_EMAIL_RELINK` environment variable
  - If disabled (default): raises `HTTPException(409, "email_already_linked_to_different_account")`
  - If enabled: allows email relinking (auto-repair behavior)
- **Enhanced logging**: Added warning log when 409 is raised with email and auth_user_id details

#### 2. `backend/app/core/auth.py`
- **Enhanced 409 error logging**: Added logging in `get_current_user` to capture:
  - Endpoint (method + path)
  - `auth_user_id` from token
  - `auth_email` from token
  - Error detail

### Frontend Changes

#### 3. `frontend/src/api/client.ts`
- **Added 409 error handling in interceptor**: When 409 error with `email_already_linked_to_different_account` or `email_mismatch` is detected:
  - Clears onboarding draft state from localStorage
  - Clears auth token
  - Redirects to login page with helpful error message
- **Updated `saveOnboarding`**: Added specific handling for 409 errors (no retry, let interceptor handle logout)

## Error Source Analysis

### Call Stack
```
1. Frontend: apiClient.saveOnboarding() or apiClient.uploadReadingHistoryCsv()
2. Backend: POST /api/onboarding or POST /api/reading-history/upload-csv
3. Backend: get_current_user() dependency
4. Backend: get_or_create_user_by_auth_id()
5. Backend: Raises HTTPException(409, "email_already_linked_to_different_account")
```

### Exception Type
- `HTTPException` from FastAPI
- Status code: `409 Conflict`
- Detail: `"email_already_linked_to_different_account"`

### Routes That Trigger It
- `POST /api/onboarding` - when saving onboarding profile
- `POST /api/reading-history/upload-csv` - when uploading reading history CSV

### Service Method
- `get_or_create_user_by_auth_id()` in `app/core/user_helpers.py`
- Triggered when:
  - User doesn't exist by `auth_user_id`
  - User exists by email with different `auth_user_id`
  - `ALLOW_EMAIL_RELINK` is disabled (default)

## Database Schema Summary

### Users Table
- **Primary Key**: `id` (UUID)
- **Unique Constraints**:
  - `auth_user_id` (unique index, nullable)
  - `email` (unique index with case-insensitive functional index `ix_users_email_lower_unique`, nullable)

### Onboarding Profiles Table
- **Primary Key**: `id` (UUID)
- **Foreign Key**: `user_id` → `users.id` (unique constraint)
- **No email field**: Uses `user_id` only

### Reading History Table
- **Primary Key**: `id` (UUID)
- **Foreign Key**: `user_id` → `users.id`
- **No email field**: Uses `user_id` only

## Auth Identity Plumbing

### Token Decoding
- `get_current_user()` in `app/core/auth.py`:
  - Extracts JWT from `Authorization: Bearer <token>` header
  - Decodes using Supabase JWT secret
  - Extracts `sub` (auth_user_id) and `email` from token payload
  - Calls `get_or_create_user_by_auth_id()` with these values

### Identity Fields
- **Primary**: `auth_user_id` (from token `sub` claim) - used for all lookups
- **Secondary**: `email` (from token `email` claim) - used for user creation/update only
- **Client-provided email**: NOT trusted - endpoints don't accept email in payloads

## Idempotency

### Onboarding Endpoint
- **Already idempotent**: Uses upsert pattern (check for existing profile by `user_id`, update if exists, create if not)
- **Uses auth_user_id only**: `user.id` comes from `get_current_user()` which is based on `auth_user_id`
- **No email in payload**: `OnboardingPayload` schema doesn't include email field

### Reading History Endpoint
- **Uses auth_user_id only**: `user.id` comes from `get_current_user()` which is based on `auth_user_id`
- **No email references**: Endpoint doesn't use email anywhere

## Testing Plan

### Before Fix (Expected: 409 Error)

```bash
# Setup: Create user with email test@example.com and auth_user_id_1
# Then try to authenticate with different auth_user_id_2 but same email

TOKEN_1="<token_with_auth_user_id_1_and_email_test@example.com>"
TOKEN_2="<token_with_auth_user_id_2_and_email_test@example.com>"

# First request succeeds
curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN_1" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales"
  }'

# Expected: 201 Created

# Second request with different auth_user_id but same email fails
curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN_2" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User 2",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales"
  }'

# Expected: 409 Conflict with "email_already_linked_to_different_account"
```

### After Fix (Expected: Same Behavior, Better Logging + Frontend Handling)

```bash
# Same test as above, but:
# 1. Backend logs will include detailed 409 error info
# 2. Frontend will automatically logout and redirect to login
# 3. User sees helpful error message
```

### Idempotency Test

```bash
# Same token, multiple requests - should succeed and update existing profile
TOKEN="<valid_token>"

# First request
curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales"
  }'

# Expected: 201 Created

# Second request with same token (idempotent)
curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Updated Name",
    "business_model": "saas",
    "business_stage": "early-revenue",
    "biggest_challenge": "marketing"
  }'

# Expected: 201 Created (updates existing profile)
```

## Logging

### 409 Error Log Format
```
[409_EMAIL_CONFLICT] endpoint=POST /api/onboarding, auth_user_id=<uuid>, auth_email=test@example.com, detail=email_already_linked_to_different_account
```

### Email Conflict Warning Log Format
```
[EMAIL_CONFLICT_409] email=test@example.com is already linked to auth_user_id=<uuid1>, attempted auth_user_id=<uuid2>
```

## Frontend Error Handling

When 409 error is detected:
1. Clears `pending_onboarding` from localStorage
2. Clears `readar_preview_recs` from localStorage
3. Clears auth token
4. Stores error message in sessionStorage: "Your email is linked to a different account. Please log in with the correct account."
5. Redirects to `/login`
6. Login page can display the error message from sessionStorage

## Environment Variables

- `ALLOW_EMAIL_RELINK`: Controls whether email relinking is allowed
  - Default: `false` (disabled) - raises 409 on conflict
  - When `true`: allows auto-repair (updates auth_user_id on existing email)

## Security Notes

- Endpoints do NOT trust client-provided email
- All identity is derived from JWT token (`auth_user_id` and `email` from token)
- Email in payloads is ignored (onboarding payload doesn't even include email)
- All user lookups use `auth_user_id` as primary key

