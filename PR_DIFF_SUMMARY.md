# PR: Fix 409 "email_already_linked_to_different_account" Error

## Files Changed

### Backend

#### `backend/app/core/user_helpers.py`

**Change**: Added proper 409 error handling when email is already linked to different auth_user_id

```diff
        elif existing_by_email.auth_user_id != auth_user_id:
-            # Email drift: auto-repair by repurposing the existing row
-            old_auth_user_id = existing_by_email.auth_user_id
-            existing_by_email.auth_user_id = auth_user_id
-            
-            try:
-                db.commit()
-                db.refresh(existing_by_email)
-                
-                logger.info(
-                    f"[USER REPAIR] email={normalized_email} "
-                    f"old_auth_user_id={old_auth_user_id} new_auth_user_id={auth_user_id}"
-                )
-                
-                if DEBUG:
-                    logger.info(f"[get_or_create_user_by_auth_id] repaired_user: user_id={existing_by_email.id}, auth_user_id={auth_user_id}")
-                
-                return existing_by_email
-            except IntegrityError:
-                # Race condition: another thread may have created this auth_user_id
-                db.rollback()
-                # Re-fetch by auth_user_id
-                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
-                if user:
-                    if DEBUG:
-                        logger.info(f"[get_or_create_user_by_auth_id] race_refetch_after_repair: auth_user_id={auth_user_id}, user_id={user.id}")
-                    return user
-                raise
+            # Email is already linked to a different auth_user_id
+            # Check if email relink is allowed
+            allow_email_relink = os.getenv("ALLOW_EMAIL_RELINK", "false").lower() == "true"
+            
+            if not allow_email_relink:
+                # Raise 409 conflict - email already linked to different account
+                logger.warning(
+                    f"[EMAIL_CONFLICT_409] email={normalized_email} "
+                    f"is already linked to auth_user_id={existing_by_email.auth_user_id}, "
+                    f"attempted auth_user_id={auth_user_id}"
+                )
+                raise HTTPException(
+                    status_code=409,
+                    detail="email_already_linked_to_different_account"
+                )
+            
+            # Email relink is enabled: auto-repair by repurposing the existing row
+            old_auth_user_id = existing_by_email.auth_user_id
+            existing_by_email.auth_user_id = auth_user_id
+            
+            try:
+                db.commit()
+                db.refresh(existing_by_email)
+                
+                logger.warning(
+                    f"[EMAIL_RELINK] Relinked email: email={normalized_email}, "
+                    f"old_auth_user_id={old_auth_user_id}, new_auth_user_id={auth_user_id}, "
+                    f"user_id={existing_by_email.id}"
+                )
+                
+                if DEBUG:
+                    logger.info(f"[get_or_create_user_by_auth_id] repaired_user: user_id={existing_by_email.id}, auth_user_id={auth_user_id}")
+                
+                return existing_by_email
+            except IntegrityError:
+                # Race condition: another thread may have created this auth_user_id
+                db.rollback()
+                # Re-fetch by auth_user_id
+                user = db.query(User).filter(User.auth_user_id == auth_user_id).one_or_none()
+                if user:
+                    if DEBUG:
+                        logger.info(f"[get_or_create_user_by_auth_id] race_refetch_after_repair: auth_user_id={auth_user_id}, user_id={user.id}")
+                    return user
+                raise
```

#### `backend/app/core/auth.py`

**Change**: Added enhanced logging for 409 errors in get_current_user

```diff
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: returns the current authenticated User (SQLAlchemy object).

    - Reads Authorization: Bearer <token>
    - Verifies JWT
    - Extracts sub (Supabase user id) and email
    - Upserts into local users table via get_or_create_user_by_auth_id()
    """
    token = _extract_bearer_token(request)
    payload = _decode_supabase_jwt(token)

    auth_user_id = payload.get("sub")
    if not auth_user_id:
        raise _unauthorized("Token missing subject (sub)")

    email = payload.get("email") or ""
+    
+    # Extract endpoint info for logging
+    endpoint = f"{request.method} {request.url.path}"

    try:
        user = get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=str(auth_user_id),
            email=str(email),
        )
        return user
+    except HTTPException as e:
+        # Enhanced logging for 409 errors
+        if e.status_code == 409 and e.detail == "email_already_linked_to_different_account":
+            logger.error(
+                f"[409_EMAIL_CONFLICT] endpoint={endpoint}, "
+                f"auth_user_id={auth_user_id}, "
+                f"auth_email={email}, "
+                f"detail={e.detail}"
+            )
+        raise
```

### Frontend

#### `frontend/src/api/client.ts`

**Change 1**: Added 409 error handling in response interceptor

