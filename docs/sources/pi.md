# Source: Pi

- Task: SRC-PI-001
- Observed version/account scope: No Pi executable, process, global npm package,
  default agent directory, default session directory, or Pi directory override was
  available in the inspected environment. The installed version and account scope
  are therefore unavailable. Upstream package/docs source was inspected at
  `@earendil-works/pi-coding-agent` 0.85.1, commit
  `b2602be77cb7b0de45dd616407fd210daa48aa75`.
- Inspected: 2026-09-08

## Evidence boundary

The live check was deliberately metadata-only. It did not inspect credentials,
prompt bodies, session text, account identifiers, or raw provider payloads. These
sanitized checks all returned unavailable/absent:

```text
command -v pi                                      -> exit 1 (not on PATH)
pgrep -x pi                                        -> exit 1 (no process)
test -d "$(npm root -g)/@earendil-works/pi-coding-agent"
                                                    -> exit 1 (not installed globally)
test -n "${PI_CODING_AGENT_DIR+x}"                 -> exit 1 (unset)
test -n "${PI_CODING_AGENT_SESSION_DIR+x}"         -> exit 1 (unset)
test -d "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"  -> exit 1 (absent)
test -d "$HOME/.pi/agent/sessions"                 -> exit 1 (absent)
```

Consequently, no claim below is a claim about the user's installed Pi build or
account. Capability claims come from Pi's official documentation and the pinned
upstream TypeScript source. `npm view @earendil-works/pi-coding-agent version`
returned `0.85.1`; `git ls-remote https://github.com/earendil-works/pi.git HEAD`
returned the commit above. [E1] [E2]

Evidence references used throughout this report:

- [E1]: the sanitized live checks recorded above.
- [E2]: [package manifest at the inspected commit][package-manifest].
- [E3]: [official session-format documentation][session-format].
- [E4]: [official sessions documentation][sessions].
- [E5]: [official RPC documentation][rpc].
- [E6]: [official JSON event-stream documentation][json-events].
- [E7]: [official settings documentation][settings].
- [E8]: [official custom-model documentation][models].
- [E9]: [official SDK documentation][sdk].
- [E10]: [official extensions documentation][extensions].
- [E11]: pinned [`pi-ai` message and usage types][ai-types].
- [E12]: pinned [session manager source][session-manager].
- [E13]: pinned [agent session source][agent-session].
- [E14]: pinned [resource loader][resource-loader] and
  [system-prompt builder][system-prompt] sources.

## Session and request identity

Pi's documented current session format is version 3 JSONL. The first record is a
header with `type`, `version`, `id`, `timestamp`, `cwd`, and optional
`parentSession`; subsequent records form a tree through `id` and `parentId` and
carry ISO timestamps. Message objects also carry Unix-millisecond timestamps.
The session manager defaults the header ID to a UUIDv7. Entry IDs are generated
as collision-checked eight-character UUID prefixes, with a full UUID fallback.
`cwd` and `parentSession` are private path-bearing fields and must be normalized
or retained only in private storage. [E3] [E11] [E12]

A safe structural example, with no real values, is:

```json
{"type":"session","version":3,"id":"<session-id>","timestamp":"<ISO-8601>","cwd":"<redacted>"}
{"type":"message","id":"<entry-id>","parentId":null,"timestamp":"<ISO-8601>","message":{"role":"user","content":"<redacted>","timestamp":0}}
```

The session ID and `(session ID, entry ID)` are the strongest harness-local keys.
Entry IDs are unique only within the session manager's in-memory index, so imports
should not treat an entry ID alone as globally unique. `parentId`, `targetId` on
label records, `fromId` on branch summaries, and optional `parentSession` express
intra-session or session-lineage relationships. A display name is represented by
an append-only `session_info` entry, not by replacing the header. [E3] [E12]

