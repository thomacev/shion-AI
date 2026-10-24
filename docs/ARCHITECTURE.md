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
| `frontend/` | React/TypeScript workspace, Tailwind/CSS styling, Axios API client, Playwright browser tests |

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

1. Check assistant ownership and conversation membership, then acquire an expiring
   generation claim. Load up to 20 previous messages, releasing the read transaction
   before provider calls.
2. With `use_rag=true`, check for this assistant's READY documents. If any exist,
   embed the question with `RETRIEVAL_QUERY`, retrieve matching chunks, and build
   a JSON user message containing the question and source IDs, text, file/page
   metadata. With no READY documents, skip the embedding request.
3. Select the conversation's answer policy:
   - `use_rag=true`, `allow_general_knowledge=false`: documents only. No matches
     produce the fixed insufficient-evidence response without generation. Generated
     answers must cite supplied source IDs or are replaced with that response.
   - `use_rag=true`, `allow_general_knowledge=true`: combined answers. Gemini returns
     a structured object with separate `document_answer` and `general_answer`
     strings. Either can be empty. General knowledge works with no documents or
     no retrieval matches; provider/retrieval errors remain errors.
   - `use_rag=false`: general knowledge, without document retrieval.
4. `answer_grounding.py` validates combined output and document citation IDs,
   rejects document citations in the general section, and builds labeled Markdown.
   Invalid structured output returns a domain error, without saving the message
   pair. The model never supplies the persisted answer-origin label.
5. Save the user/assistant pair and release the claim. Each new assistant message
   stores `answer_basis`: `documents`, `general_knowledge`, `mixed`, or
   `insufficient_evidence`, plus cited sources. These describe the accepted answer
   sections and supplied references, not an independent verification of every
   claim's factual support. Source text and history remain untrusted model input.

No web-search tool is configured. General knowledge is explicitly labeled as
having no web search; it can be outdated. Structured output uses the SDK's
`response_mime_type` and `response_json_schema` configuration; see Google's
[structured-output documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en).

Migration `d3e5f708192a` follows `ef4d56b1d7f0`. It adds the non-null conversation
flag with default false and nullable message provenance. Existing conversations
retain their previous behavior; old messages have unknown provenance rather than
being relabeled from the conversation's current mode. Downgrade removes these
fields and their saved settings/labels, but keeps message text and source lists.

## Frontend boundary

`App.tsx` owns authentication and assistant selection. `Workspace.tsx` owns document
polling and conversation navigation; the chat and document panels call typed
wrappers in `src/api/workspace.ts`. The Axios client uses HTTP-only cookies and a
shared refresh promise for concurrent unauthorized requests.

New UI conversations default to Documents + general knowledge. The Answer using
selector also supports Documents only and General knowledge. Existing conversation
changes are persisted by PATCH; failed changes keep the previous mode. Only
Documents only blocks sending while documents are loading or none are ready.
Answer labels come from persisted message metadata, not the selected mode. Source
cards download authenticated originals. Markdown rendering excludes raw HTML and
remote images.

Vite proxies `/auth` and `/assistants` to the backend during development. Production
requires its own reverse proxy or compatible API origin configuration. The UI uses
teal `#35B8A4`, off-white `#F7F8F2`, and charcoal `#21332F`, without gradients.
