# RD-65: finish onboarding after a confirmed summary

The September 26 roadmap review made first-use reliability the first delivery milestone. This follow-up addresses a reproduced summary-to-recommendations blocker. It extends the earlier [RD-65 handoff work](rd65-recommendation-handoff.md).

## Observed failure and release baseline

The public onboarding review used a synthetic residential-cleaning business. Readar summarized the reader's context and asked, “Does that land right, or should I adjust anything?” The reader replied, “Yes, that accurately describes my situation and goal.” Discovery continued, then generated book suggestions in ordinary chat. Asking to finish produced a retryable error twice.

Render's live backend deployment was `dep-dap7rgjncjis73a1uajg`, commit `7ab0199550cb163686d82c1654d648fcd9ff4259`, deployed September 22. Its backend files match this change's base, dev commit `4304cf0ac3117c7befb460176af4389417f3f83e`. Runtime logs at September 26 20:06:57Z and 20:07:21Z both reported:

> No actionable onboarding question after one rewrite: Give a brief factual summary followed by one confirmation question, with ui=confirm.

The service runs migrations before startup and its startup log confirms email delivery is paused. The exact database migration revision and production frontend alias/commit still need direct verification under RD-31. GitHub records a successful Vercel deployment for main `bd15820dc15cd73a875525d3b5381493c0c7f221`; that alone does not certify which revision the public alias serves.

## Change

- Recognize the observed summary wording, including an older saved conversation.
- Keep summary text, confirmation controls and conversation stage aligned when a summary arrives as discovery advances to the next objective.
- Accept the observed complete affirmation without another AI call. Full matching keeps corrections and uncertainty, including “yes, but…”, in the summary-review flow.
- Tell the discovery model to gather reader intent and leave book selection to the catalog engine. Common generated book-list/pick wording triggers the existing single rewrite before display; discussion of books the reader has already read remains valid.

The language checks are deliberately bounded. They do not prove that every possible generated statement is factual or that every natural-language agreement can be recognized. Unknown or ambiguous replies continue through review rather than silently completing onboarding. Provider failures retain the existing retry behavior and answers.

## Verification

The new regression cases fail against the previous implementation and pass with the fix. All 38 onboarding unit tests pass, covering the exact observed summary/agreement, summary-stage boundaries, older saved summaries, corrections, generated recommendations, reading-history discussion, question quality, handoff and provider failure. Backend byte-compilation passes. The pull request's CI remains the gate for the full PostgreSQL suite, application import, frontend tests and production build.

## Live acceptance still required

1. Complete a new onboarding conversation using the cleaning-business scenario and a second reader with a different goal. Confirm that a final summary displays confirmation controls and agreement reaches catalog-backed results.
2. Reply to a summary with a correction. Verify the corrected facts appear for review and the app does not finish until confirmed.
3. Resume an existing saved summary using the observed long agreement. Verify it finishes without another discovery question.
4. Verify anonymous preview, sign-in, optional reading-history import/skip, results, and beginning a reading journey. Exercise a failed request and retry with answers preserved.
5. Confirm RD-71/RD-73 accepted behavior remains intact. Record the tested frontend/backend revisions and database revision before marking RD-65 accepted.

This branch changes backend conversation handling only. RD-65 remains awaiting live acceptance; no deployment, migration, provider replacement or email setting change is included.

Approved planning sources: [Readar HQ](https://app.notion.com/p/Readar-HQ-3dcd7550b0c481e2b2afe89d519360fa), [master/UX roadmap](https://app.notion.com/p/ac9f4d37b45e4d2ca52d5220c72943a8?v=3ded7550b0c48114a3f6000cd69e0fbc), and [13-week season plan](https://app.notion.com/p/13-week-season-plan-3dcd7550b0c481748e3fd03ef346f9ad).
