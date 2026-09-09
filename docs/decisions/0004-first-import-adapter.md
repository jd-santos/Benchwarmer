# ADR 0004: Select Hermes as the first import adapter

- Status: Accepted by `SRC-002` coordinator review
- Task: SRC-002
- Date: 2026-09-09

## Context and evidence

Benchwarmer needs one useful local source before it can prove source records,
private snapshots, incremental imports, activity views, and reconciliation. The
selection must use the completed [source coverage matrix](../source-coverage.md)
and its detailed source reports. It must not turn an upstream or unknown
capability into installed support.

[Hermes](../sources/hermes.md) is the richest locally observed source for the
first activity slice:

- One active profile has a canonical local `state.db` in WAL mode. Its schema
  version, tables, and columns were observed without reading private rows.
- A profile/database scope plus `sessions.id` and `messages.id` supplies stable
  local identities. The full `session_model_usage` primary key supplies a stable
  identity for each mutable usage aggregate.
- Message IDs are database-local, monotonic integers, so a committed message-ID
  watermark can reduce repeat reads. A consistent read transaction plus full
  key reconciliation covers limitations of that watermark.
- Observed session and usage tables contain input, output, cache-read,
  cache-write, and version-gated reasoning token counters. They also distinguish
  estimated and actual USD fields through cost status, source, and pricing
  provenance.
- Benchwarmer is intended to run beside Hermes. This source can provide locally
  useful session and usage history without an account API or a paid request.

The evidence also establishes constraints that the first adapter must expose:

- Hermes has no first-party change cursor, deletion tombstone, generic provider
  request ID, or general session `updated_at` field.
- The installed application is version 0.20.5 and declares schema 26, while the
  observed active profile and a newer source checkout use schema 30. Application
  and schema versions must be negotiated independently.
- Session metadata, usage counters, message flags, prompts, archive state, and
  other fields can change in place. A message watermark alone is incomplete.
- A zero `actual_cost_usd` is not a confirmed zero charge unless `cost_status`
  and `cost_source` establish that meaning.
- Rows and exports can contain complete conversations, prompts, reasoning, tool
  arguments and results, local paths, and account identifiers. No private values
  were inspected to make this decision.

## Decision

### Source and interface

Select **Hermes Agent read-only SQLite** as Benchwarmer's first import adapter.
The adapter reads the canonical profile-selected `state.db`; the JSONL export is
only a bounded bootstrap or recovery option because its filters do not form a
complete change cursor.

Each configured Hermes installation/profile becomes a distinct Benchwarmer
source scope with a private, stable internal source ID. The adapter records the
Hermes application version, observed schema version, capability/column manifest,
adapter version, observation time, and source provenance for every import batch.
The profile name and database path remain private configuration, not public
source identity.

The first supported target is the locally observed schema-30 capability set.
Support is granted only to an application/schema pair represented by sanitized
fixtures and an explicit capability manifest. Schema 26 is not assumed to match
schema 30 merely because installed 0.20.5 source declares it. An absent required
identity column fails closed. Additive unknown columns are retained in the
private raw snapshot and reported as not normalized; they do not silently gain
semantics.

The adapter is import-only. It must not call Hermes execution surfaces, migrate
or write `state.db`, inspect credentials, or use an older writable Hermes library
to open a newer store.

### Cursor and reconciliation semantics

The durable incremental cursor for one source scope is:

```json
{
  "schema_version": 30,
  "last_message_id": 102,
  "last_full_message_reconciliation_batch": "fixture-batch-001"
}
```

The values above are synthetic. `last_message_id` means the greatest
`messages.id` whose source row and private snapshot were committed to
Benchwarmer. It is scoped to exactly one Hermes installation/profile database.
It is not portable to another profile, a replacement database, or a restored
copy whose identity conflicts with prior observations.

For each normal import, the adapter must:

1. Open the source read-only and establish one consistent SQLite read
   transaction in WAL mode, or use SQLite's backup API to obtain an equivalent
   consistent source snapshot. Copying `state.db` alone while Hermes is writing
   is invalid because committed data may still be in the WAL.
2. Verify the schema capability manifest before reading private payloads.
3. Read messages where `id > last_message_id`. In the same source snapshot,
   reread and upsert all session and `session_model_usage` rows because those
   records are mutable and have no complete change cursor.
4. Publish changed raw payloads only under Benchwarmer's private snapshot root,
   then commit normalized upserts, coverage, provenance, and snapshot references
   in one import unit.
5. Advance `last_message_id` only after that import unit commits. A crash before
   commit leaves the old watermark, so retrying reads the same source rows and
   relies on duplicate keys rather than skipping data.

