# Test Setup Instructions

## Test Database Configuration

The tests require a Postgres database because the models use Postgres-specific features:
- `PostgresEnum` for SubscriptionStatus and BusinessStage
- `UUID` type for primary keys
- `JSONB` for JSON columns
- `ARRAY` for array columns

### Option 1: Use Test Database (Recommended)

Set the `TEST_DATABASE_URL` environment variable to point to a test Postgres database:

```bash
export TEST_DATABASE_URL="postgresql://user:password@localhost:5432/test_readar"
pytest tests/test_user_helpers_identity_linking.py -v
```

### Option 2: Use Production Database (Not Recommended)

If `TEST_DATABASE_URL` is not set, tests will use the production `DATABASE_URL` from settings.
**Warning**: This will create and drop tables in your production database!

## Running Tests

### Activate Virtual Environment

```bash
cd backend
source .venv/bin/activate  # or: source venv/bin/activate
```

### Run All Identity Linking Tests

```bash
pytest tests/test_user_helpers_identity_linking.py -v
```

### Run Specific Test

```bash
pytest tests/test_user_helpers_identity_linking.py::test_fresh_user_creates_new_user -v
```

### Run All User Helper Tests

```bash
pytest tests/test_user_helpers.py tests/test_user_helpers_identity_linking.py -v
```

## Test Fixtures

### `db` (function scope)

Provides a database session for each test. Uses a transaction that is rolled back after each test for isolation.

```python
def test_example(db: Session):
    # Test code here
    # Transaction is automatically rolled back after test
    pass
```

### `engine` (session scope)

Provides the test database engine. Creates all tables at the start and drops them at the end.

### `db_with_commit` (function scope)

Provides a database session with commit support. Uses a savepoint (nested transaction) that is rolled back at the end.

## Test Isolation

Each test runs in its own transaction that is rolled back at the end. This ensures:
- Tests don't affect each other
- No test data persists between tests
- Tests can be run in any order

## Troubleshooting

### "fixture 'db' not found"

Make sure `conftest.py` is in the `tests/` directory and pytest can find it.

### "SQLite not supported"

The models use Postgres-specific features. You must use a Postgres test database.

### "Tables already exist"

The test setup tries to create tables. If they already exist, it will print a note but continue.
To clean up, manually drop tables or use a fresh test database.

### Import Errors

Make sure you're running tests from the `backend/` directory and the virtual environment is activated.

