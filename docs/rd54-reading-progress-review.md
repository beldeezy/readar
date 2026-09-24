# RD-54 — quick reading logs and book progress

User outcome: record reading with little effort and see progress.

This draft builds on RD-53 (PR #12), following RD-52 (#11) and RD-51 (#10).
Michael will review the experience later; no merge or release is implied.

## Reader experience

- Each Now reading card asks **Where did you stop?** Save the page reached or
  the number of chapters completed. The current position and optional percentage
  appear alongside the daily reading goal.
- Defaults: 10 pages/day; selecting chapter tracking starts at 1 chapter/day.
  Goals are adjustable. Book settings also allow a starting position and edition
  length. The catalog's page count is a starting suggestion, not an immutable
  edition fact. Unknown lengths show position without a percentage.
- One entry per book and local calendar day. More reading that day updates the
  stopping point; retries do not add duplicate credit. Browser IANA time zone
  is sent to the server, which determines today (including DST).
- Reading history supports correction and removal. Amounts are differences
  between successive stopping points, starting from the configured baseline.
  Correcting an earlier entry recalculates later amounts. Gaps between entries
  are not evidence of the exact days on which those intervening pages were read.
- Existing reading before the starting position earns no newly logged credit.
  Positions must stay in date order and within the edition length, when known.
  Tracking units stay fixed while logs exist to avoid mixing pages and chapters.
- Loading, empty, saving and error states are explicit. Failed writes retain
  input; stale revisions require a reload of the saved values before retrying.

## Persistence and scope

Authenticated endpoints under `/api/reading/books/{book_id}` read progress,
save settings, and upsert/delete dated logs. All queries scope data to the
authenticated reader. Mutations require the book to be Currently reading.
Progress survives moving a book back to Up next or removing/re-adding its shelf
entry. It does not change that shelf state or create a completed-book rating.

Settings and log writes share a row lock and revision counter per user/book.
GET uses a shared lock for a consistent settings/log snapshot. Identical retries
are no-ops; stale conflicting writes return 409. A unique date constraint adds a
database guarantee against duplicate daily entries. Settings and logs commit
together, with rollback on failure.

Streaks and points remain RD-55. Completion, rating and next-book guidance remain
RD-61. Daily logged amounts are derived data; future rewards must handle edits,
removals and backdated entries, and must not award credit just because a save
request succeeded.

## Migration and release

New migration `b8c9d0e1f2a3`, after existing head `a7b8c9d0e1f2`, creates
`reading_progress` and `reading_logs`. It does not alter existing user/book data.
Apply `alembic upgrade head` to an isolated preview database first, then deploy
matching backend and frontend. Full-stack testing needs all three steps.
When a production release is approved, apply the migration before deploying
code that reads the new tables. No migration has been run in production here.

The downgrade drops the new tables and their logs; it is for disposable test
databases or a separately approved data-loss operation. Prefer retaining these
additive tables if rolling application code back after readers have used them.

## Verification

Local frontend typecheck/build, backend compile/import and offline migration SQL
generation pass. PR CI runs the full Postgres suite plus new tests for:

- Save, reload, same-day updates, identical retries, correction and removal.
- Starting position, custom goals, chapters and unknown edition lengths.
- Stale-device edits, invalid/future/backwards/out-of-range entries.
- Waiting-book rejection, account isolation, auth and failed commits.
- Progress retained on pause; reaching the final page does not auto-complete.
- Local-day boundaries and invalid time zones.
- Actual migration upgrade/downgrade in a disposable Postgres schema.

Visual and interactive full-stack acceptance remain pending for Michael's later
review. The previous local-preview browser attempt was blocked by the browser
client; build/test success is not a claim of visual verification.

## Later review

1. Start a book, log a stopping page, reload, and log further progress the same
   day. Confirm the amount replaces the day's earlier amount instead of adding
   it twice.
2. Change the goal and edition length; try a partially read book and chapter
   tracking. Check unknown totals and first-use guidance.
3. Edit/remove an earlier log. Confirm current position, daily amounts and goal
   feedback recalculate without negative progress.
4. Open two sessions and save in both; the older conflicting edit must be
   blocked with a reload action. Simulate network/save failures and retry.
5. Review date controls, keyboard navigation, phone-width wrapping and how much
   effort the main logging action requires. Decide whether it feels lovable.
