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

`BENCHWARMER_DATA_ROOT` is the implemented configuration interface; tests
isolate it with temporary directories. Path resolution and the runtime gate
are application code. Coordinated backup/restore remains separate planned work;
foundation completion does not prove production recovery.

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

At the original proposal date the application did not yet exist. Current
implementation status belongs to the work records, not that historical baseline.
Serving, process binding, and supervision belong to
[the serving decision](0003-serving-supervision.md).

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

### Implementation ownership

The accepted backup/restore protocol above is the contract, not an implemented
command. The [recovery work record](../../todo/work/backup-and-recovery/README.md)
owns executable tests, command interfaces, and the target-host drill. The old
embedded design prototype is preserved in Git history at commit `aee6cee`; it is
not an application backup tool and is no longer a maintained runbook.

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
- The pinned runtime now selects SQLite 3.53.4; the in-process gate still rejects
  unsafe replacement runtimes. The original SQLite 3.50.4 inspection is historical,
  not a current environment diagnosis.
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
- The [runtime choice](../runtime-recovery.md) is resolved. Each deployed process
  must still pass its linked-library gate; a toolchain pin is not a substitute
  for runtime validation or target-host recovery verification.
- Backup destination, schedule, notification, encryption mechanism, generation
  count, and transient job/log age or size limits remain operator policy. They
  must be selected and tested before recovery is presented as unattended.
- Future selective deletion must define referential garbage collection, audit
  metadata, backup expiry, and user-visible secure-erasure limits.
- A target-host restore drill must determine whether the chosen filesystems
  support the required atomic sibling rename and directory flush behavior. If
  not, the implementation needs a documented, verified offline fallback.

## Verification

The maintained runtime predicate is in
[`sqlite_runtime.py`](../../src/benchwarmer/sqlite_runtime.py), not a copied
prototype. Runtime tests must reject vulnerable branch boundaries before any
SQLite connection or file creation. Data-root tests cover invalid overrides,
owner-only creation, fixed child paths, and no import-time filesystem mutation.

The [recovery work record](../../todo/work/backup-and-recovery/README.md) owns
write-gate, active-WAL, manifest, unsafe-path, corruption, rollback, and restart
tests. Backups are not operational until a completed external generation passes
a target-host restore drill. Passing foundation tests or the retired prototype
is not equivalent evidence.
