# Application foundation implementation plan

Execution status and the only live checklist belong to [the work record](README.md).
Completed sections below preserve implementation details; do not rerun them as
new tasks. Future commands and suggested commit messages are planning guidance,
not evidence of execution or authorization to commit.

**Goal:** Produce a fixture-backed vertical slice in which a migrated SQLite
store, Python API, and mobile-friendly SvelteKit UI expose source/import status
through a same-origin `/api` boundary.

**Architecture:** The Python service owns configuration, domain rules, SQLite,
provenance, and API contracts. SvelteKit is a TypeScript presentation client; it
does not access SQLite. Development proxies `/api` to Python. The accepted
[serving decision](../../../docs/decisions/0003-serving-supervision.md) selects
the static adapter and production routing; operational verification remains pending.

**Tech stack:** Python 3.12+, uv, FastAPI, SQLAlchemy, Alembic, SQLite, pytest,
Ruff, Svelte 5, SvelteKit, TypeScript, Vitest, Playwright, and the adapter
selected by [the serving decision](../../../docs/decisions/0003-serving-supervision.md).

---

## Scope and assumptions

This plan supplies implementation details for [the foundation work record](README.md). It does not
implement a real source adapter, private deployment, annotations, usage
aggregation, or experiment execution.

The commands below implement the foundation decisions accepted by [the accepted foundation decisions](../../../docs/decisions.md):

- FastAPI with explicit `/api/v1` routes.
- SQLAlchemy 2 and Alembic for persistence and migrations.
- SvelteKit with TypeScript, npm, ESLint, Prettier, and Vitest; no CSS framework
  initially. Use `adapter-static` with a `200.html` SPA fallback. Playwright
  lands with the first browser-test harness in [Add the disposable browser process harness](README.md).
- `web/` for the frontend and `src/benchwarmer/` for Python.
- A configurable private data root outside the checkout, overridden by
  `BENCHWARMER_DATA_ROOT`; tests always use a temporary directory.
- Separate API and future worker processes. Do not add an idle worker stub.
- [the pinned Python and SQLite runtime](../../../docs/runtime-recovery.md) pins Python 3.13.15 with SQLite 3.53.4 and provides the in-process
  WAL-safety gate. Every later database entry point calls that gate before its
  first connection.
