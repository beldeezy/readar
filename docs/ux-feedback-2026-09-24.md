# September 24 feedback

- RD-69: reduce visible typing rate to 75% of the current rate. The existing
  length-based duration, including its min/max bounds, is divided by 0.75.
  Reduced motion, full-text reveal and restored history remain immediate.
  This does not add network latency or block the composer.
- RD-66: keep the desktop reply box active after Enter/Send. Drafting is allowed
  while a request is pending; sending remains guarded. Restore focus only during
  a desktop submit gesture, never asynchronously when a response arrives. Touch
  devices receive no programmatic focus. Failed requests and retry retain the
  next draft. Existing Enter/Shift+Enter behavior is preserved.
- RD-74: existing catalog cover audit/backfill, UX Order 2.1 after RD-52.
- RD-75: correct-cover safeguards for future ingestion, UX Order 2.2 after RD-74.
  Both belong to Lovable v1 and RD-62 acceptance. These are planned catalog tasks,
  not a claim that cover data has already been populated.
- RD-53: checked the current implementation and tightened unconfirmed-response
  handling on the Reading page. See rd53-reading-handoff-review.md.

## Owner review

After pulling dev and restarting both servers, submit a desktop chat answer with
Enter and Send. Type the next draft while waiting, then ensure it remains when
the reply arrives. Deliberately click elsewhere and confirm the next reply does
not steal focus. Check the slower reveal feels right. Complete the RD-53
save/wait/return/start checklist with a real book before accepting the task.
