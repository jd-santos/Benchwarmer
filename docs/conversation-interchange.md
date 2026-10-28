# Conversation interchange

The **Benchwarmer conversation file** is how another system hands a
conversation to the library. One JSON document holds one conversation. Any
language can write it; Benchwarmer validates it, keeps the whole file as the
private native snapshot, normalizes it, and assigns the library ids and the
revision hash. The writer never computes those.

This page is the format reference (version 1), the mapping guide for an agent
product log, the import semantics, and how a writer validates a file before
sending it. The JSON Schema is
[`schemas/conversation-file.v1.schema.json`](schemas/conversation-file.v1.schema.json);
the Python validator, builder, and reference converter live in
`benchwarmer.interchange`. The work record is
[todo/work/conversation-interchange](../todo/work/conversation-interchange/README.md).

## Where it sits

```
agent product log  --converter-->  conversation file  --import-->  library revision
                                      (validated)        |             |
                                                     snapshot      evidence bundle
                                                                       |
                                                                  task version
                                                                       |
                                                              case record (pull)
```

Import kind `conversation_file` accepts a file or a directory of files from a
configured import root (`POST /api/v1/sources/{source_id}/imports`), and
`POST /api/v1/imports/conversation-files` accepts one file as the request
body. Approved task versions are pulled with `GET /api/v1/task-versions?status=approved`
and `GET /api/v1/tasks/{id}/export/{version}`.

## Format reference (version 1)

A conversation file is a JSON object. Unknown fields are rejected at every
level, so a writer finds a misspelt field at validation time rather than
losing it silently. `null` and omitted mean the same thing for optional fields.

### Document

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `format` | yes | `"benchwarmer-conversation-file"` | Identifies the file. |
| `format_version` | yes | `1` | Bumped when a field changes meaning. |
| `scope_id` | yes | string, 1–255 | The writer's own identity for where conversations come from (a tenant, an installation, an account). One `conversation_file` source per scope. |
| `native_id` | yes | string, 1–255 | The conversation's identity in the writing system. Stable across re-exports of the same conversation. |
| `source_version` | no | string | The writer's format or application version, recorded on the revision. |
| `title` | no | string | Becomes the `title` metadata entry. |
| `events` | yes | array, at least one | The conversation tree, in order. See below. |
| `tools` | no | array of tool | Tool definitions available to the model. |
| `context` | no | array of context item | Attached material (files, retrieved documents) that `attachment` blocks reference. |
| `annotations` | no | array of annotation | Human judgements about the conversation, such as feedback. |
| `relationships` | no | array of relationship | Links to other conversations (branch, continuation, derived_from). |
| `metadata` | no | array of `{name, value}` | Anything else worth keeping as imported metadata. Names `title`, `annotation`, and `usage_observations` are reserved; Benchwarmer derives those. |
| `coverage` | no | object of dimension → state | What the writer captured. States: `available`, `partial`, `unavailable`, `unknown`, `redacted`. Defaults are listed under import semantics. |
| `extensions` | no | object | Free-form writer data at the document level. The key `tool_definitions` is reserved. |
| `native` | no | any JSON | Raw payloads (provider responses and the like). The whole file is retained as the snapshot, so this is the place for anything that does not fit above. |

### Event

Events appear in the order they happened. A parent must appear before its
children; Benchwarmer assigns ordinals from file order. Siblings that share a
parent are branches.

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `native_id` | yes | string, 1–255 | Unique within the file. |
| `parent_native_id` | no | string or null | The event this one follows. `null` or omitted for a root. Must name an earlier event. |
| `kind` | no | `message` (default), `configuration`, `compaction`, `unknown` | `configuration` carries system prompt text, model switches, and other setup. |
| `role` | yes | `system`, `developer`, `user`, `assistant`, `tool`, `unknown` | |
| `occurred_at` | no | RFC 3339 timestamp with offset | |
| `content` | yes | array of block | May be empty for events with no captured content. |
| `provenance` | no | provenance | Which model produced this event and under what settings. Meant for assistant events. |
| `supersedes_native_id` | no | string | For a rewind: the earlier sibling this event replaced. Must name an earlier event. |
| `extensions` | no | object | Free-form. Keys `provenance` and `supersedes_native_id` are reserved. |

### Block

