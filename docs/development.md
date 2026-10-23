# Development workflow

Benchwarmer has two development toolchains and one product-shaped runtime:
Python owns persistence and serves the built Svelte application and `/api/v1`
from one loopback origin. Vite remains an optional live-reload tool for frontend
work. It is not part of the production process topology.

## Safety boundary

Use synthetic fixtures and an explicit disposable data root for development.
Never point fixture-loading commands at a private Benchwarmer data root. API
startup does not run migrations or load fixtures.

Application databases, imported conversations, annotations, snapshots, logs,
and generated reports remain outside Git. The repository's
`tests/fixtures/` content is intentionally synthetic.

## Prepare a checkout

Build the pinned Python runtime and install locked dependencies:

```bash
scripts/build-python-runtime.sh
uv sync --locked --dev
npm --prefix web ci
npm --prefix web exec -- playwright install chromium
```

Keep the `UV_PYTHON` override printed by the runtime provisioner exported when
using a non-default `BENCHWARMER_RUNTIME_ROOT`. See the root
[README](../README.md) and [runtime recovery guide](runtime-recovery.md) before
handling an interrupted or invalid runtime build.

## Run the synthetic demo

The quick-start script builds the frontend, creates a private temporary data
root, migrates it, loads sanitized source fixtures, and starts the single
FastAPI application on loopback:

```bash
scripts/run-foundation-demo.sh
```

Open <http://127.0.0.1:8000/>. Stop the process with `Ctrl-C`; the script removes
its temporary database and related state. It intentionally refuses to run when
`BENCHWARMER_DATA_ROOT` is already set so it cannot reuse private data by
accident.

Choose another loopback port when needed:

```bash
BENCHWARMER_DEMO_PORT=8765 scripts/run-foundation-demo.sh
```

The generated `web/build/` directory is ignored by Git and may remain for later
runs. Each demo invocation replaces its contents with a fresh build.

## Run the product-shaped application manually

Choose a new, explicit development data root outside the checkout. The example
below creates one and prints its location so cleanup remains deliberate:

```bash
export BENCHWARMER_DATA_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/benchwarmer-development.XXXXXX")"
export BENCHWARMER_UI_ROOT="$(pwd)/web/build"
printf 'Development data root: %s\n' "$BENCHWARMER_DATA_ROOT"
# Optional: directories the web app may import conversation files from.
# export BENCHWARMER_IMPORT_ROOTS="$HOME/benchwarmer-inbox"
# Optional: let the app start approved harness runs (ADR 0006).
# export BENCHWARMER_HARNESS_DIR="$PWD/harness"

npm --prefix web run build
uv run alembic upgrade head
uv run python -m benchwarmer.services.fixtures \
  --load tests/fixtures/sources.json
uv run python -m benchwarmer.services.demo_conversations \
  --load tests/fixtures/demo-conversations.json
uv run python -m benchwarmer.services.demo_conversations \
  --load tests/fixtures/demo-long-conversations.json
uv run uvicorn benchwarmer.api.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8000
```

`demo-conversations.json` holds short synthetic conversations covering the
browsing states; `demo-long-conversations.json` holds four long synthetic
coding-agent sessions (a debugging session, a feature build with compaction and
a model change, a branched session with a failed tool call, and a prose review
that continues the debugging session) for exercising outlines and the
`propose-bundles` harness workflow. Both are invented content under the
`fixture-source-pi-failed` source and must stay under 1 MiB each.

This is the local form of the accepted one-process boundary. FastAPI serves the
built UI and versioned API from the same origin. Unknown API paths, mutations,
and missing static assets do not fall through to the SPA document.
Environment-driven startup requires an absolute UI root containing `200.html`
and fails before serving requests when the contract is invalid.

The production image will copy the generated build to
`/opt/benchwarmer/ui` and set
`BENCHWARMER_UI_ROOT=/opt/benchwarmer/ui`. The image and target-host checks
belong to [private deployment](../todo/work/private-deployment/README.md); the
application does not search its working directory or private data root for web
assets.

