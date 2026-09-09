# Source: Hermes Agent

- Task: SRC-HERMES-001
- Observed version/account scope: Docker-installed Hermes Agent 0.20.5
  (`2026.8.19`, upstream `987064ca`); schema-only inspection of one active
  named profile; separate clean source checkout 0.21.0 at `693641aa8b4359c6`
- Inspected: 2026-09-08

## Evidence boundary

No conversation, prompt, configuration, credential, account-identifier, or raw
provider-response values were read. The active profile database was opened
read-only only to inspect `schema_version`, `PRAGMA journal_mode`, table names,
and column names. No row counts or content rows were queried.

Evidence labels used below:

- **E1 — installed command surface:** observed `hermes --version`, top-level
  `--help`, and help for `sessions`, `sessions list`, `sessions export`,
  `sessions prune`, `sessions archive`, `profile`, `cron`, `webhook`, `acp`,
  `serve`, and `gateway` in the installed environment.
- **E2 — installed source:** inspected `pyproject.toml`,
  `hermes_state_common.py` (`SCHEMA_SQL`), `hermes_state.py` (usage,
  persistence, pruning), `hermes_state_portability.py` (listing/export),
  `hermes_state_schema.py`, `hermes_cli/config_defaults.py`, and
  `tui_gateway/server.py` without opening user data.
- **E3 — live schema:** a read-only schema query observed WAL mode and schema
  version 30. The relevant tables were `system_prompts`, `sessions`,
  `messages`, `session_model_usage`, and `gateway_routing`.
- **E4 — newer checkout:** `git rev-parse HEAD`, `pyproject.toml`, and
  `hermes_state_common.py` in the separate checkout reported 0.21.0, commit
  `693641aa8b4359c602283bdbbc14041e03bc47bc`, and schema version 30.
- **E5 — official documentation:** [Sessions], [Profiles], the [documentation
  index], and its links to [Programmatic Integration], [Cron Jobs], and
  [Webhooks]. These pages describe current upstream behavior and are not
  assumed to be identical to the installed 0.20.5 build.

The installed code declares schema version 26, while the active database and
newer checkout are at version 30. Therefore this report treats E1/E2 as the
installed execution contract, E3 as the observed storage contract, and E4/E5
as newer evidence that must be version-gated rather than silently combined.

[Sessions]: https://hermes-agent.nousresearch.com/docs/user-guide/sessions
[Profiles]: https://hermes-agent.nousresearch.com/docs/user-guide/profiles
[documentation index]: https://hermes-agent.nousresearch.com/docs/llms.txt
[Programmatic Integration]: https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[Cron Jobs]: https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
[Webhooks]: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks

## Session and request identity

- A profile is a separate Hermes home. Its canonical conversation store is
  `$HERMES_HOME/state.db`; named profiles have their own config, secrets,
  memory, skills, cron state, and database. The default and named-profile
  stores must be imported as separate source scopes. **Evidence: E3, E5
  Profiles.**
- `sessions.id` is the primary session identifier. Current documentation gives
  `YYYYMMDD_HHMMSS_<hex>` as the normal shape, with six random hex characters
  for CLI/TUI and eight for gateway sessions; installed TUI source constructs
  a local-clock timestamp plus six UUID-derived hex characters. Treat the ID
  as opaque, and namespace it by Hermes installation/profile when importing.
  **Evidence: E2 `tui_gateway/server.py::_new_session_key`; E3; E5 Sessions.**
- `parent_session_id` links continuation segments created by compression.
  Titles are human-readable and unique when non-null, but can be generated,
  renamed, and suffixed across lineage; they are not durable import keys.
  **Evidence: E2 `SCHEMA_SQL`; E5 Sessions.**
- Gateway identity is represented by `session_key` on `sessions` and by the
  composite primary key `(scope, session_key)` in `gateway_routing`, whose row
  also has `updated_at`. Session rows can additionally contain source,
  user/chat/thread fields and `origin_json`. Those fields may contain account
  identifiers and must remain private. **Evidence: E2 `SCHEMA_SQL`; E3.**
