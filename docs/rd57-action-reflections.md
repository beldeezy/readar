# RD-57 — Revisit actions and reflect on results

Draft for Michael’s later UX review. Based on RD-56 (`codex/rd56-reading-takeaways`, PR #15); the preceding drafts stay unmerged.

## Reader outcome

Return to an action saved from a book, record what happened, decide whether it helped, and choose a next step or mark it completed. The reading page keeps pending actions, completed actions, and ideas without an action distinct, with filters across the full saved collection.

Each reflection saves an attempt date, a result in the reader’s own words, an outcome (helped / mixed / didn’t help / too soon), and a next step unless completed. It retains the action, takeaway and goal context from that attempt. A subsequent attempt uses the previous next step as its action context. History is paginated and can be corrected. Completed actions can be reopened.

Correcting an older reflection does not replace a newer plan. Correcting the latest reflection updates the action only while its context is still current. Editing the action text resets its next step and completion state; changing the idea or goal keeps that state but protects it from corrections to the older context. Reopening also protects the open state from earlier completion corrections. No reflection history is deleted by these operations.

## Implementation and data

- New migration `e1f2a3b4c5d6`, following RD-56 `d0e1f2a3b4c5`: action state and counters on `reading_takeaways`, plus `reading_reflections` history.
- Existing saved actions become pending; entries without an action remain ideas. Existing text is preserved, with no fabricated attempts.
- Authenticated, owner-scoped history/read/create/update/reopen routes. Filters run before pagination. A reflection belongs to a specific takeaway; a reflection ID alone cannot access another reader’s history.
- Writes lock the parent takeaway, check its revision, and commit history and action state together. Client request IDs make uncertain create retries safe. Identical edit/reopen retries return the current saved state without applying an old transition again.
- Loading an editable reflection returns its parent revision and reflection in one coherent read. Conflict recovery keeps drafts until the reader explicitly chooses to replace them. Failed saves keep inputs. Reload/close warns about unsaved inputs; drafts are not persisted across internal app navigation or a closed browser.
- Attempt dates use the browser’s current IANA timezone and are checked on the server. No future attempts. Dates in history render as calendar dates rather than UTC timestamps.
- No reminders, emails, scheduled jobs, generated summaries, reading-credit changes, or book-completion changes. Sophisticated spaced repetition remains RD-45 scope.

## Preview setup

Use the full-stack PR preview SOP and this branch’s backend and frontend together. Run `alembic upgrade head` against the isolated preview database before starting the matching backend. RD-54 through RD-57 migrations are included in this stack. Never point preview migrations at production.

Downgrading RD-57 preserves the original takeaways but drops reflection history, next steps and completion state. Export or back up that data before any intentional rollback. No production migration or deployment is part of this draft.

## Review walkthrough

1. Open Reading → My takeaways & actions. Save an idea with no action and confirm it appears under Ideas. Add an action and confirm it moves to Pending.
2. Record an attempt: choose the date, describe what happened, select a result, and give one next step. Reload and confirm the action and reflection persist.
3. Record another attempt, mark it completed, and confirm it moves from Pending to Completed. Read both reflections and their original goal/idea context.
4. Reopen the action. Correct the earlier completed reflection and confirm the action remains pending. Record a new attempt.
5. Edit an older reflection after a newer next step exists; confirm the new plan stays intact. Replace the original action and verify past reflections remain readable.
6. In two tabs, edit the same action. Save in one and confirm the other reports a conflict, keeps the draft, and offers to load the latest version before editing again.
7. Temporarily stop the preview backend during a save. Confirm inputs survive the failure. Restart it and retry; confirm no duplicate attempt appears.
8. Check keyboard navigation, mobile layout, long multiline notes, all filters, and loading older reflections. Confirm a second test account cannot see the first account’s notes or history.

## Validation

Focused backend tests cover schema validation, outcomes and next steps, persistence and snapshots, idempotency, historical corrections, state transitions, context/reopen guards, stale edits, filtering and pagination, owner isolation, dates, atomic rollback, auth, migration upgrade/downgrade, and no reading-reward side effects. Full PostgreSQL integration coverage runs in GitHub CI. Frontend typecheck and production build run locally and in CI.

Visual and full-stack UX acceptance remains for Michael’s later review. Passing automated checks does not mark the feature accepted or released.
