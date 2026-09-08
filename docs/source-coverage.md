# Source coverage matrix

**Status:** Completed evidence synthesis for `SRC-001`

**Evidence date:** 2026-09-08

This document compares the four independent source inspections without choosing
an import adapter. Source selection remains the responsibility of `SRC-002`.

Detailed reports:

- [Pi](sources/pi.md)
- [Hermes](sources/hermes.md)
- [Codex](sources/codex.md)
- [OpenRouter](sources/openrouter.md)

## Reading the matrix

- **Observed** means the capability was established from the installed or live
  environment without reading private conversation content.
- **Upstream** means the capability was established from versioned source or
  current official documentation, but not from a usable local installation.
- **Unknown** means the inspection did not have enough evidence. Unknown never
  means zero, unavailable, or unsupported.
- Every imported record must retain source, source version or schema evidence,
  observation time, and provenance. No adapter may flatten estimated and actual
  economics into the same field.

## Availability and evidence boundary

| Source | Local evidence | Version boundary | Account evidence |
| --- | --- | --- | --- |
| Pi | No installation observed | Upstream 0.85.1 | Unknown |
| Hermes | Local store | App 0.20.5 / schema 30 | Profile only |
| Codex | Installed and authenticated | CLI 0.129.0 | Private values not read |
| OpenRouter | Public API only | Live public schemas | No credential available |

The Hermes version distinction is material: the running application version and
state schema do not move in lockstep. The Codex report similarly separates the
installed generated schemas from newer official documentation. OpenRouter
account fields remain unknown because no authenticated request was made. Pi's
local behavior remains unknown because no installation was found.

## Identity and incremental import

### Pi

- **Primary local identity:** source installation, session ID, and entry ID.
- **Lineage:** append-only tree entries have parent IDs; branches must not be
  flattened into one linear transcript.
- **Incremental path:** RPC `get_entries` supports an entry cursor. Offline JSONL
  retains the last imported entry ID per session and parses new records; it does
  not treat byte offset as the canonical cursor.
- **Reconciliation:** detect truncation, rewrite, missing cursor, and session-file
  replacement, then perform a full rescan.
- **Provider bridge:** optional assistant `responseId` is the strongest candidate;
  RPC IDs and tool-call IDs are harness-local.

### Hermes

- **Primary local identity:** profile/source installation plus `sessions.id` and
  `messages.id`.
- **Lineage:** session parent/root/fork metadata and message ordering are stored.
- **Incremental path:** no first-party change cursor or deletion tombstone was
  observed. A message-ID watermark can reduce reads but is not sufficient alone.
- **Reconciliation:** periodically rescan sessions for mutable metadata, usage,
  rewinds, forks, and deletions; version-gate every schema capability.
- **Provider bridge:** canonical session storage has no generic provider request
  or response ID. Platform message IDs are optional and not billing IDs.

### Codex

- **Primary local identity:** source installation plus `Thread.id`.
- **Lineage:** `Thread.sessionId` groups threads in a session tree; it is not a
  unique thread key. Turn and item IDs provide finer local identity.
- **Incremental path:** `thread/list` provides opaque cursors and update ordering;
  `thread/read` hydrates selected threads. Installed experimental schemas also
  expose paginated `thread/turns/list`.
- **Reconciliation:** overlap recent pages and revisit archived or changed
  threads because cursor lifetime and deletion behavior are not guaranteed.
- **Provider bridge:** observed `response_id` may help, but its pass-through and
  billing semantics are unverified.

### OpenRouter

- **Primary provider identity:** the OpenRouter generation ID from the HTTP
  `X-Generation-Id` header and generation-detail `data.id`.
- **Protocol identity:** Responses and Messages may use body IDs such as
  `resp_...` and `msg_...`; preserve them separately with the interface.
- **Incremental path:** ordinary generations have no documented global cursor.
  Options are execution-time header capture, known-ID enrichment, overlapping
  30-day Activity imports, management Analytics windows, and batch cursors.
  Activity and stored-content lookup require a management key; ordinary keys
  can receive `403` and must not be treated as equivalent import credentials.
- **Reconciliation:** preserve generation ID, request ID, nullable upstream ID,
  session ID, provider, observed model, endpoint, and router evidence without
  collapsing them into one key. Supplying `session_id` is an execution choice
  because it can pin provider routing and alter caching/economics.
- **Provider bridge:** nullable `upstream_id` is the strongest direct provider
  cross-check when exposed.

## Usage and economics

| Capability | Pi | Hermes | Codex | OpenRouter |
| --- | --- | --- | --- | --- |
| Input/output tokens | Upstream | Observed | Observed | Public schema |
| Cache categories | Upstream | Observed | Observed | Public schema |
| Reasoning tokens | Upstream | Version gated | Observed | Schema |
| Media/search units | Unknown | Not generic | Item partial | Schema |
| Monetary cost | Estimated | Tagged | Not stored | Actual |
| Account balance | Unknown | Not applicable | Credits schema | Unknown |
| Rate limits | Provider | Provider | Installed | Unknown |

Interpretation rules:

1. OpenRouter generation metadata is the strongest candidate for actual provider
   cost, but authenticated account coverage was not inspected.
