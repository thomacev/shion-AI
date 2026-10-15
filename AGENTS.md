# Working in Shion AI

Shion AI is a document-assisted chat application. The backend uses Python 3.12+,
FastAPI, Pydantic, async SQLAlchemy/asyncpg, PostgreSQL with pgvector, Celery,
Redis, and Google's `google-genai` SDK. The frontend is React/TypeScript with Vite.

## Navigation

- Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component boundaries,
  request/data flows, and current implementation limitations.
- Read [docs/TESTING.md](docs/TESTING.md) before validation: it owns setup,
  actual commands, test selection, mocks, and database precautions.
- Repository workflows live in [.agents/skills](.agents/skills):
  `backend-validation`, `rag-debugging`, and `schema-change`.

## Follow the existing code

- Backend imports use `app.*` from `src/`. Routers handle HTTP and dependencies;
  services own business logic and database commits. Schemas define validation
  and response serialization; models define persistence.
- Reuse the ownership lookups in assistant, conversation, and document services.
  Existing ownership failures return 404. Assistant deletion is a soft delete.
- Keep Gemini-specific calls in the LLM/embedding services and shared client.
  Document background execution belongs in `tasks/`.
- Follow existing Pydantic field validators, `from_attributes` response schemas,
  typed SQLAlchemy models, and domain exceptions handled in
  `core/exceptions_handlers.py`.
- Match surrounding style. The repo mixes English/Spanish comments and has no
  configured Python formatter or backend type-check command.
- Frontend scripts belong to `frontend/package.json`; root `package.json` only
  declares Axios. Do not assume root npm scripts or a frontend test runner exist.

## Keep guidance accurate

Use source, manifests, migrations, and CI as evidence when README claims differ.
Some historical documents linked from README are absent. Put architecture changes
in the architecture doc and validation changes in the testing doc rather than
copying their details here. Keep local `.env` values out of committed guidance.