Documented entry types include `message`, `model_change`,
`thinking_level_change`, `compaction`, `branch_summary`, `custom`,
`custom_message`, `label`, and `session_info`. Message roles include user,
assistant, tool result, direct bash execution, custom, branch summary, and
compaction summary. Extension `custom` data and tool `details` are open-ended and
must be treated as untrusted, potentially private payloads. [E3] [E11]

Sessions are local files. The session picker supports confirmed deletion and uses
the platform `trash` command when available; direct file deletion is also
supported. The reviewed core documentation names no automatic expiry period, so
retention duration, Trash retention, external cleanup extensions, backups, and
source-log deletion status remain unknown. [E3] [E4] [E7]

## Incremental import

The format is designed as an append-only tree: normal appends add a JSONL record
and do not modify or delete earlier entries. Branches remain in the same file,
and the active leaf selects one path without erasing abandoned branches. A full
import therefore needs all entries, not only the context returned for the active
branch after compaction. [E3] [E12]

For an active RPC process, `get_entries` returns entries in append order and
accepts `since: <entry-id>`. The documented contract returns only records strictly
after that ID, rejects an unknown cursor, and also returns `leafId`. This is the
best documented incremental cursor for one open session. RPC command `id` values
correlate commands and responses but are not session-entry or provider-request
IDs. [E5]

For offline files, use the header session ID plus entry ID as the duplicate key,
and retain the last imported entry ID per session. Scan for new session files,
then parse new records; if the stored cursor disappears, the file shrinks, the
header ID changes, or parsing sees a legacy version, fall back to a full parse and
deduplicate by `(source, session_id, entry_id)`. This fallback is required because
loading legacy versions can migrate and rewrite a complete file even though
normal current-version writes append. A newly started persisted session is not
materialized until an assistant message is present, so discovery based only on
files can lag session creation. [E3] [E12]

The SDK exposes `SessionManager.open`, `list`, and `listAll`; RPC exposes only the
currently attached session plus explicit `switch_session`. JSON event-stream mode
is useful for live capture but is not a historical listing API. Ordering is file
append order; timestamps should be retained as observations, not used as a unique
cursor. [E5] [E6] [E9] [E12]

Labels and session names are append-only changes whose latest record determines
current display state. Importers should retain their revision records rather than
updating earlier entries in place. Compaction changes active context but does not
remove pre-compaction records from the full session file. [E3] [E12]

## Usage and economics

At the individual assistant-message/request level, the pinned `Usage` type exposes
`input`, `output`, `cacheRead`, `cacheWrite`, optional `cacheWrite1h`, optional
`reasoning`, `totalTokens`, and `cost.{input,output,cacheRead,cacheWrite,total}`.
`reasoning` is explicitly a subset of `output` and must not be added to it.
`cacheWrite1h` is explicitly a subset of `cacheWrite`. Assistant messages also
carry `api`, `provider`, requested `model`, optional routed `responseModel`,
optional provider-native `providerThinkingLevel`, optional `responseId`, stop
reason, and timestamp. [E11]

Tool-result messages may contain their own nested `usage`. Compaction and branch
summary entries may also contain usage. Pi's session statistics intentionally sum
assistant, nested tool, compaction, and branch-summary usage over all entries,
including compacted and abandoned history. Importing both per-entry observations
and session totals is useful for audit, but those two scopes overlap and must not
be added together. [E3] [E5] [E13]

Pi model records carry per-million-token price metadata for input, output, cache
read, and cache write, with optional input-size tiers. The harness calculates the
stored cost fields from that model metadata. Therefore Benchwarmer should ingest
Pi cost as a harness-side estimate with the model/pricing snapshot and capture
time, not as proof of an actual provider charge. The usage schema has no currency
field; the official model documentation describes its rates as USD, but custom or
stale model metadata still needs provenance. [E8] [E11] [E13]