```diff
        // If backend answered with 401, clear token + redirect once
        if (error.response?.status === 401) {
          clearAccessToken();

          const path = window.location.pathname;
          const isAuthPage = path === '/login' || path === '/auth' || path === '/auth/callback';

          if (!isAuthPage && !redirectingToLogin) {
            redirectingToLogin = true;
            window.location.href = '/login';
          }
        }

+        // Handle 409 email conflict errors
+        if (error.response?.status === 409) {
+          const detail = error.response?.data?.detail;
+          const errorCode = typeof detail === 'string' ? detail : 
+                           (typeof detail === 'object' && detail?.code) ? detail.code : null;
+          
+          if (errorCode === 'email_already_linked_to_different_account' || 
+              errorCode === 'email_mismatch') {
+            // Clear onboarding draft state and localStorage
+            localStorage.removeItem('pending_onboarding');
+            localStorage.removeItem('readar_preview_recs');
+            
+            // Clear auth token and redirect to login
+            clearAccessToken();
+            
+            // Redirect to login with helpful message
+            const path = window.location.pathname;
+            const isAuthPage = path === '/login' || path === '/auth' || path === '/auth/callback';
+            
+            if (!isAuthPage && !redirectingToLogin) {
+              redirectingToLogin = true;
+              // Store error message in sessionStorage to show on login page
+              sessionStorage.setItem('auth_error', 
+                'Your email is linked to a different account. Please log in with the correct account.');
+              window.location.href = '/login';
+            }
+          }
+        }

        return Promise.reject(error);
```

**Change 2**: Updated saveOnboarding to handle 409 errors

```diff
      const status = error?.response?.status as number | undefined;

+      // Handle 409 email conflict - don't retry, let interceptor handle logout
+      if (status === 409) {
+        const detail = error.response?.data?.detail;
+        const errorCode = typeof detail === 'string' ? detail : 
+                         (typeof detail === 'object' && detail?.code) ? detail.code : null;
+        
+        if (errorCode === 'email_already_linked_to_different_account' || 
+            errorCode === 'email_mismatch') {
+          // Let the interceptor handle the logout/redirect
+          throw error;
+        }
+      }

      // Do NOT retry auth/permission/validation-style failures
      if (status === 401 || status === 403 || status === 422) {
        if (error.response?.data?.detail) throw new Error(error.response.data.detail);
        throw new Error(error.message || "Failed to save onboarding");
      }
```

## Verification

### Endpoints Already Use auth_user_id

✅ **Onboarding endpoint** (`POST /api/onboarding`):
- Uses `user.id` from `get_current_user()` which is based on `auth_user_id`
- Idempotent: upserts by `user_id`
- No email in payload schema

✅ **Reading history endpoint** (`POST /api/reading-history/upload-csv`):
- Uses `user.id` from `get_current_user()` which is based on `auth_user_id`
- No email references

### No Client-Provided Email Trust

✅ **OnboardingPayload schema**: Does not include email field
✅ **Reading history upload**: Does not accept email parameter
✅ **All identity**: Derived from JWT token only

## Testing Commands

### Test 1: 409 Error (Before Fix - Should Still Work After)
```bash
# Create user with email test@example.com and auth_user_id_1
# Then authenticate with different auth_user_id_2 but same email

TOKEN_2="<token_with_auth_user_id_2_and_email_test@example.com>"

curl -i https://readar-backend.onrender.com/api/onboarding \
  -H "Authorization: Bearer $TOKEN_2" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "service",
    "business_stage": "pre-revenue",
    "biggest_challenge": "sales"
  }'

# Expected: 409 Conflict
# Response: {"detail": "email_already_linked_to_different_account"}
# Logs: [409_EMAIL_CONFLICT] endpoint=POST /api/onboarding, auth_user_id=..., auth_email=test@example.com
```

### Test 2: Idempotency (Should Work)
```bash
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

# Second request (same token, different data)
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

### Test 3: Reading History Upload (Should Work)
```bash
TOKEN="<valid_token>"

curl -i https://readar-backend.onrender.com/api/reading-history/upload-csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@goodreads_export.csv"

# Expected: 200 OK with {"imported_count": N, "skipped_count": M}
# Uses auth_user_id from token, no email involved
```

## Summary

- ✅ Fixed 409 error handling with proper `ALLOW_EMAIL_RELINK` check
- ✅ Added enhanced logging for 409 errors
- ✅ Verified endpoints use `auth_user_id` only (already correct)
- ✅ Verified endpoints are idempotent (already correct)
- ✅ Updated frontend to handle 409 errors with logout and redirect
- ✅ No client-provided email is trusted (already correct)

