# Diagnostic Logging for Onboarding 500 Errors

## Changes Made

### Frontend (`frontend/src/api/client.ts`)

1. **Enhanced `getOnboarding()` error logging:**
   - Logs URL, status, statusText, headers (content-type), response data, response text
   - Only logs when `VITE_DEBUG=true` in production (or in dev mode)

2. **Enhanced `getRecommendations()` error logging:**
   - Added try/catch with detailed error logging
   - Logs same details as getOnboarding

3. **Enhanced `getPreviewRecommendations()` error logging:**
   - Added detailed error logging
   - Logs same details as other methods

### Backend (`backend/app/main.py`)

1. **Improved global exception handler:**
   - Always logs full exception with stacktrace
   - Returns JSON with `detail`, `error_type`, and `error` (no secrets)
   - Includes CORS headers

2. **Startup enum validation:**
   - Logs BusinessStage enum values
   - Logs SubscriptionStatus enum values
   - Logs SQLAlchemy column types for subscription_status and business_stage
   - Only when `DEBUG=true`

### Backend (`backend/app/routers/onboarding.py`)

1. **GET handler:**
   - Wrapped DB query in try/except
   - Logs exceptions with full stacktrace

2. **POST handler:**
   - Enhanced debug logging to include subscription_status
   - Already has exception handling

### Backend (`backend/app/routers/recommendations.py`)

1. **GET handler:**
   - Enhanced exception logging with user_id, auth_user_id, error_type, error message
   - Returns JSON error response with detail, error_type, error

## How to Enable Debug Logging

**Frontend:**
- Set `VITE_DEBUG=true` in environment variables
- Or use dev mode (automatically enabled)

**Backend:**
- Set `DEBUG=true` in environment variables

## Email Relink Feature

### Overview

The email relink feature allows the system to automatically update a user's `auth_user_id` when an email is already linked to a different Supabase auth user. This is useful during testing when you need to reuse the same email with different auth accounts.

### Configuration

**Environment Variable:** `ALLOW_EMAIL_RELINK`

- **Default:** `false` (disabled)
- **When enabled:** `ALLOW_EMAIL_RELINK=true`

### Behavior

**When `ALLOW_EMAIL_RELINK=false` (default):**
- If a user exists with the same email but a different `auth_user_id`, the system raises a `409 Conflict` error with detail `"email_already_linked_to_different_account"`.
- This prevents accidental account linking in production.

**When `ALLOW_EMAIL_RELINK=true`:**
- If a user exists with the same email but a different `auth_user_id`, the system automatically updates the existing user's `auth_user_id` to the current value.
- A warning is logged with the email, old `auth_user_id`, and new `auth_user_id`.
- The existing user record is returned (no new user is created).

### Use Cases

- **Testing:** Allows reusing the same email address with different Supabase auth accounts during development/testing.
- **Account Recovery:** Can help recover accounts when auth providers change user IDs.

### Security Note

⚠️ **Warning:** Only enable this feature in development/testing environments. In production, this could allow unauthorized account access if an attacker gains control of an email address.

### Example Log Output

When email relink occurs (with `ALLOW_EMAIL_RELINK=true`):
```
[EMAIL_RELINK] Relinked email: email=test@example.com, old_auth_user_id=abc-123, new_auth_user_id=xyz-789, user_id=user-uuid
```

## Curl Commands for Testing

### 1. Health Check (No Auth)
```bash
curl -i https://readar-backend.onrender.com/health
```

Expected: `200 OK` with `{"status": "ok"}`

### 2. GET Onboarding (No Auth)
```bash
curl -i https://readar-backend.onrender.com/api/onboarding
```

Expected: `401 Unauthorized` or `403 Forbidden` (NOT 500)

### 3. GET Onboarding (With Auth)
```bash
# First, get a token (replace with actual token)
TOKEN="your-jwt-token-here"

curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Either `200 OK` with profile data, or `404 Not Found` if no profile exists (NOT 500)

### 4. POST Onboarding (With Auth)
```bash
TOKEN="your-jwt-token-here"

curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales",
    "economic_sector": "technology",
    "industry": "software"
  }'
