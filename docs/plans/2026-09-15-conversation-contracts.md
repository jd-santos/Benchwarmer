# First conversation-library slice

## Approval and purpose

The user approved the conversation-centered design, documentation updates, and
starting implementation agents. Cross-machine transport choices and numeric
model-work budgets remain open. This slice does not choose them.

Deliver two independent Python contracts: normalized conversations and bounded
model-work approval. Both are pure, standard-library code with synthetic tests.
This is a prerequisite slice, not a claim that collection or browsing works yet.
The chosen architecture and product semantics are in
[../conversation-library.md](../conversation-library.md).

Alternatives rejected for this slice: start a network collector before device and
trust choices; add a live enrichment pipeline before approval/budget controls;
finish usage dashboards before reusable conversation evidence exists.

## Ownership and integration

- `LIB-001` owns `src/benchwarmer/conversations.py`,
  `tests/test_conversations.py`, and `tests/fixtures/conversations/`.
- `ENR-001` owns `src/benchwarmer/model_work.py` and
  `tests/test_model_work.py`.
- Neither lane imports the other, edits package initialization, adds dependencies,
  changes runtime provisioning, creates a database, calls a model, or edits shared
  docs/task status. Use separate managed worktrees. The coordinator integrates
  both patches and owns documentation and acceptance transitions.
- Reviewer checks the integrated diff against this plan, especially branch
  preservation, misleading provenance, stale approvals, and implicit inference.
- Escalate missing product choices rather than inventing networking or budgets.

## LIB-001: Normalized conversation v1

**Type:** Subsystem or file cluster `[context: medium]`.
**Dependencies:** `PLAN-003`, existing `FND-002` tooling; no database dependency.

Provide these public functions and exception in `conversations.py`:

- `validate_conversation(document: object) -> None`
- `load_conversation_json(text: str) -> dict[str, object]`
- `dump_conversation_json(document: object) -> str`
- `ConversationValidationError(ValueError)`

Use ordinary JSON values as the serialized seam. No Pydantic or framework
dependency is needed for this implemented feature. Validation is strict about
known structure; native unknown fields belong in `extensions`. Do not mutate the
input. Errors identify the invalid field/position without echoing private values.

### Envelope

All keys listed here are required unless marked optional. Structured objects
reject undeclared keys except within `extensions` and JSON metadata values.
Empty lists and extension objects are valid. IDs are nonempty strings; they are
opaque, not paths. `null` is permitted only where stated. All JSON numbers must
be finite; booleans do not count as integer versions or ordinals.

| Key | Shape |
| --- | --- |
| `schema_version` | Integer `1`; reject other versions |
| `id` | Opaque normalized conversation ID |
| `revision` | Nonempty immutable revision identifier |
| `source` | Source object below |
| `events` | List of event objects below |
| `artifacts` | List of artifact objects below |
| `relationships` | List of relationship objects below |
| `metadata` | List of provenance-bearing metadata objects below |
| `coverage` | Nonempty-string field names mapped to `available`, `partial`, `unavailable`, `unknown`, or `redacted` |
| `extensions` | Object containing source-specific JSON |

Source object: `kind`, `scope_id`, `native_id`, `adapter_version` (nonempty
strings), `source_version` (nonempty string or null), `captured_at` (timezone-aware
ISO timestamp), `snapshot_id` (opaque reference to retained private native
evidence), and `extensions` (object). Do not restrict `kind` to today's harnesses.
Do not dereference snapshots or claim this validator proves their existence.

Event object:

- `id`, `native_id`: nonempty strings, each unique within this conversation.
- `ordinal`: unique nonnegative integer expressing source ordering. List order
  must be ascending by ordinal; gaps are allowed.
- `parent_id`: event ID or null. Non-null references must resolve within the
  conversation, be acyclic, and precede the child in source ordering.
- `kind`: `message`, `compaction`, `configuration`, or `unknown`.
- `role`: `system`, `developer`, `user`, `assistant`, `tool`, or `unknown`.
- `occurred_at`: timezone-aware ISO timestamp or null.
- `content`: ordered list of content blocks.
- `extensions`: object, including source-native roles/kinds not normalized yet.

