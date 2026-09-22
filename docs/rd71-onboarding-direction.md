# RD-71 — Clear onboarding questions and confirmation

Readers could receive an acknowledgement such as “I've got what I need” while the
reply box still expected input. The hidden stage had advanced, but the message
did not ask the next question. Finishing could also rely on the model's completion
flag instead of an explicit reply to a reviewable summary.

## Behavior

- Keep Michael's approved business-problem/curiosity opener as fixed product copy.
- Supply the following objective so a completed stage bridges into its next
  question in the same reply. Ask one question grounded in the existing answers;
  do not invent business details, pain, urgency or emotional stakes.
- Check that an input-seeking reply ends with one question. Reject common stock
  sales phrases, exact repeated questions and acknowledgement-only responses.
  Give the model one rewrite using the full transcript and the resulting
  objective, without advancing twice or saving the rejected draft.
- If rewriting fails, return the existing retryable error. Keep the reader's
  transcript and stage. Each provider call has a 20-second timeout and no SDK
  retries; the frontend allows 60 seconds for the two-call path. Profile
  extraction retains its 30-second provider timeout with a 45-second client limit.
- Offer Yes/No only for suitable questions; keep open questions free-text.
- End discovery with a factual summary and the fixed question: “Does that capture
  what you want from your next book, or would you change anything?” Show
  **Yes, that's right** and **I'd like to change something**. The correction
  button focuses the reply box and preserves an existing draft.
- Finish only after an explicit short agreement to that summary. “Yes, but…” or
  uncertainty requires a revised summary and confirmation, even past the turn
  budget. Older saved summaries receive a new reviewable summary before finishing.
- After confirmation, give the explicit **Take me to my recommendations** action.
  Do not redirect or extract the profile until the reader selects it. Keep the
  full transcript, profile fields, retry behavior and resume-on-refresh support.

Question structure is checked in code; relevance and tone still depend on the
model and the reader's answers. No live provider credentials were used for local
verification. Michael's representative conversation review remains the acceptance
gate. No reference library or model training was added.

## Verification

- `python -m unittest discover -s tests -p 'test_nepq*.py'` from backend:
  22 passing tests using provider fixtures. Covers the reported dead end, stage
  caps, malformed output, question repair, correction/confirmation, explicit
  handoff, profile preservation and aspiring/new/established/curiosity contexts.
- `npm test` from frontend: 56 passing tests, including six full-page onboarding
  tests for confirmation, correction focus, failed-request retry, refresh recovery,
  explicit handoff and saved profile data.
- `npm run build` from frontend: passing typecheck and production build.
- Full PostgreSQL-backed backend suite and frontend gates also run in PR CI.

## Owner review on dev

Pull `dev` and restart both backend and frontend (see [local setup](setup-macos.md)).
Start a fresh conversation, then use these answers when the corresponding topic
comes up; questions should adapt to information already supplied.

1. “I run a residential cleaning company. I need consistent leads so my cleaners
   have full schedules and stay with us.”
2. “Referrals help, but they are unpredictable. I've tried local ads without a
   repeatable way to tell what works.”
3. “I want concrete steps and real examples I can apply this week.”
4. “The goal is steady bookings while keeping enough profit to hire a manager.”
5. At the summary, choose **I'd like to change something** and type:
   “Yes, but improving margins matters more than increasing leads right now.”
6. Verify it summarizes that correction and asks for confirmation again. Choose
   **Yes, that's right**, then **Take me to my recommendations**.

Every waiting turn should end with an answerable question; the final confirmed
turn should direct you to the visible action. Refresh during a summary and verify
both confirmation and correction remain available. Repeat with “I don't have a
business yet; I'm curious about opening a bakery” and a short uncertain reply
(“I'm not sure yet”) to check that it avoids assuming staff, revenue or distress.

The typing-speed, footer-spacing and combined purchase/currently-reading CTA
follow-ups remain in their existing roadmap tasks.
