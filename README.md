# Benchwarmer

Benchwarmer is a private conversation library and model evaluation app. It will
collect Codex, Pi, and Hermes histories across the user's machines, preserve
native transcripts alongside shared records, and make that work searchable and
reusable for evaluations. Usage and cost are part of the metadata, not the only
reason to collect it.

The project has Python quality tooling and a minimal SvelteKit scaffold. The
planned application uses a Python backend, SQLite database and mobile-friendly
frontend on an always-on Mac mini, with private access over Tailscale. The API
foundation and responsive shell are partly implemented. Real importers,
conversation browsing, enrichment, and experiment execution are not implemented yet.

## Scope

- Collect conversations across machines through a service owned by this project.
- Preserve native snapshots and normalize messages, tools, branches, and artifacts.
- Browse conversations with keyword, metadata, and later semantic search.
- Enrich summaries, descriptions, classifications, usage, and cost with provenance.
  Model-powered work requires explicit bounded approval; imports never launch it.
- Build live collections and frozen datasets, including private programmatic
  access for ad hoc evaluation projects.
- Add personal ratings and notes to real sessions.
- Derive meaningful task units and rerun them with visible applied judges inside
  the approved budget. Adaptive simulated follow-ups come later.
- Compare models, reasoning levels, harnesses, prompts, skills and tools as
  distinct dimensions. Direct Python API execution is a harness too.
- Track accessible system prompts and make missing or partial capture visible.
- Start with native harness configurations; add controlled comparisons later.
- Add detailed usage reporting and trusted external evaluations after the library
  is useful, preserving dates, sources, and configuration details.
- Preserve trial results and quality/cost tradeoffs without one combined score.

Imported session content is retained as private snapshots alongside metadata.
Central application data stays on the Mac mini and outside the public checkout
by default; source-side collection storage remains a design decision. Sending
content to remote models needs separate disclosure permission and bounded spend
approval. Private sessions, prompts, databases, artifacts and annotations must
not be committed.
Tool-capable simulations run only in disposable fixture workspaces.

## Design and tasks

- [Architecture](docs/architecture.md): product direction, application components,
  data boundaries and delivery stages.
- [Conversation library](docs/conversation-library.md): collection, normalization,
  enrichment approvals, search, datasets, and the first useful workflow.
- [Evidence bundles](docs/evidence-bundles.md): planned references, observations,
  behavior patterns, and conversion into leakage-aware task drafts.
- [Retained contract design](todo/work/conversation-contracts/README.md): shared
  conversation records and bounded approval validation using synthetic tests.
- [Experiments](docs/experiments.md): task derivation, harness dimensions and
  system-prompt provenance.
- [Design decisions](docs/decisions.md): accepted choices and remaining
  decisions.
- [Decision records](docs/decisions/README.md): independent ADR proposals and
  coordinator integration rules.
- [Source reports](docs/sources/README.md): per-source evidence and privacy
  requirements.
- [Source coverage](docs/source-coverage.md): cross-source identity, import,
  usage, economics, prompt, execution, and retention comparison.
- [Buildout roadmap](docs/roadmap.md): delivery slices, dependencies, acceptance
  gates and agent handoff protocol.
- [Task workbench](todo/README.md): workflow and stable work records.
- [Priorities](todo/TODO.md): the live P1–P5 queue, using readable task names.
- [History](todo/DONE.md): Git and retained evidence.

## Project setup

Benchwarmer pins a source-built Python 3.13.15 runtime with SQLite 3.53.4 linked
statically into the standard-library `sqlite3` extension. The build script
verifies both source archives with SHA-256 and installs the runtime under the
gitignored `.benchwarmer/` directory. It does not install host packages. Prepare
a supported build host explicitly before running it. On Linux, a cheap compile
preflight checks the required headers and OpenSSL major before downloads begin;
user-supplied `CPPFLAGS`, `CFLAGS`, `LDFLAGS`, and `PKG_CONFIG_PATH` are honored.

On Debian or Ubuntu:

```bash
sudo apt-get update
sudo apt-get install --yes \
  build-essential ca-certificates curl pkg-config tar xz-utils \
  libssl-dev libbz2-dev liblzma-dev libreadline-dev libncurses-dev \
  libffi-dev zlib1g-dev
```

