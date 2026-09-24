# RD-52 — explain why each book fits

User outcome: choose a book confidently, with less searching.

This draft builds on the unmerged RD-51 branch. RD-51 remains draft PR #10.
Review RD-52 separately; neither change is approved for release by this work.

## What changed

- Each recommendation carries `fit`: the reader's stated challenge or goal,
  a supported topic connection, an excerpt from the actual book details, and
  a suggested reading focus. Preview, signed-in, generic and legacy response
  builders use the same service.
- A goal connection is explicitly labelled as a goal. Stage-only connections
  and sparse/unrelated book details get honest fallbacks. Topic connections
  use existing catalog tags, without claiming the book solves the challenge.
- The card displays this explanation immediately with the recommendation.
  It no longer calls the separate AI presentation endpoint or reuses its
  book-ID-only pitch cache. Older responses without `fit` remain renderable.
- The first card says “First suggestion”; position alone no longer implies
  “High fit.” Catalog excerpts and suggested actions are visually separate.

Ranking weights, filters, refresh allowances, purchase actions and saved-book
behavior are unchanged. No database migration or additional provider call is
required. The old presentation endpoint remains available for compatibility,
but this screen no longer invokes it.

## Verification

- 14 new backend tests pass locally. They cover relevant/unrelated books,
  goal vs challenge, stage matching, missing data, false substring matches,
  text cleanup, legacy paragraph accuracy, and response serialization through
  the real preview/signed-in/generic ranking paths with database reads mocked.
- Frontend TypeScript check and production build pass.
- Full Postgres suite runs in PR CI; local tests did not access a live database.
- Browser visual review remains pending: the cloud browser rejected the local
  preview URL with `ERR_BLOCKED_BY_CLIENT`. No visual or full-stack acceptance
  is claimed from the build result.

## Review before accepting

Use the PR testing SOP with both frontend and backend on this branch and an
isolated test database. A frontend-only preview against the old backend cannot
verify the new `fit` response.

1. Onboard with a concrete challenge, then compare at least two recommended
   books: does each explanation help you choose, with recognizable reader
   words and different book details?
2. Review a goal-only connection, a stage-only connection, an unrelated book,
   and a book with sparse details. None should claim a specific solution
   without evidence. A missing `fit` response should show useful fallback copy.
3. Change the reader profile and refresh: the displayed priority must follow
   the current recommendation response. Navigate back and through the carousel.
4. At desktop and phone widths, check wrapping, readability, and access to
   save/read/get-book actions. Confirm the screen makes no presentation request.
5. Review real catalog quality and recommendation relevance. Explanations
   depend on catalog tags/details being accurate; this task does not validate
   those source claims or fix RD-11's ranking issues.

RD-15 overlaps this explanation work; reference this implementation when
reviewing that item. RD-11 remains a separate relevance task. Keep RD-52 in
progress until the relevant and fallback UX cases are accepted.