2. Pi's cost is derived from model metadata and must remain estimated.
3. Hermes can preserve cost provenance and estimate/actual status; its canonical
   data does not supply a universal provider request ID.
4. Installed Codex exposes token usage and rate-limit state, but no installed
   account-usage method or durable monetary-cost field was established. Its
   credits snapshot is current state, not spend history.
5. Overlapping totals and category details are alternative views, not additive
   facts. Adapters must not double-count them.

## Classification coverage

- **Pi:** no provider classification field was found. User labels and extension
  records are not provider metadata and need explicit classifier provenance if
  reused.
- **Hermes:** source, chat type, end reason, model/provider, and usage task are
  operational facets. No dedicated classifier identity, version, confidence, or
  user-label schema was observed.
- **Codex:** source kinds, review targets, sandbox modes, and rate-limit status
  are operational classifications, not a verified semantic task/provider
  taxonomy.
- **OpenRouter:** custom classifiers and classifier dimensions are documented,
  but workspace configuration, sampling, failures, per-generation extraction,
  and private historical coverage were not observed. Its public task-market API
  is sampled aggregate evidence, not account classifier history.

Derived classifications must retain origin, classifier/version, confidence, and
coverage. Missing classification is unknown, not an implicit category.

## Prompt and harness reconstruction

| Source | Historical prompt evidence | Exact replay status |
| --- | --- | --- |
| Pi | Messages plus some runtime surfaces | Incomplete |
| Hermes | Session prompt snapshots plus config layers | Incomplete |
| Codex | Rollout instructions, config, and items | Incomplete |
| OpenRouter | Opt-in or management-key capture | Incomplete |

None of the four sources establishes a complete replay package by itself. A
replay claim would also require tool definitions, skills, extension/plugin state,
model/provider routing, approvals, environment, files, artifacts, retries, and
harness version. Benchwarmer must label imported prompt evidence as partial and
must not infer absent components.

## Execution support

- **Pi:** upstream CLI print/JSON stream, RPC, SDK, and extensions; local execution
  is unavailable until an installation is discovered and version-gated.
- **Hermes:** local CLI/gateway/runtime surfaces exist, but execution must remain
  separate from read-only import and needs explicit approval and private output.
- **Codex:** installed `exec`, `review`, resume, and app-server thread/turn methods
  provide real execution surfaces with sandbox and approval controls.
- **OpenRouter:** synchronous completion-compatible routes and asynchronous batch
  execution exist; this inspection made no paid inference request.

Import capability is not replay capability. Read-only discovery must never
silently trigger paid or externally mutating work.

## Retention and deletion uncertainty

- **Pi:** versioned session files can be inspected offline, but the report did not
  establish a local retention policy because no installation was present.
- **Hermes:** installed defaults and current documentation conflict on pruning;
  effective private configuration was intentionally not inspected.
- **Codex:** current documentation distinguishes archive from deletion and
  describes a deletion schedule, while installed 0.129.0 lacks some newer
  lifecycle methods.
- **OpenRouter:** prompt/completion content is not retained by default. Opt-in
  logging and batch artifacts have documented but different retention behavior;
  ordinary metadata guarantees remain incomplete.

An importer must treat source disappearance as a reconciliation event, not proof
that Benchwarmer should delete its private snapshot. Product retention policy is
separate from source retention and requires explicit user controls.

## Overlap and reconciliation limits

The sources overlap on model identity, timestamps, token usage, and some form of
session or request grouping. That overlap can support confidence checks, but it
cannot currently support universal deterministic joins:

- Pi may retain a provider response ID, but it is optional.
- Hermes lacks a generic provider request/response ID in canonical storage.
- Codex exposes harness response IDs whose provider semantics are unverified.
- OpenRouter exposes generation, request, and upstream IDs but does not know the
  local harness session unless the caller captured or supplied that link.

Therefore the normalized model must preserve source-native identifiers and allow
zero or more explicit evidence links. It must not merge records solely by model,
timestamp, token total, title, or prompt similarity. Heuristic candidates need a
confidence label and user-visible provenance.

## Known gaps to carry forward

1. Pi must be inspected again if a local installation becomes available.
2. Hermes schema adapters need fixtures for each supported schema/version pair,
   including rewinds, forks, usage updates, and deletions.
3. Codex account/rate-limit coverage needs a privacy-preserving live probe before
   private account claims can become available.
4. OpenRouter account endpoints, historical coverage, and workspace scope need an
   authenticated read-only probe approved for a later task.
5. Cross-source provider-ID semantics need fixture evidence before automatic
   reconciliation is enabled.
6. Historical pricing is unavailable from current catalogs alone; price snapshots
   must be timestamped from first observation onward.
7. No source alone captures all prompt, tool, artifact, environment, and approval
   state required for exact replay.

## SRC-002 handoff

The first-adapter decision must score at least:

- local availability and privacy boundary;
- stable source-native identity;
- viable incremental import plus full-rescan recovery;
- schema/version compatibility strategy;
- fixture availability without private payloads;
- usage provenance and unknown-field handling; and
- user value from the sessions currently available.

`SRC-002` must record the choice and rejected alternatives in ADR 0004. This
matrix deliberately makes no selection.
