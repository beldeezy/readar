# RD-59 — Fair weekly reading competitions

Draft for Michael’s later review, stacked on RD-58 / PR #17. Nothing in this draft is merged or deployed to production. The exact scoring weights and calendar are product hypotheses, not previously accepted rules.

## Reader outcome

After pairing, both readers can explicitly opt into weekly progress sharing. Each sees a clear scoring rule, a shared calendar, a seven-day score bar, qualifying days and the fraction of each reader’s own book read during the round. Results recognize a win or a shared win, while a private all-time competition total survives a pairing ending.

## Draft rules

- A qualifying day earns 10 competition points. Page readers must log at least 10 pages; chapter readers must meet their saved daily chapter goal, frozen when joining. Maximum: 70 consistency points per round.
- Reading a fraction of the selected book earns up to 5 extra points per round: 20% of the book adds 1 point; 100% adds 5. One additional qualifying day outweighs the entire bonus. Scores use integer hundredths of a point, with the bonus rounded down deterministically.
- The first consenting reader chooses their browser’s timezone as the shared round calendar. The second reader sees and explicitly accepts that calendar. Log dates are evaluated in that calendar; a date ahead of it waits until that day arrives.
- Both readers get a full first round, beginning the next calendar day after both consent. Each subsequent round lasts seven days. These are rolling seven-day rounds, not Monday–Sunday league weeks.
- Positions already reached before both opt in, plus reading before the round begins, earn no competition credit. The percentage reflects reading during the round, not total historical completion.
- Equal nonzero scores share the recognition. Two zero scores produce a quiet week without a winner. There are no winner bonus points or cosmetics in this draft.
- Closed results stay fixed. Backdated corrections still change the personal reading record; they do not rewrite closed competition results. Corrections affecting an open round update its score.
- Leaving ends the open round without a winner. The reader keeps earned competition points. A private all-time total includes closed, interrupted and current rounds; the UI shows the latest 12 closed/interrupted results.
- Competition points are separate from RD-55’s individual reading points. No multipliers, discount rewards, leagues, promotions or notifications are included.

## Fairness limits for review

The system relies on self-reported reading. Chapter sizes and reader-selected chapter goals differ, so chapter scoring is a practical draft rather than a claim of exact page equivalence. Book units, starting position and edition length cannot change while a reader has opted into the current pairing’s rounds; leaving allows correcting those settings. Personal daily goals can change, but the competition target stays frozen. A completed or paused selected book can remain in a pairing, but future credit still requires actual reading logs on that book.

The closed-round rule is deliberately firm: a reader who misses logging before a round closes can correct their personal record later but receives no retroactive competition credit. Review whether a clearly defined grace period would improve the experience before accepting this rule.

## Consent and privacy

RD-58 consent only covered a chosen reading name and book title/author. Migration does not expand it. Each reader must separately choose to share their qualifying-day count, percentage read in the round and competition score. Until both consent, no partner progress is returned. The second reader can review the shared calendar before joining.

Only the current consenting pair sees the live comparison. After either leaves, subsequent summary responses return the requesting reader’s own total and results; no former-partner identity, book, score or progress is returned. Already displayed details cannot be retracted from an offline browser. Email, notes, reflections and onboarding answers remain private.

## Data and transitions

Migration `a3b4c5d6e7f8` follows RD-58 `f2a3b4c5d6e7`. It adds nullable consent/configuration fields and creates `friendly_rounds`; existing readers start without progress-sharing consent. One row per pairing/start date stores each side’s qualifying days, normalized progress, integer score and closing state.

Explicit round synchronization uses POST `/api/reading/competition/rounds/sync`: it may finalize elapsed rounds and create the next round. Pairing GET remains read-only. Synchronization is idempotent and also runs before and after each reading-progress mutation. Before a late correction is applied, elapsed rounds close using their unchanged source data. The updated log and open-round score then commit together. Log retries derive the same score instead of adding points.

Pairing, round sync and reading-progress writes share a transaction advisory lock, always acquired before per-book locks. This simple ordering prevents match/departure/rollover races across workers and preserves RD-58’s small-launch queue design. It serializes reading writes too, so throughput should be revisited before a larger launch. No network operation or email happens within the lock.

Consent uses request IDs and the pairing revision, plus the reading revision the user reviewed. A changed book configuration or calendar prompts a refresh before joining. Rejoining another pairing clears progress-sharing consent; old requests cannot turn it back on.

## Full-stack preview

Use the existing PR preview SOP with this branch’s matching backend/frontend, two test accounts in separate browser profiles and an isolated preview database. Run `alembic upgrade head` through `a3b4c5d6e7f8` first. Do not point preview migrations at production. Downgrade removes weekly scores/configuration while retaining RD-58 pairings and personal reading data; back up results first if needed.

1. Pair two readers using different books. Save each book’s edition length in Book settings. Verify neither sees partner progress before joining rounds.
2. Opt in with reader A, check the target/calendar, and confirm A waits for B. Opt in with B and confirm the first full round is scheduled for the next shared calendar day.
3. Once the round begins, log reading for both. Confirm 10 pages on a 100-page book and 20 on a 200-page book each earn 10.5 points for that day. A second qualifying day should beat a one-day whole-book finish.
4. Retry a saved log, correct a current-day position and delete a current log. Confirm the score follows saved positions, with no duplicate credit.
5. Review the comparison bar at zero/zero, equal nonzero scores and a lead. Check long book titles, narrow screens, keyboard controls and loading/error recovery.
6. For natural rollover, return after the round’s final calendar day. Review the result, fresh score and all-time total. Automated tests use controlled clocks for midnight, calendar transitions and catch-up; do not change production clocks for previewing.
7. Correct a prior-round log after rollover. Confirm personal progress updates and the completed result remains fixed. Test both a shared win and a quiet week.
8. Leave during a round. Confirm no winner for that interrupted round, earned points remain, both lose partner-summary access, and a new pairing requires new progress-sharing consent.
9. Try a third account and verify it cannot see either reader’s rounds. Interrupt a save and check recovery without duplicate consent or lost reading data.

## Validation and acceptance

Focused tests cover scoring dominance, book-relative fairness, chapter targets, deterministic ties, consent and privacy, timezone boundaries, pre-competition baselines, duplicate logs, rollover, late corrections, departure, settings changes, atomic rollback, catch-up and migration behavior. The full PostgreSQL suite runs in CI alongside frontend typecheck/build.

Visual and two-account full-stack acceptance remains pending Michael’s review. Prepared means reviewable implementation, not accepted scoring rules or a released feature.
