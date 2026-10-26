# Start and package the application with one command

Status: Proposed. Nothing here is implemented; the record exists to decide the shape before a start script, a settings file, or an image is written.

## Purpose

Starting Benchwarmer today means knowing two toolchains and four environment
variables: build the Svelte app with npm, install the harness with npm, export
`BENCHWARMER_DATA_ROOT`, `BENCHWARMER_UI_ROOT`, `BENCHWARMER_HARNESS_DIR`, and
`BENCHWARMER_IMPORT_ROOTS`, export provider keys, then start Uvicorn. On
2026-10-26 the operator restarted the API from a fresh shell and it refused to
start for want of `BENCHWARMER_UI_ROOT`; the server that had been running
belonged to an agent session's scratchpad environment and its data root sat
under `/private/tmp`. The UI, the API, and the harness are one product and
should start as one.

This is a packaging problem. The work below keeps the architecture of
[ADR 0003](../../../docs/decisions/0003-serving-supervision.md) and
[ADR 0006](../../../docs/decisions/0006-app-started-model-work.md) and removes
the ceremony around it.

## Dependencies and order

Follows [the application foundation](../application-foundation/README.md) and
[app-started model work](../bounded-model-work/README.md), both delivered.
Slices 1 and 2 are local-only and can land now. Slice 3 is the image that
[private deployment](../private-deployment/README.md) builds; that record's
verification stays where it is and consumes this image rather than defining
its own build.

## Decisions needed before implementation

These change what gets built, so they are the operator's call.

1. **Where settings live.** Proposed: one TOML file outside the checkout,
   default `~/.config/benchwarmer/config.toml`, overridable with
   `BENCHWARMER_CONFIG`. Environment variables keep working and win over the
   file, so the container and the tests change nothing. The file holds
   `data_root`, `import_roots`, and provider key *references*, never key
   values.
2. **How keys reach the process.** Proposed: the file names a 1Password
   reference per provider (`anthropic = "op://<vault>/<item>/credential"`)
   and the start script resolves each with `op read` into the child
   environment only. Inside the container, where `op` is absent, Compose
   injects the same variables from its secrets store. The key never lands in
   a file the application reads, a log, or a plan.
3. **Node in the production image: decided.** ADR 0003 says production has
   "no Node server" and "avoids a Node runtime"; ADR 0006 then made the
   application start the harness as a subprocess. On 2026-10-26 the operator
   decided the image carries a pinned Node solely to run harness subprocesses,
   with no Node listener and no second long-running process. Slice 3 records
   this as an amending ADR before the Dockerfile lands.
4. **Whether `run-foundation-demo.sh` survives.** Proposed: it becomes a thin
   wrapper over the start script with a disposable data root, so there is one
   start path to maintain.

## Acceptance criteria

- A fresh clone with the runtimes installed starts with one command and one
  settings file, and the command prints where the data root is and which
  providers have keys (names only) before serving.
- The same command on a stale checkout rebuilds the UI and installs harness
  dependencies when their lockfiles changed, and does neither when nothing
  changed.
- A missing or unmigrated data root is refused with the exact command that
  fixes it; the start command never migrates on its own.
- The Bundles page shows the provider and model selects for every provider
  the settings file names, with no variable exported by hand.
- The production image runs an approved plan end to end on the target host,
  and the deployment verification in [private deployment](../private-deployment/README.md)
  passes against that image unchanged.
- `docs/development.md` describes the one command and the settings file; the
  manual export block becomes an appendix for tests and unusual layouts.

## Work

- [ ] Start and package the application with one command
  - [ ] **Slice 1, start script.** `scripts/serve.sh [--check] [--port N]`
    derives `BENCHWARMER_UI_ROOT` and `BENCHWARMER_HARNESS_DIR` from the
    checkout, reads the settings file for the rest, resolves key references,
    rebuilds `web/build` when `web/src` or the web lockfile is newer, runs
    `npm --prefix harness ci` when the harness lockfile is newer than its
    `node_modules`, compares the data root's Alembic revision with the
    packaged head and refuses with the fix when they differ, then `exec`s
    Uvicorn in the foreground. `--check` stops after printing the resolved
    settings and findings without starting anything.
    - Verify: a shell test (bats or a small Python test driving the script)
      covering fresh start, stale build, missing data root, unmigrated data
      root, and `--check`; `run-foundation-demo.sh` rewritten over it keeps
      its existing behavior.
  - [ ] **Slice 2, settings file.** `BenchwarmerSettings.from_environment`
    gains the file as a lower-precedence source for `data_root`,
    `import_roots`, and `harness_dir`; key references are the script's
    concern, not Python's, so the application never learns to read `op`.
    `docs/development.md` and the README describe the file; the demo script
    and tests keep passing explicit settings.
    - Verify: `tests/test_config.py` cases for file only, environment
      overriding file, a relative path in the file, and a file that names a
      key value instead of a reference (rejected with a message).
  - [ ] **Slice 3, image.** A Dockerfile that builds the UI to
    `/opt/benchwarmer/ui`, installs the pinned Python runtime and locked
    dependencies, installs a pinned Node and the harness `node_modules` to
    `/opt/benchwarmer/harness`, and sets both `BENCHWARMER_*` roots; the
    Compose service in ADR 0003 gains the data-root mount and secret-backed
    key variables. Write ADR 0007 (Proposed) for the Node amendment before
    the Dockerfile lands.
    - Verify: `docker compose build` in CI or on the target host, the
      ADR 0003 render and port assertions, and one approved `propose-bundles`
      plan run inside the container against a disposable data root.
  - [ ] **Closeout.** Reconcile ADR 0003's consequences, shorten
    `docs/development.md`, and hand the image to
    [private deployment](../private-deployment/README.md).

## Rejected alternatives

- **SvelteKit `adapter-node` serving the API too.** Rejected in ADR 0003 and
  unchanged by this record; it would move the problem rather than remove it.
- **Autodetect settings from the current directory or data root.** ADR 0003
  deliberately forbids asset discovery from the working directory; the script
  derives paths from the checkout it lives in, which is explicit.

## Verification

Record actual commands and results here at each handoff, following
[repository validation](../../../AGENTS.md). Nothing has run yet.

## Supporting material

- [Current priorities](../../TODO.md)
- [Development workflow](../../../docs/development.md)
- [ADR 0003: private serving and process supervision](../../../docs/decisions/0003-serving-supervision.md)
- [ADR 0006: app-started model work](../../../docs/decisions/0006-app-started-model-work.md)
- [Private deployment](../private-deployment/README.md)
