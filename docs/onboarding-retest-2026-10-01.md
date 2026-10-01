# October 1 onboarding and book-action retest

Review branch: `codex/rd65-summary-handoff`, draft PR #28. This extends the
September 26 fix and includes dev through PR #27, including the combined
recommendation/book-detail action. Keep the PR unmerged until Michael retests;
dev automatically deploys the backend. Main promotion and user outreach follow
acceptance, not the automated test result.

## Report and findings

Michael's ten October 1 screenshots show repeated HTTP 503 responses from
`/api/onboarding/chat`: after discussing lead channels, reading preferences,
confirming a summary with “That's perfect,” and asking for quicker application.
Retry eventually produced recommendations. Browser screenshots do not expose
the backend exception, so they cannot establish the cause of every failed call.

The exact summary opener “Let me pull together what I'm hearing” and agreement
“That's perfect” were not recognized by the pending September 26 fix. Regression
tests reproduced that gap. The conversation service also deliberately returned
503 if generated output remained unusable after one rewrite, and did not retry
transient provider failures inside the request.

The final screenshot's standalone “Choose this book” is inconsistent with both
current dev and this review branch. The current recommendation and book-detail
components already use **Get book + add to Reading**. We cannot establish the
user's local checkout from a screenshot. No duplicate CTA implementation is
needed; restart both servers from the verified review branch below.

## Changes and verification

- Recognize the reported summary and standalone agreement; finish confirmation
  without another model call. An agreement with a correction still needs review.
- After unusable generated replies, use a controlled next question. If a final
  summary cannot be generated, quote the user's answers for review, preserving
  corrections. Rejected model drafts never become user facts or book matches.
- Retry transient provider errors once. Retry and rewrite share a maximum of
  two model calls per chat request. Persistent outages and configuration/auth
  errors still return an honest retryable error with saved answers retained.
- Confirm the combined action on actual fetched, prefetched and saved-preview
  recommendation screens, including the screenshot's title without a purchase
  URL. The title/author Amazon search opens only after the reading choice saves.
- No dependency, migration, catalog data, provider replacement or email change.

Local checks: 52 onboarding service/HTTP tests pass, including 14 new recovery
cases; all 91 frontend tests pass; TypeScript/production build and diff checks
pass. Provider responses and frontend APIs are fixtures. PR CI supplies the full
PostgreSQL regression gate. Live model tone, real browser popup behavior and
Michael's full onboarding acceptance remain for the retest.

## Get the matching frontend and backend

Stop both running local servers. From the `readar-v1` repository root:

```sh
git status --short
git fetch origin
git switch codex/rd65-summary-handoff
git pull --ff-only origin codex/rd65-summary-handoff
git log -1 --oneline
```

Confirm the latest commit matches PR #28. Start both servers from this same
checkout using the existing backend virtual environment and environment file,
and the usual frontend command:

```sh
npm run dev -- --host localhost --port 5173 --strictPort
```

No new packages or migration are needed for this follow-up. Open a fresh
incognito window so a prior session does not obscure the baseline.

## Short acceptance pass

1. Repeat the cleaning-company scenario: referrals/Thumbtack, a repeatable lead
   system, stories plus practical frameworks, and quick application. Normal
   replies should progress without manually pressing Try again.
2. Confirm the summary with “That's perfect.” It should offer the handoff, not
   ask another discovery question. Separately try “That's perfect, but margins
   matter more”; the correction must be reviewed before handoff.
3. Complete sign-in and the existing reading-history confirm/skip flow. On
   recommendations, see one **Get book + add to Reading** primary button, plus
   **I already have this book**. There should be no standalone Choose/Get pair.
4. Use the combined action. Confirm the choice saves, Amazon opens separately,
   and Reading shows Waiting for my copy. Reload, sign out/in, then explicitly
   Start reading. Check the already-owned and blocked-popup paths.

If a 503 still occurs, record the matching backend `NEPQ next_turn unavailable`
log with stage/error class and the tested commit. The log avoids recording the
reader's transcript or provider response body.