| Field | Applies to | Meaning |
| --- | --- | --- |
| `kind` | all (required) | `text`, `reasoning`, `tool_call`, `tool_result`, `attachment`, `unknown`. |
| `text` | all | The captured text. For `tool_call` it defaults to `tool_name` so readers that only show text still see which tool ran. |
| `tool_call_id` | `tool_call`, `tool_result` (required) | Links a call to its result. Within one branch each id is called once; a result must follow its call on the same branch unless `coverage.tool_calls` is not `available`. |
| `tool_name` | `tool_call` | The tool invoked. Required when `input` is given. |
| `input` | `tool_call` | The arguments, any JSON. |
| `output` | `tool_result` | The result, any JSON. |
| `is_error` | `tool_result` | Boolean. |
| `context_id` | `attachment` (required) | The `context` item attached here. |
| `extensions` | all | Free-form. Keys `tool_call` and `tool_result` are reserved. |

### Provenance

| Field | Required | Meaning |
| --- | --- | --- |
| `model` | yes | Model identifier as the writer knows it. |
| `provider` | no | Provider or gateway name. |
| `params` | no | Object of sampling and request parameters. |
| `system_prompt_sha256` | no | Lowercase hex SHA-256 of the system prompt text in effect for this turn; lets a reader tell which `configuration` event applied without repeating the prompt. |
| `usage` | no | Raw provider usage object, kept as reported. Pricing is never applied here. |

### Tool

`{"name": string, "description": string|null, "input_schema": object|null}`.
Names are unique within the file.

### Context item

`{"id": string, "kind": string|null, "name": string|null, "media_type": string|null, "text": string|null}`.
`text` is the item's content when the writer has it; without it the item is
recorded as unavailable.

### Annotation

`{"kind": string, "event_native_id": string|null, "rating": string|integer|null, "text": string|null, "by": string|null, "at": timestamp|null}`.
Use `kind: "feedback"` for end-user or reviewer feedback. `event_native_id`
names the event the annotation is about, or is null for the whole conversation.

### Relationship

`{"kind": "branch"|"continuation"|"derived_from"|"unknown", "target_scope_id": string, "target_native_id": string, "target_source_kind": string (default "conversation_file")}`.

### Minimal example

```json
{
  "format": "benchwarmer-conversation-file",
  "format_version": 1,
  "scope_id": "example-tenant",
  "native_id": "conv-42",
  "events": [
    {"native_id": "u1", "role": "user",
     "content": [{"kind": "text", "text": "What does the sync flag do?"}]},
    {"native_id": "a1", "parent_native_id": "u1", "role": "assistant",
     "content": [{"kind": "text", "text": "It enables the faster path."}],
     "provenance": {"model": "example-model"}}
  ]
}
```

A full example with every feature is
[`tests/fixtures/conversation-files/valid/agent-product-log.json`](../tests/fixtures/conversation-files/valid/agent-product-log.json).

## Mapping guide: an agent product log

Most agent products log a conversation as a system prompt, a tool list, a
sequence of turns with blocks, per-call model metadata, and end-user feedback.
`benchwarmer.interchange.agent_log.convert_agent_log` is a reference converter
from a synthetic log of that shape (`example-agent-log`, documented in the
module and in
[`tests/fixtures/agent-logs/example-agent-log.json`](../tests/fixtures/agent-logs/example-agent-log.json)).
Writers of real logs follow the same mapping:

| In the agent log | In the conversation file | After import |
| --- | --- | --- |
| Tenant or installation | `scope_id` | One `conversation_file` source per scope |
| Conversation id | `native_id` | Conversation id is derived from source and native id |
| System prompt text | A `configuration` event with role `system` and one `text` block, as the root; its SHA-256 in each model turn's `provenance.system_prompt_sha256` | Event kind `configuration`; hash in `events[].extensions.provenance` |
| Tool list | `tools` | `extensions.tool_definitions` |
| User turn text | `text` block on a `user` event | |
| Attached file or retrieved document | A `context` item plus an `attachment` block on the turn that attached it | An `artifacts` entry (`available` with the text in `extensions.context_item`, locator `context/<id>` inside the snapshot) and an `attachment` block referencing it |
| Assistant text, thinking, tool use | `text`, `reasoning`, `tool_call` blocks (name and `input`) on an `assistant` event | Block extensions `tool_call: {name, input}` |
| Tool output | A `tool` event whose `tool_result` block repeats the call id, with `output` and `is_error` | Block extension `tool_result: {output, is_error}` |
| Model, parameters, usage per call | `provenance` on the assistant event | `extensions.provenance`; usage also collected into the `usage_observations` metadata entry with origin `imported` |
| Rewind or edit of an earlier turn | A new event whose `parent_native_id` is the turn before the rewound one and whose `supersedes_native_id` names the turn it replaced | A sibling branch; `extensions.supersedes_native_id` |
| Thumbs up/down, comments | `annotations` with `kind: "feedback"` | Metadata entry `annotation` with origin `human` |
| Raw provider responses | `native` | Retained in the snapshot only; never normalized |

