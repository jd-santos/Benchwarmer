# ADR 0005: Push collection from personal Macs

- Status: Accepted by `COL-001`
- Task: COL-001
- Date: 2026-09-15

## Context and evidence

Benchwarmer histories live on personal Macs and in containers running on those
Macs. The first target sources are Codex, Pi, and Hermes. The central Mac mini is
always on, while laptops sleep frequently. The user wants all available history
backfilled and prefers little source-machine infrastructure. Three or four
collection attempts per day are sufficient if near-real-time capture would add a
larger service architecture.

The central installation remains authoritative. Browsing from other Macs uses the
private web interface over Tailscale. A native desktop application, offline
browsing, third-party cloud storage, and bidirectional application synchronization
are not required for collection.

The existing serving decision exposes one loopback-only application through
Tailscale Serve. Tailscale documents that Serve is tailnet-only, applies tailnet
access policy, strips spoofed identity headers, and can proxy to a localhost
service. Identity headers are not populated for tagged-device traffic. Tailscale
app-capability headers require newer clients and separate policy. Benchwarmer
therefore cannot treat Tailscale reachability or user identity alone as collector
enrollment.

Relevant sources checked on 2026-09-15:

- [Tailscale Serve](https://tailscale.com/kb/1312/serve)
- [Tailscale Serve examples](https://tailscale.com/kb/1313/serve-examples)
- [Apple timed job guidance](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html)

Apple documents that a `StartCalendarInterval` job missed while a Mac sleeps runs
when the Mac wakes. Multiple missed collection opportunities must still coalesce
into one non-overlapping collector run rather than replaying every schedule slot.
A powered-off Mac may wait until the next scheduled time, so the collector also
needs an explicit manual command.

## Decision

### One central library, no application sync

The Mac mini owns the Benchwarmer database, private native snapshots, normalized
records, search index, annotations, and browser interface. Source Macs push
capture batches to that installation over private Tailscale Serve HTTPS. They do
not receive a replica of the library.

The first browsing interface remains the central Svelte web application. A future
macOS wrapper may manage collection and display that interface, but native UI,
offline browsing, local library databases, merge conflict handling, and cloud
synchronization require a separate decision.

### One collector command per source Mac

Install one Benchwarmer collector on each approved Mac. It provides source
adapters rather than one daemon per tool:

```text
benchwarmer collect codex
benchwarmer collect pi
benchwarmer collect hermes
benchwarmer collect --all
```

The command names are the intended interface shape, not an implemented CLI. An
adapter runs only when its source kind and local location are explicitly
configured. The collector does not scan arbitrary home directories, Docker
volumes, or running containers. Container data must be exposed through an
operator-approved read-only host mount. The collector does not receive the Docker
socket or use `docker exec` to discover private data.

Collectors are read-only toward source histories. They must not resume sessions,
execute captured commands, load source execution credentials, migrate source
databases, or modify source retention. Live SQLite inputs require a consistent
read transaction or the SQLite backup API; copying a database file without its
WAL state is invalid.

Hermes remains the first implemented adapter. Codex and Pi use the same collector
protocol when their source adapters are implemented, without pretending their
native capabilities or cursors are identical.

### Manual first, scheduled second

The initial collector is an explicit command. This provides observable backfill,
configuration, failure, and retry behavior before installing background work.

After the manual path passes its collection tests, an optional per-user
`launchd` job runs the same command three or four times per day. It uses
`StartCalendarInterval`, prevents overlapping runs, and does not wake a sleeping
laptop solely for collection. A missed sleep interval may run after wake, but the
service makes no near-real-time freshness promise. Manual collection remains
available.

The first release has no source-machine listener, file watcher, persistent
collector daemon, or remote shell access. Updates to the collector are explicit
until a later packaging decision defines installation, signing, and upgrades.

### Enrollment and authorization

Each source Mac is manually enrolled from the private Benchwarmer interface. A
short-lived, single-use enrollment credential is exchanged for a random,
device-scoped collector credential. The device credential is stored in macOS
Keychain; the central service stores only the material needed to verify it. It is
sent only through the private Tailscale Serve HTTPS origin.

Enrollment records an opaque device ID and allowed source kinds. Source paths,
profile names, account identifiers, and hostnames remain private configuration
and are not stable source identities. Every configured source installation or
profile receives its own opaque source-scope ID.

Both layers are required:

1. Tailnet policy restricts which identities or devices can reach the private
   Benchwarmer origin.
2. Benchwarmer validates the active device credential, device status, source
   kind, source scope, protocol version, and configured allowlist for every
   ingestion request.

Tailscale identity or app-capability headers may later support audit or narrower
policy, but they are not the sole ingestion credential in this decision. The API
continues to trust proxy headers only from its loopback Serve proxy.

Revocation immediately blocks new enrollment renewal and batch acceptance for the
device. Re-enrollment issues a new credential. Revocation does not delete already
accepted evidence. Removing the local Keychain item and collector configuration
is a separate source-machine action.

### Backfill, spooling, and acknowledgment

The collector eventually backfills all available records from each configured
source. It processes bounded chunks rather than constructing one unbounded
archive. The implementation plan must set explicit per-batch record, byte, and
run-time ceilings before live use.

For each chunk, the collector:

1. Reads one consistent source view and records adapter/source capability data.
2. Writes an immutable private batch to an owner-only local spool outside the
   checkout.
3. Sends a versioned envelope containing opaque device/source IDs, batch and
   sequence IDs, capture time, adapter version, content digests, and payload.
4. Retains the spool entry until the central service durably commits its native
   snapshot, normalized import unit, and receipt record.
5. Deletes the local entry only after a matching durable acknowledgment.

No response, an interrupted request, or an uncertain result causes the same batch
to be retried. Central batch identity, content digests, and source-native keys
make duplicate delivery idempotent. An acknowledgment never means merely that
bytes reached an HTTP handler.

The spool has a configured size ceiling. When full, collection stops with a
bounded operational error and retains unacknowledged batches. It never drops old
private data to make room. The source history remains the fallback for a later
rescan, but the collector does not assume the source will retain it forever.

### Retention and content boundary

The central private data root retains accepted native snapshots and normalized
records indefinitely by default. Source deletion is recorded as an observation
and does not propagate as central deletion. Any future selective deletion or
retention limit needs an explicit operator action and a separate policy.

The first collector payload includes available messages, reasoning, tool calls
and results, source metadata, provenance, and coverage. It does not copy arbitrary
attachments, workspaces, repositories, or generated artifacts. Oversized,
unsupported, redacted, or unavailable attachments are recorded as explicit
coverage gaps. Exact batch and attachment metadata limits belong in the
implementation plan and must fail closed without printing private values.

Source paths, spool contents, credentials, payloads, and private identifiers never
enter repository fixtures or ordinary logs. Synthetic fixtures cover protocol and
failure behavior. Secret scrubbing is not anonymization.

### No implicit model work

Collection performs deterministic capture, validation, normalization, and
index-maintenance work only. Backfill, scheduled runs, retries, or collection
growth do not authorize enrichment, embeddings, reruns, judges, or simulations.
Those operations remain subject to an exact model-work approval.

## Alternatives considered

### Central pull over SSH or shared files

Rejected. Sleeping laptops make central polling unreliable, and remote login or
shared-volume access gives the central host broader source-machine access than
collection needs. It also makes source availability and credentials part of the
central service.

### Manual archive copying only

Rejected as the durable protocol. Hand-copied exports minimize installed software
but provide weak incremental cursors, acknowledgments, idempotency, and error
recovery. The selected manual CLI keeps explicit operation while using the same
protocol that later scheduling needs.

### One service per source tool

Rejected. It multiplies installation, credentials, logs, update paths, and failure
modes. One collector process with source-specific adapters keeps those differences
without one daemon per application.

### Near-real-time watchers or a permanent source daemon

Deferred. They add long-running source-machine processes, wake/sleep edge cases,
and file-change semantics before the scheduled path proves useful. The same push
protocol can support a watcher later if measured freshness requires it.

### Native desktop application and library synchronization

Deferred. The private browser already works across the tailnet. Offline replicas
would add local database lifecycle, synchronization, conflict resolution, signing,
and update work unrelated to reliable collection.

## Consequences

- Each participating Mac needs the collector package, local private configuration,
  a Keychain credential, and temporary spool storage.
- The source Mac initiates outbound application traffic; it exposes no collector
  listener and grants no remote shell or Docker access.
- Initial all-history backfill may require many bounded runs. Progress and coverage
  must remain visible without claiming a single-run completion.
- Sleeping laptops may be stale until wake or manual collection. The Mac mini and
  browser interface remain available independently.
- The central data root grows without an automatic retention cutoff. Capacity and
  backup monitoring must account for native snapshots.
- Manual and scheduled collection share one protocol, cursor, spool, and test
  surface. Adding `launchd` does not create a second importer.
- Browsing requires tailnet connectivity. There is no offline desktop library or
  third-party cloud copy.

## Unresolved questions

`COL-002` must decompose implementation into bounded protocol, enrollment,
collector, and scheduling tasks. Those plans must pin:

- versioned request and acknowledgment schemas;
- per-batch record, byte, duration, and spool ceilings;
- attachment metadata limits and coverage states;
- credential expiry or rotation behavior;
- collector packaging, signing, updates, and exact `launchd` intervals;
- source-specific cursor and consistent-read behavior for Codex, Pi, and Hermes;
- sanitized status fields and operational error codes; and
- central capacity warnings and explicit deletion tooling.

These parameters may narrow resource use but cannot change push ownership,
durable acknowledgment, indefinite central retention, explicit allowlists, or the
no-sync boundary without replacing this decision.

## Verification

Before implementing transport, compare its plan with the collection gate in
[conversation-library.md](../conversation-library.md). Synthetic tests must cover:

- manual enrollment, expired single-use enrollment, credential rotation, and
  revoked devices;
- allowed and disallowed source kinds/scopes;
- initial chunked backfill and incremental capture;
- interrupted upload, duplicate delivery, digest conflict, and acknowledgment
  only after durable commit;
- spool retention before acknowledgment, deletion afterward, and fail-closed
  behavior at its size ceiling;
- sleeping/offline catch-up, non-overlapping scheduled runs, and manual fallback;
- consistent reads of live SQLite fixtures;
- unsupported or oversized attachment coverage; and
- bounded logs and errors that contain no payloads, private paths, credentials,
  or supplied private identifiers.

Operational rollout also requires `DEP-003`: verify private Tailscale Serve HTTPS,
no Funnel or published application port, restricted tailnet policy, revoked-device
rejection, source-host sleep/retry behavior, and central restart recovery. Keep
hostnames, policy principals, paths, credentials, identities, and raw responses
out of committed verification records.
