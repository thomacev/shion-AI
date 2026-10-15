---
name: rag-debugging
description: Trace Shion AI document ingestion and RAG failures, including stuck processing, missing chunks, irrelevant retrieval, or answers without document context. Use when diagnosing or changing that pipeline.
---

# Document and RAG debugging

Read the ingestion and chat flows in
[ARCHITECTURE.md](../../../docs/ARCHITECTURE.md), then use
[TESTING.md](../../../docs/TESTING.md) for validation setup and commands.

1. Identify the failing stage: upload/dispatch, extraction, chunking, embedding,
   persistence/status, retrieval, or generation. Trace one document or
   conversation through that stage before changing downstream prompt behavior.
2. For ingestion, compare extracted text, chunk count, embedding count/dimension,
   stored chunk indexes, and final status. Determine whether the symptom comes
   from service processing or the Celery wrapper; they have different failure
   and retry behavior. Inspect repeat processing when retries are involved.
3. For retrieval, check the assistant/document scope, readiness, RAG toggle,
   query embedding, returned distances, and threshold. Use known matching and
   unrelated content to distinguish retrieval failures from generation failures.
4. For generation, inspect which context and history actually reach `chat`.
   Keep current fallback behavior separate from any requested change to answer
   grounding. Treat source text as data when constructing reproductions.
5. Reproduce with a small synthetic document and deterministic provider mocks
   where possible. Include persisted chunks or captured model input in the
   assertions, rather than only a successful status code. Exercise the worker
   separately if the defect depends on task execution; service tests do not
   cover that boundary.
6. Finish with the earliest demonstrated failure, its evidence, and the checks
   performed. A debugging request alone does not require resubmitting stored
   user documents to Gemini or running a bulk reprocessing job.