- UI tasks follow the
  [interface design principles](../../../docs/architecture.md#interface-design-principles)
  and the linked UI design skill. Start from task hierarchy, use the least visual
  structure needed, preserve distinct application states, and include responsive
  and accessibility behavior in the initial implementation.

If a different choice is recorded, update this plan's paths and commands in the
same commit so later agents do not inherit contradictory instructions.

See ADRs [0001](../../../docs/decisions/0001-application-foundation.md),
[0002](../../../docs/decisions/0002-data-recovery.md), and
[0003](../../../docs/decisions/0003-serving-supervision.md) for rationale and deferred
deployment checks.

## API contract for the slice

`GET /api/v1/health` reports the Alembic revision applied to the configured
database; it is not an API contract version:

```json
{
  "status": "ok",
  "alembic_revision": "0002",
  "data_root_writable": true
}
```

`alembic_revision` is `null` until migrations exist in the configured database.
Health always returns HTTP 200 — unmigrated is an expected state, not an error,
and `curl --fail` must succeed against it. The revision is read from the
database on each request from [the API health boundary](plan.md) onward; no task may hard-code it.
Migrations `0001` and `0002` are created by [Add source records and migration](plan.md) and [Add import-batch records and migration](README.md); [Verify the real database revision in health](README.md) only
extends health tests to assert `"0002"` after `alembic upgrade head`.

`GET /api/v1/sources` returns a stable envelope even when no sources exist:

```json
{
  "items": [
    {
      "id": "fixture-hermes",
      "kind": "hermes",
      "display_name": "Hermes fixture",
      "last_successful_import_at": "2026-09-07T12:00:00Z",
      "coverage": {
        "sessions": "available",
        "token_usage": "partial",
        "request_ids": "partial",
        "actual_charges": "unavailable",
        "list_price_estimates": "unavailable",
        "subscription_expense": "unavailable",
        "quota": "unknown",
        "credits": "unknown",
        "prompts": "partial",
        "classifications": "unknown"
      }
    }
  ]
}
```

Coverage values are `available`, `partial`, `unavailable`, or `unknown`; absence
must not be encoded as zero. Actual charges, API-equivalent price estimates,
subscription expense, quota, and credits are distinct dimensions. The exact
fixture timestamp is test data, not a runtime default.

### Record application foundation defaults

Already implemented at the migration baseline; reference only.

**Objective:** Turn foundation-level technology choices into explicit,
reviewable decisions before agents generate code.

**Files:**

- Create: `docs/decisions/0001-application-foundation.md`

**Steps:**

1. Record the selected backend framework, ORM/migration layer, frontend package
   manager and tooling, exact `sv` scaffold version, API path/versioning,
   API/UI process boundary, and the future worker boundary in a dedicated
   foundation decision document.
2. State why the SvelteKit server cannot own domain persistence and why no
   worker stub is needed yet.
3. Record which items remain under [the data and recovery decision](../../../docs/decisions/0002-data-recovery.md) and [the serving decision](../../../docs/decisions/0003-serving-supervision.md) instead of silently
   choosing private deployment or backup behavior here.
4. Run `git diff --check` and inspect the rendered links.
5. Commit with `docs: record application foundation defaults`.
6. Return the proposal to the coordinating agent. [the accepted foundation decisions](../../../docs/decisions.md) reviews it with the
   data/recovery and serving proposals before updating canonical decisions or
   work-record status.

**Acceptance:** Every later task has one unambiguous toolchain and path layout;
no deployment or source-capability claim is presented as verified.

### Add Python test and lint tooling

Already implemented at the migration baseline; reference only.

**Objective:** Establish executable checks before application code is added.

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/test_package.py`

**Steps:**

1. Add development tooling only. Runtime packages land with the first task that
   consumes them ([private data-root configuration](plan.md) adds pydantic, [Add database migration plumbing](plan.md) adds sqlalchemy and alembic,
   [the API health boundary](plan.md) adds fastapi and uvicorn); this respects the repo rule that
   dependencies wait for an implemented feature:

   ```bash
   uv add --dev pytest ruff
   ```

2. Configure Ruff's supported Python version, formatting, and a minimal rule
   set in `pyproject.toml` without repo-wide speculative policy.
3. Add a package smoke test that imports `benchwarmer`.
4. Run `uv run pytest` and verify it passes.
5. Run `uv run ruff check .`, `uv run ruff format --check .`, and
   `uv run python -m compileall src`.
6. Update `AGENTS.md` Commands so Install reads `uv sync --dev` for development
   once pytest and Ruff exist.
7. Commit with `build: add Python test and lint tooling`.

**Acceptance:** A fresh `uv sync --dev` followed by all four checks succeeds.

### Provision a WAL-safe SQLite runtime

Already implemented at the migration baseline; reference only.

**Objective:** Provision a development and production Python runtime whose linked
SQLite contains the WAL-reset fix, and prevent later regressions from opening a
WAL database.

**Files:**

- Modify: `.python-version` and runtime/container inputs selected by the task
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/benchwarmer/sqlite_runtime.py`
- Create: `tests/test_sqlite_runtime.py`

**Steps:**

1. Record the current Python executable and `sqlite3.sqlite_version`; the
   existing project virtual environment's SQLite `3.50.4` is an expected failing
   precondition, not an acceptable runtime.
2. Pin one reproducible interpreter/runtime mechanism for development, CI, and
   the target deployment. Do not rely on whichever system Python happens to be
   first on `PATH`.
3. Test the ADR 0002 predicate: reject `3.50.4`, `3.51.2`, and the vulnerable
   `3.45` through `3.49` lines; accept `3.51.3`, `3.50.7`, `3.44.6`, and newer
   fixed releases on those branches.
4. Implement a pre-connection guard using `sqlite3.sqlite_version_info`. Every
   API, worker, migration, backup, and restore entry point must call it before
   opening a database whose journal mode may be WAL.
5. Recreate the project environment from the pinned inputs and require:

   ```bash
   uv run python -c \
     'from benchwarmer.sqlite_runtime import require_wal_safe_sqlite; require_wal_safe_sqlite()'
   ```

6. Run focused and full Python checks. Commit with
   `build: require a WAL-safe SQLite runtime`.

**Acceptance:** A clean environment resolves a fixed SQLite runtime; vulnerable
boundary tests fail closed; the live gate passes before [private data-root configuration](plan.md) begins.

### Implement private data-root configuration

Already implemented at the migration baseline; reference only.

**Objective:** Resolve runtime paths centrally while keeping tests and
application data outside the checkout by default.

**Files:**

- Create: `src/benchwarmer/config.py`
- Create: `tests/test_config.py`
- Modify: `.gitignore` only if a generated runtime path is not already covered

**Steps:**

1. Add the first runtime dependency this task consumes:

   ```bash
   uv add pydantic
   ```

2. Write failing tests for the configuration interface and default accepted by
   [the accepted foundation decisions](../../../docs/decisions.md), directory creation, and a non-writable/invalid path.
3. Run `uv run pytest tests/test_config.py -q` and verify the new tests fail.
4. Implement a typed settings object that resolves database, artifact,
   snapshot, and job/log paths from one root. Avoid module-import side effects.
5. Run the focused tests, then execute ADR 0002's complete disposable
   WAL/recovery prototype without bypassing its preflight. Require
   `recovery prototype: PASS` and verify it leaves no state in the checkout.
6. Run all Python checks from [Python quality tooling](plan.md).
7. Commit with `feat: add private data root configuration`.

**Acceptance:** Tests use `tmp_path`; importing the package creates no files;
an invalid root fails with an actionable error; the recovery fixture passes;
and no private path or runtime state enters git.

### Add database migration plumbing

Already implemented at the migration baseline; reference only.

**Objective:** Add Alembic wiring that can migrate the configured disposable
SQLite database before domain tables exist.

**Files:**

- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `src/benchwarmer/db.py`
- Create: `tests/db/test_migration_environment.py`

**Steps:**

1. Add the first persistence dependencies this task consumes:

   ```bash
   uv add sqlalchemy alembic
   ```

2. Run the [the pinned Python and SQLite runtime](../../../docs/runtime-recovery.md) in-process guard and stop immediately if it fails. Do not
   create a database or enable WAL on a rejected runtime.
3. Write failing tests that initialize an empty temporary database, report its
   current Alembic revision, and reject a non-SQLite URL if unsupported.
4. Implement SQLAlchemy engine/session configuration and Alembic configuration
   using the resolved application database URL, never a checkout-relative
   production default. Call the WAL-safety guard before the first connection.
5. Define exact commands for task verification:

   ```bash
   root="$(mktemp -d)"
   BENCHWARMER_DATA_ROOT="$root" uv run alembic current
   BENCHWARMER_DATA_ROOT="$root" uv run alembic upgrade head
   BENCHWARMER_DATA_ROOT="$root" uv run alembic downgrade base
   ```

6. Run focused tests and all Python checks.
7. Commit with `build: add database migration plumbing`.

**Acceptance:** Alembic can inspect and migrate a temporary database through
the configured data root; no domain table is required yet.

### Add truthful unmigrated API health

Already implemented at the migration baseline; reference only.

**Objective:** Provide a real Python process whose health response truthfully
reports migration state without pretending `0001` exists.

**Files:**

- Create: `src/benchwarmer/api/__init__.py`
- Create: `src/benchwarmer/api/app.py`
- Create: `tests/api/test_health.py`

**Steps:**

1. Add the first web dependencies this task consumes:

   ```bash
   uv add fastapi 'uvicorn[standard]'
   uv add --dev httpx
   ```

2. Write a failing FastAPI client test for `/api/v1/health`, including status
   code, content type, exact keys, explicit null `alembic_revision`, and
   data-root writability.
3. Implement an application factory that accepts settings explicitly in tests,
   expose the health route through an `/api/v1` router, and inspect the applied
   Alembic revision on every request. Return `null` when the configured database
   has no Alembic version table; never hard-code a revision.
4. Start it with the exact command:

   ```bash
   BENCHWARMER_DATA_ROOT="$(mktemp -d)" \
     uv run uvicorn benchwarmer.api.app:create_app --factory \
     --host 127.0.0.1 --port 8000
   ```

5. Verify with `curl --fail http://127.0.0.1:8000/api/v1/health`.
6. Run focused and full Python checks.
7. Stop the process and commit with `feat: add API health endpoint`.

**Acceptance:** Startup does not require a repository-local database and cannot
claim an applied migration before the migration task creates it.

### Add source records and migration

Already implemented at the migration baseline; reference only.

**Objective:** Persist stable source identity separately from import attempts.

**Files:**

- Create: `src/benchwarmer/models/source.py`
- Create: `migrations/versions/0001_sources.py`
- Modify: `migrations/env.py` if model registration is needed
- Create: `tests/db/test_source_migration.py`
- Create: `tests/models/test_source.py`

**Steps:**

1. Write failing migration/model tests for required source fields, uniqueness,
   timestamps, and nullable coverage metadata.
2. Verify the focused tests fail before implementation.
3. Define only the source record; do not add sessions, usage, prices, trials,
   import batches, or an unversioned JSON dump.
4. Run upgrade, downgrade, upgrade round-trip tests on a temporary database.
5. Run focused tests and all Python checks.
6. Commit with `feat: add source provenance records`.

**Acceptance:** Source identity is durable and does not overwrite prior import
or coverage facts.

### Add import-batch records and migration

**Objective:** Persist each import attempt, cursor, outcome, and coverage
provenance without mutating source identity.

**Files:**

- Create: `src/benchwarmer/models/import_batch.py`
- Create: `migrations/versions/0002_import_batches.py`
- Create: `tests/db/test_import_batch_migration.py`
- Create: `tests/models/test_import_batch.py`

**Steps:**

1. Write failing migration/model tests for source foreign keys, stable source
   IDs, cursor/coverage metadata, timestamps, outcome, error summary, and
   retry/idempotency semantics.
2. Verify the focused tests fail before implementation.
3. Implement only import batches; do not infer economics or reconcile overlap.
4. Run upgrade, downgrade, upgrade round-trip tests on a temporary database.
5. Run focused tests and all Python checks.
6. Commit with `feat: add import batch records`.

**Acceptance:** Failed, partial, and successful imports are distinct records;
the latest batch never erases earlier evidence.

### Verify the real database revision in health

**Objective:** Verify the per-request revision inspection implemented by
[the API health boundary](plan.md) against the completed foundation migrations.

**Files:**

- Modify: `tests/api/test_health.py`

**Steps:**

1. Extend health tests so a temporary database reports `"alembic_revision":
   "0002"` after `uv run alembic upgrade head` and `null` before migrations.
2. Run the focused test and require it to pass against [the API health boundary](plan.md). If it fails,
   stop and correct the earlier health contract rather than adding a second
   revision implementation here.
3. Run full Python checks plus the loopback HTTP verification from
   [the API health boundary](plan.md).
4. Commit with `test: verify migrated database revision in health`.

**Acceptance:** The response reflects the actual Alembic revision and clearly
separates migration state from the `/api/v1` contract version.

### Add sanitized source fixture loading

**Objective:** Make sanitized source/import records reproducibly loadable for
API, UI, and browser tests.

**Files:**

- Create: `tests/fixtures/sources.json`
- Create: `src/benchwarmer/services/fixtures.py`
- Create: `tests/services/test_fixtures.py`

**Steps:**

1. Add intentionally sanitized source/import fixture records. Include one
   partial source and one failed or never-imported source.
2. Write failing tests for load, idempotent reload, foreign-key integrity, and
   distinct economics coverage fields.
3. Implement the smallest deterministic fixture loader.
4. Define the exact command and expected result:

   ```bash
   root="$(mktemp -d)"
   BENCHWARMER_DATA_ROOT="$root" uv run alembic upgrade head
   BENCHWARMER_DATA_ROOT="$root" \
     uv run python -m benchwarmer.services.fixtures \
     --load tests/fixtures/sources.json
   ```

5. Run focused tests and all Python checks.
6. Commit with `test: add sanitized source fixtures`.

**Acceptance:** Fixture loading is idempotent in a disposable data root and no
private source content is represented.

### Expose fixture-backed source status

**Objective:** Exercise persistence through an API response while preserving
unknown and unavailable coverage.

**Files:**

- Create: `src/benchwarmer/api/routes/sources.py`
- Create: `src/benchwarmer/services/source_status.py`
- Create: `tests/api/test_sources.py`
- Create: `tests/services/test_source_status.py`

**Steps:**

1. Write failing service and API tests for ordering, last-success timestamps,
   every documented coverage dimension, and the empty `{"items": []}` response.
2. Implement the smallest query service and `/api/v1/sources` route that
   satisfy the contract. Do not implement an importer or infer missing metrics.
3. Run focused tests and all Python checks.
4. Commit with `feat: expose source import status`.

**Acceptance:** The endpoint reads migrated records, not an in-memory
hard-coded response; missing coverage never becomes zero or `available`.

### Scaffold SvelteKit with the selected adapter and checks

Already implemented at the migration baseline; reference only.

**Objective:** Add a reproducible Svelte 5/SvelteKit frontend toolchain with
unit checks and the accepted static production adapter.

**Files:**

- Create: `web/` using the Svelte CLI
- Create: `web/src/routes/+layout.ts`
- Modify: root `.gitignore` if generated output is not fully ignored

**Steps:**

1. Use the exact `sv` version accepted by [the accepted foundation decisions](../../../docs/decisions.md); do not resolve `latest`:

   ```bash
   npx -y sv@0.17.0 create web --template minimal --types ts \
     --add prettier eslint 'vitest=usages:unit' \
     'sveltekit-adapter=adapter:static' --install npm
   ```

2. Review every generated file. Keep the minimal template and remove demo
   content; do not add Tailwind, authentication, an ORM, or experimental remote
   functions.
3. Configure adapter-static with fallback `200.html` and set `ssr = false` in
   `web/src/routes/+layout.ts`; API and missing-asset paths must not use the SPA
   fallback when Python serves the production bundle.
4. Run `npm run check`, `npm run lint`, `npm run test:unit -- --run`, and
   `npm run build` from `web/`.
5. Commit with `build: scaffold SvelteKit frontend`.

**Acceptance:** The committed lockfile reproduces installation; the production
build produces `web/build/200.html`; Playwright is not yet installed; generated
build/cache directories are untracked.

### Build the responsive application shell

Already implemented at the migration baseline; reference only.

**Objective:** Establish semantic navigation and layout states without creating
empty future-feature pages.

**Files:**

- Modify: `web/src/routes/+layout.svelte`
- Create: `web/src/lib/components/AppNavigation.svelte`
- Create: `web/src/lib/styles/app.css`
- Create: `web/src/lib/components/AppNavigation.test.ts`

**Steps:**

1. Write failing component tests for landmarks, current-page indication,
   keyboard operation, and narrow-screen navigation state.
2. Implement an app shell linking only `/` and `/sources` for this slice. List
   future routes in the roadmap, not as dead UI controls.
3. Use semantic HTML, visible focus, touch targets, reduced-motion-safe
   behavior, and layout rules that work at 375px and desktop widths.
4. Run component tests, `npm run check`, `npm run lint`, and the production
   build.
5. Commit with `feat: add responsive application shell`.

**Acceptance:** Navigation works without pointer input, no page-level
horizontal scroll appears at 375px, and no accessibility warning is ignored
without rationale.

### Add the typed API client and `/api` proxy

Already implemented at the migration baseline; reference only.

**Objective:** Give SvelteKit one narrow, testable path to the Python API while
keeping browser requests same-origin.

**Files:**

- Create: `web/src/lib/api/client.ts`
- Create: `web/src/lib/api/types.ts`
- Modify: `web/vite.config.ts`
- Create: `web/src/lib/api/client.test.ts`

**Steps:**

1. Write failing client tests for request paths, cancellation, non-2xx
   responses, and malformed JSON.
2. Configure the Vite development proxy for `/api` from a server-side
   `BENCHWARMER_API_ORIGIN`, defaulting to `http://127.0.0.1:8000` for local
   development. Do not expose that target to browser code.
3. Implement a typed client only for `/api/v1/health` and `/api/v1/sources`; do
   not create a generic request framework.
4. Run focused tests, all frontend checks, and the production build.
5. Commit with `feat: add typed source status client`.

**Acceptance:** Browser code calls only same-origin `/api/v1/*` paths and
represents API failures without substituting fabricated data.

### Add the first useful home page

**Objective:** Make `/` useful for this slice by presenting typed health and
source-status state without pretending later features exist.

**Files:**

- Modify: `web/src/routes/+page.svelte`
- Create: `web/src/routes/+page.ts`
- Create: `web/src/routes/page.test.ts`

**Steps:**

1. Write failing tests for loading, healthy, unmigrated, unavailable, and
   partial coverage states.
2. Render only information supported by the current API: service status,
   Alembic migration state, source count/status, and links to `/sources`.
3. Run all frontend checks and the production build.
4. Commit with `feat: add foundation status home page`.

**Acceptance:** The home page has no dead future-feature controls and clearly
labels unavailable or unmigrated state.

### Connect the source status page

**Objective:** Complete the vertical slice from SQLite through Python to typed,
mobile-friendly UI states.

**Files:**

- Create: `web/src/routes/sources/+page.ts`
- Create: `web/src/routes/sources/+page.svelte`
- Create: `web/src/routes/sources/page.test.ts`

**Steps:**

1. Write failing tests for populated, empty, loading, partial-coverage,
   unavailable, and API-failure states.
2. Render source freshness and every economics/capability coverage label as
   text plus visual treatment; color alone cannot carry meaning.
3. At 375px, present source records as readable cards or stacked rows. At wide
   widths, a table is acceptable if it does not force the page to scroll.
4. If Svelte MCP is available, run its `svelte-autofixer` on changed components;
   otherwise record the fallback and run all required local checks.
5. Commit with `feat: show source coverage status`.

**Acceptance:** Every API state is actionable; unknown values remain unknown;
the browser reaches Python only through `/api`.

### Add the disposable browser process harness

**Objective:** Make Playwright responsible for disposable migration, fixture
loading, process startup, process shutdown, and cleanup.

**Files:**

- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Create: `web/playwright.config.ts`
- Create: `web/tests/support/foundation.ts`
- Create: `web/tests/foundation.spec.ts`

**Steps:**

1. Add Playwright with the pinned Svelte CLI and install Chromium:

   ```bash
   npx -y sv@0.17.0 add playwright --cwd web --install npm
   npm --prefix web exec -- playwright install chromium
   ```

2. Remove the generated Playwright demo route and example test; retain only the
   dependency, scripts, and configuration needed by the foundation harness.
3. Allocate free loopback ports for the API and frontend and configure a
   temporary `BENCHWARMER_DATA_ROOT` for each browser run. Export the API URL as
   `BENCHWARMER_API_ORIGIN` for the Vite process.
4. Start the API with:

   ```bash
   BENCHWARMER_DATA_ROOT="$test_root" uv run alembic upgrade head
   BENCHWARMER_DATA_ROOT="$test_root" \
     uv run python -m benchwarmer.services.fixtures \
     --load tests/fixtures/sources.json
   BENCHWARMER_DATA_ROOT="$test_root" \
     uv run uvicorn benchwarmer.api.app:create_app --factory \
     --host 127.0.0.1 --port "$api_port"
   ```

5. Start the frontend with:

   ```bash
   BENCHWARMER_API_ORIGIN="http://127.0.0.1:$api_port" \
     npm --prefix web run dev -- --host 127.0.0.1 --port "$web_port"
   ```

6. Inject the API-error state by intercepting requests with Playwright
   `page.route('/api/**')` in the specific error-state test (or a second
   dev-server proxy target); do not mutate the shared disposable database.
7. Ensure test teardown stops both processes and removes the temporary data
   root.
8. Run `npm run test:e2e` and all frontend checks.
9. Commit with `test: add foundation browser harness`.

**Acceptance:** Tests allocate their own ports and create, migrate, seed, stop,
and delete their own state; parallel or repeated runs do not collide or require
repository-local data.

### Verify desktop and mobile browser flows

**Objective:** Prove navigation and source status are usable at both desktop
and phone-sized viewports.

**Files:**

- Modify: `web/tests/foundation.spec.ts`

**Steps:**

1. Add a desktop viewport test: load `/`, observe health/source status,
   navigate to `/sources`, and verify fixture records.
2. Add a 375px mobile viewport test covering the same path, keyboard-visible
   navigation, and no page-level horizontal overflow.
3. Include a same-run API-error state using the Playwright request interception
   mechanism defined by [Add the disposable browser process harness](README.md).
4. Run `npm run test:e2e` and all frontend checks.
5. Commit with `test: verify desktop and mobile foundation flows`.

**Acceptance:** Both viewports complete the storage-to-UI path and expose
coverage labels without horizontal page scrolling.

### Serve the built application through FastAPI

**Objective:** Exercise the product-shaped one-process boundary selected by ADR
0003: FastAPI serves both the built Svelte application and `/api/v1` from one
origin, while SQLite and domain policy remain Python-owned.

**Files:**

- Modify: `src/benchwarmer/api/app.py`
- Modify or create: focused API/static-serving tests under `tests/api/`
- Modify: `web/tests/support/foundation.ts`
- Modify: `web/tests/foundation.spec.ts` only where the origin contract changes

**Steps:**

1. Add an explicit built-UI root contract that is separate from the private
   data root. The deployment image copies `web/build` to the immutable
   `/opt/benchwarmer/ui` path and sets
   `BENCHWARMER_UI_ROOT=/opt/benchwarmer/ui`; the Uvicorn factory requires an
   absolute root containing `200.html` and fails startup otherwise. Tests may
   inject a temporary build root, and local tools may set the environment value
   to an absolute checkout build. Do not auto-discover the current directory or
   serve anything from the private data root.
2. Register `/api/v1` routes before UI handling. Keep `/api`, unknown API paths,
   and non-GET/HEAD requests out of the SPA fallback.
3. Serve exact generated assets when present. Missing assets and path-traversal
   attempts return a normal error rather than `200.html`.
4. Return the generated `200.html` only for safe application-route GET/HEAD
   requests. Preserve explicit content types and avoid reading file contents
   into application memory when FastAPI or Starlette can stream them.
5. Build the frontend before browser startup, replace the Vite process with one
   Uvicorn process configured with the build root, and run the existing desktop
   and mobile flows against that origin.
6. Add focused route-precedence, fallback, method, missing-asset, traversal,
   startup-validation, HTML content-type, and generated-asset content-type
   tests. Run Python and frontend checks.
7. Commit with `feat: serve the built application from FastAPI`.

**Acceptance:** One loopback FastAPI process serves the built UI and versioned
API. SPA convenience cannot mask API mistakes, missing assets, unsafe methods,
or traversal attempts. Environment-driven startup fails when the built UI is
missing or invalid and never migrates or seeds data.

### Verify API restart persistence

**Objective:** Prove migrated fixture records survive a restart of the
single-origin FastAPI process; the stateless frontend is not the persistence
owner.

**Files:**

- Modify: `web/tests/foundation.spec.ts`
- Modify: `web/tests/support/foundation.ts`

**Steps:**

1. In the disposable browser harness, migrate and seed the temporary database.
2. Start FastAPI with the built UI, fetch `/api/v1/health` and
   `/api/v1/sources`, stop it, and start a new process with the same
   `BENCHWARMER_DATA_ROOT` and built-UI root.
3. Assert the records and Alembic revision are unchanged and startup did not
   migrate, seed, or rewrite data.
4. After the replacement process reports ready, request the root application
   route in the browser and verify that it reconnects to the unchanged source
   records. Record that the browser may show a transient request failure while
   the process is down; automated recovery during the interruption is not a
   foundation gate.
5. Run `npm run test:e2e` and all frontend checks.
6. Commit with `test: verify API restart persistence`.

**Acceptance:** Data survives FastAPI restart from durable SQLite state. The
same-origin UI returns after readiness without owning or recreating records.

### Document development and final integration

**Objective:** Leave a human or agent with one concise synthetic demo command
plus exact setup, verification, and cleanup instructions.

**Files:**

- Create: `docs/development.md`
- Create: `scripts/run-foundation-demo.sh`

**Steps:**

1. Add a small fail-fast demo script that builds the frontend, prepares clearly
   identified disposable state, migrates and loads only sanitized fixtures, and
   starts the single FastAPI application on loopback. It must print the local
   URL and cleanup behavior, forward termination, and never inspect or reuse a
   private data root implicitly.
2. Document `uv sync --locked --dev`, the demo script,
   `BENCHWARMER_DATA_ROOT`, the built-UI root, migration, fixture loading, direct
   API startup, `npm --prefix web ci`, Playwright browser installation,
   development, test, build, restart behavior, and cleanup commands.
3. Record the pinned `sv` scaffold version chosen by
   [Scaffold SvelteKit with the selected adapter and checks](plan.md) and the
   adapter chosen by
   [the serving decision](../../../docs/decisions/0003-serving-supervision.md).
4. Document optional Svelte MCP use: verify `mcp_servers.svelte` in
   `config.yaml`, run `hermes mcp test svelte` where available, and use
   `svelte-autofixer` after component changes. If MCP is unavailable, fall back
   to `npm run check`, `npm run lint`, tests, and browser verification.
5. Run the Final integration gate below.
6. Stop all processes, confirm no runtime artifacts are tracked, and commit
   with `docs: add foundation development workflow`.

**Acceptance:** A fresh checkout can follow `docs/development.md` or the demo
script; browser, restart, and unit checks prove the one-process storage-to-UI
path; test state is disposable.

## Svelte MCP use

Agents with a configured Svelte MCP server should verify availability before
relying on it:

```bash
hermes mcp test svelte
```

Use `list-sections` and `get-documentation` for current Svelte/SvelteKit
guidance, and `svelte-autofixer` for changed `.svelte` files. The optional tool
is not a substitute for the required local checks. If it is unavailable, state
that in the handoff and use `npm run check`, `npm run lint`, tests, and browser
verification instead.

## Final integration gate

Before checking the foundation work complete and requesting reviewed closeout:

```bash
scripts/build-python-runtime.sh
uv sync --locked --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall src
npm --prefix web ci
npm --prefix web run check
npm --prefix web run lint
npm --prefix web run test:unit -- --run
npm --prefix web run test:e2e
npm --prefix web run build
git diff --check
git status --short
```

Verify manually that only expected source files are tracked. Confirm the
repository has no private data or generated build output. The acceptance gate
in [../roadmap.md](../../../docs/roadmap.md) must be satisfied before requesting a final
integration review.
