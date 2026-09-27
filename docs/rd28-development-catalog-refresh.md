# RD-28: representative development catalog

Use a dated, verified copy of the shared catalog for recommendation acceptance.
The August local/production counts in the backlog are historical observations.
Neither the checked-in seed files nor a passing fixed benchmark establishes what
is currently in production.

## Scope and known differences

Copy only `public.books` and `public.book_sources`. Preserve IDs, tags, knowledge
levels, topic-fit decisions, insight JSON, URLs and provenance exactly. The
destination is a **new local review database**, with synthetic reader accounts.
No customer identities, onboarding answers, reading histories, feedback, payment
records, events, pairings or credentials are copied. A catalog match does not
prove that authentication, payments, email or per-reader recommendations match
production. Test those paths separately with the existing acceptance checklists.

As of September 27, 2026:

| Evidence | Observation | Limit |
| --- | --- | --- |
| GitHub API `dev` | `4304cf0ac3117c7befb460176af4389417f3f83e` | A shell fetch returned older `18f3852`; compare the local SHA to the API before testing. Do not reset or force-push a shared branch to resolve the discrepancy. |
| Render backend | Live deployment `dep-dap7rgjncjis73a1uajg`, commit `7ab0199550cb163686d82c1654d648fcd9ff4259` | Deployment finished September 22. It follows `dev` and runs Alembic before startup. That start command does not prove the current database revision. |
| RD-65 follow-up | Draft PR [#28](https://github.com/beldeezy/readar/pull/28), head `79f2f806eb749f43ab37427809fcc488ab69cd61` | Still open/unmerged when checked. Live acceptance remains outstanding. |
| Production database | No Render-managed Postgres instance was returned for the Readar workspace; the repository uses Supabase | Production migration head and current catalog/customer/payment counts were not directly queried in this task. |
| Public frontend | Earlier review recorded successful Vercel status for main `bd15820d` | Exact revision behind the public alias remains unverified under RD-31. |
| Local catalog | No live catalog refresh has been performed by this change | Do not report local counts as production facts until the procedure below passes. |

## 1. Record the code and database baseline

Preserve any local edits before switching branches. Fetch the intended branch and
record `git rev-parse HEAD`, the branch name, and the PRs included in that revision.
Use the GitHub branch page/API as a cross-check if fetch and PR metadata disagree.
Frontend and backend acceptance must identify both tested revisions.

Use PostgreSQL client tools compatible with the source server. Configure two
libpq service entries outside the repository: `readar_catalog_source` for the
existing production database, and `readar_catalog_local` for a new local database
named `readar_review_YYYYMMDD`. Use an existing read-only source role where
available. Put passwords in a protected password file, not shell history, reports
or this document. Verify the local entry's host is loopback, not a tunnel to a
hosted database. The commands below use service names, not connection secrets.

From `backend/`, with its Python dependencies installed:

```bash
umask 077
mkdir -p ../.local/catalog-review
READAR_BASELINE_DATABASE_URL='service=readar_catalog_source' \
  python scripts/catalog_baseline.py snapshot --label live-before \
  --output ../.local/catalog-review/source-before.json
```

The utility opens a PostgreSQL **read-only, repeatable-read** transaction. It reads
only the migration revision, catalog schema and the two catalog tables. Its JSON
contains counts and SHA-256 fingerprints, not record contents or connection
details. It does not load the app's `.env`, invoke AI, call an enrichment API,
start a scheduler, or write to the database. Missing migration evidence cannot
pass the comparison command. Cover URL presence is only a coverage count; it is
not proof that the pictured book is correct or that the URL works.

## 2. Export a consistent catalog

```bash
PGSERVICE=readar_catalog_source PGOPTIONS='-c default_transaction_read_only=on' \
  pg_dump --format=custom --data-only --no-owner --no-acl \
  --table=public.books --table=public.book_sources \
  --file=../.local/catalog-review/catalog.dump

READAR_BASELINE_DATABASE_URL='service=readar_catalog_source' \
  python scripts/catalog_baseline.py snapshot --label live-after \
  --output ../.local/catalog-review/source-after.json

python scripts/catalog_baseline.py compare \
  ../.local/catalog-review/source-before.json \
  ../.local/catalog-review/source-after.json
```

`pg_dump` uses its own consistent snapshot. Require the before/after reports to
match before using the dump; if catalog writes occurred, take a new set of files
and repeat. Never disable production writes to get a convenient result. Inspect
`pg_restore --list ../.local/catalog-review/catalog.dump`: only the two requested
table-data entries (plus archive metadata) belong in this artifact. Do not export
the full database or upload this dump to GitHub.

## 3. Restore into a fresh local database

Stop local Readar processes. Create the new database on the verified local
server; if that name already exists, choose another name. Preserve the existing
development database. No drop, truncate, clean restore, or production migration
is needed.

```bash
PGSERVICE=readar_catalog_local createdb --maintenance-db=postgres readar_review_YYYYMMDD
```

Set `READAR_REVIEW_DATABASE_URL` in the local shell to the SQLAlchemy PostgreSQL
URL for that same new database, using local credentials only. Alembic uses this
URL, while the dump/restore tools use the service entry; **verify they identify
the same local database** before continuing.

```bash
DATABASE_URL="$READAR_REVIEW_DATABASE_URL" python -m alembic upgrade head
DATABASE_URL="$READAR_REVIEW_DATABASE_URL" python -m alembic current
```

Compare the migration revision with the source report. Stop on a migration error
or revision mismatch. Do not stamp a database, prune migrations, or edit the
production schema to make the check pass. A deliberately newer local schema is a
separate compatibility test and must be labelled as such.

Check that the new database has zero catalog and customer rows before restoring:

```bash
PGSERVICE=readar_catalog_local psql -X -v ON_ERROR_STOP=1 \
  -c 'SELECT (SELECT count(*) FROM public.books) AS books, (SELECT count(*) FROM public.book_sources) AS sources, (SELECT count(*) FROM public.users) AS users;'

PGSERVICE=readar_catalog_local pg_restore --dbname='service=readar_catalog_local' \
  --data-only --no-owner --no-acl --single-transaction --exit-on-error \
  ../.local/catalog-review/catalog.dump

READAR_BASELINE_DATABASE_URL='service=readar_catalog_local' \
  python scripts/catalog_baseline.py snapshot --label local-restored \
  --output ../.local/catalog-review/local-restored.json

python scripts/catalog_baseline.py compare \
  ../.local/catalog-review/source-after.json \
  ../.local/catalog-review/local-restored.json
```

Only an exit code of **0** with `matches: true` passes. The comparison checks both
tables' schemas, row counts, content fingerprints and migration revisions. A
same-count edit to a tag, knowledge level, description or cover still fails.
Exit 1 means different data; exit 2 means incomplete/invalid evidence or an error.
If restore fails, retain the old development database and use another fresh name
after resolving the cause. Do not fall back to a seed file and call it equivalent.

## 4. Exercise representative journeys

Point the local backend at the new database. Keep `USER_EMAILS_PAUSED=true`, use
test payment/auth configuration, and keep production mail/payment secrets out of
the local app. Create synthetic profiles through the normal test flow; no live
customer export is necessary.

Use the cleaning-business lead-flow scenario (P16/P17), cash-flow and
owner-dependence cases from `backend/tests/fixtures/relevance_personas.json`.
Also test a curious/pre-business reader, a reader who already owns a book, a
waiting-for-copy reader, and a returning reader with saved progress. For the
Goodreads path, upload a synthetic CSV that marks one suggested book as read and
verify fresh results exclude it. Record the preserved challenge, top three
books, explanation quality and any missing catalog metadata. Run the RD-53 and
RD-65 handoff checklists on the **same recorded code/catalog combination**.

The fixed benchmark seeds its own fixtures. Run it in a separate disposable
`TEST_DATABASE_URL`; never point pytest at this review database or production.
An unchanged benchmark result does not validate the refreshed catalog's matches.

For a smaller sample, label it `sample`, record the selected IDs and selection
rule, and report its missing coverage. A sample cannot pass full-catalog parity
or establish production ranking quality.

## Evidence to put in Notion

Record UTC capture time, code SHAs, source/local migration heads, both table
counts/fingerprints, knowledge-level and topic-fit coverage, comparison exit code,
scenario results, and deliberate environment differences. Record unknowns as
unknowns. RD-28 stays **Prepared** until a current-source restore is verified;
RD-31 stays **Verify live** until release identification and the full first-use
acceptance gate pass. No live database was copied or changed in preparing this
procedure.
