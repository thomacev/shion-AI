---
name: schema-change
description: Implement or review Shion AI SQLAlchemy and Alembic schema changes, especially pgvector dimensions and indexes. Use for database model or migration work, not ordinary service-only edits.
---

# Schema changes

Read the stored-data section in
[ARCHITECTURE.md](../../../docs/ARCHITECTURE.md) and the database prerequisites
and migration commands in [TESTING.md](../../../docs/TESTING.md).

1. Inspect the affected SQLAlchemy models, the Alembic revision graph, and
   `alembic/env.py`. It imports model metadata explicitly; check that a new
   model is included if the requested change adds one.
2. Compare the model with the existing migration chain, including nullability,
   defaults, enums, foreign keys, and indexes. For embedding changes, compare
   settings, stored vector dimensions, and the provider output. A model change
   does not itself alter an existing database or regenerate embeddings.
3. Implement the requested model/schema change and a new Alembic revision as
   appropriate. Review generated operations for unrelated removals, especially
   indexes absent from ORM metadata. Keep data backfills or re-embedding work
   explicit rather than silently including them in a structural migration.
4. Validate the upgrade against a disposable database using the documented
   commands. Exercise both a fresh migration chain and the preceding revision
   when existing data is affected. Assess downgrade data loss before running a
   downgrade; do not treat rollback as inherently safe.
5. Run the affected domain tests, and verify migration-created structures
   separately from fixture-created ORM tables. Report the revision, data impact,
   validation performed, and any deployment prerequisites without applying the
   migration to an unrelated running application database.
