# shion-AI

![CI](https://github.com/thomacev/shion-AI/actions/workflows/ci.yml/badge.svg)

A backend platform to create and manage personalized AI assistants, featuring conversational memory and the ability to answer based on custom documents (RAG). Built as a portfolio project to demonstrate real-world backend design — this is not a thin LLM wrapper, but a complete system with authentication, multi-tenancy, resilience to external service failures, background processing, and a highly defensible architectural decision surface.

- **Live Demo:** `https://shion-ai-production.up.railway.app`
- **Interactive Documentation:** `https://shion-ai-production.up.railway.app/docs`

---

## Project Status

- ✅ **Week 1** — Auth, Assistant CRUD, conversations with mock responses, testing, CI
- ✅ **Week 2** — Real LLM integration (retries, error handling), rate limiting, network-isolated testing
- ✅ **Week 3** — RAG with custom documents: text extraction, chunking, embeddings, vector search using `pgvector`
- ✅ **Week 4** — Background document processing with Celery, full migration to the Gemini API (chat + embeddings)
- ✅ **Week 5** — Critical architectural review applied, Celery resilience, file size limits, relevance thresholds, RAG toggle, original file persistence, **deployment on Railway**

- Detailed documentation for each week (in Spanish): [`SEMANA_1.md`](./SEMANA_1.md) · [`SEMANA_2.md`](./SEMANA_2.md) · [`SEMANA_3.md`](./SEMANA_3.md) · [`SEMANA_4.md`](./SEMANA_4.md) · [`SEMANA_5.md`](./SEMANA_5.md)
- AI concepts explained from scratch (vectors, embeddings, RAG, etc.): [`CONCEPTOS_IA.md`](./CONCEPTOS_IA.md)

---

## Key Design Decisions

For those evaluating this project quickly, here is what is worth reviewing before diving into the code:

- **The AI provider was migrated once, in production, without touching business logic.** `conversation_service.py` didn't change a single line when the project moved from OpenRouter to the Gemini API — proof that decoupling by function (without formal interfaces or heavy frameworks) is highly effective when well thought out. Full details in `SEMANA_4.md`.
- **The document pipeline is idempotent.** A Celery retry on the same task does not duplicate chunks — this was detected and fixed before reaching production, not as a post-incident patch. Details in `SEMANA_5.md`.
- **An external architectural review was analyzed critically, not applied blindly.** Out of 10 suggested points, 4 were accepted (with justified severity), 4 were rejected (with explicit criteria on when to reconsider them), and 2 were partially accepted. The complete reasoning, including disagreements, is in `SEMANA_5.md`.
- **RAG with real safeguards, not just the happy path.** Minimum relevance thresholds (not everything "closest" is relevant), per-conversation RAG toggles, and file size limits — built after explicitly reasoning the risk of each gap, rather than following a generic checklist.

---

## Stack

- **FastAPI** (async) + **SQLAlchemy 2.0** (`AsyncSession`, `asyncpg`)
- **PostgreSQL with `pgvector`** — relational persistence and vector search in the same database
- **Redis** — JWT token blacklist, rate limiter storage, and Celery broker
- **Celery** — background document processing with retries and exponential backoff
- **Alembic** — database migrations
- **structlog** — structured JSON logging, with `request_id` correlated per request via `contextvars`
- **Google Gemini API** (`google-genai` async SDK) — chat (`gemini-3-flash-preview`) and embeddings (`gemini-embedding-001`)
- **pypdf** — PDF text extraction
- **slowapi** — rate limiting per user/IP
- **pytest + pytest-asyncio** — integration testing against a real database, isolated per transaction
- **GitHub Actions** — CI with Postgres (`pgvector/pgvector:pg15`) and Redis as service containers
- **Docker / Docker Compose** — local development environment
- **Railway** — production deployment

## Architecture at a glance

```mermaid
flowchart TD
    A[User sends message] --> B{conversation.use_rag?}
    B -->|false| F[Only history + system_prompt]
    B -->|true| C[Embed query]
    C --> D[Search chunks via cosine similarity]
    D --> E{Any chunk within threshold?}
    E -->|no| F
    E -->|yes| G[Append chunks to system_prompt]
    F --> H[Chat with LLM]
    G --> H
    H --> I[Response to user]

Documents are uploaded, processed in the background (extraction → chunking → embeddings), and become available for any conversation belonging to the same assistant. The full breakdown, including diagrams for each stage, is in SEMANA_3.md and SEMANA_4.md.

## Project Structure

```
shion-AI/
├── src/app/
│   ├── api/            # routers: auth, assistants, conversations, documents
│   ├── core/           # config, security, dependencies, rate_limit, celery_app, gemini_client, logging, exceptions
│   ├── db/              # SQLAlchemy async session
│   ├── models/          # User, Assistant, Conversation, Message, Document, DocumentChunk
│   ├── schemas/         # input/output Pydantic schemas
│   ├── services/        # business logic, domain-driven
│   │   ├── auth_service.py
│   │   ├── assistant_service.py
│   │   ├── conversation_service.py
│   │   ├── document_service.py       # CRUD and orchestration
│   │   ├── document_processing.py    # extraction & chunking (pure functions)
│   │   ├── llm_service.py            # chat
│   │   └── embedding_service.py      # embeddings
│   ├── tasks/           # Celery tasks
│   └── tests/           # async test suite
├── alembic/              # migrations
├── scripts/entrypoint.sh # waits for Postgres, runs migrations, starts uvicorn
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Endpoints

| Method | Path | Rate limit | Description |
|---|---|---|---|
| POST | `/auth/register` | 5/hour (IP) | User registration |
| POST | `/auth/login` | 5/minute (IP) | Login, returns access + refresh token |
| POST | `/auth/refresh` | — | Refreshes the access token |
| POST | `/auth/logout` | — | Invalidates the token (Redis blacklist) |
| POST | `/assistants` | — | Creates an assistant |
| GET | `/assistants` | — | Lists assistants for the authenticated user |
| GET / PATCH / DELETE | `/assistants/{id}` | — | Details, partial update, and deletion (soft delete) |
| POST | `/assistants/{id}/conversations` | — | Creates a conversation (`use_rag` optional, default `true`) |
| GET | `/assistants/{id}/conversations` | — | Lists conversations for an assistant (paginated) |
| PATCH | `/assistants/{id}/conversations/{id}` | — | Toggles `use_rag` for an existing conversation |
| POST | `/assistants/{id}/conversations/{id}/messages` | 10/minute (user) | Sends a message; uses RAG only if enabled for the conversation and relevant context is found |
| GET | `/assistants/{id}/conversations/{id}/messages` | — | Conversation history (paginated) |
| POST | `/assistants/{id}/documents` | — | Uploads a document (`.pdf`, `.txt`, max size configurable), processed in the background |
| GET | `/assistants/{id}/documents` | — | Lists documents for an assistant (paginated) |
| GET | `/assistants/{id}/documents/{id}` | — | Document status (`pending` / `processing` / `ready` / `failed`) |
| GET | `/assistants/{id}/documents/{id}/file` | — | Downloads the original uploaded file |
| DELETE | `/assistants/{id}/documents/{id}` | — | Deletes a document, its chunks, and the original file |

Complete interactive documentation available at `/docs`.

---

## Installation and Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (only if running the API outside of Docker)
- A Google AI Studio API key (free, no credit card required) for `GEMINI_API_KEY`

### 1. Clone the repo and create the `.env` file

```bash
git clone [https://github.com/thomacev/shion-AI.git](https://github.com/thomacev/shion-AI.git)
cd shion-AI
```

The repo does not include an .env.example, so create an .env file in the root directory:

```bash
# --- Database (Development) ---
POSTGRES_USER=shion_agent
POSTGRES_PASSWORD=changeme
POSTGRES_DB=shion_ai_db
DATABASE_URL=postgresql+asyncpg://shion_agent:changeme@localhost:5432/shion_ai_db

# --- Database (Testing) ---
POSTGRES_USER_TEST=shion_test
POSTGRES_PASSWORD_TEST=changeme_test
POSTGRES_DB_TEST=shion_test_db
DATABASE_TEST_URL=postgresql+asyncpg://shion_test:changeme_test@localhost:5432/shion_test_db

# --- JWT ---
SECRET_KEY=reemplazar-por-una-clave-larga-y-aleatoria
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14

# --- CORS ---
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]

# --- App ---
APP_NAME=shion-AI
DEBUG=true
API_V1_STR=/api/v1

# --- LLM (Google Gemini) ---
GEMINI_API_KEY=tu-key-de-google-ai-studio
MODEL_NAME=gemini-3-flash-preview
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.7
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=1536

# --- RAG ---
RAG_MAX_DISTANCE=0.5
MAX_DOCUMENT_SIZE_MB=10

# --- Redis ---
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
RATE_LIMIT_ENABLED=false
CACHE_TTL_DEFAULT=300

# --- Celery ---
CELERY_BROKER_URL=redis://localhost:6379/1
```

> `GEMINI_API_KEY` The GEMINI_API_KEY can be obtained for free from Google AI Studio without a credit card — the free tier is more than enough for development (1500 requests/day).

### 2. Run everything with Docker Compose

```bash
docker compose up -d --build
```

This spins up Postgres (using the pgvector/pgvector:pg15 image), Redis, the API, and the Celery worker. Without the worker running, documents will remain in status=pending forever — it is treated as just another service in the docker-compose.yml, not an afterthought.

The API container waits for Postgres to be ready, automatically runs Alembic migrations, and starts uvicorn. The API will be available at http://localhost:8000, and the docs at http://localhost:8000/docs.

### 3. Alternative: Infrastructure in Docker, local API

```bash
docker compose up -d db redis

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

alembic upgrade head
python main.py
```

In a separate terminal, to enable document processing:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

Note: DATABASE_URL, REDIS_URL, and CELERY_BROKER_URL must point to localhost in this mode, not to the service names defined in docker-compose.yml.

## Database Access

With the containers running, access the Postgres container (not the API container):

```bash
docker ps   # verify the exact name of the database container
docker exec -it -e PGPASSWORD=changeme shionaiassistant-db psql -U shion_agent -d shion_ai_db
```

```sql
\dt              -- list tables
\d documents      -- view table structure
\q               -- quit
```

## Testing

Tests run against a real Postgres database (not SQLite) with pgvector enabled, isolating each test in its own transaction with automatic rollbacks. The LLM and embeddings are mocked; document processing is tested in separate layers (task dispatching vs. actual processing bypassing Celery). The test suite never requires a running Celery worker, nor does it hit the real Gemini API:

```bash
docker compose up -d db redis
pytest --cov=app --cov-report=term-missing
```

## CI

Every push triggers GitHub Actions: Postgres (pgvector/pgvector:pg15) and Redis are spun up as service containers, migrations are executed, and the full test suite runs with a 70% coverage threshold. See .github/workflows/ci.yml.

## Deployment

Deployed on Railway. In addition to the environment variables listed above, the production environment requires:

A separate service running the Celery worker (using the same command as local: celery -A app.core.celery_app worker --loglevel=info). Without this, documents will never transition out of pending.

DATABASE_URL, REDIS_URL, and CELERY_BROKER_URL must point to the managed services provided by Railway (Postgres and Redis), not localhost.

DEBUG=false.

## Known Limitations

No summarized conversation persistence: The chat history is strictly truncated to the last 20 messages; there is currently no long-term memory mechanism (like periodic summarization).

Scanned PDFs: Text extraction (pypdf) does not support scanned PDFs lacking a selectable text layer. These are processed with empty or near-empty content without throwing explicit errors. Evaluated using pymupdf4llm for OCR support, but discarded it for now due to its AGPL license and misalignment with the current use case. Details in SEMANA_4.md.

RAG Calibration: The relevance threshold (RAG_MAX_DISTANCE) is a baseline starting value and has not yet been calibrated against real-world production usage.

No UI: The project is tested via /docs or direct HTTP clients by design. The goal is to demonstrate backend proficiency, not frontend development.