# RD-53 — from choosing a book to Now reading

User outcome: know what to do after choosing a book, and keep the choice when
waiting to obtain a copy.

This draft builds on RD-52 (draft PR #11), which builds on RD-51 (draft PR #10).
Michael will review all three later. No merge, release, or UX acceptance is
implied. Retarget in dependency order after the preceding changes are accepted.

## Reader flow

1. **Choose this book** on a recommendation or book detail saves the choice
   and opens Reading. Search in Reading offers the same selection action.
2. **Up next** holds chosen books. **I'm waiting for my copy** records a manual
   waiting state. Get book opens the purchase link without starting reading.
3. **Start reading** moves the chosen/waiting book into **Now reading** only
   after the write succeeds. **Move to Up next** allows correction.
4. Reloading or returning restores the saved state. Choosing a waiting or
   started book again preserves its state. Multiple reading books are supported.

Saved-for-later books remain in My Shelves and can be selected from their
detail page. Removing a book is an explicit action. Failed reads do not render
as an empty list; failed changes retain the current view and offer retry.

## Implementation and boundaries

- Add `reading_next` and `waiting_for_book` to the existing text status column;
  retain `currently_reading` for an explicit start. No migration is needed.
- `POST /api/reading/selection` validates the catalog book and uses an atomic
  upsert that preserves any existing reading journey state. The normal status
  endpoint makes explicit waiting/start/correction changes.
- Status and removal of an old recommendation interaction commit together.
  Selection/waiting/start do not create completed reading history or ratings.
- The reading list is authenticated and scoped to the current user. Covers and
  purchase URLs come from catalog metadata, with an Amazon title/author search
  fallback when no purchase URL is available.
- Recommendation and detail actions await shelf persistence before navigating
  or confirming. Optional feedback/preference writes cannot mask a save failure.
- Shipping tracking/integrations remain RD-63; logs, goals and progress remain
  RD-54. Existing recommendation ranking is unchanged.

Deploy the backend before the frontend when eventually releasing. An older
backend will reject the new selection endpoint/status values; the new frontend
shows retryable errors and must not pretend the book was saved. Existing rows
remain usable by the updated code.

## Verification

Frontend typecheck/build and backend compilation/import pass locally. New
Postgres-backed endpoint tests cover the complete choose/wait/start/correct
flow, reloads, retries, account isolation, unknown books, commit failure,
optional event failure, authentication, and existing read-history behavior.
Their executed results are recorded in PR CI and Notion.

Visual and full-stack acceptance remain pending for Michael's later review.
The previous local-preview browser attempt was blocked by the browser client;
no visual verification is claimed here.

## Later review checklist

Use the PR testing SOP with frontend and backend from this branch and an
isolated test database. A frontend-only Vercel preview cannot validate the new
backend behavior.

- Choose a recommendation and confirm Up next appears; reload.
- Mark Waiting for my copy, leave, return, and confirm the same choice remains.
- Open Get book and confirm the book is still waiting; no start is inferred.
- Start reading, reload, then choose the same book again: it stays Now reading.
- Move a started book back to Up next and retry a choice: no duplicate appears.
- Choose from a saved book's detail page and from Reading search.
- Simulate load/save failures: the list must not look empty or claim success;
  retry must remain possible. Check keyboard controls and phone-width wrapping.
- Confirm the flow feels clear and low effort before marking RD-53 Done.
