# Start and package the application with one command

Status: In progress. The settings file and the `benchwarmer serve` and
`benchwarmer init` commands exist on `task/toml-config`; the start script's
rebuild steps, key references, and the image remain.

## Purpose

Starting Benchwarmer used to mean knowing two toolchains and four environment
variables: build the Svelte app with npm, install the harness with npm, export
`BENCHWARMER_DATA_ROOT`, `BENCHWARMER_UI_ROOT`, `BENCHWARMER_HARNESS_DIR`, and
`BENCHWARMER_IMPORT_ROOTS`, export provider keys, then start Uvicorn. On
2026-10-26 the operator restarted the API from a fresh shell and it refused to
start for want of `BENCHWARMER_UI_ROOT`; the server that had been running
belonged to an agent session's scratchpad environment and its data root sat
under `/private/tmp`. The UI, the API, and the harness are one product and
should start as one.

This is a packaging problem. The work keeps the architecture of
[ADR 0003](../../../docs/decisions/0003-serving-supervision.md) and
[ADR 0006](../../../docs/decisions/0006-app-started-model-work.md) and removes
the ceremony around it.

## What exists now

- **Settings file.** `benchwarmer.toml` at the data root, or at
  `BENCHWARMER_CONFIG`, with `[paths]` (`data_root`, `import_roots`,
  `harness_dir`, `ui_root`), `[server]` (`host`, `port`), and `[providers]`
  (`allow`, `deny`). Every existing environment variable keeps working and
  overrides the file; `BENCHWARMER_HOST`, `BENCHWARMER_PORT`,
  `BENCHWARMER_PROVIDER_ALLOW`, and `BENCHWARMER_PROVIDER_DENY` are new.
  Parsing uses the standard library `tomllib`; unknown keys, relative paths,
  and bad types are refused with the file and key named. Reading settings
  creates nothing on disk. Reference: [configuration](../../../docs/configuration.md).
- **Provider lists are operator settings.** The harness registers the pi-ai
  catalog within `BENCHWARMER_PROVIDER_ALLOW` and `BENCHWARMER_PROVIDER_DENY`,
  which the application sets (always both) in the environment of every
  harness process it starts, so the settings file is the one source. The
  repository ships no list values.
- **`benchwarmer serve`.** Console script in `pyproject.toml`
  (`benchwarmer.cli:main`). Loads settings, uses the checkout's `web/build`
  when no `ui_root` is configured, refuses an absent, unmigrated, or outdated
  data root with the exact fix (`uv run alembic upgrade head`), prints the
  resolved settings (file, data root, UI root, harness, import roots,
  provider lists, listen address), and runs Uvicorn in the foreground.
  `--host`, `--port`, and `--check` are accepted. It never migrates and never
  starts model work.
- **`benchwarmer init`.** Writes a commented example `benchwarmer.toml`
  (owner-only) to the data root, creating the data root with the private
  layout when needed, or to `BENCHWARMER_CONFIG` when its directory exists.
  Never overwrites.
- The UI root moved into settings: `create_app()` in environment mode reads
  `settings.ui_root` instead of the variable directly, with the same errors.

## Decisions still open

1. **How keys reach the process.** Proposed: the file names a 1Password
   reference per provider (`anthropic = "op://<vault>/<item>/credential"`)
   and the start path resolves each with `op read` into the child environment
   only. Inside the container, where `op` is absent, Compose injects the same
   variables from its secrets store. The key never lands in a file the
   application reads, a log, or a plan. Not started; the settings file holds
   no key material and no key references yet.
2. **Node in the production image: decided.** ADR 0003 says production has
   "no Node server" and "avoids a Node runtime"; ADR 0006 then made the
   application start the harness as a subprocess. On 2026-10-26 the operator
   decided the image carries a pinned Node solely to run harness subprocesses,
   with no Node listener and no second long-running process. Slice 3 records
   this as an amending ADR before the Dockerfile lands.
3. **Whether `run-foundation-demo.sh` survives.** Proposed: it becomes a thin
   wrapper over `benchwarmer serve` with a disposable data root, so there is
   one start path to maintain. Not changed yet.

## Acceptance criteria

- [x] A fresh clone with the runtimes installed, a built UI, and a migrated
  data root starts with one command and one settings file, and the command
  prints where the data root is before serving. (Which providers have keys
  is still reported only by `npm run list-models` in the harness.)
