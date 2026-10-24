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
- Configuration comes from environment variables and optionally the root `.env`.
  Pytest also loads `.env`; explicit environment values in the recipe below take
  precedence. Even collection imports settings.

## Isolated backend test setup

Fixtures require `TEST_ALLOW_SCHEMA_RESET=1` and **drop ORM tables at session
teardown**. Do not point them at the application's working database. Keep Redis
separate too, since authentication tests write session state.

With Python 3.12+ and Docker installed, prepare the Python tools from the root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Use fresh disposable containers on ports distinct from the application:

```bash
docker run --rm -d --name shion-test-db \
  -e POSTGRES_USER=shion_test -e POSTGRES_PASSWORD=shion_test \
  -e POSTGRES_DB=shion_test_db \
  -p 127.0.0.1:15439:5432 pgvector/pgvector:pg15
docker run --rm -d --name shion-test-redis \
  -p 127.0.0.1:16389:6379 redis:7-alpine
docker exec shion-test-db pg_isready -U shion_test -d shion_test_db
```

Wait until PostgreSQL reports that it accepts connections, then run this block
in Bash. Parentheses keep the test settings out of the parent shell:

```bash
(
  export DATABASE_URL=postgresql+asyncpg://shion_test:shion_test@127.0.0.1:15439/shion_test_db
  export DATABASE_TEST_URL="$DATABASE_URL"
  export REDIS_URL=redis://127.0.0.1:16389/0
  export CELERY_BROKER_URL=redis://127.0.0.1:16389/1
  export REDIS_PASSWORD=
  export SECRET_KEY=isolated-tests-only-secret
  export GEMINI_API_KEY=fake-test-key
  export MODEL_NAME=gemini-3-flash-preview
  export EMBEDDING_MODEL=gemini-embedding-001
  export EMBEDDING_DIM=1536
  export DEBUG=true
  export RATE_LIMIT_ENABLED=false
  export TEST_ALLOW_SCHEMA_RESET=1

  alembic upgrade head &&
  ruff check src/app &&
  pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=70
)
```

Use focused pytest commands from the table below inside the same block when
appropriate. When done, stop only these disposable containers:

```bash
docker stop shion-test-db shion-test-redis
```

Start fresh containers before repeating the migration-plus-tests sequence:
fixture teardown removes ORM tables but does not reset Alembic's revision table.
The application's Compose stack does not provision the example's separate test
database/user automatically.

## Backend commands

| Purpose | Command |
| --- | --- |
| Collect tests without executing fixtures | `pytest --collect-only -q` |
| Auth behavior | `pytest src/app/tests/test_auth.py` |
| Assistant behavior and ownership | `pytest src/app/tests/test_assistants.py` |
| Document API and processing | `pytest src/app/tests/test_documents.py src/app/tests/test_document_tasks.py` |
| Conversations and RAG | `pytest src/app/tests/test_conversations.py src/app/tests/test_answer_modes.py` |
| Full CI test/coverage check | `pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=70` |
| Static analysis (Ruff version pinned in pyproject.toml) | `ruff check src/app` |
| Migration revision graph without a DB connection | `alembic heads` and `alembic history` |
| Apply migrations to the configured disposable DB | `alembic upgrade head` |
| CI image build | `docker build -t shion-ai:ci .` |

Use `-k` or a pytest node ID to narrow an existing test target. Tests using
`db_session` or API fixtures inherit the session-wide schema setup, even when
selected from a single file. Pure helper/provider tests can avoid DB fixtures, but
still import application settings. Collection does not establish database
connectivity or prove test behavior. Imports may create local logs.

CI runs migrations, the coverage check (minimum 70%), and then the Docker build.
Ruff is also a CI gate; there is no configured backend formatter,
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
- Embedding mocks use 1,536 dimensions. Processing tests assert saved chunk
  contents/order, idempotence, vector validation, status and recovery behavior.
- No Celery worker is required by the suite: the ingestion tests call the
  processing service directly, so these tests do not exercise task delivery, actual
  retry scheduling, or the worker's event-loop lifecycle.
- The autouse provider guard blocks unmocked Gemini generation, embeddings and
  token counting. Patch the specific adapter/service the path reaches so tests
  cannot accidentally depend on live model calls.
- Fixtures use ORM `create_all`, not migrations. A passing test alone does not
  verify migration-specific indexes or schema agreement. Migration validation
  needs the separate upgrade step against a disposable database.

For new behavior tests, follow these fixtures and patch the external calls that
the path actually reaches. Assert observable API responses and persisted state;
for ingestion changes, check chunk contents/counts as well as status.

## Frontend commands

There are separate root and frontend npm manifests/lockfiles. Run `npm ci` at
the root for the separate root dependency and `npm --prefix frontend ci` for
frontend development. Axios is now declared in the frontend manifest too; the
frontend does not require installing the root npm package.

| Purpose | Command from repository root |
| --- | --- |
| ESLint | `npm --prefix frontend run lint` |
| TypeScript build and Vite bundle | `npm --prefix frontend run build` |
| Development server | `npm --prefix frontend run dev` |
| Preview the built frontend | `npm --prefix frontend run preview` |
| Install Chromium for browser tests | `npx --prefix frontend playwright install chromium` |
| Browser flow tests | `npm --prefix frontend run test:e2e` |

Playwright starts a Vite server at `127.0.0.1:4173`; keep that port free. The browser
suite mocks HTTP responses and does not prove real API/worker/Gemini integration.
It covers authentication, document actions, chat history, failures, session refresh,
mobile navigation, answer-mode persistence, source labels and Markdown rendering.
Generated screenshots/traces in `frontend/test-results` are ignored by Git and
ESLint. Build includes `tsc -b`; there is no separate `typecheck` script. GitHub
Actions currently validates only the backend and its Docker image.

## Answer-mode validation

`test_answer_modes.py` uses the standard disposable database/Redis fixtures and
mocks provider calls. It checks document-only, general and mixed answer provenance,
no-document/no-match behavior, mode changes, invalid structured output/citations,
rollback/claim release and ownership. `test_providers.py` verifies structured-output
configuration at the Gemini adapter boundary.

For migration `d3e5f708192a`, separately verify a fresh `alembic upgrade head` and
an upgrade from `ef4d56b1d7f0` with synthetic conversations/messages. Existing
conversations must get `allow_general_knowledge=false`; historical messages must
keep their content with null `answer_basis`. Never use the application's working
database for fixture teardown or migration rollback tests.
