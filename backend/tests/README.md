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

## CI

The full suite runs in GitHub Actions (`.github/workflows/ci.yml`, backend job)
against a Postgres service container. The whole suite is green — keep it that way.

Notes for endpoint tests: override **both** `get_current_user` and `get_db`
(`app.dependency_overrides[get_db] = lambda: db`) so the endpoint shares the
test's transaction. The `db` fixture uses a SAVEPOINT-restart pattern, so code
under test may call `db.commit()` and the changes are still rolled back after the
test. Onboarding's `business_stage` normalization now lives in the
`OnboardingPayload` Pydantic validator (test by constructing the model).
