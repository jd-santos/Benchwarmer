# ADR 0002: Private data and recovery boundary

- Status: Accepted by [the accepted foundation decisions](../decisions.md)
- Work: [the data and recovery decision](0002-data-recovery.md)
- Date: 2026-09-08

## Context and evidence

Benchwarmer will run on one always-on Mac mini beside Hermes, while its source
repository may be public. The architecture therefore requires SQLite, imported
session snapshots, prompts, annotations, fixtures, outputs, and logs to remain
in a configurable private root outside the checkout by default. Database rows
can refer to private files, so a database-only backup or an unrelated file copy
can produce a restore with missing or mismatched evidence.

The foundation plan already reserves `BENCHWARMER_DATA_ROOT` as the proposed
configuration interface and requires tests to override it with a temporary
directory. [private data-root configuration](../../todo/work/application-foundation/plan.md) needs deterministic child paths without creating files at
module import. [foundation integration verification](../../todo/work/application-foundation/README.md) needs a disposable recovery check, but neither task may
claim that a production recovery implementation exists merely because this ADR
contains an executable prototype.

SQLite's [WAL documentation](https://www.sqlite.org/wal.html) explains that a
commit can live in the `-wal` file without yet appearing in the main database.
The `-wal` and `-shm` files are therefore part of live runtime state, and copying
only `benchwarmer.sqlite3` is not a valid live-backup procedure. It also states
that all WAL users must be on the same host, so the live database belongs on a
local filesystem, not a network share.

