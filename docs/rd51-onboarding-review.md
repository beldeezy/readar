# RD-51: onboarding that preserves the reader's intent

Started September 17, 2026, from deployed dev revision `991f19b`.
Status: in progress. This is the first implementation slice, not the full
lovable onboarding release.

## Reader outcome

Feel understood without repeating answers. The stated challenge, desired
outcome and ideal reading style should reach the first recommendations, and a
temporary failure should not erase progress or require another explanation.

## Current flow inspected

1. `ChatOnboardingPage` runs a seven-stage conversation and saves the transcript
   locally for resume after refresh.
2. The final conversation summary is followed by a reader-controlled finish
   action. A separate extraction call produces the structured profile.
3. Pending profile data passes through recommendation preview and sign-in,
   then the authenticated onboarding save and recommendation request.
4. The stored profile already supports the challenge, future vision and ideal
   book description. The existing questions document describes an older
   questionnaire; `app/config/nepq.py` defines the active conversation.

## First slice

- Carry the extracted `future_vision` into `vision_6_12_months`, which existing
  recommendation scoring reads. Preserve an explicitly supplied scoring goal.
- Carry `ideal_book_description` into the preview scoring adapter, so reading
  preferences are not omitted before sign-in.
- Return a retryable service error when the model request fails. Do not invent
  another question, advance the stage, or return an empty successful profile.
- Reject incomplete required extraction fields without inventing a business
  stage. Retain the chat on the frontend until a usable profile is ready.
- Retry the failed operation: chat for a conversation failure, extraction for
  a finish failure. Keep the reader's submitted answer and prevent adding a new
  answer while the previous request awaits retry.

## Remaining RD-51 review

- Walk through aspiring, new and established entrepreneur personas. Check for
  unnecessary probing, repeated questions, unearned assumptions and whether the
  final summary represents the reader's actual goal and reading preferences.
- Review the final confirmation behavior near the conversation's turn cap.
- Test browser refresh, sign-in return and saved-profile reload end to end.
- Review whether the reader can correct their summary naturally before the
  handoff, and decide what intentional editing should look like.
- Evaluate perceived effort, mobile use, loading and error recovery with
  Michael before declaring the experience lovable.

## Boundaries

No ranking-weight changes, shipping integrations or email resumption are in
this slice. Purchase/shipping/arrival automation is the later RD-63 placeholder;
simple book selection and starting remain RD-53. Both application and Friendly
Competition remain part of the complete lovable release.

## Verification

Provider-mocked regression tests cover profile fields, incomplete responses,
failed calls and repeatable retries. No live AI call, production database write
or email send is needed for these tests. Frontend typecheck/build validates the
component change; full interactive onboarding remains a separate acceptance
check before RD-51 is complete.