On Fedora:

```bash
sudo dnf install \
  gcc make ca-certificates curl pkgconf-pkg-config tar xz \
  openssl-devel bzip2-devel xz-devel readline-devel ncurses-devel \
  libffi-devel zlib-devel
```

On macOS, install the Command Line Tools and keg-only build dependencies with
Homebrew. The script configures their include, library, pkg-config and runtime
search paths, including `openssl@3`; the system LibreSSL is neither a checksum
prerequisite nor used for Python TLS.

```bash
xcode-select --install
brew install pkgconf openssl@3 bzip2 xz readline ncurses libffi
```

The provisioner validates exact Python and SQLite versions, an OpenSSL 3.x TLS
runtime, and the required standard-library modules. Builds use an owned `mkdir`
lock and a unique same-filesystem staging directory. Source archives are both
SHA-256 verified before either is extracted.

Publication is immutable and create-only. The checked-in
`scripts/rename-noreplace.c` helper atomically moves a complete candidate to the
exact absent final path using Linux `renameat2(RENAME_NOREPLACE)` or macOS
`renamex_np(RENAME_EXCL)`. It never replaces an entry or nests into a raced
directory. Every final runtime has a regular `.benchwarmer-runtime-owner` file
containing `benchwarmer-python-runtime-v1\n`.

If the final path exists but is not an owned, fully valid runtime, the script
leaves it untouched and stops. It also stops before validation or building when
a matching lock or staging path exists. The script never repairs, replaces,
marks, quarantines, or removes a final runtime. Follow the exact validation and
no-replace archival steps in
[`docs/runtime-recovery.md`](docs/runtime-recovery.md) to clear stale
artifacts or archive an owned invalid final.

`BENCHWARMER_RUNTIME_ROOT` and `TMPDIR` must not contain whitespace or shell glob
characters (`*`, `?`, `[`, `]`). Build flags intentionally follow shell
word-splitting semantics. `CPPFLAGS`, `CFLAGS`, and `LDFLAGS` may contain
conventional space-separated flag words, but individual flag values containing
whitespace are unsupported.

`.python-version` points to the default runtime inside the checkout. When
`BENCHWARMER_RUNTIME_ROOT` selects a different root, set `UV_PYTHON` for every
`uv` command that should use that runtime. The provisioner prints a shell-safe
`export` command with the canonical interpreter path after a successful build or
valid-runtime check. The equivalent explicit setup is:

```bash
RUNTIME_ROOT_INPUT=$BENCHWARMER_RUNTIME_ROOT
scripts/build-python-runtime.sh
ROOT=$(CDPATH= cd -- "$RUNTIME_ROOT_INPUT" && pwd)
export UV_PYTHON="$ROOT/python-3.13.15-sqlite-3.53.4/bin/python3.13"
uv sync --locked --dev
```

Keep `UV_PYTHON` exported for all later `uv run`, `uv add`, `uv sync`, and other
`uv` commands that use the custom root. Alternatively, prefix each command with
the same `UV_PYTHON="$ROOT/python-3.13.15-sqlite-3.53.4/bin/python3.13"`
assignment.

A fresh successful publication removes an existing project virtual environment.
The valid-runtime fast path leaves `.venv` unchanged. Production image,
deployment, serving, and target-host verification remain deferred to [private deployment verification](todo/work/private-deployment/README.md).
For the default runtime root, the relative interpreter path in `.python-version`
makes `uv` stop if the runtime has not been provisioned instead of downloading a
Python build with an unknown SQLite version. Run project `uv` commands from the
repository root. Use the same bootstrap in development and CI:

```bash
scripts/build-python-runtime.sh
uv sync --locked --dev
uv run python -c \
  'from benchwarmer.sqlite_runtime import require_wal_safe_sqlite; require_wal_safe_sqlite()'
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall src
```

The frontend uses npm and the committed lockfile:

```bash
cd web
npm ci
npm run check
npm run lint
npm run test:unit -- --run
npm run build
```

The static build writes `web/build/200.html`. There are no backend runtime
dependencies or application start commands yet.