The reviewed session/RPC schemas expose no actual invoice charge, subscription
payment, account total, quota/rate-limit consumption, credits, balance, tax, or
billing time-zone fields. They also expose no general latency field or explicit
batch-discount flag. A deferred handle can carry a provider token such as a
response ID or batch/row ID, but that is not a billed-usage classification.
Account-level economics and actual-vs-estimated reconciliation are unavailable
from the inspected Pi schema and require a provider source. [E5] [E11]

## Classification and prompt visibility

No provider classification field is present in the reviewed session/message
schemas. Pi `label` entries are user-defined tree bookmarks, while extension
`custom` and `custom_message` records are arbitrary extension data; none should
be silently reclassified as provider metadata. Any useful classification derived
from those fields needs explicit origin and classifier provenance. [E3] [E11]

Prompt and configuration visibility is substantial at runtime but is not captured
as a complete session snapshot. The source-defined prompt builder combines a Pi
base or replacement prompt, an appended prompt, selected tool guidance, project
context files, skills, and current working directory. The resource loader exposes
loaded context files, skills, prompt templates, system-prompt content/source, and
append-prompt content/sources. Global and project settings can also select model,
thinking level, tools, packages, extensions, skills, and prompts. [E7] [E9] [E14]

`AgentSession.systemPrompt` exposes the current effective prompt, and extensions
can call `ctx.getSystemPrompt()` and alter the prompt in `before_agent_start`.
`AgentSession.getAllTools()` exposes tool definitions and source metadata. These
runtime surfaces can support a private prompt/configuration snapshot during a
Benchwarmer-dispatched run. The built-in RPC command set has no direct
`get_system_prompt` or full settings-snapshot command, so RPC-only capture would
need a trusted extension or a parallel SDK integration. [E5] [E10] [E13]

The JSONL header does not record the Pi package version, and session entries do
not contain a complete system prompt, loaded skills, full tool definitions,
extensions, settings, or project-trust decision. Model and thinking changes are
recorded, but their presence does not reconstruct the full effective request.
Imports must therefore mark historical prompt/config capture as unavailable or
partial unless a contemporaneous private snapshot exists. [E3] [E12] [E14]

Credential files and custom model configuration can contain secrets or commands
that resolve secrets. They are configuration inputs, not safe report artifacts;
an importer should record only sanitized provider/model/config metadata and never
copy credential values or raw configuration wholesale. [E8] [E9]

## Import and execution support

Read/import interfaces, listed separately:

- Offline JSONL parsing provides complete append history, including abandoned
  branches and pre-compaction entries. [E3]
- The SDK `SessionManager` can create, open, list, and list-all sessions and expose
  entries, trees, headers, branch context, and IDs. [E3] [E9] [E12]
- RPC can read state, messages, entries since a cursor, tree structure, session
  statistics, and the active leaf from one running Pi process. [E5]
- JSON mode emits live session and agent events but is not an all-session history
  endpoint. [E6]

Automation/execution interfaces, listed separately:

- CLI print mode performs a non-interactive request; JSON mode emits live events;
  RPC is a bidirectional line-delimited JSON protocol; and the TypeScript SDK
  embeds `AgentSession` directly. These interfaces are documented upstream but
  could not be exercised in the inspected environment. [E1] [E5] [E6] [E9]
- RPC supports prompt, steer, follow-up, abort, model and thinking changes,
  compaction/retry control, session switching/forking/cloning, and direct shell
  execution, with streamed agent/tool events. [E5]
- Extensions can register tools and commands, intercept or replace provider
  payloads, inspect response status/headers, inspect the effective prompt, and
  persist custom entries. Extensions execute with the user's system permissions.
  [E10]

An execution adapter must use disposable fixture workspaces, explicit project
trust, a strict tool allowlist, controlled credentials/network access, and its own
paid-work reservation/recovery state. RPC prompt acceptance is asynchronous:
`success: true` means accepted or queued, while later failure is reported in the
event stream. `agent_settled`, rather than prompt acceptance or a low-level
`agent_end`, is the documented terminal signal after retries, compaction, and
queued continuations. [E5] [E7] [E10]