Branches are not special-cased: an event's parent is whatever it followed,
and Benchwarmer reads the tree from the parents. Every branch of a rewound
conversation is kept.

## Import semantics

- **Idempotent.** The import key is the file's content. The same file imported
  again (same bytes, or the same canonical JSON over the API) stores nothing
  new and reports `unchanged`. Re-importing an unchanged directory is also
  `unchanged`.
- **A changed file yields a new revision.** The conversation keeps its id;
  the revision hash covers the normalized document, so any content change
  produces a new revision alongside the old one, and a new snapshot of the
  file.
- **Snapshots.** The whole file is written under the data root as a
  content-addressed private snapshot before anything is normalized. Raw
  payloads under `native` live there.
- **Ids.** `conversation_id` is derived from the source id and `native_id`;
  event ids are derived from the conversation id and each event's
  `native_id`. A writer cannot choose or predict them and does not need to:
  the upload response returns them, and the library is searched by
  `native_id`.
- **Coverage gaps are explicit.** When the writer omits `coverage`, the
  import records `messages: available`, `branches: available`,
  `usage: partial` if any provenance carries usage else `unknown`,
  `prompts: available` if a system/developer or configuration event exists
  else `unknown`, and `tool_calls: partial`. A writer that captured every tool
  call and result sets `tool_calls: available`, which also makes the validator
  insist that each result follows its call on the same branch. Partial or
  redacted capture is stated, never guessed.
- **Scopes stay separate.** A path import into a `conversation_file` source
  requires every file's `scope_id` to equal the source's scope. The upload
  route picks the source from the file's `scope_id`, creating it on first use,
  unless `?source_id=` names one (which must be a `conversation_file` source
  with that scope).
- **Nothing runs.** Importing never starts model work. Enrichment, judges,
  and runs remain separately approved.
- **Normalized document version.** Imported files land as normalized
  conversation `schema_version: 1`. The additions this format needs
  (`tool_definitions`, `provenance`, `supersedes_native_id`, `tool_call`,
  `tool_result`, `context_item`, and `annotation` metadata) are well-known
  extension keys with typed validation when present; documents without them
  are unchanged, so no version bump or migration was needed.

## Validating a file

Without a database:

```
uv run benchwarmer-validate path/to/conversation.json [more files]
```

The command prints `<file>  ok  <n> events` for a valid file, or one line per
issue as `<file>  <json path>  <message>` on standard error, and exits 1 when
any file has issues (2 when a file cannot be read). Content is never echoed.
`--normalized` prints the normalized conversation a valid file would import
as, with preview ids. `--agent-log` converts an `example-agent-log` first;
with `--output` the converted file is written for inspection or upload.

In Python:

```python
from benchwarmer.interchange import validate_conversation_file

issues = validate_conversation_file(document)  # [] when valid
```

With any JSON Schema validator, `docs/schemas/conversation-file.v1.schema.json`
checks the shape. The schema cannot express the rules that relate parts of
the file (parents before children, `context_id` naming an item, tool results
following their calls on a branch), so a file that passes the schema can still
be refused by the import with the same JSON-path issues the CLI prints.
`tests/interchange/test_schema_parity.py` keeps the two in step on the
fixtures under `tests/fixtures/conversation-files/`.

Python writers can use `benchwarmer.interchange.ConversationFileBuilder`
instead of assembling the document by hand; `build()` validates.

## Pulling case records

The pipeline side reads approved task versions without the web app:

- `GET /api/v1/task-versions?status=approved` lists every approved version
  with the fields that fix its export digest (task id, version, bundle
  revision, cut-point conversation and revision, criterion count) and its
  `export_url`. Superseded approved versions stay listed.
- `GET /api/v1/tasks/{id}/export/{version}?terms=a&terms=b` returns the same
  case record as `POST /api/v1/tasks/{id}/export`, scrubbing the given terms
  besides the built-in kinds, and re-checks leakage flags before writing. The
  `Content-Disposition` header carries the `file` sink's filename.

The registry (`benchwarmer.registry`) names the import kinds the API lists,
the export sinks (`file` today), and the scrub detector kinds. New kinds are
added there.
