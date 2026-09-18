# Finish the application foundation

Status: Complete on `task/conversation-library`; pull request #5 is pending merge. The final integration gate and independent acceptance review passed.

## Purpose

Complete the fixture-backed path through SQLite, the Python API, and the responsive web application. This is the next executable work and unblocks the first importer.

## Dependencies and order

The fixture-backed foundation is complete. The [implementation plan](plan.md) is retained as reference material for the accepted boundaries and verification.

## Acceptance criteria

A fresh checkout can migrate and seed disposable state, build the Svelte application, browse source status from one FastAPI origin on desktop and mobile, and restart the API without losing records. API paths, static assets, and SPA fallback behavior remain distinct. All checks in the plan’s final integration gate pass.

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

- [x] Add the disposable browser process harness
  - Dependencies: [Expose fixture-backed source status](../application-foundation/README.md), [Connect the source status page](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#add-the-disposable-browser-process-harness)
  - Verify: Playwright starts, migrates, seeds, stops, and cleans up disposable
    processes/state

- [x] Verify desktop and mobile browser flows
  - Dependencies: [Add the disposable browser process harness](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-desktop-and-mobile-browser-flows)
  - Verify: `npm --prefix web run test:e2e` at desktop and 375px viewports

- [x] Serve the built application through FastAPI
  - Dependencies: [Verify desktop and mobile browser flows](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#serve-the-built-application-through-fastapi)
  - Verify: one origin serves the built UI and `/api/v1`; unknown API routes,
    mutations, and missing assets never fall through to the SPA document

- [x] Verify API restart persistence
  - Dependencies: [Serve the built application through FastAPI](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-api-restart-persistence)
  - Verify: migrated fixture records survive a single-origin API process
    restart; the stateless frontend does not own persistence

- [x] Document development and final integration
  - Dependencies: [Verify API restart persistence](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#document-development-and-final-integration)
  - Output: `docs/development.md` and `scripts/run-foundation-demo.sh`
  - Acceptance: a fresh checkout can run the synthetic demo, migrate disposable
    state, start the single application process, and pass desktop, mobile, and
    restart flows with no private or generated artifacts tracked

## Shipping reconciliation

A second local session created the initial changelog commit while this branch was
under review. Preserve that commit and reconcile forward without rewriting history:

- [x] Merge both changelog drafts and link the maintained changelog from the workbench.
- [x] Remove generated test output and rerun affected validation.
- [x] Push `task/conversation-library` and open
  [pull request #5](https://github.com/jd-santos/Benchwarmer/pull/5) against `main`.

Reconciliation validation reused the green Python and frontend checks from the
shipping review. The reviewer fix then passed 27 frontend unit tests, 4 browser
tests, lint, `svelte-check`, the production build, LSP diagnostics, and
`git diff --check`. The generated `.vitest/` output was removed.

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

The browser-harness slice added Playwright with a worker-scoped application
fixture. Each worker allocates independent loopback ports and a temporary data
root, migrates and seeds synthetic records, starts the API and Vite proxy, waits
for both services, and owns process-group shutdown and recursive cleanup. The
generated demo was removed. A smoke test verifies the migrated API and source
page, while a second overlapping application instance proves that teardown
removes its root without colliding with the active worker fixture.

Additional checks for this slice:

- `npm --prefix web test` — 27 unit tests and 2 browser tests passed
- `npm --prefix web run lint` — passed
- `npm --prefix web run check` — 0 errors and 0 warnings
- `npm --prefix web run build` — static production build passed
- Temporary-root audit after Playwright exit — no `benchwarmer-playwright-*` directories remained

The browser-flow slice expanded the harness into full desktop and 375px paths.
Both start at the fixture-backed overview, verify health and source counts,
navigate to the source page, and assert all ten coverage labels and explicit
coverage states. The phone path reaches navigation through the visible skip
link and keyboard focus order, opens the menu with Enter, and completes
navigation without pointer input. Both viewports measure page width to prevent
horizontal overflow. A same-run request interception verifies the actionable
API-failure message without changing disposable storage.

Additional checks for this slice:

- `npm --prefix web test` — 27 unit tests and 4 browser tests passed
- `npm --prefix web run lint` — passed
- `npm --prefix web run check` — 0 errors and 0 warnings
- `npm --prefix web run build` — static production build passed
- Desktop and 375px flows — fixture-backed overview and source records verified
- Mobile keyboard flow — skip link, brand, menu, overview, and source links verified in focus order
- API interception — same-origin `/api/` failure rendered the recovery alert
- Overflow checks — desktop and mobile document widths remained within their viewports

The final single-origin slice replaced Vite in the browser harness with the built
Svelte application served by FastAPI. Environment startup now requires a valid,
absolute `BENCHWARMER_UI_ROOT`; explicit API-only test construction remains
available. API routes take precedence, unsafe methods and unknown API paths do
not receive the SPA document, static traversal is rejected, and missing assets
return errors. The restart flow verifies unchanged health and source responses,
then reloads the browser view from the replacement process.

Final integration checks:

- Pinned runtime validation and `uv sync --locked --dev`: passed
- `uv run pytest`: 185 passed with one upstream Starlette/AnyIO deprecation warning
- `uv run ruff check .`, `uv run ruff format --check .`, and compileall: passed
- `npm --prefix web ci`: passed; npm reported 3 low-severity audit findings
- `svelte-check` and frontend lint: 0 errors and 0 warnings
- Frontend unit tests: 27 passed
- Single-origin desktop, 375px, API-failure, cleanup, and restart browser tests:
  5 passed
- Static production build and `git diff --check`: passed
- `scripts/run-foundation-demo.sh`: served the UI and API, loaded only 3
  synthetic sources, and removed its temporary data root after termination
- Demo refusal checks: rejected a preconfigured data root and invalid port
  before preparing state
- Independent acceptance review: no runtime, privacy, traversal, routing, or
  shell-cleanup blocker found

Image construction, immutable `/opt/benchwarmer/ui` packaging, cache headers,
Tailscale routing, proxy trust, and target-host verification remain in
[private deployment](../private-deployment/README.md).

The next ready step is
**[Import Hermes conversations reliably](../hermes-import/README.md)**.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Implementation plan](plan.md), including completed foundations as reference