Stop Uvicorn before cleaning up. Inspect the printed path and remove only the
specific temporary development root that you created. Do not apply cleanup
commands to the default or private application data root.

## Use Vite for frontend iteration

For component work, run the API and Vite in separate terminals. Vite proxies
relative `/api` requests to the loopback API and provides live reload:

```bash
# Terminal 1, after explicitly selecting and preparing a disposable data root
npm --prefix web run build
export BENCHWARMER_UI_ROOT="$(pwd)/web/build"
uv run uvicorn benchwarmer.api.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8000
```

```bash
# Terminal 2
npm --prefix web run dev
```

`BENCHWARMER_API_ORIGIN` may select another absolute HTTP or HTTPS origin for
the Vite proxy. It must not contain credentials, a path, query parameters, or a
fragment. Rebuild the static application before validating the single-origin
FastAPI path.

## Restart behavior

SQLite records belong to the configured data root, not to the API or browser
process. Restarting FastAPI with the same `BENCHWARMER_DATA_ROOT` preserves the
Alembic revision and source records. Startup never migrates or seeds the store.

Because FastAPI serves both the API and static UI in the product-shaped runtime,
both are briefly unavailable while that process is stopped. An already open
page may show a request error during the interruption. After FastAPI reports
ready, refreshing the page reconnects to the same durable records.

## Run the analysis harness

The `harness/` package runs Benchwarmer's own model-driven workflows on Pi
Durable against a running API. Point it at a development data root, never a
private one, until a workflow has been reviewed on synthetic data:

```bash
cd harness
npm ci
npm run list-models -- anthropic
ANTHROPIC_API_KEY=... npm run propose-bundles -- \
  --api http://127.0.0.1:8000 --model anthropic/<model-id> \
  --conversation <conversation-id>
```

Running a workflow by hand is the approval for its model work. Durable state
goes to `.benchwarmer/harness/` and run reports to `reports/harness/`, both
gitignored. See [harness/README.md](../harness/README.md).

### Scrub a Pi session locally without a model

The scrub route parses session content in memory and stores nothing, so it can
be exercised against the demo data root with the synthetic session fixture:

```bash
uv run python - <<'EOF'
import json, urllib.request
content = open("tests/fixtures/pi-session-synthetic.jsonl", encoding="utf-8").read()
body = json.dumps({"content": content, "terms": ["Dana", "widget"]}).encode()
request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/fixtures/scrub-pi-session",
    data=body, headers={"content-type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    result = json.load(response)
print(result["report"]["counts"])
print(json.dumps(result["fixture"], indent=1)[:2000])
EOF
```

`POST /api/v1/fixtures/check` takes the same `content` and `terms` plus a
`candidate` fixture conversation and returns typed fidelity and leak issues.
Point these routes at a real session only on a loopback API you started
yourself; the response contains the scrubbed text.

## Run checks

Python checks:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall src
```

Harness checks:

```bash
npm --prefix harness run check
npm --prefix harness test
```

Frontend and browser checks:

```bash
npm --prefix web run check
npm --prefix web run lint
npm --prefix web run test:unit -- --run
npm --prefix web run test:e2e
npm --prefix web run build
```

The Playwright harness allocates temporary ports and a temporary data root,
migrates and seeds only synthetic fixtures, starts the product-shaped FastAPI
origin, and removes its state after the worker exits.

Before committing:

```bash
git diff --check
git status --short
```

Confirm that no database, private transcript, runtime log, Playwright output, or
built frontend artifact is tracked.

## Optional Svelte MCP review

The frontend was scaffolded with stable `sv@0.17.0` and uses
`@sveltejs/adapter-static` with `200.html` as its SPA fallback. If the Svelte MCP
server is configured, verify it and run its autofixer after component changes:

```bash
hermes mcp test svelte
```

Use `list-sections` and `get-documentation` for current framework guidance and
`svelte-autofixer` for changed components. If MCP is unavailable, use
`svelte-check`, ESLint, Prettier, unit tests, the production build, and browser
verification instead.
