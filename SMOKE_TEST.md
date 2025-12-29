# Readar V1 — Smoke Test (Local + Production)

Purpose: Prove the end-to-end user journey works reliably:
Onboarding → Preview recommendations → Login (magic link) → Auth callback → Recommendations

If any step fails, stop and fix before shipping changes.

---

## Pre-reqs

- Backend running (local) OR deployed (prod)
- Frontend running (local) OR deployed (prod)
- Supabase redirect URLs configured for the environment you’re testing
- `VITE_SITE_URL` set correctly for the environment

---

# A) Local Smoke Test (10 minutes)

## A1) Start services

From repo root:

- Backend:
  - `make dev-backend`
- Frontend:
  - `make dev-frontend`

Open:
- Frontend: http://localhost:5173
- Backend health: http://127.0.0.1:8000/health

Expected:
- `/health` returns 200 with `{"status":"ok"}`

---

## A2) Reset browser state (required)

In Chrome:
- DevTools → Application → Storage → Clear site data

Also confirm Local Storage for `http://localhost:5173` is cleared:
- Remove any `sb-*-auth-token`
- Remove any `readar_*` keys

---

## A3) Full flow (logged out → onboarding → preview → login → recommendations)

1) Visit:
- `http://localhost:5173/`

2) Complete onboarding normally.
Expected:
- No redirect to `/login` during onboarding.

3) After submit, you should land on:
- `/recommendations/loading`

Expected:
- Page stays on loading while generating preview
- Network shows exactly ONE call to:
  - `/recommendations/preview` (200)
- Network shows ZERO calls to:
  - `/api/onboarding` during preview generation

4) After preview is ready, you should be redirected to:
- `/login?next=/recommendations`

Expected:
- Login page appears only AFTER preview is ready.

5) Request magic link with email.
Expected:
- Email arrives
- Link target is:
  - `http://localhost:5173/auth/callback?...`
  - NOT `readar.ai` and NOT some old domain

6) Click link → Auth callback runs.
Expected:
- You land on `/recommendations`

7) Recommendations page behavior:
Expected:
- Recommendations render immediately (preview-first)
- Background fetch runs to load authenticated recommendations
- After authenticated fetch succeeds, preview keys are cleared:
  - `readar_preview_recommendations`
  - `readar_preview_onboarding` (if used)
  - `readar_preview_ready`

8) Refresh test:
- Hard refresh `/recommendations`
Expected:
- Still authenticated
- Recommendations render cleanly

---

## A4) Local Pass / Fail

PASS if:
- Onboarding never forces login
- Preview generates while logged out
- Redirect to login happens only after preview is ready
- Magic link returns to localhost callback
- Recommendations render and persist

FAIL if:
- Any step loops, hangs, or requires manual navigation
- Magic link redirects to wrong domain
- Preview triggers `/api/onboarding` or repeated requests

---

# B) Production Smoke Test (10 minutes)

## B1) Confirm environment variables

Frontend (Vercel):
- `VITE_API_BASE_URL` points to Render backend
- `VITE_SITE_URL` points to the production frontend origin (choose ONE canonical):
  - `https://readar.ai` (after DNS cutover)
  - OR `https://<vercel-prod>.vercel.app` (before cutover)

Backend (Render):
- Supabase keys present and correct
- CORS allows:
  - `readar.ai`, `www.readar.ai`, and Vercel domains as needed

Supabase:
- Auth → URL Configuration allowlist includes:
  - `https://<prod-origin>/auth/callback`
  - `https://<prod-origin>/**`

---

## B2) Run the same flow in Incognito

1) Open production frontend URL
2) Clear site data (Incognito is usually enough)
3) Complete onboarding
4) Confirm `/recommendations/loading` generates preview
5) Confirm redirect to `/login?next=/recommendations`
6) Request magic link
7) Click link
8) Confirm `/auth/callback` runs and lands on `/recommendations`
9) Confirm preview-first render then authenticated refresh
10) Hard refresh `/recommendations`

PASS criteria: same as local.

---

# C) Troubleshooting Quick Hits

## C1) Redirect goes to wrong domain
- Check `VITE_SITE_URL`
- Check Supabase allowed redirect URLs
- Re-deploy frontend after env var changes

## C2) Stuck on loading page
- Confirm only one preview request is fired
- Ensure preview path does not call `/api/onboarding`
- Check Network tab for 401 loops

## C3) 401 Unauthorized / expired JWT
- Clear localStorage (Supabase token can be stale)
- Confirm backend uses correct `SUPABASE_JWT_SECRET` and `JWT_ALGORITHM=HS256`

---

# D) Notes

This smoke test is the gate for:
- DNS cutover
- inviting any external users
- changing auth flow