Section 11 of SQLite's WAL documentation describes the
[WAL-reset bug](https://www.sqlite.org/wal.html#the_wal_reset_bug), a rare
corruption race likely present from SQLite 3.7.0 through 3.51.2 when multiple
connections on one database write or checkpoint concurrently. The general fix
is in 3.51.3 and later, with backports on two older release branches at 3.44.6
and 3.50.7. Benchwarmer's planned API and worker boundary can create the affected
concurrency, so WAL use must fail closed unless the SQLite library linked into
the running process has one of those fixes.

SQLite's [Online Backup API documentation](https://www.sqlite.org/backup.html)
states that a completed backup is a consistent snapshot of the source database.
Python 3.12 exposes that API as
[`sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup).
That API is available in the required Python runtime and avoids depending on a
particular `sqlite3` shell installation. It solves SQLite consistency, but not
the separate race between database references and private files; an
application-level write barrier is still required.

No application, backup command, worker, frontend, or process supervisor exists
at the time of this proposal. Serving, process binding, and supervision belong
to [the serving decision](0003-serving-supervision.md) and are not decided here.

## Decision

### Data-root resolution

Use one settings resolver as the only source of runtime paths. It resolves the
root in this order:

1. If `BENCHWARMER_DATA_ROOT` is present, expand a leading `~` with the current
   user's home directory and require the result to be absolute. Do not expand
   embedded environment-variable syntax such as `$HOME`; configuration must not
   depend on a second interpolation pass.
2. An empty or whitespace-only environment value is an error rather than a
   request for the default. A relative value is also an error.
3. If the variable is absent on macOS, compute the default from the current
   home directory as `~/Library/Application Support/Benchwarmer`. The
   implementation uses the home-directory API; it must not hardcode a `/Users`
   path.
4. On other platforms, use an absolute `XDG_DATA_HOME` when supplied; otherwise
   compute `~/.local/share/benchwarmer`. This fallback keeps Linux development
   and CI outside the checkout without changing the target-host default.

An explicit override may select a gitignored development location or a test
temporary directory, but documentation must warn that private data still must
not be committed. The live root must be on a local filesystem that supports
SQLite locking. Remote storage may hold completed backup generations, not the
active WAL database.

Path resolution itself has no filesystem side effects. Application startup or
an explicit initialization command creates the root and children with owner-only
permissions (`0700` directories and `0600` files, subject to the host's stronger
controls). Startup fails with an actionable error if the root cannot be created,
is not a directory, is not writable, or cannot provide the required child
layout.

### SQLite WAL safety gate

WAL is permitted only when `sqlite3.sqlite_version_info` reports one of these
fixed version lines:

- 3.51.3 or later;
- 3.50.7 or later on the 3.50 release branch; or
- 3.44.6 or later on the 3.44 release branch.

The precise predicate is:

```python
def sqlite_has_wal_reset_fix(version: tuple[int, int, int]) -> bool:
    return (
        version >= (3, 51, 3)
        or (version[:2] == (3, 50) and version[2] >= 7)
        or (version[:2] == (3, 44) and version[2] >= 6)
    )
```

The branch checks are intentional. In particular, 3.45.x through 3.49.x do not
inherit the 3.44 backport; 3.50.0 through 3.50.6 and 3.51.0 through 3.51.2 also
remain blocked.

Every application, worker, migration, maintenance, backup, or restore process
that can open the live database in WAL mode must evaluate this predicate in the
same Python process, using the runtime-linked SQLite version. It does so before
its first `sqlite3.connect`, including before opening a database whose persistent
journal mode may already be WAL. A failed gate aborts before touching the
database; package metadata, a separately installed `sqlite3` shell, and a check
performed by another process are not substitutes. A deployment that does not
meet the gate must keep the database in a rollback journal mode and must not
enable, open, write, or checkpoint it in WAL mode.

### Directory layout and ownership

All database file references use validated POSIX-style paths relative to the
resolved root. Absolute references and `..` traversal are invalid. The initial
layout is:

```text
<data-root>/
├── database/
│   ├── benchwarmer.sqlite3
│   ├── benchwarmer.sqlite3-wal    # SQLite-managed, when present
│   └── benchwarmer.sqlite3-shm    # SQLite-managed, when present
├── artifacts/                     # durable generated/private results
├── snapshots/                     # durable imported source captures
├── jobs/
│   ├── staging/                   # incomplete file publication
│   └── workspaces/                # disposable execution workspaces
├── logs/                           # bounded, privacy-filtered operations logs
└── locks/                          # local coordination; no durable job truth
```

The categories have these contracts:

- `database/benchwarmer.sqlite3` is the one authoritative structured store.
  Durable import and job status belongs here. Adding an attached authoritative
  database would require revisiting the atomic-backup contract because SQLite
  does not make transactions across multiple attached WAL databases atomic as
  a set.
- `artifacts/` contains durable outputs, reviewed fixtures, reports, and other
  large files referenced by database records.
- `snapshots/` contains immutable private captures needed to preserve import
  provenance when source logs change or disappear. Snapshots are not executable
  instructions.
- `jobs/` contains only reconstructible staging and disposable workspaces.
  Nothing needed to decide whether an import or paid attempt may retry can live
  only there.
- `logs/` is operational and non-authoritative. Logs must avoid credentials,
  raw prompt text, private payloads, and provider responses by default.
- `locks/` coordinates local processes. A lock file never proves durable job
  state after a crash.

Published files in `artifacts/` and `snapshots/` are immutable. Writers create a
same-filesystem temporary file, flush it, atomically rename it to its final
relative path, and only then commit the database reference and its byte length
and SHA-256 digest. A changed payload receives a new path; it does not overwrite
an existing referenced file. A failed database commit may leave an unreferenced
file for later garbage collection, but a committed reference must never point
to a partially published file.

Credentials and secret-bearing configuration remain outside this tree. Use
environment references, the macOS Keychain, or another separately configured
secret store. The database may record a credential reference or provider/account
identity, never an API key. Importers must exclude credential files and redact
recognized secrets before durable snapshot, artifact, or log publication.
Backups contain private content and must use owner-only access on encrypted
private storage, but they do not contain the external credentials needed to
resume provider access.

### Retention boundary

Retention follows data semantics rather than one timer for the entire root:

- The database, published artifacts, and imported snapshots are durable. The
  initial application performs no age-based deletion of them. A future deletion
  operation must be explicit, remove references and files coherently, and retain
  enough metadata to explain the deletion.
- Job staging, disposable workspaces, logs, and lock files are transient and are
  not recovery inputs. They may be cleaned after terminal job reconciliation or
  bounded by a later operational policy. The exact age and size limits remain a
  deployment setting, not a prerequisite for [private data-root configuration](../../todo/work/application-foundation/plan.md).
- Completed backup generations are immutable. The initial backup implementation
  does not silently prune them. Rotation is an operator policy and must preserve
  at least one successfully verified generation.
- Deleting live private data does not erase it from existing backup generations.
  Backup expiration must be included in any future user-facing deletion promise;
  this design does not claim immediate secure erasure.

This boundary deliberately keeps durable job truth in the backed-up database
while allowing large failed workspaces and verbose logs to be discarded.

### Coordinated backup contract

A backup generation contains only these recovery inputs:

```text
<backup-generation>/
├── database/benchwarmer.sqlite3   # standalone Online Backup API result
├── artifacts/
├── snapshots/
├── manifest.json
└── COMPLETE
```

`jobs/`, `logs/`, `locks/`, and live SQLite `-wal`/`-shm` files are excluded.
The backup destination must not be equal to, inside, or symlinked into the live
data root. Prefer a different encrypted device or a completed-generation copy to
remote storage so a single disk failure does not remove both copies.

Every API, importer, and future worker mutation participates in one
application-level write gate. The gate is independent of how processes are
started or supervised. Backup performs these steps:

1. Allocate a unique generation ID and an owner-only `.partial` directory on the
   destination filesystem.
2. Close the write gate, reject new mutations, and wait for active database/file
   publication units to finish. Reads may continue. Timeout fails the backup;
   it never bypasses the gate.
3. While the gate is closed, use `sqlite3.Connection.backup` to write a
   standalone `database/benchwarmer.sqlite3` in the partial generation, then set
   that destination to `journal_mode=DELETE` so opening the portable copy does
   not require or create WAL sidecars. Application startup may enable WAL again
   after restore only after passing the SQLite WAL safety gate. Do not copy the
   live database, `-wal`, or `-shm` files and do not treat a checkpoint as a
   substitute for the backup API.
4. Copy `artifacts/` and `snapshots/` without following symlinks. Any symlink,
   path traversal, unreadable file, or file change is a failed generation.
5. Run `PRAGMA quick_check` on the backup database. Inventory every recovery
   file by relative path, byte length, and SHA-256 digest. Write `manifest.json`
   with backup-format version, generation ID, UTC creation time, application
   version, Alembic revision, SQLite version, and the inventory. It must not
   expose the source's absolute private path.
6. Flush files and directories, write `COMPLETE` last with the manifest digest,
   and atomically rename the partial directory to the final generation name on
   the same filesystem. A partial directory or a generation without a valid
   `COMPLETE` marker is never restorable.
7. Reopen the write gate. Only a completed, verified generation is reported as a
   successful backup.

Holding the gate across both the database snapshot and file copy is intentional.
The Online Backup API alone allows concurrent SQLite writes, but those writes
could publish or delete referenced files at a different point in the copy.
Immutable file publication narrows the risk; the gate removes it for the initial
implementation. Backup may briefly defer imports or experiment state changes,
but it must not terminate or automatically retry paid work.

A filesystem or Time Machine copy of the live root is not the coordinated
backup. Such tools may safely copy an already completed backup generation. An
operator may also make an offline copy after all Benchwarmer writers have
stopped, but restore verification is still required.

### Restore contract

Restore is offline with respect to Benchwarmer mutations. It does not depend on
a particular supervisor command:

1. Stop or otherwise fence every API and worker writer. Refuse restore if the
   write gate cannot be held exclusively.
2. Require `COMPLETE`, verify its manifest digest, reject symlinks and unexpected
   recovery files, and verify every manifest byte length and SHA-256 digest.
3. Restore into a new owner-only sibling staging root, never over the active
   root. Copy the standalone database, artifacts, and snapshots. Create empty
   `jobs/`, `logs/`, and `locks/`; never restore SQLite `-wal` or `-shm` files.
4. Run `PRAGMA quick_check`, read the schema/Alembic revision, and run an
   application verifier that proves every database file reference exists under
   the staged root with the recorded digest. Before joining or reading any path
   obtained from the database, require a non-empty, canonical POSIX relative
   path: absolute paths, `..` components, and normalized spellings that differ
   from the stored value are invalid. Refuse unsupported newer schema or
   backup-format versions. Do not migrate or mutate the only backup generation
   during verification.
5. After verification, retain the old root as a rollback sibling and atomically
   place the staged root at the configured path when the filesystem permits. If
   atomic replacement is unavailable, fail with documented manual recovery
   steps rather than exposing a half-restored root.
6. Start the application against the restored root, run read-only health and
   reference checks, and only then allow new imports or jobs. Migrations, if
   required and supported, occur as a separately backed-up operation after the
   unmodified restore has passed verification.

A restore proves data integrity and cross-boundary references; it does not prove
external credentials are still available. Missing credentials produce a clear
configuration state rather than being reconstructed from private snapshots.

### Disposable WAL/recovery prototype

The following prototype is the executable design fixture for [private data-root configuration](../../todo/work/application-foundation/plan.md) and
[foundation integration verification](../../todo/work/application-foundation/README.md). Run the entire block in one POSIX shell from the checkout. Its first
operation checks the SQLite library linked to `uv run python`, before `mktemp`,
`sqlite3.connect`, or any WAL file creation. Failure stops the entire shell; do
not bypass the gate or run the remaining lines separately. After a successful
gate, the writer and backup Python blocks repeat the exact predicate in their own
processes before filesystem mutation or connection to the live database; the
standalone preflight is not a substitute for either same-process check. The
fixture then writes only beneath `mktemp`, creates a committed row that remains
in an active WAL, backs up only the durable boundary through Python's Online
Backup API, restores to a fresh root, checks hashes/references, prints one success
line, and removes all temporary state.

At [the data and recovery decision](0002-data-recovery.md) verification time, `uv run python` links SQLite 3.50.4. The gate
correctly reports it as blocked, so the WAL portion of this prototype must not be
run in the current environment. A future run requires an accepted SQLite build.

The fixture writer becomes idle before backup and remains open only to keep the
committed WAL present. That idle point represents the closed application write
gate; it is not an implementation of cross-process locking.

```bash
set -eu

# Safety preflight: this must run before any SQLite connection or temporary root.
uv run python - <<'PY'
import sqlite3


def sqlite_has_wal_reset_fix(version: tuple[int, int, int]) -> bool:
    return (
        version >= (3, 51, 3)
        or (version[:2] == (3, 50) and version[2] >= 7)
        or (version[:2] == (3, 44) and version[2] >= 6)
    )


if not sqlite_has_wal_reset_fix(sqlite3.sqlite_version_info):
    raise SystemExit(
        "WAL safety gate: BLOCKED; linked SQLite "
        f"{sqlite3.sqlite_version} lacks the WAL-reset fix"
    )
PY

prototype_root="$(mktemp -d \
  "${TMPDIR:-/tmp}/benchwarmer-recovery.XXXXXX")"
export BENCHWARMER_DATA_ROOT="$prototype_root/live"
export BACKUP_ROOT="$prototype_root/backup-target"
export RESTORE_ROOT="$prototype_root/restored"
ready_file="$prototype_root/writer.ready"
stop_file="$prototype_root/writer.stop"
writer_pid=""

cleanup() {
  if [ -n "$writer_pid" ] && kill -0 "$writer_pid" 2>/dev/null; then
    : >"$stop_file"
    wait "$writer_pid" 2>/dev/null || true
  fi
  rm -rf "$prototype_root"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$BACKUP_ROOT"
chmod 700 "$prototype_root" "$BACKUP_ROOT"

# Setup: create private files and hold committed pages in the WAL.
uv run python - \
  "$BENCHWARMER_DATA_ROOT" "$ready_file" "$stop_file" <<'PY' &
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import time


def sqlite_has_wal_reset_fix(version: tuple[int, int, int]) -> bool:
    return (
        version >= (3, 51, 3)
        or (version[:2] == (3, 50) and version[2] >= 7)
        or (version[:2] == (3, 44) and version[2] >= 6)
    )


if not sqlite_has_wal_reset_fix(sqlite3.sqlite_version_info):
    raise SystemExit(
        "WAL safety gate: BLOCKED; linked SQLite "
        f"{sqlite3.sqlite_version} lacks the WAL-reset fix"
    )

os.umask(0o077)
root = Path(sys.argv[1])
ready = Path(sys.argv[2])
stop = Path(sys.argv[3])
for relative in (
    "database",
    "artifacts/trials/example",
    "snapshots/imports/example",
    "jobs/staging",
    "jobs/workspaces",
    "logs",
    "locks",
):
    (root / relative).mkdir(parents=True, exist_ok=True, mode=0o700)

payloads = {
    "artifacts/trials/example/output.txt": b"fixture artifact\n",
    "snapshots/imports/example/source.json": b'{"fixture": true}\n',
}
for relative, payload in payloads.items():
    path = root / relative
    path.write_bytes(payload)
    path.chmod(0o600)

(root / "jobs/workspaces/not-durable.txt").write_text(
    "discard me\n", encoding="utf-8"
)
(root / "logs/not-durable.log").write_text(
    "fixture log\n", encoding="utf-8"
)

database = root / "database/benchwarmer.sqlite3"
connection = sqlite3.connect(database)
assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
connection.execute("PRAGMA synchronous=FULL")
connection.execute("PRAGMA wal_autocheckpoint=0")
connection.execute(
    "CREATE TABLE private_files ("
    "path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL)"
)
for relative, payload in payloads.items():
    connection.execute(
        "INSERT INTO private_files(path, sha256, bytes) VALUES (?, ?, ?)",
        (relative, hashlib.sha256(payload).hexdigest(), len(payload)),
    )
connection.commit()
ready.write_text("ready\n", encoding="utf-8")
while not stop.exists():
    time.sleep(0.05)
connection.close()
PY
writer_pid=$!

while [ ! -f "$ready_file" ]; do
  kill -0 "$writer_pid"
  sleep 0.05
done
test -s \
  "$BENCHWARMER_DATA_ROOT/database/benchwarmer.sqlite3-wal"

# Backup: snapshot SQLite, copy durable files, then publish a manifest.
export BACKUP_SET="$BACKUP_ROOT/fixture-generation"
export BACKUP_STAGE="$BACKUP_ROOT/.fixture-generation.partial"
uv run python - \
  "$BENCHWARMER_DATA_ROOT" "$BACKUP_STAGE" "$BACKUP_SET" <<'PY'
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys


def sqlite_has_wal_reset_fix(version: tuple[int, int, int]) -> bool:
    return (
        version >= (3, 51, 3)
        or (version[:2] == (3, 50) and version[2] >= 7)
        or (version[:2] == (3, 44) and version[2] >= 6)
    )


if not sqlite_has_wal_reset_fix(sqlite3.sqlite_version_info):
    raise SystemExit(
        "WAL safety gate: BLOCKED; linked SQLite "
        f"{sqlite3.sqlite_version} lacks the WAL-reset fix"
    )

os.umask(0o077)
source_root = Path(sys.argv[1]).resolve()
stage = Path(sys.argv[2]).resolve()
final = Path(sys.argv[3]).resolve()
if source_root == final or source_root in final.parents:
    raise SystemExit("backup destination must be outside the data root")
if stage.exists() or final.exists():
    raise SystemExit("backup generation already exists")
stage.mkdir(parents=True, mode=0o700)
(stage / "database").mkdir(mode=0o700)

source_database = source_root / "database/benchwarmer.sqlite3"
backup_database = stage / "database/benchwarmer.sqlite3"
with sqlite3.connect(source_database, timeout=5.0) as source:
    with sqlite3.connect(backup_database) as destination:
        source.backup(destination)
        journal_mode = destination.execute(
            "PRAGMA journal_mode=DELETE"
        ).fetchone()[0]
        if journal_mode != "delete":
            raise SystemExit("could not make backup database standalone")
        result = destination.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise SystemExit(f"backup quick_check failed: {result}")
backup_database.chmod(0o600)

for directory in ("artifacts", "snapshots"):
    source_directory = source_root / directory
    for path in source_directory.rglob("*"):
        if path.is_symlink():
            raise SystemExit(f"refusing symlink: {path}")
    shutil.copytree(source_directory, stage / directory)

inventory = []
for path in sorted(item for item in stage.rglob("*") if item.is_file()):
    relative = path.relative_to(stage).as_posix()
    payload = path.read_bytes()
    inventory.append(
        {
            "path": relative,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    )
    path.chmod(0o600)

manifest = {
    "backup_format": 1,
    "generation": "fixture-generation",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "application_version": "prototype",
    "alembic_revision": None,
    "sqlite_version": sqlite3.sqlite_version,
    "files": inventory,
}
manifest_bytes = (
    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
).encode("utf-8")
manifest_path = stage / "manifest.json"
manifest_path.write_bytes(manifest_bytes)
manifest_path.chmod(0o600)
complete_path = stage / "COMPLETE"
complete_path.write_text(
    hashlib.sha256(manifest_bytes).hexdigest() + "\n",
    encoding="ascii",
)
complete_path.chmod(0o600)

for path in stage.rglob("*"):
    if path.is_file():
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
for path in sorted(
    (item for item in stage.rglob("*") if item.is_dir()),
    key=lambda item: len(item.parts),
    reverse=True,
):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
descriptor = os.open(stage, os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
os.replace(stage, final)
descriptor = os.open(final.parent, os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PY

# Restore: verify the generation before publishing a fresh data root.
uv run python - "$BACKUP_SET" "$RESTORE_ROOT" <<'PY'
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys


def validated_database_relative_path(raw_path: object) -> PurePosixPath:
    relative = PurePosixPath(raw_path) if isinstance(raw_path, str) else None
    if (
        relative is None
        or not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != raw_path
    ):
        raise SystemExit("invalid database file reference")
    return relative


os.umask(0o077)
backup = Path(sys.argv[1]).resolve()
restore = Path(sys.argv[2]).resolve()
stage = restore.with_name(f".{restore.name}.partial")
if restore.exists() or stage.exists():
    raise SystemExit("restore target must not exist")
if not (backup / "COMPLETE").is_file():
    raise SystemExit("backup is incomplete")
for path in backup.rglob("*"):
    if path.is_symlink():
        raise SystemExit(f"refusing symlink: {path}")

manifest_bytes = (backup / "manifest.json").read_bytes()
expected_manifest = (backup / "COMPLETE").read_text(
    encoding="ascii"
).strip()
if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest:
    raise SystemExit("manifest digest mismatch")
manifest = json.loads(manifest_bytes)
if manifest.get("backup_format") != 1:
    raise SystemExit("unsupported backup format")
entries = manifest.get("files")
if not isinstance(entries, list):
    raise SystemExit("invalid backup inventory")
expected_paths = set()
for item in entries:
    raw_path = item.get("path") if isinstance(item, dict) else None
    relative = PurePosixPath(raw_path) if isinstance(raw_path, str) else None
    allowed = raw_path == "database/benchwarmer.sqlite3" or (
        isinstance(raw_path, str)
        and raw_path.startswith(("artifacts/", "snapshots/"))
    )
    if (
        relative is None
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != raw_path
        or not allowed
        or raw_path in expected_paths
    ):
        raise SystemExit("invalid backup inventory path")
    expected_paths.add(raw_path)
actual_paths = {
    path.relative_to(backup).as_posix()
    for path in backup.rglob("*")
    if path.is_file()
    and path.relative_to(backup).as_posix()
    not in {"manifest.json", "COMPLETE"}
}
if actual_paths != expected_paths:
    raise SystemExit("backup inventory mismatch")
for item in entries:
    payload = (backup / item["path"]).read_bytes()
    if len(payload) != item["bytes"]:
        raise SystemExit(f"length mismatch: {item['path']}")
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise SystemExit(f"digest mismatch: {item['path']}")

stage.mkdir(parents=True, mode=0o700)
for directory in ("database", "artifacts", "snapshots"):
    shutil.copytree(backup / directory, stage / directory)
for directory in ("jobs/staging", "jobs/workspaces", "logs", "locks"):
    (stage / directory).mkdir(parents=True, exist_ok=True, mode=0o700)
for path in stage.rglob("*"):
    path.chmod(0o700 if path.is_dir() else 0o600)

database = stage / "database/benchwarmer.sqlite3"
with sqlite3.connect(database) as connection:
    result = connection.execute("PRAGMA quick_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"restored quick_check failed: {result}")
    for raw_relative, digest, length in connection.execute(
        "SELECT path, sha256, bytes FROM private_files ORDER BY path"
    ):
        relative = validated_database_relative_path(raw_relative)
        path = stage / relative
        payload = path.read_bytes()
        if len(payload) != length:
            raise SystemExit(f"restored length mismatch: {raw_relative}")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise SystemExit(f"restored digest mismatch: {raw_relative}")
os.replace(stage, restore)
PY

# Verify: prove WAL content and durable files survived; transient data did not.
uv run python - "$RESTORE_ROOT" <<'PY'
import hashlib
from pathlib import Path, PurePosixPath
import sqlite3
import sys


def validated_database_relative_path(raw_path: object) -> PurePosixPath:
    relative = PurePosixPath(raw_path) if isinstance(raw_path, str) else None
    if (
        relative is None
        or not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != raw_path
    ):
        raise SystemExit("invalid database file reference")
    return relative


root = Path(sys.argv[1]).resolve()
database = root / "database/benchwarmer.sqlite3"
if Path(f"{database}-wal").exists() or Path(f"{database}-shm").exists():
    raise SystemExit("live SQLite sidecars were restored")
with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise SystemExit("restored database failed quick_check")
    rows = connection.execute(
        "SELECT path, sha256, bytes FROM private_files ORDER BY path"
    ).fetchall()
if len(rows) != 2:
    raise SystemExit("WAL-backed rows were not restored")
for invalid_reference in (
    "",
    ".",
    "/tmp/benchwarmer-outside",
    "../outside",
    "artifacts/../outside",
    "./artifacts/trials/example/output.txt",
    "artifacts//trials/example/output.txt",
    "artifacts/trials/example/output.txt/",
):
    try:
        validated_database_relative_path(invalid_reference)
    except SystemExit:
        pass
    else:
        raise SystemExit(
            f"accepted invalid database file reference: {invalid_reference!r}"
        )
for raw_relative, digest, length in rows:
    relative = validated_database_relative_path(raw_relative)
    payload = (root / relative).read_bytes()
    if len(payload) != length:
        raise SystemExit(f"restored length mismatch: {raw_relative}")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise SystemExit(f"restored digest mismatch: {raw_relative}")
if any(path.is_file() for path in (root / "jobs").rglob("*")):
    raise SystemExit("transient job data was restored")
if any(path.is_file() for path in (root / "logs").rglob("*")):
    raise SystemExit("transient logs were restored")
print("recovery prototype: PASS")
PY
```

[the pinned Python and SQLite runtime](../runtime-recovery.md) first supplies a runtime linked to an accepted SQLite build. It tests
the safety predicate against fixed and vulnerable boundary versions and proves
gate failure occurs before database or sidecar creation. [private data-root configuration](../../todo/work/application-foundation/plan.md) then executes
this prototype as a design fixture, including rejection of empty, dot-only,
absolute, `..` traversal, and noncanonical database file references before file
reads. It separately tests the accepted resolver behavior, directory creation,
permissions, invalid roots, and lack of import-time side effects with `tmp_path`.
Passing the prototype at that stage validates the selected path layout and
recovery algorithm only; it does not mean an application backup command or
multi-process write gate exists.

[foundation integration verification](../../todo/work/application-foundation/README.md) executes the same prototype again on an integrated toolchain whose
in-process gate passes and records `recovery prototype: PASS` in its verification
output. It must also test any implemented application backup/restore surface
through the migrated schema and real file-reference verifier. Until that surface
exists, QA documentation must call this a prototype rather than a production
backup test.

## Alternatives considered

### Put the default under the checkout

A gitignored `.benchwarmer/` remains useful as an explicit development override,
but it is rejected as the default. Checkout deletion, branch worktrees, broad
git tooling, and accidental force-adds are the wrong lifecycle and privacy
boundary for personal evidence.

### Store every private payload as a SQLite BLOB

One database would simplify backup atomicity, but large transcripts, fixtures,
and generated outputs would inflate database churn and make direct artifact
inspection and lifecycle management harder. SQLite remains authoritative for
metadata and references; immutable files keep large payloads separate without
relaxing consistency.

### Copy the database file, WAL, and artifacts with filesystem tools

This is rejected for a live service. The WAL may hold committed state, sidecar
copy timing can differ, and ordinary recursive copying has no atomic relationship
to artifact publication. A checkpoint followed by `cp` also does not establish
the database/artifact write barrier.

### Use the Online Backup API while file writers continue

The database copy would be consistent by itself, but its reference set could
precede or follow filesystem changes. This may become optimizable with stronger
content-addressed and generation semantics; the initial design chooses the
simpler cross-boundary write gate.

### Treat Time Machine or another whole-directory snapshot as the only backup

Host snapshots are valuable defense in depth, but Benchwarmer cannot assume that
a snapshot tool coordinates SQLite and application file publication. These
tools should consume completed generations or take a documented fully offline
copy.

### Apply one automatic retention duration to all data

This risks deleting source evidence needed to explain normalized records or job
state needed to prevent duplicate paid attempts. Durable evidence and transient
workspaces have different semantics, so deletion must respect their categories.

## Consequences

- The target host has one predictable private root, while tests and development
  can isolate all state with one environment variable.
- WAL remains an application runtime choice without making sidecar files part of
  the portable backup format, but every WAL-capable process now depends on an
  accepted runtime-linked SQLite build and must fail before opening the database
  when the version gate rejects it.
- The current `uv run python` SQLite 3.50.4 build cannot run the WAL prototype or
  serve a WAL database. Rollback journaling remains available while the
  toolchain upgrade path is resolved.
- Backups may briefly pause imports, annotations, and experiment-state changes.
  Read service can continue, but restore requires an exclusive offline window.
- Durable private data grows until an explicit deletion or backup-rotation policy
  is implemented. Disk usage and last verified backup age must become observable
  before real imports become operationally important.
- Database/file publication and deletion must use a shared write gate. Bypassing
  it from a maintenance script can invalidate recovery guarantees.
- Recovery can detect corruption, truncation, missing files, extra files, and
  unsupported formats before replacing live state. Keeping the previous root
  permits rollback after an application-level health failure.
- Restores do not recover API keys or credential material. Reauthorization may be
  required, which is safer than duplicating secrets into every backup.
- Completed generations can be copied by ordinary backup tools after publication,
  but at least one verified copy should live outside the active disk failure
  domain.
- This proposal adds no frontend-serving or process-supervision decision and no
  runtime dependency. Production command names and scheduling can be selected
  when the recovery implementation is planned.

## Unresolved questions

- [The recovery implementation](../../todo/work/backup-and-recovery/README.md)
  must choose the concrete cross-process write-gate mechanism and backup/restore
  command names while preserving this protocol.
  That implementation depends on the final API/worker process boundary but not
  on the supervisor selected by [the serving decision](0003-serving-supervision.md).
- [the pinned Python and SQLite runtime](../runtime-recovery.md) must choose and pin a Python/runtime distribution that links an
  accepted SQLite version on development, CI, and the target Mac mini. The
  executable in-process gate remains required after that toolchain choice so a
  later runtime downgrade cannot silently re-enable vulnerable WAL use.
- Backup destination, schedule, notification, encryption mechanism, generation
  count, and transient job/log age or size limits remain operator policy. They
  must be selected and tested before recovery is presented as unattended.
- Future selective deletion must define referential garbage collection, audit
  metadata, backup expiry, and user-visible secure-erasure limits.
- A target-host restore drill must determine whether the chosen filesystems
  support the required atomic sibling rename and directory flush behavior. If
  not, the implementation needs a documented, verified offline fallback.

## Verification

### Decide the private data and recovery boundary design verification

This proposed record is complete when the following checks pass:

```bash
git diff --check
npx -y markdownlint-cli2@0.18.1 \
  docs/decisions/0002-data-recovery.md
git status --short
```

Review the complete diff to confirm that it contains no absolute private path,
credential, prompt, session payload, or raw provider response and that the only
changed path is `docs/decisions/0002-data-recovery.md`. Test the version predicate
with 3.50.4 and 3.51.2 rejected and 3.51.3, 3.50.7, and 3.44.6 accepted. Run the
prototype preflight against the current environment and require it to report
`WAL safety gate: BLOCKED` for linked SQLite 3.50.4 with a nonzero status. Confirm
that no prototype root, database, `-wal`, or `-shm` file was created; do not run
the WAL portion in that environment. Statically inspect or extract each later
Python block with a fixed-version `sqlite3` stub and prove that the writer and
backup processes each evaluate the exact predicate before their first filesystem
mutation or `sqlite3.connect` to the live database.

Once `uv run python` links an accepted SQLite build, execute the whole disposable
prototype and require exactly `recovery prototype: PASS` with a zero exit status.
This verifies that the proposed commands exercise an active WAL, manifest hashes,
durable-file restoration, and transient-file exclusion; it does not verify
unimplemented application behavior.

### Later implementation verification

After [the accepted foundation decisions](../decisions.md) accepts the record:

- [the pinned Python and SQLite runtime](../runtime-recovery.md) tests the WAL gate's accepted and rejected version boundaries and
  rejection before any SQLite file creation.
- [private data-root configuration](../../todo/work/application-foundation/plan.md) tests every data-root resolution branch, invalid input, owner-only
  creation, fixed child paths, and no import-time filesystem mutation, then runs
  the disposable prototype on the accepted build.
- [The recovery implementation](../../todo/work/backup-and-recovery/README.md)
  tests write-gate timeout/failure, a concurrent
  attempted mutation, partial-generation rejection, symlink rejection, corrupt
  database and file hashes, missing and extra files, unsupported formats/schema,
  rollback preservation, and external credential absence. Before allowing a
  file-read spy to observe any access, its database-reference tests reject `""`,
  `"."`, `"/tmp/benchwarmer-outside"`, `"../outside"`,
  `"artifacts/../outside"`, `"./artifacts/example"`,
  `"artifacts//example"`, and `"artifacts/example/"`; a canonical relative
  reference remains accepted.
- [foundation integration verification](../../todo/work/application-foundation/README.md) runs the exact prototype and the implemented backup/restore path in a
  disposable root, restarts the migrated application against the restored root,
  verifies all database file references, and confirms that no runtime or private
  file is tracked by git.
- The recovery work includes a separate target-host restore drill to an empty
  root from an external backup device before calling backups operational. Its
  evidence must name the application/SQLite versions and completed generation
  without recording private paths or content.