```

Expected: `201 Created` with profile data, or `400 Bad Request` for validation errors (NOT 500)

## Expected Log Outputs

### Browser Console (when VITE_DEBUG=true)

**On GET /api/onboarding error:**
```javascript
[DEBUG getOnboarding error] {
  url: "https://readar-backend.onrender.com/api/onboarding",
  method: "GET",
  status: 500,
  statusText: "Internal Server Error",
  headers: { "content-type": "application/json" },
  responseData: '{"detail":"internal_error","error_type":"InvalidTextRepresentation","error":"..."}',
  responseText: "...",
  message: "..."
}
```

### Render Logs (when DEBUG=true)

**Startup enum validation:**
```
[DEBUG] Enum values for onboarding-related types:
BusinessStage enum values:
  IDEA = 'idea'
  PRE_REVENUE = 'pre-revenue'
  EARLY_REVENUE = 'early-revenue'
  SCALING = 'scaling'
SubscriptionStatus enum values:
  FREE = 'free'
  ACTIVE = 'active'
  CANCELED = 'canceled'
[DEBUG] SQLAlchemy column types:
  User.subscription_status type: <PostgresEnum or SQLEnum>
  OnboardingProfile.business_stage type: <PostgresEnum or SQLEnum>
```

**Exception handler log:**
```
[UNHANDLED EXCEPTION] GET /api/onboarding - InvalidTextRepresentation: invalid input value for enum...
Traceback (most recent call last):
  ...
```

**Onboarding GET error:**
```
[DEBUG GET /api/onboarding ERROR] user_id=<uuid>, error_type=InvalidTextRepresentation, error=...
Traceback (most recent call last):
  ...
```

**Recommendations error:**
```
[DEBUG GET /api/recommendations ERROR] user_id=<uuid>, auth_user_id=<uuid>, error_type=..., error=...
Traceback (most recent call last):
  ...
```

## Testing Recommendations Endpoint

### GET /api/recommendations

Test the recommendations endpoint with authentication:

```bash
# Set your JWT token (get from Supabase auth or browser dev tools)
TOKEN="your-jwt-token-here"

# Test with limit=5
curl -i https://readar-backend.onrender.com/api/recommendations?limit=5 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response (when DEBUG=true):**
```json
{
  "request_id": "uuid-here",
  "items": [...],
  "debug": {
    "feedback": 0,
    "interactions": 0,
    "status_rows": 0,
    "reading_history": 0,
    "candidates": 120,
    "returned": 5,
    "reason": null
  }
}
```

**Expected Response (when DEBUG=false or not set):**
```json
{
  "request_id": "uuid-here",
  "items": [...]
}
```

**Empty Results (when DEBUG=true):**
```json
{
  "request_id": "uuid-here",
  "items": [],
  "debug": {
    "feedback": 0,
    "interactions": 0,
    "status_rows": 0,
    "reading_history": 0,
    "candidates": 120,
    "returned": 0,
    "reason": "no_signal"
  }
}
```

**Debug Reason Values:**
- `"no_signal"`: User has no interactions, reading history, or status rows
- `"no_catalog"`: No books in catalog
- `"no_matches"`: User has signal but no matching recommendations

## User Authentication and Email Conflicts

### Supabase Auth as Source of Truth

The application uses Supabase Auth as the source of truth for user authentication. The `auth_user_id` (Supabase "sub" claim) is the primary key for user lookups.

### Email Conflict Resolution

If you see `email_already_linked_to_different_account` (409 error) during testing:

1. **Delete the Supabase Auth user** in your Supabase dashboard
2. **Delete the app database user rows** (if any exist with that email)
3. **OR use a never-before-used email** for testing

The system will automatically:
- Orphan conflicting emails (set to NULL) when updating a user's email
- Link legacy users (email exists but no auth_user_id) to the current auth_user_id
- Raise 409 only when email is truly linked to a different Supabase auth account

### Testing User Creation

To test user creation without conflicts:

```bash
# Use a unique email each time
TOKEN="your-jwt-token-here"
curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales"
  }'
```

## Next Steps

1. Deploy with `DEBUG=true` and `VITE_DEBUG=true` set
2. Reproduce the error
3. Collect:
   - Browser console logs (GET /api/onboarding error)
   - Browser console logs (recommendations error)
   - Render logs (exception stacktrace)
   - Render logs (startup enum validation)
   - Render logs (method/path from global exception handler)
   - Render logs (DEBUG GET /api/recommendations diagnostic counts)
4. Run curl commands and capture outputs

