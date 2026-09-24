# Lovable loop: implementation steps 1–5

Prepared 2026-09-21 from `dev` at `51a5cfd`. These items require Michael's acceptance review before being marked Done in the UX Roadmap.

| Order | Tasks | Implemented behavior | Next stage |
| --- | --- | --- | --- |
| 1 | RD-71 | Exact agreed opener; contextual, neutral discovery prompts; curiosity/aspiring-reader paths; summary confirmation survives the turn budget | Review wording with real conversations |
| 2 | RD-66, RD-67, RD-68 | Conversation viewport shrinks as composer grows; follows latest unless reader scrolls up; bottom padding and rounded outer composer | Desktop/mobile review |
| 3 | RD-70, RD-69 | Shared Readar mark and surface tokens across onboarding/import/loading/sign-in; centered Choose this book; progressive replies with skip and reduced-motion support | Visual/accessibility review |
| 4 | RD-72 | App-side branding and safe internal OAuth return paths; exact provider setup below | External configuration required; not complete |
| 4 | RD-73 | Saved/skipped import receipt, 1.8-second pause, Continue now/Stay here controls, zero-row and failure recovery; fresh picks after import | Review payoff/timing with real CSV |
| 5 | RD-60 | Returning sign-ins default to Reading; relevant saved-action, active/stalled, queued/waiting, finished and new-reader prompts; persisted in-app snooze/opt-out | End-to-end acceptance |
| 5 | RD-61 | Explicit finish, quiet celebration, optional usefulness rating/private reflection, optional challenge update, durable finished list and fresh next-book link | End-to-end acceptance |

Shipping/tracking integrations stay outside Lovable v1. Email delivery remains paused under the existing policy. No reminder emails or scheduled messages were added.

## Data and behavior

Run migration `b4c5d6e7f8a9` before using Reading. It adds `reading_completions` and `reading_journey_preferences`; it does not rewrite existing reading data.

A finish atomically saves completion, shelf state, reading history, optional rating/reflection and optional challenge update. It never fills in unlogged pages or creates points/streak/competition credit. An existing imported rating survives when the reader skips rating. Saved history excludes the finished title from subsequent recommendations. The updated challenge is used by the existing recommendation engine; private reflection text is stored for the reader, not interpreted by an AI or shared with a partner.

Finish retries use the same request ID and return the original saved result. A different request for an already-finished book or a stale challenge gets a conflict. There is one recorded finish per reader/book in this version; repeated-read tracking is not part of this scope. Previous progress and takeaways remain saved. Recently finished shows the latest 50 recorded completions.

Return prompts are in-app only. An unfinished action takes priority, then current reading, an up-next/waiting book, and finally a next-book suggestion. Three days without a log (or since starting if no log exists) changes the encouragement to a gentle restart. Snoozes use the reader's local calendar and are stored per account. Visiting Reading does not count as meaningful engagement or earn credit.

## RD-72: recognizable Google sign-in

The app can display Readar branding, but Google's hosted sign-in label is controlled by the OAuth project/domain. Do not mark this task done based on the React sign-in page alone.

1. In the Google Cloud project used by the existing Supabase Google provider, open **Google Auth Platform → Branding**. Set the app name to **Readar**, use the Readar logo, and supply the real support email, homepage, privacy policy and terms links. Verify ownership of `readar.ai` and complete Google's brand verification where required. Do not create a second unrelated OAuth client.
2. Verify the consent screen in an incognito sign-in. If the project host is still shown and a branded auth host is desired, configure an approved Supabase custom domain such as `auth.readar.ai`. This is an optional paid add-on and DNS change; it has not been purchased or activated here.
3. Before activating a custom domain, add its `/auth/v1/callback` URL to the existing Google client's authorized redirect URIs. Retain the current callback during the transition. Verify DNS/TLS following Supabase's instructions, then activate the domain.
4. Point the frontend's existing `VITE_SUPABASE_URL` to the activated project domain and rebuild. Check backend Supabase/JWT settings against the project's actual issuer; do not guess or expose secrets. Keep the app callback URL in Supabase's redirect allow-list, including the actual local test origin when testing.
5. Test new and returning Google sign-ins, cancellation/retry, onboarding draft preservation, import handoff and a refresh of an authenticated page. Confirm that the actual Google screen identifies Readar. Restore the previous frontend host/configuration if the transition breaks sign-in.