A scheduled full reconciliation rereads all message keys and mutable rows. It
detects edits, rewinds, compaction-flag changes, missing keys, source-side
session deletion, and a watermark that no longer exists. Detection does not
delete Benchwarmer's private snapshot. It records source presence and a
reconciliation outcome. A missing cursor, lower source maximum, schema change,
source replacement signal, or identity/payload conflict forces a full rescan or
fails for operator review rather than advancing the cursor.

The implementation task must choose and test the full-reconciliation interval;
the evidence does not establish a safe time-only interval. Reconciliation must
also run after an adapter/schema upgrade and on explicit user request.

### Duplicate keys and idempotency

Use these source-native duplicate keys:

- Session: `(source_scope_id, sessions.id)`.
- Message: `(source_scope_id, messages.id)`, with `messages.session_id` checked
  against the stored session relationship.
- Model/task usage: `(source_scope_id, session_id, model, billing_provider,
  billing_base_url, billing_mode, task)`.
  An empty source-native task remains `task=""` in this key; normalized display
  metadata is not a key component.
- Gateway route, if a later task imports it: `(source_scope_id, scope,
  session_key)`.

Titles, timestamps, model names, token totals, costs, workspace paths, and
platform message IDs are not session or message duplicate keys. A non-null
`platform_message_id` is transport-local evidence, not a provider billing ID.

An unchanged source row upserts to the same logical record and does not create a
second session, message, or usage observation. Changed mutable values update the
same source-native subject while the import batch and immutable private snapshot
preserve provenance. If an existing message key is later associated with a
different session or incompatible payload, the adapter records an integrity
conflict and stops automatic replacement.

### Explicit unavailable and unknown fields

The first adapter must publish field coverage with the import batch and expose
these limits rather than filling them with zero, an empty string, or an inferred
value:

- Generic provider request, response, generation, invoice-line, and idempotency
  IDs are unavailable in the observed canonical Hermes session schema.
- Per-request usage and cost are unavailable; Hermes usage is aggregated at
  session and model/provider/task scopes.
- For the following economics semantics, no dedicated canonical column was
  observed. That column-coverage finding does not establish that the semantic is
  unavailable or unsupported. Each value remains unknown:

  | Semantic | Observed canonical column | Value classification |
  | --- | --- | --- |
  | Currency beyond USD-named cost fields | None observed | Unknown |
  | Reporting time zone | None observed | Unknown |
  | Batch discount | None observed | Unknown |
  | Quota | None observed | Unknown |
  | Credits | None observed | Unknown |
  | Remaining capacity | None observed | Unknown |
  | Subscription period | None observed | Unknown |
  | Subscription payment | None observed | Unknown |

  `billing_mode` is present, but it does not establish batch-discount or
  subscription semantics.
- A dedicated semantic classification, classifier identity/version, confidence,
  and user-label schema was not observed.
- Complete effective prompts, hidden provider instructions, exact historical
  tool schemas, complete runtime state, and replay equivalence remain partial or
  unknown.
- Effective source retention, deletion history before first import, schema-30
  added-field semantics not established by fixtures, and exact provider
  reconciliation remain unknown.

Reasoning usage is present only when the negotiated schema capability supports
it. Cost fields remain raw observations with `cost_status`, `cost_source`, and
pricing version. An actual-cost numeric zero without confirming provenance stays
unknown for charge reporting.

### Private-data boundary

All source rows, IDs, paths, prompts, content, reasoning, tool data, account
metadata, and raw exports remain under the configured Benchwarmer data root from
ADR 0002. Files are published immutably under `snapshots/` before their database
references commit. Import logs contain only bounded operational status and must
not print source rows or private identifiers.

The repository contains only deliberately synthetic fixtures such as the trace
below. `hermes sessions export --redact` is secret scrubbing, not proof of
anonymization, so its output is still private by default.

## Sanitized import trace

Assume synthetic source scope `fixture-hermes-profile-a`, schema 30, and this
initial private source shape:

```text
session: sess-a
messages: (101, sess-a), (102, sess-a)
source usage primary key: (sess-a, model-a, provider-a,
                           https://example.invalid, fixture-mode, task="")
import duplicate key: (fixture-hermes-profile-a, sess-a, model-a, provider-a,
                       https://example.invalid, fixture-mode, task="")
normalized display metadata: task_display=main
usage values: input=10, output=4, actual_cost_usd=0,
              cost_status=unknown
```

`main` is only the synthetic fixture's normalized display for the source's empty
main-agent task value. The source-native key component remains `task=""`; `main`
is not a Hermes enum or a duplicate-key component.

### Initial import

The stored cursor is absent. The adapter reads message IDs 101 and 102, upserts
session key `(fixture-hermes-profile-a, sess-a)`, message keys
`(fixture-hermes-profile-a, 101)` and
`(fixture-hermes-profile-a, 102)`, and usage key
`(fixture-hermes-profile-a, sess-a, model-a, provider-a,
https://example.invalid, fixture-mode, task="")`. After the private snapshot and
normalized rows commit, the cursor becomes 102. There is one session, two
messages, and one usage aggregate. The zero actual-cost value is retained but
not reported as a confirmed zero charge.

