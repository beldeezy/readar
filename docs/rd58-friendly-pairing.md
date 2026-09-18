# RD-58 — Pair readers for optional Friendly Competition

Draft for Michael’s later UX review. Based on RD-57 (`codex/rd57-action-reflections`, PR #16). The prior drafts remain unmerged.

## Reader outcome and scope

A reader can opt into a reading partnership, meet another willing reader, see a useful waiting state, stop searching, or leave a pairing. This implements the pairing foundation of Friendly Competition. Weekly rounds, consistency-weighted scoring, partner progress and results belong to RD-59. No emails, chat, invitations, notifications, multipliers, leagues or reading-credit changes are included.

The August 6 direction allowed matching any available reader. Same-book and skill-based matching remain later; the September 17 Minimum Lovable Product direction makes core pairing part of v1.

## Experience

On Reading, open Friendly Competition. Select a book from Now reading, choose a short reading name, and explicitly agree to share that name and book title/author. The checkbox starts unchecked on every new opt-in. No profile name or email is automatically exposed.

The oldest waiting opted-in reader is paired with the newcomer. With nobody waiting, the reader enters a durable queue. They can keep reading, leave the page, check status manually, or stop searching. The queue does not invent a wait estimate or promise a notification. The page checks status every 30 seconds while visible and when the reader returns to the window.

A paired reader sees their partner’s chosen reading name and selected book, alongside an explanation of their own shared fields. These book details are snapshots: moving a book on a shelf or editing catalog metadata does not silently change what was shared. To choose different shared details, leave and opt in again.

Either reader can leave. The pair ends atomically for both, and subsequent responses reveal no former-partner details. The other reader sees that the pairing ended on their next successful status check; the page cannot retract details already displayed while offline. Neither is automatically requeued. Both retain individual reading progress and can explicitly opt in again. Former partners may match again if both choose to rejoin; blocking and custom partner selection are not part of this draft.

## Persistence, privacy and concurrency

- Migration `f2a3b4c5d6e7`, after RD-57 `e1f2a3b4c5d6`, creates `friendly_pairs` and `friendly_participations`. It does not enroll existing users or modify reading data.
- One participation record per reader, explicit consent timestamp, monotonic revision, and saved request fingerprint. Pair records retain membership and lifecycle timestamps for future round handling.
- All match/leave writes take a PostgreSQL transaction advisory lock. This deliberately simple approach serializes a small launch queue across workers, preventing duplicate claims and partial departures. No network work occurs inside the lock. A larger launch may need a more concurrent queue design.
- GET takes the shared version of the lock for a coherent, read-only response. It never joins, matches, requeues or otherwise changes state. Responses use `Cache-Control: no-store, private`.
- A lost-response retry returns the current state if it matches the reader’s last saved request. A changed request with the same ID conflicts. Older requests after another command fail the revision check, so retries cannot revive old consent or leave a newer pairing.
- A stale Stop searching request after a match conflicts; the reader must check status and deliberately decide whether to leave the pairing.
- The partner response is an explicit allowlist: reading name, book title, book author. No account ID, email, onboarding context, notes, takeaways, reflections, daily logs or points are returned. There is no arbitrary-user lookup endpoint.
- Failed writes preserve the form. Conflict recovery explicitly loads current state. Cancelling a form also checks status, so an uncertain successful join is not hidden. Unsaved inputs are not stored across internal navigation or a closed browser.

## Full-stack preview

Use the existing PR preview SOP with this branch’s backend and frontend together, an isolated preview database, and two separate test accounts/browser profiles. Run `alembic upgrade head` before testing. The complete migration stack through `f2a3b4c5d6e7` is required. No production migration, merge or deployment is part of this draft.

Downgrading RD-58 drops pairing and consent/lifecycle records, while leaving individual reading data intact. Back up the preview data first if you intend to preserve pairing history.

## Review walkthrough

1. In account A, start a book. Open Friendly Competition, choose a nickname and book, and verify joining is disabled until the sharing checkbox is checked.
2. Join with A while nobody else is waiting. Confirm the waiting copy is useful, reload, and confirm the search persists. Record ordinary reading progress while waiting.
3. In account B, start a different book and opt in. Confirm both accounts show each other after Check status or the next visible-page update. Verify only the chosen name and book title/author are shared.
4. In a third account, confirm no partner information is visible. Its own search should remain waiting while A and B are paired.
5. Leave from either paired account. Confirm the other sees Pairing ended, with no automatic new match and no loss of individual progress. Explicitly rejoin to find another available reader.
6. Cancel a waiting search. Verify it stays stopped after reload and does not match a later newcomer.
7. Use two tabs of one account: keep one waiting view stale while another account joins. Try Stop searching in the stale tab, load current status after the conflict, then decide whether to leave.
8. Interrupt a request or temporarily stop the preview backend. Confirm errors leave choices intact; retry or Check status without duplicate enrollment. Cancelling an uncertain join form should reveal any search that actually saved.
9. Check mobile layout, keyboard navigation, long book titles, nickname validation, loading feedback, empty reading lists and offline status recovery.

## Validation

Automated tests cover consent/name validation, authenticated access, book eligibility, empty/read-only state, waiting and cross-book pairing, strict shared-field boundaries, leaving/rejoining, stale commands, retries after departure, FIFO ordering, snapshot semantics, atomic rollback, migration upgrade/downgrade, and no reading-reward side effects. Independent PostgreSQL sessions race three joins, including repeated requests from the same reader, to verify that one reader cannot be claimed twice.

Frontend typecheck/build and the full PostgreSQL suite run in GitHub CI. Visual and two-account full-stack UX acceptance remains for Michael’s later review; passing automated checks does not mark the draft accepted or released.
