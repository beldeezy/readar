# Backend tests

Pytest suite covering critical paths. Models use Postgres-specific types
(UUID/JSONB/ARRAY/enums), so a **Postgres** test database is required — SQLite is
not supported.

## Running

```bash
cd backend
createdb test_readar   # once
export TEST_DATABASE_URL="postgresql://<user>@localhost:5432/test_readar"
python -m pytest tests/ -q
```

`conftest.py` creates the schema via `Base.metadata.create_all` and rolls back
each test in a transaction for isolation. If you add columns/models, recreate the
DB (`dropdb test_readar && createdb test_readar`) so the schema is current.

## What's covered

- `test_dedup_canonical_key.py` — the catalog de-dup key (subtitle/parenthetical/
  punctuation collapsing) used by import de-dup and `dedupe_books`.
- `test_book_status.py` — book-status critical path: reading-history side-effect
  on read, two-store sync (`currently_reading` clears the engine interaction),
  `_lookup_book` UUID/external_id resolution, plus validation (400) and auth (401/403).
- `test_recommendations_integration.py`, `test_recommendation_stability.py`,
  `test_user_helpers*.py`, `test_health.py` — older suites.

## Known pre-existing failures (not from the test layer above)

A handful of older tests fail due to behaviour drift (recommendation scoring,
email-relink semantics) and a TestClient design issue (those tests don't override
`get_db`, so the endpoint uses a different connection than the test transaction).
These predate this test layer and should be triaged separately before wiring the
full suite into CI. `test_onboarding.py` is skipped (it imports a function that
moved into the Pydantic schema validator and needs a rewrite).
