# RD-73 — Confirm reading history before continuing

The Goodreads receipt previously advanced after 1.8 seconds unless the reader
selected Stay here. Michael's September 21–22 feedback supersedes that behavior:
only the reader's explicit confirmation should open recommendations.

## Behavior

- Keep the backend-confirmed saved/skipped counts on screen with no countdown.
- Continue to my recommendations opens fresh recommendations without uploading
  the CSV again. No pre-import prefetched or preview fallback is used on this path.
- A failed recommendation request shows Try again instead of stale preview books.
- Preserve the import receipt in browser history: reload or Back restores it.
- Choose another CSV is available for successful, partial and zero-row receipts.
  Imports add/update entries; they do not remove previously saved books.
- Retain the previous receipt when another upload fails or the picker is cancelled.
  While uploading, prevent duplicate submissions and disable receipt actions.
- Skip before uploading remains immediate and keeps already prepared picks.
- No backend, schema, dependency or email changes are required. Existing import
  persistence/read-book exclusion tests remain part of backend CI. Background
  metadata/profile enrichment remains asynchronous; this change does not promise
  that all enrichment has finished when the receipt appears.

## Verification

Frontend regressions cover a 60-second wait without navigation or recommendation
fetching, explicit continuation, fresh-pick delivery, failed-fetch retry without
stale preview fallback, Back and router remount receipt persistence, zero/partial
imports, same-file retry, invalid responses, duplicate submissions and unmounts.
The full frontend tests and production build/typecheck passed locally. PR CI is
the published verification gate; Michael's live UX acceptance remains pending.

## Quick owner test

1. Pull current dev and restart the frontend. Finish onboarding and upload a CSV.
2. Check the saved/skipped counts. Wait at least 10 seconds: stay on the receipt.
3. Refresh: the receipt remains and no file is submitted again.
4. Select Continue to my recommendations: fresh picks load.
5. Go Back: the receipt returns and still waits for confirmation.

The bot's missing closing questions are already captured under RD-71 and remain
separate work. No duplicate roadmap item was created for the latest screenshot.