Sources checked 2026-09-21: [Supabase Google setup](https://supabase.com/docs/guides/auth/social-login/auth-google), [Supabase custom domains](https://supabase.com/docs/guides/platform/custom-domains).

## Terminal quick reference

First stop both running servers with Ctrl+C. From the root of `readar-v1`, check `git status --short`. If it lists local edits, preserve them before switching; do not discard or reset them.

For the combined implementation, use `dev`:

```bash
git fetch origin && git switch dev && git pull --ff-only origin dev
git branch --show-current
git log -1 --oneline
```

The branch must be `dev` and include the PR #20 merge (`462481b`) or a later descendant. `npm ci` only installs dependencies; it does not fetch code or change branches. Run both servers from this same updated checkout and use a fresh incognito session for a new onboarding review. See [the September 21 UX review](ux-review-2026-09-21.md) for the version mismatch and acceptance cases.

With the existing working test credentials in `backend/.env` and `frontend/.env.local`:

Terminal 1:

```bash
cd backend
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
ENVIRONMENT=development CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 USER_EMAILS_PAUSED=true python -m uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

If your existing virtual environment is named `venv`, activate `venv/bin/activate` instead. Create one with `python3 -m venv .venv` only if needed. Use a test database for review; the migration applies to the configured database. Keep production mail credentials out of a local test environment.

Terminal 2, from the repository root:

```bash
cd frontend
npm ci
npm run dev -- --host localhost --port 5173 --strictPort
```

Open `http://localhost:5173/onboarding`. Keep `VITE_API_BASE_URL=http://127.0.0.1:8000/api`. Stop either process with Ctrl+C. Restart Vite after environment changes. The agreed opener is local product copy; subsequent conversation still needs the working backend Anthropic key.

## Acceptance review

1. Start a new onboarding conversation; verify the exact opener. Try a concrete business issue and a curiosity/no-business path. Confirm follow-ups reference actual answers, avoid sales clichés and allow summary corrections. NEPQ source examples offered by Michael are still welcome; no training library has been supplied or represented as incorporated.
2. Write a multiline reply up to the current 200px composer cap. The newest question stays above it. Scroll up intentionally; typing must not pull the reader away. Use Back to latest message. Review narrow mobile widths, keyboard focus, bottom spacing and rounded corners.
3. Read a progressively revealed response; select Show full message; enable reduced motion; refresh a saved chat. Existing messages should not replay typing. Review the landing→onboarding→import→recommendation visual continuity and the centered primary book choice.
4. Import a real Goodreads CSV. Verify actual saved/skipped counts; pause or continue immediately. Try a zero-row file, an invalid file and interrupted upload. A successful import must request fresh picks. Verify Google branding separately as described above.
5. Sign in as a returning reader; resume Reading. Save progress, capture an action, snooze the next-step prompt and reload. Finish a started book with optional feedback, change the challenge, and follow Find my next book. Reload to verify the finished record; confirm the finished book is not offered again. Verify a second account cannot see the first account's check-in. Points must not increase just from finishing.

GitHub CI passed 319 backend tests and 42 frontend tests, plus TypeScript/build and lint (run 35604196654). Automated checks cover the provider-failure/summary behavior, import timing and recovery, typing accessibility, safe OAuth destinations, finish retry/conflict behavior, database atomicity/isolation, local-date preferences and migration upgrade/downgrade. They use mocked AI/auth responses and an isolated test database; live recommendation quality, Google branding and the owner's UX acceptance remain separate gates.
