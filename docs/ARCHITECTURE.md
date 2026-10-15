# Existing architecture

This describes the checked-in implementation, not a target design. Validation and
development commands are in [TESTING.md](TESTING.md).

## Components

| Location | Responsibility |
| --- | --- |
| `src/app/app.py` | FastAPI app, routers, CORS, exception handlers, request middleware, Prometheus instrumentation |
| `src/app/api/` | Auth, assistant, conversation/message, and document HTTP endpoints |
| `src/app/services/` | Auth and resource operations, document processing, retrieval, prompt assembly, Gemini calls |
| `src/app/schemas/` | Pydantic request validation and response models |
| `src/app/models/` | SQLAlchemy entities and relationships |
| `src/app/db/session.py` | Global async engine, session factory, declarative base |
| `src/app/core/` | Settings, JWT/password handling, Redis, Gemini client, Celery setup, rate limiting, logging |
| `src/app/tasks/document_tasks.py` | Celery wrapper around document processing and failure status updates |
| `alembic/` | Database migrations; `env.py` imports model metadata |
| `frontend/` | Vite React starter and an Axios auth client |

`main.py` starts Uvicorn with reload for development. Docker's entrypoint waits
for PostgreSQL at host `db`, applies migrations, and starts four Uvicorn workers
on port 8000. Compose defines `db` (PostgreSQL 15/pgvector), `redis` (Redis 7),
`api`, and a separate Celery `worker`. The worker shares the backend image/code.

Settings load environment variables and `.env` through Pydantic Settings.
`DATABASE_URL` configures the app and migrations; `REDIS_URL` serves JWT
blacklisting and rate limiting; `CELERY_BROKER_URL` selects the task broker.
Gemini uses `GEMINI_API_KEY`, `MODEL_NAME`, `EMBEDDING_MODEL`, and `EMBEDDING_DIM`.
Redis is not currently used as a document or answer cache.

## HTTP and authentication

Routers are mounted at `/auth`, `/assistants`,
`/assistants/{assistant_id}/conversations`, and
`/assistants/{assistant_id}/documents`. `API_V1_STR` changes the OpenAPI URL
(default `/api/v1/openapi.json`), not the router prefixes. Swagger is at `/docs`.

Registration hashes passwords with Argon2 through Passlib. Login accepts an
OAuth2 password form and returns access/refresh JWTs, also setting HTTP-only
cookies. `get_current_user` takes a bearer token first, falls back to the access
cookie, checks the token and user, and supplies the user ID and DB instance.
Services check assistant ownership before accessing nested resources.

Logout blacklists the access token in Redis until expiry and clears the cookies;
it does not revoke the refresh token server-side. The refresh route currently
passes a DB argument to a service accepting only the token and treats the
service's dictionary result as a token string. These are existing mismatches.

SlowAPI limits registration, login, and sending messages. Request middleware
binds a request ID and returns `X-Request-ID`. Logs go to stdout and
`logs/app.log`; metrics are exposed at `/metrics`. `/health` returns a static
healthy response without probing dependencies.

## Stored data

```text
User -> Assistant -> Conversation -> Message
                  -> Document -> DocumentChunk
```

IDs are UUIDs. Assistants store their system prompt and an `is_active` flag;
deletion sets that flag false. Conversations store `use_rag` (default true).
Messages store role, text, and optional token usage. Documents store filename,
content type, original bytes in PostgreSQL, status, and an optional error.
Chunks store text, sequence index, and an embedding. ORM relationships cascade
document deletion to chunks and conversation deletion to messages.

The document migration creates `vector(1536)`. The model instead takes the
dimension from settings, whose default is 768; `.env.example` and CI specify
1536. Migration `3371a442b4ca` creates an HNSW cosine index, but
`baff9cff71dd` drops it; that index is absent from current ORM metadata.

## Document ingestion

1. The upload route reads the file. The service checks ownership and the size
   limit, stores original bytes with status `PENDING`, and commits.
2. The route dispatches `process_document_task` with the document UUID and returns
   HTTP 202. The worker reloads the stored bytes and marks it `PROCESSING`.
3. `document_processing.py` uses pypdf for `.pdf` filenames; other files are
   decoded as UTF-8 with invalid bytes ignored. There is no OCR.
4. Text is grouped into character-based chunks (default 1,000 characters).
   Oversized paragraphs use a hard split with 150-character overlap; ordinary
   paragraph boundaries do not receive that overlap.
5. `embedding_service.embed` sends all chunks in one SDK call with
   `RETRIEVAL_DOCUMENT`. Processing deletes old chunks, pairs text with embeddings
   using `zip`, inserts the pairs, marks `READY`, and commits.
6. Extraction failures mark `FAILED`. `LLMServiceError` propagates to Celery for
   up to three retries with backoff; exhaustion marks `FAILED`. Other processing
   errors are generally recorded as failures in the service.

There is no atomic database/queue dispatch or stale-job recovery mechanism.
Sequential processing replaces chunks, but there is no concurrent task claim or
embedding-count validation. Celery uses a new `asyncio.run()` loop per invocation
while the database engine and Gemini client are process globals.

## Chat and retrieval

1. Check assistant ownership and conversation membership; add and flush the user
   message within the request's database session.
2. Load up to 20 previous messages and append the current message.
3. If `use_rag` is true, embed the current message with `RETRIEVAL_QUERY`. Search
   chunks belonging to this assistant's `READY` documents by cosine distance;
   take up to four candidates and retain those within `RAG_MAX_DISTANCE`.
4. Append retrieved text to the assistant system prompt. With no matches, or
   with RAG disabled, use the base prompt. There is no forced abstention or
   source/page citation response field.
5. `llm_service.chat` converts assistant roles to Gemini's `model` role, calls
   generation (up to two attempts), and returns text, token counts, and model.
6. Save the assistant message and commit both messages. The session dependency
   rolls back on exceptions. The transaction spans the external model calls.

## Frontend boundary

`frontend/src/main.tsx` mounts `App.tsx`, which is still the Vite starter screen.
The separate `src/api/` modules use `VITE_API_URL`, send cookies, and attempt a
refresh/retry after HTTP 401. They are not connected to the starter UI, and there
is no implemented login route despite the client's `/login` redirect.
Axios is declared in the root npm manifest, not the frontend manifest. Styling
is plain CSS; no Tailwind dependency or configuration is present.
