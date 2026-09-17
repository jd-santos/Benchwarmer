# Implement coordinated backups and prove recovery

Status: Planned. Implementation and delivery are pending unless a supporting
record explicitly says otherwise.

## Purpose

Turn the accepted recovery protocol into an application-owned backup and restore
path, then prove it on the target host from an external completed generation.

## Dependencies and order

Implementation is blocked on [the application foundation](../application-foundation/README.md)
because every mutating process must share the final write gate. Disposable tests
can precede deployment. The target-host drill also depends on
[private deployment](../private-deployment/README.md) and the chosen operator
storage policy.

## Acceptance criteria

Application commands create and verify immutable backup generations containing a
standalone database plus referenced durable files. Restore rejects incomplete,
corrupt, unexpected, or unsafe input before replacing live state. A sanitized
target-host drill restores one completed external generation into an empty root,
starts the application read-only for verification, and records versions and the
generation identifier without private paths or content.

## Work

- [ ] Implement the coordinated application backup and restore path
  - Dependencies: [Document development and final integration](../application-foundation/README.md)
  - Scope: choose the cross-process write gate and command interfaces; make every
    API, importer, worker, migration, maintenance, and deletion path participate;
    use SQLite's Online Backup API; publish immutable, manifest-verified
    generations; exclude live WAL sidecars, jobs, logs, locks, and credentials
  - [ ] Refuse destinations inside the live root, unsafe paths and symlinks,
    unsupported formats or schemas, missing or extra recovery files, and any
    digest, size, or database integrity mismatch.
  - [ ] Restore to a new owner-only staging root, recreate transient directories,
    preserve the previous root for rollback, and keep writers fenced until
    application reference and health checks pass.

- [ ] Prove crash-safe recovery in disposable roots
  - Dependencies: [Implement the coordinated application backup and restore path](../backup-and-recovery/README.md)
  - Scope: write-gate timeout and concurrent mutation, interrupted publication,
    partial generation, database and durable-file corruption, path traversal,
    rollback, absent external credentials, restart, and reference verification

- [ ] Run and record a target-host restore drill
  - Dependencies: [Prove crash-safe recovery in disposable roots](../backup-and-recovery/README.md), [Implement and validate private deployment](../private-deployment/README.md)
  - Scope: restore a completed generation from a different encrypted device or
    failure domain into an empty root; verify filesystem rename/flush behavior,
    application and SQLite versions, recovery references, and a safe return to
    service without recording private identifiers or content
  - Promotion requirement: do not call backups operational until this drill
    passes; a database copy, design prototype, or Time Machine copy of the live
    root is not equivalent evidence

## Verification

Before implementation, name the command surfaces, affected mutation paths,
fixtures, target-host storage policy, and focused checks here. Follow
[repository validation](../../../AGENTS.md) and the complete ADR verification
matrix. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Private data and recovery boundary](../../../docs/decisions/0002-data-recovery.md)
- [Private deployment](../private-deployment/README.md)
- [Application foundation](../application-foundation/README.md)
