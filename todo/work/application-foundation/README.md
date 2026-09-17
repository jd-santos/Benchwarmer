# Finish the application foundation

Status: In progress on `task/conversation-library`. The fixture-backed API and source status UI are complete; the disposable browser harness is next.

## Purpose

Complete the fixture-backed path through SQLite, the Python API, and the responsive web application. This is the next executable work and unblocks the first importer.

## Dependencies and order

The existing source records, health boundary, runtime, shell, and API client are present. Follow the remaining sections of [the implementation plan](plan.md); completed sections are reference material.

## Acceptance criteria

A fresh checkout can migrate and seed disposable state, browse source status on desktop and mobile, and restart the API without losing records. All checks in the plan’s final integration gate pass.

## Work

- [x] Add import-batch records and migration
  - Dependencies: Add source records and migration (already recorded)
  - Plan: [Implementation details](plan.md#add-import-batch-records-and-migration)
  - Verify: migration round-trip and focused model tests

- [x] Verify the real database revision in health
  - Dependencies: Add truthful unmigrated API health (already recorded), [Add import-batch records and migration](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-the-real-database-revision-in-health)
  - Verify: health tests for unmigrated and migrated temporary databases

- [x] Add sanitized source fixture loading
  - Dependencies: [Add import-batch records and migration](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#add-sanitized-source-fixture-loading)
  - Verify: deterministic, idempotent fixture-load command and focused tests

- [x] Expose fixture-backed source status
  - Dependencies: [Verify the real database revision in health](../application-foundation/README.md), [Add sanitized source fixture loading](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#expose-fixture-backed-source-status)
  - Verify: service/API contract tests plus all Python checks

- [x] Add the first useful home page
  - Dependencies: Build the responsive application shell (already recorded), Add the typed API client and `/api` proxy (already recorded)
  - Plan: [Implementation details](plan.md#add-the-first-useful-home-page)
  - Verify: loading/healthy/unmigrated/error UI tests and frontend checks

- [x] Connect the source status page
  - Dependencies: [Expose fixture-backed source status](../application-foundation/README.md), [Add the first useful home page](../application-foundation/README.md), Add the typed API client and `/api` proxy (already recorded)
  - Plan: [Implementation details](plan.md#connect-the-source-status-page)
  - Verify: populated/empty/error UI tests, frontend checks, and Svelte MCP
    autofixer review where available

- [ ] Add the disposable browser process harness
  - Dependencies: [Expose fixture-backed source status](../application-foundation/README.md), [Connect the source status page](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#add-the-disposable-browser-process-harness)
  - Verify: Playwright starts, migrates, seeds, stops, and cleans up disposable
    processes/state

- [ ] Verify desktop and mobile browser flows
  - Dependencies: [Add the disposable browser process harness](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-desktop-and-mobile-browser-flows)
  - Verify: `npm --prefix web run test:e2e` at desktop and 375px viewports

- [ ] Verify API restart persistence
  - Dependencies: [Verify desktop and mobile browser flows](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-api-restart-persistence)
  - Verify: migrated fixture records survive an API process restart; the
    stateless frontend does not own persistence

- [ ] Document development and final integration
  - Dependencies: [Verify API restart persistence](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#document-development-and-final-integration)
  - Output: `docs/development.md`
  - Acceptance: a fresh checkout can migrate disposable state, start both
    processes, and pass desktop/mobile/restart flows with no private or
    generated artifacts tracked

## Verification

The import-batch slice added `ImportBatch`, versioned cursor and observed-coverage
envelopes, migration `0002`, SQLite foreign-key enforcement, and model/migration
coverage for terminal outcomes, retry identity, provenance, and round trips.

Actual checks on `task/conversation-library`:

- `uv run pytest tests/models/test_import_batch.py tests/db/test_import_batch_migration.py` — 11 passed
- `uv run ruff check .` — passed
- `uv run ruff format --check .` — 82 files already formatted
- `uv run python -m compileall src` — passed
- `uv run pytest` — 168 passed with one upstream Starlette/AnyIO deprecation warning
- `git diff --check` — passed

The full suite also found and corrected one stale test reference to the legacy
foundation-plan redirect.

The health-revision slice added an integration test that migrates a disposable
database and verifies `/api/v1/health` reports revision `0002`. The existing API
implementation passed without changes, confirming that the `/api/v1` contract
version remains separate from the inspected Alembic revision.

Additional checks for this slice:

- `uv run pytest tests/api/test_health.py` — 9 passed with one upstream Starlette/AnyIO deprecation warning
- `uv run pytest` — 169 passed with the same warning
- Disposable Uvicorn and `curl` loopback check — returned status `ok` and revision `0002`

The fixture-loading slice added three strictly synthetic source states: partial
import, failed import, and never imported. The versioned loader inserts sources
before their batches in one transaction, treats exact reloads as no-ops, rejects
conflicts without rewriting evidence, and reports only bounded record counts.
Provider charges, list-price estimates, subscription expense, and quota usage
remain separate coverage dimensions.

Additional checks for this slice:

- `uv run pytest tests/services/test_fixtures.py` — 6 passed
- `uv run pytest` — 175 passed with one upstream Starlette/AnyIO deprecation warning
- `uv run ruff check .` and `uv run ruff format --check .` — passed
- `uv run python -m compileall src` — passed
- Disposable command run twice — first created 3 sources and 2 batches; second recognized all 5 as existing

The source-status slice added a database-backed `GET /api/v1/sources` route with
stable display ordering, successful-import timestamps, and all ten public
coverage dimensions. Missing configured coverage remains `unknown`; failed and
partial batches never become successful imports. The synthetic Hermes history
now includes a successful import followed by a partial attempt, so the contract
exercises both freshness and degraded later work.

Additional checks for this slice:

- `uv run pytest tests/services/test_fixtures.py tests/services/test_source_status.py tests/api/test_sources.py` — 11 passed
- `uv run pytest` — 180 passed with one upstream Starlette/AnyIO deprecation warning
- `uv run ruff check .` and `uv run ruff format --check .` — passed
- `uv run python -m compileall src` — passed
- `git diff --check` — passed

The foundation home-page slice replaced the placeholder with a responsive
system overview backed by the typed health and source clients. It distinguishes
loading, operational, unmigrated, empty, partial, unavailable, unknown, and
request-error states; an unmigrated database does not trigger a source query.
The typed client now accepts SvelteKit's request-scoped `fetch`, avoiding runtime
load warnings while preserving same-origin API paths.

Additional checks for this slice:

- `npm --prefix web test` — 23 passed
- `npm --prefix web run lint` — passed
- `npm --prefix web run check` — 0 errors and 0 warnings
- `npm --prefix web run build` — static production build passed
- Disposable migrated API and Vite browser review — rendered 3 sources, 1 successful import, and explicit coverage counts with a valid accessibility tree

The source-status page slice added responsive source cards backed by the typed
API client. Each card reports the last successful import and all ten coverage
dimensions as text and visual status treatments. Never-imported and failed-only
sources retain explicit missing-success states, while partial, unavailable, and
unknown coverage remain distinct. Empty, loading, and API-failure states provide
clear next actions.

Additional checks for this slice:

- `npm --prefix web test` — 27 passed
- `npm --prefix web run lint` — passed
- `npm --prefix web run check` — 0 errors and 0 warnings
- `npm --prefix web run build` — static production build passed
- Disposable migrated API and Vite browser review — rendered all 3 synthetic sources through `/api`, with readable narrow-screen cards, current navigation state, a valid accessibility tree, and no browser errors
- Svelte MCP was unavailable; Prettier, ESLint, `svelte-check`, component tests, production build, and browser review provided the fallback validation

The next ready step is **Add the disposable browser process harness**.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Implementation plan](plan.md), including completed foundations as reference
