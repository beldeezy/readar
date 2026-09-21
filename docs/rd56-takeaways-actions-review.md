# RD-56 — turn reading takeaways into concrete actions

User outcome: use a book to improve the real challenge that brought the reader
to Readar.

This draft builds on RD-55 (#14), following RD-54 (#13), RD-53 (#12), RD-52
(#11) and RD-51 (#10). All remain unmerged for Michael's later review.

## Reader experience

- **Capture a takeaway** on each Now reading book opens a short form in Reading.
  The book is selected, and the form asks what stood out, one thing to try, and
  the goal or challenge the idea serves.
- The takeaway and goal context are required; the action is optional. A reader
  can save an idea quickly and return to add a practical step.
- Goal context starts from onboarding when available: future vision, then
  6–12 month vision, primary problems, or biggest challenge. Blank and oversized
  suggestions are skipped without truncating their meaning. The reader can
  write or revise the context, without changing their onboarding profile.
- **My takeaways & actions** links to a persistent collection below the reading
  list. Each card keeps its book, takeaway, action and goal together. Idea-only
  entries show **Idea saved**; entries with an action show **Ready to try**.
- Edit existing entries, add an action later, or clear an action while retaining
  the idea. Book attribution is fixed after creation. Moving a book to Up next
  or removing its shelf entry does not remove or hide its takeaways.
- Only one editor opens at a time. Loading, saving, confirmation and retry
  states are explicit. Failed writes retain form inputs and the create retry
  key. A conflicting edit requires loading the saved version before retrying;
  replacing unsaved text asks for confirmation.
- Cancelling a changed draft asks before discarding it. Reloading or leaving
  the browser tab warns while a draft is unsaved. Draft text stays in component
  memory until saved; in-app navigation is not a durable draft mechanism.

RD-57 will add attempts, results and next steps. This draft does not mark an
action completed, award reading points, finish a book, generate notes or
summaries, send emails, or introduce spaced repetition.

## Persistence and integrity

Authenticated `/api/reading/takeaways` endpoints list, create, read and update
the current reader's entries. All reads and updates scope by owner, including
pagination anchors and conflict recovery. Text renders as plain React text.
Note content is not sent to AI, analytics or new logging paths.

Create requests carry a stable client UUID with a unique `(user_id, client_id)`
constraint. Identical retries return the same entry. Reusing that key with
different text returns a conflict and the owner's existing entry ID, so an
uncertain save cannot silently duplicate or lose changes. Updates use a row
lock and expected revision; identical retries are no-ops and stale conflicting
edits receive 409. Failed transactions roll back.

Each entry stores its book ID plus the title/author at capture, reader-authored
goal context, text, optional action, revision and timestamps. Onboarding and
catalog edits do not silently rewrite these snapshots. Removing a book from a
shelf leaves the entry intact. Catalog deletion is restricted while takeaways
reference that book, protecting reader notes from an unrelated catalog cleanup.

The collection is paginated by creation time and ID (50 entries by default,
maximum 100), with a Load more control. Takeaway editing does not move the
pagination boundary. The UI temporarily places a just-saved item first for
feedback; a fresh load restores creation order.

## Migration and preview

Migration `d0e1f2a3b4c5` follows RD-55's `c9d0e1f2a3b4` and adds
`reading_takeaways`, its constraints and collection index. It does not change
existing notes, profiles, reading logs or rewards.

Against the isolated preview database, run `python -m alembic upgrade head`
from `backend`, then use the matching backend/frontend. No production migration
or deployment has been performed. Downgrade drops the new table and its notes;
use only in a disposable preview or an explicitly approved data-loss rollback.

## Verification

Local frontend typecheck/build, backend compile/import, offline migration SQL
generation and 13 non-database tests pass. CI runs the complete Postgres suite
and all 25 RD-56 cases covering:

- Text validation, whitespace, optional actions and onboarding suggestions.
- Capture, edit, reload, safe retries and uncertain-save conflicts.
- Stale edit protection and account isolation, including pagination cursors.
- Book/profile snapshots retained through catalog, onboarding and shelf changes.
- Pagination, unknown books, immutable attribution and transactional failures.
- No reading credit/completion side effects and auth on every endpoint.
- Actual migration upgrade, database defaults/constraints/index and downgrade.

Visual and interactive full-stack acceptance remain pending for Michael's later
review. Build/API test success is not a claim of browser interaction validation.

## Later review checklist

1. Capture an idea from Now reading. Check the selected book, suggested context
   and how quickly you can save. Try with and without an action or onboarding.
2. Reload and edit the takeaway, action and context. Check that the profile and
   reading rewards are unchanged.
3. Move the source book off the active shelf. Revisit its saved takeaway through
   My takeaways & actions and add an action.
4. Simulate a failed save and retry. Keep the draft and verify only one entry is
   stored. Try editing after a lost response and recovering the saved entry.
5. Edit the same note in two sessions. The older conflicting edit must be
   blocked, with its draft retained until the reader chooses to load the latest.
6. Review long text, keyboard focus, phone layout, loading/empty states and
   pagination. Confirm the prompts connect the idea to a real-world next step.
7. Review unsaved-draft behavior during cancel, reload and in-app navigation.
   Decide whether broader draft recovery is needed in the whole-experience pass.