- [ ] The same command on a stale checkout rebuilds the UI and installs
  harness dependencies when their lockfiles changed, and does neither when
  nothing changed.
- [x] A missing or unmigrated data root is refused with the exact command
  that fixes it; the start command never migrates on its own.
- [ ] The Bundles page shows the provider and model selects for every
  provider the settings file permits, with no variable exported by hand.
  (The lists reach the harness; a browser check against a real harness is
  not yet recorded.)
- [ ] The production image runs an approved plan end to end on the target
  host, and the deployment verification in
  [private deployment](../private-deployment/README.md) passes against that
  image unchanged.
- [x] The README, AGENTS.md, and `docs/development.md` describe the one
  command and the settings file; `docs/configuration.md` is the reference.

## Work

- [ ] Start and package the application with one command
  - [x] **Slice 2, settings file.** `BenchwarmerSettings.from_environment`
    layers the file under the environment for every path, the server address,
    and the provider lists. Key references are deliberately not in Python.
    - Verified by `tests/test_config_file.py`: file only, environment over
      file, `BENCHWARMER_CONFIG` (present, missing, relative), relative paths
      and bad types in the file with the file and key named, and no
      filesystem side effects.
  - [x] **`benchwarmer serve` and `benchwarmer init`** (`src/benchwarmer/cli.py`).
    - Verified by `tests/test_cli.py`: init writes and refuses to overwrite,
      serve refuses without a built UI or a migrated data root, `--check`
      prints the resolved settings, host and port overrides reach Uvicorn,
      and the console script is installed.
  - [ ] **Slice 1, remaining start-script behavior.** Rebuild `web/build`
    when `web/src` or the web lockfile is newer, run `npm --prefix harness ci`
    when the harness lockfile is newer than its `node_modules`, resolve key
    references, and rewrite `run-foundation-demo.sh` over `benchwarmer serve`.
    Decide whether these belong in `benchwarmer serve` itself or in a thin
    `scripts/serve.sh` around it.
  - [ ] **Slice 3, image.** A Dockerfile that builds the UI to
    `/opt/benchwarmer/ui`, installs the pinned Python runtime and locked
    dependencies, installs a pinned Node and the harness `node_modules` to
    `/opt/benchwarmer/harness`, and ships a `benchwarmer.toml` with those
    paths; the Compose service in ADR 0003 gains the data-root mount and
    secret-backed key variables and runs `benchwarmer serve`. Write ADR 0007
    (Proposed) for the Node amendment before the Dockerfile lands.
    - Verify: `docker compose build` in CI or on the target host, the
      ADR 0003 render and port assertions, and one approved `propose-bundles`
      plan run inside the container against a disposable data root.
  - [ ] **Closeout.** Reconcile ADR 0003's consequences (the Compose command
    and `BENCHWARMER_UI_ROOT` example), shorten `docs/development.md`, and
    hand the image to [private deployment](../private-deployment/README.md).

## Rejected alternatives

- **SvelteKit `adapter-node` serving the API too.** Rejected in ADR 0003 and
  unchanged by this record; it would move the problem rather than remove it.
- **Autodetect settings from the current directory or data root.** ADR 0003
  deliberately forbids asset discovery from the working directory. The
  `web/build` fallback is derived from the location of the installed package
  (the checkout it lives in), never from the working directory, and applies
  only in `benchwarmer serve`; the Uvicorn factory still requires an explicit
  UI root.
- **Reading the settings file in the harness.** The harness stays a client of
  the API and its environment; the application hands it the provider lists,
  so there is one reader of the file.

## Verification

2026-10-27, `task/toml-config`, from the worktree:

- `uv run pytest`: see the pull request for the count on the branch (282
  passed on `main` before the change).
- `uv run ruff check .` and `uv run ruff format --check .`: clean.
- `npm --prefix harness ci && npm --prefix harness run check && npm --prefix harness test`:
  type check clean, vitest green.
- Not run: browser tests (`npm --prefix web run test:e2e`), which still start
  the bare factory with `BENCHWARMER_UI_ROOT` and were not changed.

## Supporting material

- [Current priorities](../../TODO.md)
- [Configuration reference](../../../docs/configuration.md)
- [Development workflow](../../../docs/development.md)
- [ADR 0003: private serving and process supervision](../../../docs/decisions/0003-serving-supervision.md)
- [ADR 0006: app-started model work](../../../docs/decisions/0006-app-started-model-work.md)
- [Private deployment](../private-deployment/README.md)
