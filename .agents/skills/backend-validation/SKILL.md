---
name: backend-validation
description: Validate Shion AI backend changes or diagnose pytest and CI failures using the repository's actual test setup. Use for backend verification, not frontend-only or documentation-only edits.
---

# Backend validation

Read [TESTING.md](../../../docs/TESTING.md) for commands, database setup,
fixture behavior, and provider-mocking gaps. Paths below are repository-relative.

1. Inspect the changed behavior and choose the relevant test file(s) from the
   command table. For auth or ownership changes, include the affected resource
   tests as well as auth tests.
2. Check the documented environment prerequisites before executing fixtures.
   If the configured database is not known to be disposable, use collection and
   static analysis while resolving that specific setup issue; do not run table
   teardown against an uncertain target or print connection credentials.
3. For tests that reach generation, embedding, or dispatch, inspect the actual
   patch targets along that path. A provider failure before the intended
   assertion can make a test pass for the wrong reason.
4. Run focused checks. For a requested full backend verification, run the CI
   coverage command; include migration validation for schema changes and the
   image build for container changes. Do not install tools or invent checks
   beyond the repository setup merely to produce a larger validation list.
5. Report commands and outcomes, distinguish environment failures from code
   failures, and state any path that remained untested. Do not report collection
   or mocked service tests as proof of worker or provider integration.