A content block has `id`, `kind`, `text`, `tool_call_id`, `artifact_id`, and
`extensions`. Block IDs are unique within an event. Kinds are `text`, `reasoning`,
`tool_call`, `tool_result`, `attachment`, or `unknown`. Text is string or null;
call/artifact IDs are nonempty strings or null. Tool-call and tool-result blocks
require a call ID. Attachment blocks require a resolvable artifact ID. Any
non-null artifact ID must resolve. Tool arguments/results can remain structured
JSON in block extensions; never execute them. A result whose call is absent is
permitted only when `coverage.tool_calls` is `partial`, `unknown`, `unavailable`,
or `redacted`; `available` requires a matching call on its ancestor path (including
earlier blocks in the same event). The same native call ID may occur on different
branches, so do not impose global call-ID uniqueness.

Artifact object: `id`, `kind` (nonempty strings), `media_type` (nonempty string or
null), `availability` (the coverage states above), `locator` (opaque nonempty
string or null), and `extensions`. IDs are unique. An available artifact requires
a locator; partial/redacted/unavailable/unknown do not imply a local file exists.
This code never reads a locator.

Relationship object: `kind` (`branch`, `continuation`, `derived_from`, or
`unknown`), `target_source_scope_id`, `target_native_id` (nonempty strings), and
`extensions`. Targets may be outside this document; retain the reference without
inventing or loading their content.

Metadata object: `name` (nonempty string), `value` (any finite JSON), `origin`
(`imported`, `calculated`, `generated`, or `human`), `producer` (nonempty string),
`producer_version` (nonempty string or null), `input_revision` (nonempty string),
`extensions`. This supports provenance, not automatic enrichment. It does not
claim arbitrary metadata has validated usage/cost semantics. Preserve original
short summaries as imported rather than rewriting their origin as generated.

### Serialization and tests

Reject duplicate JSON object keys, unsupported versions, non-finite numbers,
wrong primitive types, unknown structural keys, malformed references, cycles,
and unordered events. JSON errors must not include content snippets. Dump with
stable key ordering and strict JSON; load/dump round trips preserve JSON content,
branch structure, extensions, and explicit null/coverage distinctions.

Create synthetic normalized fixtures under `tests/fixtures/conversations/`:

- `pi-branch.json`: one common ancestor and two diverging branches, tool linkage.
- `hermes-continuation.json`: ordered messages and external continuation reference.
- `codex-tools.json`: tool call/result, artifact, unknown field, partial capture.
- `README.md`: explain synthetic origin and what each fixture exercises. These
  are normalized examples, not proof of live source-adapter compatibility.

Tests cover all three, same native session ID in different source scopes without
identity merging, extension round trips, metadata origins, explicit missing
coverage, branch-local tool linkage, invalid references/order, and malformed
JSON. Tests must not read private logs or write artifacts outside temporary test
state. Synthetic examples use no real usernames, paths, prompts, or account IDs.

**Acceptance:** Every fixture validates and round trips; negative cases fail with
bounded field-only errors. No filesystem, network, SQLite, harness SDK, inference,
or execution side effect exists in the module.

## ENR-001: Bounded model-work preview and approval

**Type:** Focused change `[context: medium]`.
**Dependencies:** `PLAN-003`, existing `FND-002` tooling; independent of `LIB-001`.

Implement immutable standard-library dataclasses and pure functions in
`model_work.py`. This is an in-memory policy contract, not the durable reservation
or dispatch service. No provider client, automatic estimator, scheduling,
credential lookup, or paid execution belongs here.

Public seam:

- `WorkItem`: `input_id`, `input_revision` as nonempty strings.
- `WorkStage`: `stage_id`, `operation`, `provider`, `model`, `configuration_digest`,
  `max_requests`, `max_input_tokens`, `max_output_tokens`, `max_cost`.
- `WorkPlan`: `schema_version`, `items`, `stages`, `currency`, `max_total_cost`,
  `max_total_requests`, `max_concurrency`, `pricing_basis`, `disclosure_scope`.
- `WorkApproval`: `plan_digest` and `approved_by`, both nonempty strings.
- `plan_digest(plan: WorkPlan) -> str`: deterministic SHA-256 of validated,
  canonical JSON. Equivalent plans produce the same digest.
