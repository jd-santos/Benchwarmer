# Configuration

Benchwarmer reads its settings from three layers. An environment variable
wins, then the `benchwarmer.toml` settings file, then the built-in default.
Reading settings never creates anything on disk; `benchwarmer init` and
`alembic upgrade head` are the only commands that write to the data root
before the application serves.

## The settings file

The file is `benchwarmer.toml` in the data root, or whatever path
`BENCHWARMER_CONFIG` names. When `BENCHWARMER_CONFIG` is set the file must
exist; without it an absent file means defaults. The data root used to find
the file is `BENCHWARMER_DATA_ROOT` or the platform default below, so a
`[paths] data_root` inside the file moves the data but not where the file is
read from.

Write a commented starting point with every default:

```bash
uv run benchwarmer init
```

Three sections are recognized and every key is optional. An unknown section
or key is refused by name, as is a relative path, so a typo cannot fall back
to a default silently. Paths must be absolute; a leading `~/` means the
current user's home and nothing else is expanded.

```toml
[paths]
data_root = "/absolute/path/to/benchwarmer-data"
import_roots = ["/absolute/path/to/inbox"]
harness_dir = "/absolute/path/to/Benchwarmer/harness"
ui_root = "/absolute/path/to/Benchwarmer/web/build"

[server]
host = "127.0.0.1"
port = 8000

[providers]
allow = []
deny = []
```

## Every setting

| File key | Environment variable | Default | What it controls |
| --- | --- | --- | --- |
| (file location) | `BENCHWARMER_CONFIG` | `<data root>/benchwarmer.toml` | Which settings file is read. Must exist when set. |
| `[paths] data_root` | `BENCHWARMER_DATA_ROOT` | macOS: `~/Library/Application Support/Benchwarmer`; otherwise `$XDG_DATA_HOME/benchwarmer` or `~/.local/share/benchwarmer` | The private directory holding the database, snapshots, artifacts, jobs, logs, and locks. Created owner-only (`0700`); symlinks are refused ([ADR 0002](decisions/0002-data-recovery.md)). |
| `[paths] import_roots` | `BENCHWARMER_IMPORT_ROOTS` (entries separated by the OS path separator, `:` on macOS and Linux) | none | Directories on this host the web app may import conversation files from. Empty means no host-local import; collectors push everything else. |
| `[paths] harness_dir` | `BENCHWARMER_HARNESS_DIR` (an empty value clears the file's value) | unset | The checkout's `harness/` package. Set, the application lists models through it and can start a plan the operator approved by its digest in the Bundles page; unset, plans can be previewed but not started here ([ADR 0006](decisions/0006-app-started-model-work.md)). |
| `[paths] ui_root` | `BENCHWARMER_UI_ROOT` | unset; `benchwarmer serve` falls back to `web/build` in the checkout when it holds `200.html` | The built Svelte application the API serves from the same origin. The Uvicorn factory (`benchwarmer.api.app:create_app`) requires it; `benchwarmer serve` requires it only outside a built checkout ([ADR 0003](decisions/0003-serving-supervision.md)). |
| `[server] host` | `BENCHWARMER_HOST` | `127.0.0.1` | The listen address for `benchwarmer serve`. Keep loopback; private access goes through Tailscale Serve. |
| `[server] port` | `BENCHWARMER_PORT` | `8000` | The listen port for `benchwarmer serve`, 1 through 65535. |
| `[providers] allow` | `BENCHWARMER_PROVIDER_ALLOW` (comma-separated) | empty | Provider ids the harness may register. Empty means every provider the pinned pi-ai catalog knows. |
| `[providers] deny` | `BENCHWARMER_PROVIDER_DENY` (comma-separated) | empty | Provider ids removed from whatever the allow list leaves. |

`benchwarmer serve --host` and `--port` override both layers for one run.

## How the provider lists reach the harness

The harness never reads the settings file. The application sets
`BENCHWARMER_PROVIDER_ALLOW` and `BENCHWARMER_PROVIDER_DENY` in the
environment of every harness process it starts (the model listing behind the
Bundles page and each approved plan), always both, so the harness sees exactly
the configured lists and nothing inherited from the shell. An operator who
runs the harness by hand sets the same two variables, or leaves them unset to
register every provider. Provider keys (`ANTHROPIC_API_KEY`,
`OPENROUTER_API_KEY`, and so on) are not settings; they stay in the process
environment and are never written to the file. See
[harness/README.md](../harness/README.md).

## Commands

| Command | What it does |
| --- | --- |
| `uv run benchwarmer init` | Writes a commented example `benchwarmer.toml` to the data root (creating it owner-only if needed) or to `BENCHWARMER_CONFIG`. Never overwrites an existing file. |
| `uv run benchwarmer serve [--host H] [--port N] [--check]` | Loads settings, resolves the built UI, refuses an absent, unmigrated, or outdated data root with the command that fixes it, prints the resolved settings, and runs Uvicorn in the foreground. `--check` stops after printing. It never migrates and never starts model work. |
| `uv run alembic upgrade head` | Migrates the configured data root. Uses the same settings file and variables. |
| `uv run uvicorn benchwarmer.api.app:create_app --factory` | The bare factory, used by the browser tests and the Compose service in ADR 0003. It reads the same settings but requires `ui_root` to be configured and performs no migration check. |

## Precedence examples

- No file, no variables: platform data root, no imports, no harness, no UI
  root, `127.0.0.1:8000`, every provider.
- `benchwarmer.toml` in the data root sets `port = 8765`; the shell exports
  `BENCHWARMER_PORT=9000`: the server listens on 9000.
- The file sets `harness_dir`; the shell exports `BENCHWARMER_HARNESS_DIR=`
  (empty): the application cannot start plans for that run.
- `BENCHWARMER_CONFIG=/etc/benchwarmer/benchwarmer.toml` and that file sets
  `data_root`: the data lives where the file says; the file itself stays in
  `/etc/benchwarmer`.

## Error messages

Errors name the source and the key, for example
`/path/to/benchwarmer.toml: [paths] data_root must be an absolute path`,
`BENCHWARMER_PORT must be an integer from 1 through 65535`, or
`BENCHWARMER_CONFIG names a settings file that does not exist: /path`.
`benchwarmer serve` and `benchwarmer init` print one such line to standard
error and exit with status 1.
