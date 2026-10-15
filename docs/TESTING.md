# Validation and testing

Run commands from the repository root with the backend virtual environment
activated unless stated otherwise. This is a command reference, not a claim that
all checks currently pass. CI is defined in
[ci.yml](../.github/workflows/ci.yml); Python settings are in
[pytest.ini](../pytest.ini) and [pyproject.toml](../pyproject.toml).

## Backend prerequisites

- Python 3.12 is used by CI and Docker; the package declares Python >=3.12.
- CI installs with `pip install -e ".[dev]"`. There is a `uv.lock`, but CI uses
  pip and Docker uses `uv pip install --system .`; neither installs from the lock.
- Supply the required settings from `.env.example` in the environment or a local
  `.env`. Pytest also loads `.env`. Even collection imports the app and settings.
- Execution requires PostgreSQL with pgvector and a Redis instance. Start the
  existing local services with `docker compose up -d db redis` when needed.
  Compose creates only the configured primary PostgreSQL user/database; it does
  not provision the separate test user/database shown in `.env.example`.

**Use disposable databases.** `setup_test_db` creates the vector extension and
ORM tables, then drops all ORM tables at session teardown. Point
`DATABASE_TEST_URL` at an existing disposable database using the
`postgresql+asyncpg://` scheme, with permission to create the extension/tables.
Keep test Redis separate from application Redis as auth tests can use it.

For the CI-equivalent migration/test sequence, point both `DATABASE_URL` and
`DATABASE_TEST_URL` at the same disposable database. Alembic reads the former;
test fixtures read the latter. CI sets `EMBEDDING_DIM=1536`,
`RATE_LIMIT_ENABLED=false`, and a fake `GEMINI_API_KEY`.

## Backend commands

| Purpose | Command |
| --- | --- |
| Collect tests without executing fixtures | `pytest --collect-only -q` |
| Auth behavior | `pytest src/app/tests/test_auth.py` |
| Assistant behavior and ownership | `pytest src/app/tests/test_assistants.py` |
| Document API and processing | `pytest src/app/tests/test_documents.py src/app/tests/test_document_tasks.py` |
| Conversations and RAG | `pytest src/app/tests/test_conversations.py` |
| Full CI test/coverage check | `pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=70` |
| Optional static analysis with the declared Ruff dependency | `ruff check src/app` |
| Migration revision graph without a DB connection | `alembic heads` and `alembic history` |
| Apply migrations to the configured disposable DB | `alembic upgrade head` |
| CI image build | `docker build -t shion-ai:ci .` |

Use `-k` or a pytest node ID to narrow an existing test target. All executed tests
under the configured suite inherit the session-wide DB setup, including tests
selected from a single file. Collection does not establish database connectivity
or prove test behavior. Imports may create local logs.

CI runs migrations, the coverage check (minimum 70%), and then the Docker build.
Ruff is available but is not a CI gate; there is no configured backend formatter,
type checker, or load-test scenario despite Locust being a dependency.

## Existing test conventions and gaps

- `pytest-asyncio` uses auto mode and session-scoped test/fixture event loops.
  Async test functions need no explicit asyncio marker in this configuration.
- `conftest.py` creates a test engine with `NullPool`. Each `db_session` uses an
  outer transaction and `join_transaction_mode="create_savepoint"` so service
  commits can be rolled back after the test.
- `client` uses HTTPX `AsyncClient`/`ASGITransport` and overrides `get_db`.
  Fixtures create users, bearer headers, another user, an assistant, and a sample
  document. Ownership tests expect 404 for another user's resources.
- Tests use `unittest.mock.patch` and `AsyncMock` at the service's lookup site,
  such as `app.services.conversation_service.chat` and
  `app.services.document_service.embed`. Upload tests patch task `.delay`.
- Embedding mocks currently use 1,536 dimensions. The processing success test
  checks status without checking that every chunk was persisted.
- No Celery worker is required by the suite: `test_document_tasks.py` calls the
  processing service directly, so it does not exercise task delivery, actual
  retry scheduling, or the worker's event-loop lifecycle.
- Provider calls are mocked in most relevant tests, but
  `test_llm_failure_rolls_back_and_returns_502` mocks chat without mocking query
  embedding. It can attempt a real embedding request and return 502 before
  reaching its intended chat failure. Use a fake key for routine validation;
  do not describe the suite as entirely offline.
- Fixtures use ORM `create_all`, not migrations. A passing test alone does not
  verify migration-specific indexes or schema agreement. Migration validation
  needs the separate upgrade step against a disposable database.

For new behavior tests, follow these fixtures and patch the external calls that
the path actually reaches. Assert observable API responses and persisted state;
for ingestion changes, check chunk contents/counts as well as status.

## Frontend commands

There are separate root and frontend npm manifests/lockfiles. Run `npm ci` at
the root for Axios and `npm --prefix frontend ci` for the frontend packages when
dependencies need installation; this reflects the current split manifests.

| Purpose | Command from repository root |
| --- | --- |
| ESLint | `npm --prefix frontend run lint` |
| TypeScript build and Vite bundle | `npm --prefix frontend run build` |
| Development server | `npm --prefix frontend run dev` |
| Preview the built frontend | `npm --prefix frontend run preview` |

The frontend declares no `test` script, test framework, or end-to-end suite.
Build includes `tsc -b`; there is no separate `typecheck` script. GitHub Actions
currently validates only the backend and its Docker image.
