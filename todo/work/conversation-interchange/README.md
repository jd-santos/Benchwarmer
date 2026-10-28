# Exchange conversations and case records with an evaluation pipeline

Status: In progress on `task/conversation-interchange`. Format v1, the
validator CLI and JSON Schema, the `conversation_file` import kind, the upload
route, the registry, and the pull routes are implemented with tests. Access
control and a writer outside this repository are pending.

## Purpose

Benchwarmer is one component of a larger evaluation pipeline: another system
writes a conversation, Benchwarmer imports it, a reviewer prepares a task from
the evidence, and the approved case record is pulled out. Until now the only
contract for "a conversation from elsewhere" was the Python dataclass
`FileConversation` behind the Pi and ChatGPT readers, and the only way out was
the browser download. This work makes the inbound format real and documented,
gives the outbound side pull routes, and puts the kinds Benchwarmer knows
about in one registry.

## Dependencies and order

Builds on the [application foundation](../application-foundation/README.md)
file-source persistence and the [task preparation](../task-preparation/README.md)
export. [Private deployment](../private-deployment/README.md) decides how the
routes are reached from another machine; nothing here waits for it, but the
access-control note below is revisited there. Fixture-backed reconstruction in
task preparation is the consumer of the provenance, tool, and context fields
this format carries.

## Decisions

- **One JSON document per conversation, written by anyone.** The format
  carries native ids, events with parent native ids, content blocks, tools,
  context items, per-turn provenance, annotations, relationships, metadata,
  coverage, and a raw `native` payload. Benchwarmer computes conversation ids
  and the revision hash; the writer never does. Reference:
  [docs/conversation-interchange.md](../../../docs/conversation-interchange.md).
- **The whole file is the snapshot.** Raw provider payloads go under
  `native`; the normalized document keeps typed structure only.
- **Typed well-known extension keys, not a schema bump.** The normalized
  conversation stays `schema_version: 1`. `tool_definitions` (document),
  `provenance` and `supersedes_native_id` (event), `tool_call` and
  `tool_result` (block), `context_item` (artifact), and metadata entries named
  `annotation` are validated when present and absent from older documents, so
  no migration was needed. Feedback is a metadata entry of origin `human`;
  attached context items are artifacts referenced by `attachment` blocks;
  rewinds are sibling branches with `supersedes_native_id`.
- **Scope is the source.** A file's `scope_id` names the writer's scope; one
  `conversation_file` source exists per scope, created on first upload. Path
  imports refuse files whose scope differs from the source's.
- **Idempotent by content.** The import key is the file content; a changed
  file yields a new revision of the same conversation.
- **Registry, internal only.** `benchwarmer.registry` lists importers by
  kind (`pi`, `chatgpt`, `conversation_file`), export sinks by name (`file`),
  and scrub detectors by kind (wrapping the built-in categories in
  `anonymize.py` without changing their order or behavior). No entry points;
  a new kind is a registration in that module. `IMPORTABLE_KINDS` is gone.
- **Pull, not push, for case records.** `GET /api/v1/task-versions` lists
  approved versions with digest-relevant fields, and
  `GET /api/v1/tasks/{id}/export/{version}` returns the same record as the
  POST export with the same flag re-check. Benchwarmer still does not write to
  any external store.
- **No auth layer yet.** The upload and pull routes have no authentication.
  For the single-operator deployment, access control is the network boundary
  (Tailscale, per ADR 0003); this is revisited in
  [private deployment](../private-deployment/README.md) before any other
  machine can reach the API.
- **`jsonschema` is a dev dependency only.** It backs the parity test; the
  application validates with its own code.

## Acceptance criteria

- A non-Python writer can produce a file from the reference doc and schema
  alone, check it with `uv run benchwarmer-validate`, and see the same issues
  the import would raise, with JSON paths and without echoed content.
- Importing the file (path or upload) stores a snapshot, a normalized revision
  that passes `validate_conversation`, coverage, and provenance; importing it
  again stores nothing; importing a changed file adds a revision.
- System prompt, tool definitions, per-turn provenance, attached context,
  feedback, and rewinds survive import in typed form.
- The pipeline can list approved task versions and pull each case record by
  task id and version with the same bytes the POST export gives.
- Existing Pi and ChatGPT imports and their tests are unchanged.

## Work

- [x] Format v1: `benchwarmer.interchange` (validator with JSON-path issues,
  converter to `FileConversation`, normalized preview, strict JSON loader).
- [x] Typed extension validation in `benchwarmer.conversations`;
  `FileConversation` gains `artifacts`, `extensions`, `annotations`;
  `FileImportResult.items` reports where each conversation landed.
- [x] Reference doc `docs/conversation-interchange.md`, JSON Schema
  `docs/schemas/conversation-file.v1.schema.json`, parity test, AGENTS.md
  index entry.
- [x] `benchwarmer-validate` console script, `ConversationFileBuilder`,
  `example-agent-log` reference converter, synthetic fixtures.
- [x] Import kind `conversation_file` (file or directory) through
  `import_file_conversations`; listed by `/api/v1/imports/config` and the
  Sources page import panel.
- [x] `POST /api/v1/imports/conversation-files`: validate, stage under
  `<data root>/imports/staging/conversation_file/`, import, return batch,
  conversation id, and revision.
- [x] `benchwarmer.registry` with importers, export sinks, scrub detectors.
- [x] `GET /api/v1/task-versions` and `GET /api/v1/tasks/{id}/export/{version}`.
- [ ] Access control for the upload and pull routes once another machine
  needs them (see private deployment).
- [ ] A writer outside this repository exercising the format end to end, and
  any format v2 fields it shows are missing.
- [ ] Show provenance, tool definitions, context items, and annotations in
  the conversation reader; today they are stored but not rendered.

## Verification

Record actual commands and results here at each handoff.

- 2026-10-27: `uv run pytest` (full suite, see PR), `uv run ruff check .`,
  `uv run ruff format --check .`, `npm --prefix web run check`,
  `npm --prefix web run lint`, `npm --prefix web test`,
  `npm --prefix web run build`.
- Manual: `uv run benchwarmer-validate --agent-log tests/fixtures/agent-logs/example-agent-log.json --output /tmp/converted.json`
  then `uv run benchwarmer-validate /tmp/converted.json --normalized`.

## Supporting material

- [Conversation interchange reference](../../../docs/conversation-interchange.md)
- [Conversation library](../../../docs/conversation-library.md)
- [Task preparation](../task-preparation/README.md)
- [Private deployment](../private-deployment/README.md)
