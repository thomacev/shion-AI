# Existing architecture

This describes the checked-in implementation. Use the [root README](../README.md)
to start the application and [TESTING.md](TESTING.md) for validation.

## Components

| Location | Responsibility |
| --- | --- |
| `src/app/app.py` | FastAPI app/lifespan, routers, CORS, exception handlers, middleware, metrics |
| `src/app/api/` | Auth, assistant, conversation/message, and document HTTP endpoints |
| `src/app/services/` | Business logic, persistence, document processing, retrieval, generation and answer grounding |
| `src/app/schemas/` | Pydantic request validation and response models |
| `src/app/models/` | SQLAlchemy entities and relationships |
| `src/app/db/session.py` | API engine/session factory, declarative base, embedding-schema check |
| `src/app/core/` | Settings, security, Redis, Gemini client, Celery configuration, rate limiting, logging |
| `src/app/tasks/document_tasks.py` | Document/recovery tasks and task-scoped database connections |
| `alembic/` | Database migrations; model metadata is imported in `env.py` |
| `frontend/` | React/TypeScript workspace, Tailwind/CSS, Axios client, Playwright tests |

Routers handle HTTP and dependencies; services own business logic and commits.
Services check ownership of assistants and nested resources. Ownership failures
return 404, and assistant deletion is a soft delete.

## Processes and resource lifecycle

Compose defines five services: `db` (PostgreSQL 15/pgvector), `redis` (Redis 7),
`api`, `worker`, and `scheduler`. The frontend is a separate Vite development
process. The three backend application services build from the same Dockerfile.

The API entrypoint waits for PostgreSQL, applies migrations, and starts four
Uvicorn workers on port 8000. `main.py` instead starts Uvicorn with reload for
host-side development. The FastAPI lifespan checks the embedding column dimension
at startup and closes Gemini, Redis and database resources at shutdown.

Celery task invocations run async work through `asyncio.run()`. Each invocation
creates and disposes its own SQLAlchemy engine with `NullPool`; processing also
opens and closes a task-scoped Gemini client. Those resources are not reused
across task event loops.

Settings load environment variables and the root `.env`. `DATABASE_URL` selects
the application/migration database, `REDIS_URL` stores login sessions and
rate-limit state, and `CELERY_BROKER_URL` selects the queue broker. Redis is not
currently an answer or document cache. Compose overrides connection hosts for
container-to-container networking.

## HTTP and authentication

Routers are mounted at `/auth`, `/assistants`,
`/assistants/{assistant_id}/conversations`, and
`/assistants/{assistant_id}/documents`. `API_V1_STR` changes the OpenAPI URL
(default `/api/v1/openapi.json`), not these prefixes. Swagger is at `/docs`.

Registration hashes passwords with Argon2 through Passlib. Login accepts an
OAuth2 password form, creates a Redis-backed login session, and returns
access/refresh JWTs while setting HTTP-only cookies. Both tokens carry the same
session ID and distinct token types. Authentication accepts a bearer token first,
then the access cookie, and verifies the active user and Redis session.

Refresh validates the refresh token/session and active user before issuing an
access token. Logout deletes the shared Redis session and clears both cookies,
invalidating that login's access and refresh tokens. Redis failures produce a
service-unavailable response. Cookies use SameSite=Lax; Secure is enabled when
`DEBUG=false`. The refresh cookie is scoped to `/auth/refresh`.

SlowAPI limits registration, login, assistant creation, and message generation when
enabled. Request middleware binds a request ID and returns `X-Request-ID`.
Upload middleware limits multipart bytes before parsing; the route separately
limits file bytes. Logs go to stdout and `logs/app.log`; metrics are at
`/metrics`. `/health` returns a static liveness response.

## Stored data

```text
User -> Assistant -> Conversation -> Message
                  -> Document -> DocumentChunk
```

IDs are UUIDs. Assistants contain instructions and an active flag. Conversations
store answer-mode flags and an expiring generation claim. Messages store content,
role, token usage, cited sources and nullable answer provenance.

Documents store original bytes in PostgreSQL, filename/type, processing status,
attempts, retry timing, claim token/lease, errors and embedding model/dimension.
Chunks store text, index, embedding, and PDF page metadata (null for TXT).
Document deletion cascades to chunks; conversation deletion cascades to messages.

The model/settings require 1,536-dimensional vectors, matching `vector(1536)` in
the migration chain. Current metadata and migration `c2d4e6f81012` include an HNSW
cosine index and a unique `(document_id, chunk_index)` constraint. Retrieval filters
out documents with unknown or incompatible embedding provenance; changing the
embedding model requires reprocessing affected documents.

## Document ingestion and recovery

1. Check assistant ownership and validate filename, size, nonempty bytes and
   supported extension. Check the PDF signature or TXT decoding/content; full
   PDF extraction happens in the worker. Persist original bytes with status
   `PENDING` before dispatch.
2. Publish the task from a thread so synchronous Celery dispatch does not block the
   API event loop; return HTTP 202. If publication fails, leave the stored pending
   row for scheduled recovery.
3. The worker atomically claims eligible pending or expired work within the attempt
   limit. It sets `PROCESSING`, a claim token and lease, then commits the claim.
4. Run extraction in a thread. PDFs use pypdf with page/text limits and reject
   encryption or missing readable text. TXT requires UTF-8. There is no OCR.
5. Chunk each page independently into up to 1,000-character pieces. Long
   paragraphs use 150-character overlap; ordinary paragraph boundaries do not.
   Preserve page numbers for citations.
6. Embed in bounded batches with `RETRIEVAL_DOCUMENT`. Validate vector count,
   dimension, finite numeric values and nonzero vectors before saving.
7. Recheck the claim and lease, replace old chunks in one transaction, save
   embedding provenance, and mark `READY`. A stale claimant cannot overwrite the
   result of newer processing.
8. Retryable provider failures/timeouts return the row to `PENDING` with backoff
   while attempts remain. Other errors or exhausted attempts mark `FAILED`.

Celery Beat publishes `recover_documents` every `DOCUMENT_RECOVERY_SECONDS`
(default 30 seconds). Recovery scans eligible pending/expired rows, dispatches up
to 100 per scan, and marks exhausted attempts failed. Defaults allow four
processing attempts and a 300-second processing timeout. The UI can explicitly
reprocess a ready/failed document, resetting attempts.

Database commit and broker publication are separate operations. Durable pending
rows, scheduled recovery, leases, and guarded writes make repeated delivery
recoverable; they do not provide exactly-once broker delivery.

## Provider boundary

Gemini-specific chat and embedding calls live in their service adapters and the
shared client. Each provider operation has a timeout and at most two application
attempts for transient failures. Authentication/invalid-request errors are not
retried. Chat checks the prompt token budget before generation; combined chat
also requests structured JSON output. Document and chat orchestration have their
own overall deadlines.

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