## Reconciliation identifiers

The strongest documented bridge to provider records is optional assistant-message
`responseId`, defined as the upstream provider response/message identifier when
the adapter exposes one. Preserve it with `api`, `provider`, requested `model`,
optional routed `responseModel`, message timestamp, usage tuple, and Pi session
and entry IDs. Absence must remain explicit because `responseId` and
`responseModel` are provider-dependent optional fields. [E11]

Pi session IDs may be supplied to some providers for cache affinity, but that does
not make them authoritative provider request IDs. Tool-call IDs link assistant
tool calls to Pi tool results. RPC command IDs link RPC commands to their
responses, and most RPC events do not carry them. Neither identifier class should
be used as a provider billing key. [E5] [E8] [E11]

A provider observation and its Pi assistant message describe the same underlying
request when reconciled; retain both records but do not add their tokens or costs.
Match first on `(provider, responseId)`. If no upstream ID exists, any match using
model/response model, timestamp, token components, and sequence is heuristic and
must retain confidence and mismatch details. Pi's computed cost is not a substitute
for provider actual charge. [E8] [E11] [E13]

## Unknowns and risks

- Installed Pi version, account/authentication type, enabled providers, models,
  extensions, skills, tools, project trust, and live RPC/SDK behavior are unknown
  because Pi and its data directory were unavailable. [E1]
- No real local JSONL file was available to validate schema version, malformed
  record behavior, custom extension fields, file permissions, concurrent reads,
  or cursor recovery against this installation. [E1]
- Historical prompt, tool, skill, extension, and settings snapshots are absent
  from the core session schema. Effective capture requires runtime SDK/extension
  instrumentation and careful private storage. [E3] [E10] [E13] [E14]
- Retention has manual deletion semantics but no reviewed core expiry guarantee.
  Trash behavior, backups, external cleanup extensions, and source deletion races
  require a target-host check. [E1] [E4] [E7]
- Byte-offset cursors are unsafe across legacy migration/full-file rewrite. Entry
  cursors also require a full rescan if the cursor disappears. [E5] [E12]
- Cost is model-metadata-derived and can be zero, stale, custom, tier-sensitive,
  or different from subscription economics and provider invoices. [E8] [E11]
- Provider request ID, concrete routed model, reasoning usage, one-hour cache-write
  split, and deferred/batch identifiers are optional and provider-dependent.
  Missing values must remain unknown, not zero or empty. [E11]
- The header's `cwd` and optional `parentSession`, plus message/tool/custom payloads,
  can expose private paths and content. Raw imports belong in private artifact
  storage; public fixtures need deliberate field-level sanitization. [E3] [E11]
- Before implementation, repeat the sanitized live checks on the target host,
  record `pi --version`, inspect only schema keys and aggregate counts from copied
  private fixtures, exercise `get_entries` with a disposable no-secret session,
  and compare one request's optional `responseId` with its provider record. [E1]
  [E5] [E11]

[agent-session]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/coding-agent/src/core/agent-session.ts
[ai-types]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/ai/src/types.ts
[extensions]: https://pi.dev/docs/latest/extensions
[json-events]: https://pi.dev/docs/latest/json
[models]: https://pi.dev/docs/latest/models
[package-manifest]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/coding-agent/package.json
[resource-loader]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/coding-agent/src/core/resource-loader.ts
[rpc]: https://pi.dev/docs/latest/rpc
[sdk]: https://pi.dev/docs/latest/sdk
[session-format]: https://pi.dev/docs/latest/session-format
[session-manager]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/coding-agent/src/core/session-manager.ts
[sessions]: https://pi.dev/docs/latest/sessions
[settings]: https://pi.dev/docs/latest/settings
[system-prompt]: https://github.com/earendil-works/pi/blob/b2602be77cb7b0de45dd616407fd210daa48aa75/packages/coding-agent/src/core/system-prompt.ts
