# RD-65: reliable delivery of RD-51 onboarding recommendations

This follow-up is based on `codex/rd59-weekly-competition` at `2116d7a6` and includes the full RD-51–RD-59 preview stack. It does not merge the earlier drafts or change production.

## Confirmed cause

A React StrictMode effect replay detached the first preview request's consumer. The duplicate-key guard then skipped its replacement, leaving a successful HTTP 200 response unable to advance the screen. A regression test reproduced the user's console sequence before the fix.

The loading page now shares its in-flight operation across effect replay and attaches a fresh consumer. Detached consumers cannot navigate or clear answers. The artificial 1.2-second transition delay is removed. Request duration and successful handoff are logged separately without recording onboarding answers.

## Behavior

- Anonymous completion: preview books → sign-in, preserving the draft and preview.
- Successful sign-in: loading page saves the latest answers → fetches books → optional reading-history import → results. Skipping import uses the fetched books. Importing a CSV still refreshes recommendations.
- The loading page is the sole owner of pending-answer finalization. Neither the auth provider nor callback races it or discards a failed save. A protected-route visit with pending answers resumes this flow.
- Empty results, errors and timeouts leave loading for an actionable retry state. A failed save or recommendation request preserves the draft. Retry starts a fresh attempt without a full page reload.
- Recommendation fetches have a 20-second deadline including body parsing and abort on completion/timeout. The results page no longer waits for an extra unbounded health request. Existing Axios preview/save calls retain their 15-second transport timeout, with an outer 20-second handoff deadline.
- OAuth code exchange is shared during StrictMode replay. Session identity is available before optional profile enrichment; admin routes still wait for a verified role and fail closed on lookup failure.

## Verification

`cd frontend && npm test` runs 22 automated checks. Coverage includes the original failure, StrictMode and ordinary mounts, anonymous/authenticated paths, the actual auth provider/callback/loading/import/results routes, save failure and retry, empty responses, stalled network/body parsing, stale completion after leaving, refresh/revisit, one-time OAuth exchange and the admin role gate. API and Supabase responses are mocked; the recommendation card is replaced by its title in the route integration tests.

`npm run build` passes TypeScript checking and the Vite production build. CI now requires these frontend tests as well as the existing build and backend test gates.

These checks do not replace a live Supabase/backend browser review. Test authentication, real recommendation quality and latency locally before acceptance. No production deploy, email-pause change, migration or AI-provider change is included.

## Local review on Michael's Mac

Stop Vite with Ctrl+C. From the `readar-v1` repository root:

```bash
git status --short
git fetch origin
git switch codex/rd65-recommendation-handoff
cd frontend
npm ci
npm run dev
```

If Git reports conflicting local edits, preserve those edits before switching; do not use a force checkout or discard the existing ontrack stash. Keep the working frontend/backend environment settings. The backend code is unchanged from RD-59 and may remain running.

1. Refresh the existing loading tab, preserving its saved answers. A populated preview should advance to sign-in.
2. Sign in. After the answers save and books arrive, skip the optional Goodreads import. Confirm visible book titles, explanations and normal book actions.
3. Refresh results and repeat with an already signed-in reader. Complete new onboarding answers and confirm they are used even when a profile already exists.
4. Temporarily stop the local backend while requesting books. Confirm an error with Retry and preserved answers, restart it, and retry. An empty response must also offer a recovery path.
5. Start a request, navigate away, and confirm its late response does not pull you back. Return and confirm loading works again.
6. For a production-bundle smoke test, run `npm run build` then `npm run preview -- --port 5173` after stopping Vite, preserving the same origin/CORS and auth redirect settings.

The remaining RD-66–RD-70 visual-feedback tasks stay separate. RD-65 remains Prepared until Michael's live review passes.