### Unchanged re-import

The source maximum is still 102, so `id > 102` returns no messages. The session
scan and usage scan with `task=""` upsert the same keys with the same values. The
cursor stays 102; there is still one session, two messages, and one usage
aggregate. A no-change import batch may be recorded, but no source subject or
unchanged snapshot is duplicated.

### Appended data

Hermes appends synthetic message `(103, sess-a)` and updates the existing usage
row with `task=""` to `input=16, output=7` without changing its composite primary
key. The next consistent snapshot returns only message 103 from `id > 102`. Its
key is new; the session key is unchanged; and the usage upsert uses the same
empty-task duplicate key to update the existing logical aggregate instead of
inserting a second one. After commit, the cursor advances to 103. The result is
one session, three messages, and one usage aggregate.

A metadata-only rename would similarly update the existing session key while the
message cursor remains 103. A later full reconciliation that cannot find message
102 marks a source-side disappearance/conflict for review and retains the prior
private snapshot.

## Alternatives considered

### Codex app-server

Codex is the strongest second-source candidate. Installed 0.129.0 exposes stable
`Thread.id`, `thread/list` opaque pagination ordered by `updated_at`, and
`thread/read` hydration. That supported interface is less coupled to internal
storage than the Hermes SQLite choice.

It was not selected first because the installed app-server does not expose
`account/usage/read`, no durable monetary-cost field was established, live
account/rate-limit population was not inspected, and the provider meaning of a
local `response_id` is unverified. Cursor lifetime across restarts, concurrent
mutation, archive/delete, and upgrades is also not guaranteed. Codex should
follow Hermes to prove that normalization and reconciliation do not encode
Hermes-specific assumptions.

### Pi JSONL or RPC

Pi has a well-documented append-only tree, session/entry keys, and RPC entry
cursor upstream. It was not installed in the inspected environment, so its local
version, data, extensions, and behavior are unavailable. Selecting it first
would substitute upstream evidence for a usable local source and postpone the
first real import.

### OpenRouter

OpenRouter generation IDs are strong provider identities, and captured
`X-Generation-Id` values can support known-ID enrichment. No account credential
was available, however, and ordinary generations have no documented global
history cursor. Activity and Analytics need a management key and overlapping
window imports; their account/workspace and historical coverage remain
unverified. OpenRouter is provider evidence, not the richest accessible local
session source.

### Hermes JSONL export as the primary interface

The export is supported and useful for bounded bootstrap or recovery. It was not
selected as the main interface because its time filters have different session
start/activity semantics and cannot detect every metadata-only change. It also
has no continuation or change token. Direct read-only SQLite provides the
observed stable keys and usage aggregates needed by the first slice.

## Consequences

- The first activity slice can use existing local Hermes sessions and richer
  observed usage/cost provenance without a paid or account API request.
- The adapter is deliberately schema-gated and Hermes-specific. Domain models and
  services must not import it, and normalized records must not assume every
  source has Hermes aggregates or costs.
- Message ingestion is incremental, while mutable session/usage rows are reread
  and messages need scheduled full reconciliation. This is more source I/O than
  a complete change feed but is required by the observed mutation model.
- Source disappearance never proves that Benchwarmer should delete its durable
  private evidence.
- Private-data handling is part of importer correctness. Real source validation
  runs outside the checkout and reports only sanitized counts and pass/fail
  outcomes.
- Selecting an import adapter does not select a Hermes execution adapter or claim
  replay support.

## Unresolved questions

- Adapter fixtures must determine which schema-30 columns are required versus
  optional and whether schema 26 should become a separate supported capability
  manifest.
- Implementation must define the full-message reconciliation interval and a
  bounded operator-visible response to very large stores.
- Hermes exposes no observed immutable database-generation ID. Implementation
  must test source replacement and restore conflicts without deriving identity
  from a private path alone.
- Archive, source deletion, and retained Benchwarmer snapshots need user-visible
  terminology before activity/session UI work is complete.

## Verification

The sanitized trace above exercises the required state transitions:

```text
initial:   cursor absent -> 102; sessions=1; messages=2; usage=1
unchanged: cursor 102    -> 102; sessions=1; messages=2; usage=1
appended:  cursor 102    -> 103; sessions=1; messages=3; usage=1
```

The appended run inserts only message key 103 and updates the pre-existing usage
composite key whose final component is `task=""`. Cursor advancement happens
after commit; a retry before advancement replays the still-uncommitted key 103
safely through the same upsert.

Validate this record with:

```bash
npx -y markdownlint-cli2 docs/decisions/0004-first-import-adapter.md
git diff --check
git status --short
```
