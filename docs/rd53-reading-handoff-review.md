# RD-53 — from choosing a book to Now reading

User outcome: know what to do after choosing a book, and keep the choice when
waiting to obtain a copy.

The original selection flow was merged with the lovable-loop work. The September
22 follow-up replaces separate Choose/Get actions with the combined action below.
Owner UX acceptance is still required after pulling the updated dev branch.

## Reader flow

1. **Get book + add to Reading** on a recommendation or book detail saves the
   book, opens Amazon in a separate tab, and takes the Readar tab to Reading.
   A newly selected or queued book is saved as **Waiting for my copy** in Up next.
   An already-started book keeps its existing state and progress.
2. **I already have this book** saves the choice and opens Reading without
   visiting Amazon or automatically starting reading. Search in Reading retains
   its save-only choice action. Waiting/started choices are preserved on reselect.
3. **Start reading** moves the chosen/waiting book into **Now reading** only
   after the write succeeds. **Move to Up next** allows correction.
4. Reloading or returning restores the saved state. Choosing a waiting or
   started book again preserves its state. Multiple reading books are supported.

Saved-for-later books remain in My Shelves and can be selected from their
detail page. Removing a book is an explicit action. Failed reads do not render
as an empty list; failed changes retain the current view and offer retry.

## Implementation and boundaries

- Add `reading_next` and `waiting_for_book` to the existing text status column;
  retain `currently_reading` for an explicit start. No migration is needed.
- `POST /api/reading/selection` accepts optional intent `choose` (the existing
  default) or `get_book`. The atomic upsert preserves waiting/started states and
  lets `get_book` move a queued choice to waiting. It never starts reading. The
  normal status endpoint makes explicit waiting/start/correction changes.
- Status and removal of an old recommendation interaction commit together.
  Selection/waiting/start do not create completed reading history or ratings.
  Getting a book also creates no reading logs, progress, completion or points input.
- The reading list is authenticated and scoped to the current user. Covers and
  purchase URLs come from catalog metadata, with an Amazon title/author search
  fallback when no purchase URL is available.
- Recommendation and detail actions await shelf persistence before navigating
  or confirming. Optional feedback/preference writes cannot mask a save failure.
- A blank tab is reserved during the click gesture, with its opener removed;
  it visits Amazon only after the server confirms persistence. Save failure
  closes that tab and keeps a retryable choice. A blocked/closed tab or denied
  navigation still leaves the selection saved and shows an **Open Amazon** link
  in Reading. Repeat clicks while saving make one request. Leaving Readar during
  a pending save closes only the pending tab and cannot trigger late navigation.
- Preserve valid Amazon affiliate URLs from the catalog, including on book
  details. Fall back to an Amazon title/author search for missing or unusable
  links. With neither URL nor title, offer **Add to Reading** without opening a tab.
- Existing sign-in routing already defaults returning readers to `/reading`.
  Explicit internal return links, new-user onboarding, and pending onboarding
  answers keep their existing paths; no account-local selection cache is needed.
- Shipping tracking/integrations remain RD-63; logs, goals and progress remain
  RD-54. Existing recommendation ranking is unchanged.

Restart both local servers after pulling dev. No new database migration is
required for this follow-up. Release backend before frontend so `get_book`
intent records the waiting state; an older selection endpoint may ignore that
optional field and retain the prior Up next behavior.

## Verification

Frontend tests cover save-before-Amazon ordering, duplicate clicks, save failure,
malformed success, blocked/closed/denied tabs, unmount cleanup, missing links,
already-owned books, both real card/detail entry points, and explicit/default/
new-user sign-in routing. The production build includes typechecking.
Postgres-backed endpoint tests cover choose/wait/start/correct, reloads, retries,
account isolation, authentication, failure rollback, purchase-link serialization,
and no invented reading credit. Full results are recorded in PR CI and Notion.

Automated popup cases use browser stubs; they do not claim an actual Amazon
purchase or delivery. This environment could not launch/open the local browser
preview, so live browser behavior and visual acceptance remain for Michael.

## Later review checklist

Use the PR testing SOP with frontend and backend from updated dev and an
isolated test database. A frontend-only Vercel preview cannot validate the new
backend behavior.

- Choose **Get book + add to Reading** on a recommendation. Confirm Amazon opens
  separately and Readar shows the saved book, with Waiting for my copy; reload.
- Sign out and sign back in normally: land on Reading with that book still there.
- Block popups and repeat: the saved book remains and **Open Amazon** works.
- Choose **I already have this book**: no Amazon tab, and a clear Start reading action.
- Start reading, reload, then choose the same book again: it stays Now reading.
- Move a started book back to Up next and retry a choice: no duplicate appears.
- Use the combined action from a saved book's detail page and the save-only action
  from Reading search. Check that a missing purchase URL uses an Amazon search.
- Simulate load/save failures: the list must not look empty or claim success;
  retry must remain possible. Check keyboard controls and phone-width wrapping.
- Confirm the flow feels clear and low effort before marking RD-53 Done.
