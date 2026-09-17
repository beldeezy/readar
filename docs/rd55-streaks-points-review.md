# RD-55 — streaks and points

User outcome: feel encouraged to keep reading, and know exactly what earns credit.

This draft builds on RD-54 (#13), after RD-53 (#12), RD-52 (#11) and RD-51 (#10).
Michael will review the full experience later. These drafts remain unmerged.

## Draft rules for review

| Rule | Behavior |
| --- | --- |
| Daily credit | Meeting any one book's saved goal earns 10 points, capped at 10 across all books for that reading date. |
| Units | Each book uses its own pages/chapter goal. Partial goals from separate books are not combined. |
| Streak | Consecutive qualifying dates across all books count. Yesterday's streak remains active while today is still available. |
| Missed day | A full missed date resets the current streak. Points and best streak remain; today can begin a new streak. |
| Goal changes | Each dated entry keeps the goal from its first save. Book goal changes apply to newly created entries, including backdated entries. |
| Corrections | Credit is recalculated from saved stopping points. Edits, removals and starting-position changes can increase or decrease points and best/current streaks. |
| Starting point | Earlier reading before the configured baseline earns no credit. |
| Time zone | The browser supplies an IANA zone; the server determines today. Dates remain fixed during travel, and dates ahead of local today do not count until that date arrives. |
| Late logging | An honest backdated entry can repair a missed log. No automatic streak freeze or purchase is offered. |

The scoring amount is a draft default, not a previously approved product rule.
These are private, self-reported progress points. Partner multipliers, leagues,
discounts/redemption and book-completion rewards are separate roadmap work.

## Experience

Reading now shows one summary even when the current shelf is empty: current
streak, best streak, total points and the last seven local dates. It explains the
rules and offers encouraging new, active, continue-today and restart states.
Pausing or removing a book from the shelf does not erase its logged credit.

Book cards show each date's saved goal, including when today's goal differs
from the goal configured for new entries. A newly met goal gets a simple save
confirmation. Summary refresh runs after successful changes and on return to
the browser; an unavailable summary shows an explicit retry without reporting
zero points or pretending an already saved log failed.

The calendar checks for midnight/time-zone changes on focus and every minute.
Book progress reloads after a day change, deferring while a write is in flight.
Unsaved form inputs are preserved with a notice to check their reading date.
No timer awards points; rewards come only from the saved history.

## Implementation and migration

`GET /api/reading/rewards?tz=...` requires authentication and reads only that
reader's logs and settings in one SQL statement. Qualification is based on
the difference between consecutive positions (or the starting baseline).
Dates are deduplicated across books before calculating points and streaks.
There is no mutable points counter or award write to duplicate on retries.
Existing per-book locks, revisions and transactional writes still protect logs.

Migration `c9d0e1f2a3b4`, after RD-54's `b8c9d0e1f2a3`, adds a required
`reading_logs.goal_target` with a range constraint. Existing RD-54 logs take
their book's saved goal at migration: earlier goal values were not recorded
and cannot be reconstructed. API-created logs always have matching settings;
the migration uses 10 only as a defensive fallback for orphan logs.

Preview setup: from `backend`, point `DATABASE_URL` at the isolated preview
database and run `python -m alembic upgrade head`, then start the matching
backend/frontend. This migration and the RD-55 backend must be deployed together:
older code does not populate the newly required goal field. No production
migration or deployment has been performed. Downgrade removes goal snapshots
but retains logs; it loses the historical targets. Use only in a disposable
preview or as part of an explicitly approved rollback.

## Verification

Local frontend typecheck/build, backend compile/import, offline migration SQL,
and 12 non-database tests pass. CI runs the complete Postgres suite plus all 22
new RD-55 cases covering:

- New/active/continue/restart states, gaps, best streak, DST and year boundaries.
- Same-day retries, further reading, multiple books and page/chapter goals.
- Historical goal snapshots, corrections, deletion and starting baselines.
- Cross-book streaks, shelf removal, missed-day recovery and backdated repair.
- Account isolation, rejected writes, failed commits, auth and time zones.
- Actual RD-54 → RD-55 migration with page/chapter backfill and downgrade.

Visual and interactive full-stack acceptance remain pending for later review.

## Later review checklist

1. Start a book and log less than the goal, then enough to meet it. Check the
   confirmation, today's checkmark, one-day streak and 10 total points.
2. Save again and meet a second book's goal on the same date. Points stay at 10.
3. Change the goal after today's first entry. Today's saved target stays fixed;
   new dates use the updated goal. Try chapter tracking on a different book.
4. Add consecutive past dates, correct them and remove one. Check points and
   streaks against the saved history, including backdated repair after a gap.
5. Switch books or move one to Up next. Previously logged credit remains.
6. Simulate a rewards request failure after a successful log save: the log stays
   saved, old numbers are identified as stale, and Retry rewards catches up.
7. Test an open tab across local midnight, with an unsaved form and with a save
   in flight. Confirm fresh rewards, correct date controls and preserved input.
8. Review keyboard/screen-reader feedback and phone-width layout. Decide whether
   the default score, one-book goal rule and recovery wording feel motivating.
