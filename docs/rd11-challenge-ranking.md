# RD-11 — Match the reader's actual challenge

The previous scorer compared a whole challenge sentence against short tags and
emitted `bottleneck:{whole sentence}` keys that could not match catalog keys. Its
broad domain boost also mixed current problems with future goals. Different
problems could therefore produce the same top picks.

## Change

- Use a shared, bounded phrase vocabulary for both natural-language challenges
  and catalog tags, promises, frameworks and outcomes. No title allowlist, model
  call, new API dependency, migration or rewritten reader profile.
- Prefer specific catalog evidence (for example, client acquisition/lead flow)
  over a broad sales/marketing connection. Repeated words cannot increase scores.
- Use the current challenge first; future goals are a fallback when the challenge
  is missing. Preserve broad domain fallback for unrecognized phrasing.
- Reconcile bottleneck insight keys and use the same concepts for displayed fit
  explanations. Explanations describe a catalog topic connection, not a guarantee.
- Resolve ties deterministically before diversity penalties.
- Route the legacy re-engagement entrypoint through the signed-in scorer so all
  personalized paths share the change and already-read exclusions. User emails
  remain paused; this does not send anything.

## Evaluation

Fixed 84-book tagged catalog, original 15 personas unchanged:

| Metric | Before | After |
| --- | ---: | ---: |
| Expected title in top 3 | 8/15 (53.3%) | 13/15 (86.7%) |
| Expected title in top 5 | 10/15 (66.7%) | 15/15 (100%) |
| Mean reciprocal rank | 0.446 | 0.756 |

The ratchet now protects the original 15 separately, so adding easier cases
cannot mask a regression. Added P16 (cleaning company needs steady lead flow to
retain cleaners) and P17 (the September 21 screenshot's profitable-volume and
margin challenge). Both fixed-catalog cases start with Book Yourself Solid,
The Referral Engine and The 1-Page Marketing Plan at a five-book limit.

Unit checks cover phrase normalization, word boundaries, specific versus generic
fit, repeated metadata, missing signals, full-length reader text, changed
challenge/ranking, deterministic ties and shared entrypoints. PostgreSQL checks
cover saved-profile/preview parity, an actual Goodreads CSV upload followed by
fresh picks, persisted read exclusion, and isolation from another account.

These results concern the committed fixtures, not Michael's private test database
or exact CSV. The full suite runs in GitHub CI; inspect the linked PR checks.

## Owner review on current dev

1. Pull current `dev`, restart both servers using `docs/lovable-loop-review.md`.
2. Start a fresh onboarding for the cleaning-business lead-flow problem. Confirm
   the summary preserves the root issue before accepting it.
3. Review the books and the catalog evidence shown in each card. A book about
   generic entrepreneurship should not displace a concrete lead-flow match just
   because both have marketing tags.
4. Import a CSV marking a recommended book as read; request fresh recommendations.
   That book should disappear, while the problem remains the same.
5. Repeat with a different challenge, such as cash flow or owner dependence.

Engineering verification is separate from Michael's acceptance of the actual
recommendations. Keep RD-11 in Verify live until that review passes.

## Limits and related work

This is deterministic topic matching, not full language understanding. Ambiguous
or negated language and incomplete/incorrect catalog metadata remain limitations.
The actual stored profile/catalog must be inspected for a remaining bad match.
No new book-content facts were invented. Existing business-model boosts and niche
quotas remain RD-21; broader catalog vocabulary/coverage remains RD-22/RD-14;
additional explanation refinement remains RD-52/RD-15.
