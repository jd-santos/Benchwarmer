# ADR 0001: Application foundation

- Status: Proposed
- Task: FND-001
- Date: 2026-09-08

## Context and evidence

Benchwarmer is a local, single-user application with a Python 3.12+ service,
SQLite, a Svelte frontend, and a future background worker. The Python service
is authoritative for persistence and domain rules. Browser requests use a
same-origin `/api` boundary, and private state must persist independently of
the frontend process.

The repository already uses a Python `src/` layout, `pyproject.toml`, `uv`, and
`uv.lock`. The foundation plan needs one concrete backend, migration stack,
frontend scaffold, API namespace, and package layout before implementation can
begin. It must not pre-empt the data/recovery or deployment decisions.

The following evidence was reviewed on 2026-09-08:

- [FastAPI's documented features][fastapi-features] include type-hint-driven
  validation, JSON Schema, OpenAPI, and dependency injection. Those facilities
  fit a typed JSON boundary without adding a separate schema or documentation
  framework.
- The [SQLAlchemy 2 ORM quick start][sqlalchemy-orm] documents typed declarative
  mappings and explicit `Session` use. [Alembic][alembic] is the migration tool
  maintained for SQLAlchemy and documents SQLite batch migrations.
- The [SvelteKit introduction][sveltekit] distinguishes the application
  framework from Svelte's component layer and supplies routing, loading, build,
  and rendering conventions. The [Svelte CLI documentation][svelte-create]
  documents the minimal SvelteKit template, TypeScript syntax, add-ons, and an
  explicit npm install option.
- npm documents `package-lock.json` as the exact generated dependency tree and
  `npm ci` as a frozen clean install. The frontend can therefore remain a
  standalone npm package without a repository-level JavaScript workspace.
- `npm view sv version dist-tags --json` reported stable `sv` `0.17.0`; the
  `next` tag was `1.0.0-next.7`. This proposal selects the stable tag rather
  than a prerelease.
- `npx -y sv@0.17.0 create --help` confirmed the options used below. A
  disposable scaffold with the minimal template, TypeScript, npm tooling, and
  a static adapter completed successfully. That command validated CLI syntax;
  it did not select the production adapter.
- `/opt/hermes/.venv/bin/hermes -p dev mcp test svelte` connected to the
  configured Svelte MCP and discovered `get-documentation`, `list-sections`,
  `playground-link`, and `svelte-autofixer`. MCP remains optional assistance,
  not a substitute for local checks.

No deployment command was validated on the target Mac mini. Source
capabilities, private path defaults, production routing, and process recovery
are outside this record.

## Decision

### Python API

Use FastAPI for the JSON API, loaded by Uvicorn from an application factory at
`benchwarmer.api.app:create_app`. Keep route functions thin: they validate API
input and output, establish request-scoped dependencies, and call application
services. Pydantic request and response types are API contracts rather than
SQLAlchemy persistence models.

Use normal synchronous route/service functions and synchronous database access
initially. The local workload and SQLite do not justify an async driver, async
ORM sessions, or `pytest-asyncio`. Revisit async I/O only when an implemented
external integration or measured concurrency need consumes it.

Uvicorn is the API process runner, but this record does not choose its
production host, port, proxy headers, process count, launcher, or supervisor.
Those serving details belong to `DEP-002`.

### Persistence and migrations

Use SQLAlchemy 2.x typed declarative mappings with a short-lived synchronous
`Session` per request or application-service unit of work. Use Alembic for all
persistent schema changes, including the initial schema. Application startup
must not call `MetaData.create_all()` or silently migrate a database.

Alembic revisions are committed, ordered application artifacts. Autogeneration
may prepare a candidate revision, but an implementer must review the generated
upgrade and downgrade operations. SQLite-specific batch operations are added
only when a migration needs them.

Declare supported major-version ranges in `pyproject.toml`; let `uv.lock` pin
the resolved Python dependency graph when each package first has a consumer.
Do not add SQLAlchemy or Alembic in this documentation task.

### Frontend and npm tooling

Use a SvelteKit application under `web/`, generated from the minimal template
with TypeScript syntax. Use npm as the only frontend package manager. Commit
`web/package-lock.json`, use `npm install` only when intentionally changing the
frontend graph, and use `npm ci` for clean verification.

Select these frontend tools:

- `svelte-check` and TypeScript for framework and type checks;
- Prettier and ESLint for formatting and linting;
- Vitest for unit and component tests; and
- Playwright for browser tests when the first browser test lands.

Do not add a CSS framework, component library, frontend ORM, authentication
package, Storybook, experimental remote functions, or an OpenAPI client
generator until a concrete feature consumes it. Initial API types remain the
small, explicit TypeScript types required by the implemented endpoints.

Pin the one-time scaffold generator exactly to `sv@0.17.0`; never resolve
`sv@latest` during `UI-001`. After `DEP-002` accepts either `static` or `node`,
the scaffold command is:

```bash
: "${DEP_002_ADAPTER:?set it to DEP-002's accepted adapter}"
case "$DEP_002_ADAPTER" in static|node) ;; *) exit 2 ;; esac
npx -y sv@0.17.0 create web \
  --template minimal \
  --types ts \
  --add prettier eslint 'vitest=usages:unit' \
  "sveltekit-adapter=adapter:${DEP_002_ADAPTER}" \
  --install npm
```

`DEP_002_ADAPTER` above is a temporary scaffold-command variable, not a runtime
configuration interface. `UI-001` must substitute the literal accepted by
`DEP-002`, review every generated file, and remove demo content. Playwright is
added with the same pinned CLI only in `QA-001`, alongside its first retained
browser test and process harness. This keeps the selected testing direction
without adding an unused dependency in `UI-001`.

The Svelte MCP may be used for current documentation and autofixer review, but
the required checks remain `npm run check`, `npm run lint`, focused tests, and
`npm run build`.

### API boundary

All application JSON endpoints use `/api/v1/*`; there is no unversioned alias.
The browser and any SvelteKit server-side presentation code call relative,
same-origin `/api/v1/*` paths. In development, Vite may proxy `/api` to the
Python process. Production routing is deferred to `DEP-002`.

`v1` versions the HTTP contract. It is unrelated to the package version,
Alembic revision, source schema version, or serialized task/result schema.
Backward-compatible additions can remain in `v1`; an incompatible HTTP change
requires an explicit compatibility decision rather than silently changing an
existing response.

The frontend never opens the application SQLite database or imports Python
persistence rules. Even if the selected SvelteKit adapter runs a Node process,
that process remains a presentation client of the Python API. This preserves
one owner for validation, transactions, migrations, imports, reconciliation,
and jobs, and lets the frontend restart without owning durable state.

### Package and process layout

Use these repository boundaries, creating a directory only with its first
real module:

```text
src/benchwarmer/
├── api/          # FastAPI factory, dependencies, routes, and API schemas
├── adapters/     # source, provider, pricing, and harness integrations
├── models/       # SQLAlchemy mappings for durable records
├── services/     # framework-neutral application operations and queries
├── worker/       # future `python -m benchwarmer.worker` entry point
├── config.py     # resolved application settings
└── db.py         # engine, session, and revision plumbing
migrations/       # Alembic environment and committed revisions
tests/            # Python tests grouped by the boundary under test
web/              # independent SvelteKit npm package and frontend tests
```

Models and services must not import source-, provider-, or harness-specific
adapters. Both the API and future worker call the same application services;
they do not call each other in-process.

Run the API as its own OS process. Durable imports, reconciliation, and trial
execution belong in a separate future worker process with the module entry
point `uv run python -m benchwarmer.worker`. The API records or requests work;
the worker performs it and persists progress. Do not use FastAPI background
tasks for durable work that must survive an API restart.

Do not create the `worker/` package, an idle polling loop, a broker, or a queue
framework now. Add the worker entry point and any scheduling dependency with
the first implemented background job. Job claiming, SQLite write
coordination, cancellation, and recovery semantics remain later implementation
decisions; paid-trial recovery must still satisfy the project's
`outcome_unknown` rule.

### Dependency timing

This ADR adds no dependency. Each implementation task adds only what it uses:

- Python quality tasks add pytest and Ruff with their first test/check.
- Configuration adds Pydantic when the settings object lands.
- Database plumbing adds SQLAlchemy and Alembic with the first engine and
  migration environment.
- The API slice adds FastAPI, plain Uvicorn, and HTTP test support with the
  first application factory and API test.
- The frontend scaffold adds only the checks and unit tooling exercised in
  `UI-001`; Playwright waits for `QA-001`.

Do not add `pytest-asyncio`, an async SQLite driver, a worker framework, CORS
middleware, or frontend data libraries speculatively. The coordinator should
align the implementation plan with this timing if it accepts the proposal.

### Explicit deferrals

`DEP-001`, not this ADR, decides the data-root default and override, database
and artifact paths, retention boundary, and coordinated backup, restore, and
verification behavior.

`DEP-002`, not this ADR, decides `adapter-static` versus `adapter-node`,
development and production bindings, Tailscale routing and access controls,
trusted-proxy assumptions, process supervision, restart policy, and target-host
commands. This ADR's separation of API, presentation, and future worker
processes does not prescribe how those processes are served or supervised.

## Alternatives considered

### Flask or Starlette directly

Both can expose a small API with fewer framework conventions. They were not
selected because Benchwarmer needs typed request/response validation and an
inspectable contract; recreating FastAPI's Pydantic and OpenAPI integration
would add project-specific plumbing without reducing the important runtime
boundaries.

### Django and its ORM/migrations

Django provides an integrated application stack, but its templates, admin,
authentication, and full web framework are not initial requirements. Using it
behind a separate SvelteKit client would adopt more convention and dependency
surface than the local API needs.

### SQLModel, raw `sqlite3`, or SQLAlchemy Core only

SQLModel reduces some schema repetition but couples API-shaped types more
closely to persistence. Raw SQLite or Core would avoid an ORM but would require
more manual mapping across the project's numerous related, provenance-heavy
records. Direct SQLAlchemy 2 keeps persistence explicit and leaves Pydantic API
contracts independent.

### Async SQLAlchemy and `aiosqlite`

An async stack could help with sufficiently concurrent I/O, but it introduces
another driver, async session lifecycle, and async test tooling before evidence
of that need. A separate worker is the important concurrency boundary for this
local application.

### Plain Svelte with Vite, or a Node persistence backend

Plain Svelte would require choosing routing and application conventions
piecemeal. SvelteKit supplies those conventions and retains deployment-adapter
choice. Giving SvelteKit or Node direct database access was rejected because it
would create a second persistence and migration authority.

### pnpm, Bun, or a repository-level JavaScript workspace

They can manage the frontend successfully, but one `web/` application does not
need workspace orchestration or another package manager. npm is directly
supported by `sv`, and its committed lockfile plus `npm ci` provide the needed
reproducibility.

### In-process durable jobs or an immediate queue framework

In-process jobs can disappear with API restart and are unsuitable for imports
or paid trials. Celery, RQ, Redis, and similar infrastructure are premature
before the first job exists. A separate future process establishes the safety
boundary without selecting unused machinery.

## Consequences

- Python owns one typed, versioned domain/API/persistence path; the frontend
  remains replaceable and stateless with respect to durable records.
- Developers operate separate Python and frontend toolchains. Their lockfiles
  and checks remain independent and explicit.
- API schemas and TypeScript client types have some intentional duplication.
  Generate a client only if manual drift becomes a demonstrated maintenance
  problem.
- Synchronous SQLite access is simpler but does not remove SQLite's
  single-writer constraints. Worker claiming and write coordination need tests
  when background jobs arrive.
- Alembic migrations are an operational prerequisite; health must report actual
  migration state rather than creating or claiming schema implicitly.
- `/api/v1` makes future incompatible contracts visible, but a future `v2`
  would carry an explicit compatibility and migration cost.
- `UI-001` remains blocked on the adapter accepted through `DEP-002`. This is an
  intentional dependency, not a default hidden in the scaffold.
- Deferring unused dependencies reduces the initial attack and maintenance
  surface but requires each later task to add and lock its first real consumer.

## Unresolved questions

- `DEP-001` must supply the private data-root and recovery contract before
  configuration and migration work is accepted.
- `DEP-002` must choose the frontend adapter and all serving and supervision
  details before the scaffold or deployment commands are finalized.
- The first source decision determines which adapter package is created first;
  this ADR does not claim source capabilities.
- The first background job must define claim/lease, transaction, cancellation,
  concurrency, and restart behavior before the worker process is implemented.
- A target-host check must confirm the accepted Node/npm runtime and all
  `DEP-002` commands; the observed scaffold validation ran only in the research
  environment.

## Verification

Proposal evidence and syntax were checked with:

```bash
/opt/hermes/.venv/bin/hermes -p dev mcp test svelte
npm view sv version dist-tags --json
npx -y sv@0.17.0 create --help
```

The pinned CLI also completed the proposed command shape in a disposable
`/tmp` directory with `--no-install` and an example static adapter. That check
must not be treated as acceptance of `adapter-static`.

Validate this record with:

```bash
npx -y markdownlint-cli2@0.23.2 \
  docs/decisions/0001-application-foundation.md
git diff --check
git status --short
```

After coordinated acceptance, implementation verifies the selected boundaries
through migration round trips, FastAPI contract tests, relative `/api/v1`
frontend requests, npm's committed lockfile, browser tests, and API restart
persistence. Target-host serving and supervisor checks remain owned by
`DEP-002`.

[alembic]: https://alembic.sqlalchemy.org/en/latest/
[fastapi-features]: https://fastapi.tiangolo.com/features/
[sqlalchemy-orm]: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
[svelte-create]: https://svelte.dev/docs/cli/sv-create
[sveltekit]: https://svelte.dev/docs/kit/introduction