- `messages.id` is an autoincrementing database-local integer and
  `messages.session_id` is the session foreign key. Message timestamps and
  `sessions.started_at`/`ended_at` are Unix epoch `REAL` values; message order
  should use `(timestamp, id)` or the monotonic `id` within one database.
  **Evidence: E2 `SCHEMA_SQL`; E5 Session Storage via the documentation
  index.**
- `messages.platform_message_id` optionally preserves an external messaging
  identifier and installed source defines a session-scoped uniqueness index
  for non-null values. It is useful for gateway-message deduplication but is
  neither present for every source nor a provider inference request ID.
  **Evidence: E2 `hermes_state_schema.py` and
  `hermes_state.py::has_platform_message_id`; E3.**
- No generic inference request/response ID column or request table was observed.
  `api_call_count` is a count, not identity. **Evidence: E2 `SCHEMA_SQL`; E3.**

Deletion and retention are source mutations rather than immutable history:
`sessions delete` removes a session and its messages; `archive` is a soft-hide;
and compression retains old segments rather than acting as a privacy delete.
Pinned rows are keep-marked and excluded from ordinary prune unless explicitly
included. **Evidence: E1; E2 pruning methods; E5 Sessions.**

## Incremental import

No first-party change cursor, deletion tombstone, or change-data-capture feed
was observed. `sessions list` exposes source, workspace, and limit filters but
not a machine-readable cursor. JSONL export supports session ID and time/filter
windows, but no cursor token or continuation token. **Evidence: E1.**

A practical importer can use these keys:

- **Session**
  - **Idempotent key:** installation/profile scope + `sessions.id`
  - **Incremental signal:** rescan sessions changed by observed activity
  - **Limitation:** no general `updated_at`; rename, pin/archive,
    prompt/config, usage, end-state, and deletion can change in place
- **Message**
  - **Idempotent key:** database scope + `messages.id`
  - **Incremental signal:** `id > last_message_id` in one store
  - **Limitation:** edits, compaction flags, rewinds, and deletes require
    reconciliation
- **Model/task usage**
  - **Idempotent key:** scope + full `session_model_usage` primary key
  - **Incremental signal:** `last_seen` plus row reread
  - **Limitation:** counters are updated in place; deleted rows have no
    tombstone
- **Gateway route**
  - **Idempotent key:** scope + `gateway_routing.scope` + `session_key`
  - **Incremental signal:** `updated_at`
  - **Limitation:** routing metadata is not a transcript cursor and contains
    private identifiers

**Evidence for the import keys: E2 `SCHEMA_SQL`, usage update methods, and
pruning methods; E3.**