- `validate_approval(plan: WorkPlan, approval: WorkApproval | None) -> None`:
  validate plan and exact digest match; otherwise raise `ModelWorkValidationError`.
- `ModelWorkValidationError(ValueError)` with bounded field-only messages.

Use tuples for item/stage collections and immutable field types. Do not allow
mutable lists to be smuggled into frozen dataclasses. Reject malformed primitive
types (including bool-as-int), empty identities, duplicate item identities or
stage IDs, unsupported schema versions, nonpositive request/concurrency limits,
negative allowances, missing approvals, and stale approval digests.

`operation` is one of `classification`, `description`, `embedding`, `query_embedding`,
`segmentation`, `criteria`, `rerun`, `judge`, or `simulation`. Recording a simulation
stage is not implementation or approval of an adaptive user adapter. The other
identity/configuration fields are nonempty strings. `configuration_digest` pins
prompt, rubric, model settings, retry/escalation policy, and other effective
configuration upstream; this module does not construct or verify that content.

`max_requests` is a stage-wide ceiling, including every item, retry, and
escalation, not a per-item count. Input/output allowances are per request and
nonnegative integers. `items` and `stages` must be nonempty. Stage request ceilings
sum to at most `max_total_requests`; concurrency must not exceed that total.
There is no default limit or approval.

For this initial contract, priced work only: `currency` is a three-letter
uppercase code; costs are finite nonnegative `Decimal` values, not binary floats;
`pricing_basis` is a nonempty reference to the price evidence used in the preview.
Stage `max_cost` values are whole-stage allowances in that currency, including
retries; their sum must not exceed `max_total_cost`. Validate without rounding
away precision. Canonicalize Decimal values so equivalent numeric values hash
identically. This validates supplied ceilings, not provider prices or the
probability of completing the batch. Unknown pricing/non-monetary approval is a
future policy decision, not an unbounded fallback. Zero cost still requires
approval and bounded requests/resources.

`disclosure_scope` is a nonempty reference to separately approved content/provider
permissions. Include it in the digest; a supplied string does not prove the
permission exists. The eventual service must resolve and enforce that permission
before dispatch. `approved_by` is an authenticated actor reference supplied by
that service, not authentication implemented here. Digests are not credentials,
signatures, or proof of authorization by themselves.

Tests cover exact approval, changed input revisions, stage models/configuration,
judges, limits, pricing, and disclosure scope invalidating approval; mutable input
rejection; Decimal edge cases; no-op or empty plans; duplicate records; exhausted
request/cost allocations; zero-cost work still needing approval; and missing
approval. No automatic provider escalation or network call is possible.

**Acceptance:** Valid frozen plans bind all consequential fields to explicit
approval; malformed/stale/unapproved plans fail. State clearly in docstrings that
durable spend reservation, permission lookup, dispatch, and uncertain-outcome
recovery are not implemented by this validator.

## Verification and runtime boundary

Canonical commands from the repository root:

```bash
uv run pytest tests/test_conversations.py tests/test_model_work.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall src
git diff --check
```

The coordinator's initial baseline could not run: the pinned runtime was absent
from this checkout. Do not provision, repair, replace, or bypass the required
SQLite runtime as part of either lane. Managed worktrees also may lack ignored
runtime state. If canonical commands remain blocked, report that explicitly.

Because these modules have no database/runtime dependency, write tests with
`unittest.TestCase` so they are also collected by pytest and can run as a limited
standard-library check under an available Python 3.12+ interpreter:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_conversations.py'
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_model_work.py'
```

Check that interpreter's version first. These supplemental checks do not prove
repository-wide validation or satisfy the WAL runtime gate. Do not invoke
formatters manually; format-on-save owns formatting. Report unavailable tooling
rather than installing speculative dependencies.

## Completion gate and next slice

The coordinator reviews both actual patches, runs the combined tests, and records
canonical checks that remain blocked. Move tasks to Done only with truthful
acceptance evidence; otherwise retain their validation blocker in In Progress.
No live source, inference, network service, browser, or durable budget protection
may be claimed from this slice.

Next: resolve `COL-001` with the user, finish necessary data-root/migration/API
foundation, map the Hermes importer to this shared contract, and deliver retained
conversations through a real browsing/text-search path. Do not let cost charts or
external-evidence dashboards become prerequisites for that useful release.