Use a read transaction against SQLite in WAL mode (or SQLite's backup API) so
related tables come from one consistent snapshot. Copying only `state.db` while
a writer is active can omit committed WAL content. Advance the message
watermark only after committing the private Benchwarmer snapshot. Periodic full
key reconciliation is still required for in-place updates and source-side
deletions. **Evidence: E3 observed WAL mode; E5 Sessions documents WAL and
concurrent readers.**

Export filters are useful for bounded bootstrap or recovery, not a sound change
watermark: `--after`/`--before` filter session start, while
`--newer-than`/`--older-than` filter activity, and a metadata-only change need
not advance either. JSONL export emits one complete session object with its
messages per line and may include active sessions when unfiltered. **Evidence:
E1; E5 Sessions.**

## Usage and economics

The `sessions` aggregate and `session_model_usage` rows expose:

- input, output, cache-read, cache-write, and reasoning token counters;
- API call count;
- model, billing provider, billing base URL, and billing mode;
- estimated and actual cost fields denominated by field name in USD;
- cost status, cost source, and (on the session aggregate) pricing version; and
- per-model/task `first_seen` and `last_seen` timestamps.

**Evidence: E2 `SCHEMA_SQL` and
`hermes_state.py::_record_model_usage`; E3.**

`session_model_usage` is keyed by `(session_id, model, billing_provider,
billing_base_url, billing_mode, task)`. The empty task denotes the main agent
loop; named tasks represent auxiliary work such as vision, compression, or
title generation. This table is better than the single session model/provider
columns when a session switches route. **Evidence: E2
`hermes_state.py::_record_model_usage`.**

Important limits:

- Usage is aggregated per session and per model/provider/task, not preserved as
  one record per API request. Message `token_count` is nullable and does not
  supply a complete request ledger. **Evidence: E2 `SCHEMA_SQL`; E3.**
- `session_model_usage.actual_cost_usd` is non-null with a zero default, while
  the session-level field is nullable. A zero must not be interpreted as a
  confirmed zero charge unless `cost_status` and `cost_source` establish that
  provenance. **Evidence: E2 `SCHEMA_SQL` and usage upsert code; E3.**
- No dedicated currency, reporting-time-zone, batch-discount, quota, credit,
  subscription-period, or remaining-capacity column was observed in these
  tables. `billing_mode` is present, but no stable enum proving batch or
  subscription semantics was observed. Preserve these as unknown, not zero.
  **Evidence: E2 `SCHEMA_SQL`; E3.**
- Cost and token fields describe what Hermes recorded. Without a provider
  request ID they cannot by themselves prove a one-to-one match with provider
  billing records. **Evidence: E2; E3.**

## Classification and prompt visibility

- `source`, `chat_type`, `end_reason`, model/provider fields, and usage `task`
  provide operational facets. No dedicated classification/label table,
  classifier identity/version, confidence, or user-label field was observed in
  the session schema. **Evidence: E2 `SCHEMA_SQL`; E3.**
- Sessions store `model_config` and a Hermes system-prompt snapshot. Installed
  schema deduplicates prompt bodies in `system_prompts(hash, prompt)` and links
  them through `sessions.system_prompt_hash`, while retaining the legacy
  `sessions.system_prompt` column. Prompt bodies are private artifacts even
  when a hash exists. **Evidence: E2 `SCHEMA_SQL`, `_store_system_prompt`, and
  `_system_prompt_hash`; E3; E5 Sessions.**
- Messages retain roles, tool names/calls/results, finish reason, optional
  reasoning fields, and `api_content` when the API-facing message differs from
  ordinary content. These fields can contain highly sensitive material and
  were not inspected. **Evidence: E2 `SCHEMA_SQL`; E3.**
- Profile `config.yaml`, context/rule files, skills, and invocation overrides
  are locally visible configuration layers. The installed CLI exposes model,
  provider, reasoning, toolset, skill, safe-mode, ignore-config, and
  ignore-rules overrides. Requested configuration must be captured separately
  from observed session metadata. **Evidence: E1; E5 Profiles and the
  documentation index's Prompt Assembly link.**
- The stored snapshot does not establish provider-side hidden instructions,
  the exact tool schemas sent on every call, every ephemeral injection, or the
  complete effective provider request. Those remain partial/unknown unless a
  future version exposes a sanitized effective-request trace. **Evidence:
  explicit unknown; E5 Sessions distinguishes stored history from each turn's
  selected prompt and injected content.**

The schema-30 profile also contains newer columns such as `tool_names` and
`_compressed_summary` that are absent from the installed 0.20.5 declared
schema. Their semantics must be gated to schema 30/current source and not
backported by assumption. **Evidence: E2; E3; E4.**

## Import and execution support

### Read/import interfaces

1. **Read-only SQLite:** richest local source for normalized metadata,
   messages, prompts, usage, lineage, and routing. Open the profile-selected
   `$HERMES_HOME/state.db` read-only and preserve a transactionally consistent
   private snapshot. **Evidence: E2; E3; E5 Sessions/Profiles.**
2. **`hermes sessions export --format jsonl`:** supported machine-readable
   export of complete session objects, with session/time/source/model/provider
   filters. `--redact` scrubs recognized secrets, but it is not a general
   de-identification guarantee. **Evidence: E1; E5 Sessions.**
3. **Session list/search:** CLI listing, dashboard session APIs, and the
   `session_search` tool are useful for interactive discovery. They are not a
   documented bulk incremental feed. **Evidence: E1; E5 Sessions.**
4. **Legacy files:** current documentation says old per-session JSONL files are
   no longer written or read; `state.db` is canonical. The gateway
   `sessions.json` file is a backward-compatibility routing mirror, not the
   session list. **Evidence: E5 Sessions.**

### Automation/execution interfaces

The installed build separately exposes:

- script-oriented one-shot execution with `hermes -z`, including an optional
  JSON `--usage-file` written even on failure;
- ordinary chat/query execution, resume/continue, toolset/model/provider/
  reasoning overrides, and isolated git-worktree mode;
- a headless `serve` JSON-RPC/WebSocket backend for desktop and remote clients;
- ACP server mode for compatible editors;
- scheduled cron jobs with durable attempt history;
- event-triggered webhook subscriptions and messaging-gateway runs; and
- upstream-documented OpenAI-compatible HTTP API, TUI gateway JSON-RPC, Python
  library embedding, delegation, and batch surfaces.

**Evidence: E1; E5 Programmatic Integration, Cron Jobs, Webhooks, and the
documentation index.**

These are execution surfaces, not replay guarantees. `--resume` continues a
stored conversation with current runtime/provider state; importing or reading a
session does not prove Hermes can reproduce its original environment, hidden
provider behavior, tool versions, permissions, or exact request stream.
Benchwarmer should create a fresh, disposable fixture workspace and explicit
profile/configuration snapshot for every tool-capable trial. **Evidence: E1;
explicit limitation from the observed absence of a replay protocol.**

## Reconciliation identifiers

Strong local keys are:

- Hermes installation/profile scope + `sessions.id`;
- profile/database scope + `messages.id` (and `session_id` for validation);
- the full `session_model_usage` composite primary key; and
- for gateway events only, platform/source plus optional
  `platform_message_id`, or private `(scope, session_key)` routing identity.

**Evidence: E2 `SCHEMA_SQL` and schema indexes; E3.**

Model, billing provider/base URL/mode, task, timestamps, token totals, and costs
can support heuristic comparison with provider records. They are not exact
request reconciliation keys. No generic provider request ID, response ID,
generation ID, idempotency key, invoice line ID, or provider usage-record ID
was observed in the canonical session/usage schema. **Evidence: E2; E3.**

Provider-specific opaque message fields may contain additional identifiers for
some transports, but their coverage and stability were not inspected and they
must not be treated as a cross-provider contract. **Evidence: explicit
unknown; E2 provider-specific message columns.**

## Unknowns and risks

- **Mixed-version store:** installed 0.20.5 declares schema 26, but the active
  profile and separate 0.21.0 checkout are schema 30. A Benchwarmer adapter
  must record Hermes version, observed schema version, and column capability
  per import; it must not open the database through an older writable Hermes
  library. **Evidence: E1–E4.**
- **Effective retention is unknown:** the installed 0.20.5 defaults declare
  session `auto_prune: false` and `retention_days: 90`, but the current official
  Sessions page contains conflicting statements that auto-prune is both on and
  disabled by default. The active profile's private config was intentionally
  not read. Import coverage must report the effective setting as unknown until
  queried with user approval. **Evidence: E2
  `hermes_cli/config_defaults.py`; E5 Sessions.**
- **Deletion gap:** pruning/deletion has no observed tombstone or durable change
  sequence, so incremental imports need periodic reconciliation and must retain
  their own private snapshots. **Evidence: E1; E2.**
- **Mutable aggregates:** usage, titles, end state, archive/pin state, prompts,
  and some message flags update in place. A message-only high-water mark is
  insufficient. **Evidence: E2.**
- **Cost ambiguity:** actual-cost zero can mean an unpopulated aggregate;
  currency/time-zone, quota, credit, subscription, and batch semantics are not
  complete in the session store. **Evidence: E2; E3.**
- **No exact provider join:** without persisted request identifiers,
  harness/provider reconciliation is heuristic and overlapping totals must not
  be summed until matched. **Evidence: E2; E3.**
- **Privacy:** raw SQLite rows and JSONL exports can contain full messages,
  system prompts, reasoning, tool arguments/results, local paths, and account
  identifiers. `--redact` is secret scrubbing, not proof of anonymization.
  Store imports only inside Benchwarmer's private data boundary and never log
  or commit payloads. **Evidence: E2 schema; E5 Sessions.**
- **Source evolution:** schema 30 adds fields not declared by installed 0.20.5.
  Pin and test importer behavior against sanitized fixtures for each supported
  schema/version, and preserve unknown columns in a private raw snapshot rather
  than silently discarding them. **Evidence: E2–E4.**
