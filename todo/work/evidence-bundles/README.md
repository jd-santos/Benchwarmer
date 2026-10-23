# Define evidence references and review conversation bundles

Status: In progress on `task/bundle-parsing-tools`. Manual bundle assembly,
deterministic outlines, the generated-bundle path through the API, and a first
in-app review surface for proposed drafts are implemented; the pilot run and
observation records are pending.

## Path to running evaluations

Decided with the user on 2026-10-19: build one thin path from excerpt to judged
result before deepening any stage. Each slice lands in its owning work record.

1. Evidence references and manual excerpt bundles (this record)
2. Bundle → task draft → immutable task version with a leakage check
   ([task preparation](../task-preparation/README.md))
3. Criteria and judge definitions scored 0–1 in 0.1 steps, deterministic or
   stub judges first ([evaluation planning](../evaluation-planning/README.md))
4. Test-plan task × configuration matrix with exact approval, no dispatch
5. Durable bounded execution with a direct-API harness
   ([bounded model work](../bounded-model-work/README.md))
6. Results grid with human scoring ([judged experiments](../judged-experiments/README.md))

Agent-proposed bundles, model judges, native harnesses, partitions, and
estimates deepen these stages afterward.

## Purpose

Connect separated requirements, actions, results, and corrections without turning them into a false transcript or prematurely assuming they can be rerun.

## Dependencies and order

Contract design and synthetic examples can begin now. The manual review pilot
waits for [browsing and annotations](../conversation-library/README.md). The
user-facing [history and cost dashboards](../history-and-cost-dashboards/README.md)
precede suggested-group approval in the product sequence. This is the last P2
slice, ahead of broad model-powered enrichment. Model-proposed bundles run in
the [analysis harness](../analysis-harness/README.md).

## Decisions

Decided with the user on 2026-10-19:

- Deterministic parsing (outlines, segmentation, headings, reference
  validation) lives in Python as typed pydantic models exposed over `/api/v1`.
  Model-driven proposal lives in the Pi Durable harness, which wraps those
  routes as tools and never opens the database.
- Model-proposed bundles reuse the bundle record as `origin=generated`,
  `status=draft` revisions. A separate suggestion queue is a UI concern for
  later, not a second table now.
- Pilot approval exception: an operator running the harness by hand on named
  conversations with their own keys is the exact approval for that model work.
  Nothing in the app starts a run. The bounded model-work service replaces this
  exception; until then every generated revision records its producer string
  and each run writes a usage report under `reports/harness/`.

Decided with the user on 2026-10-22, after the first operator run:

- A bundle states a `goal` (what this piece of work tried to achieve, with
  specifics) and an `objective` (the kind of work in general terms, with no
  project names, dates, or figures). The objective is the axis bundles will
  be grouped on into categories of work, so it must be reusable across
  projects; the first run's objectives were too specific and are the goals
  under this split. Version 1 documents upgrade on read with their objective
  copied into the goal; reviewers generalize the objective when they touch
  the bundle. A reviewed bundle still needs an objective.
- A third statement, `summary`, is the bundle's title for people: one or two
  plain sentences saying what happened and how it ended. The objective is for
  classification, the goal is metadata shown only in the editor, and the
  list shows summary and objective. Decided after the second run showed
  goals too dense to scan in a table.
- Run usage belongs in the application, not only in a report file. Each
  workflow records its run (`PUT /api/v1/runs/{run_id}`) with per-input raw
  usage and the catalog estimate; the editor shows what the pass that
  proposed a bundle cost and the list shows a run's total.

## Acceptance criteria

Evidence resolves against pinned conversation revisions and valid branch
ancestry. Bundles distinguish observed events from interpretations and remain
useful when a task cannot be reconstructed. Coherent phases may overlap; their
membership does not make them independent examples. A manually reviewed pilot
informs the extraction schema and later in-app review of suggested groups.

## Work

- [x] Define reusable references to conversation revision, event, content block, and optional text offsets, with explicit evidence roles and missing context.
  Text ranges count Unicode code points, half-open (`src/benchwarmer/evidence.py`).
- [x] Validate reference resolution and branch ancestry using synthetic examples, including continuations, compactions, missing content, and noncontiguous evidence.
  Items from one conversation pin one revision and lie on one path; conversations
  must be joined by captured relationships (`tests/api/test_bundle_api.py`).
- [ ] Define versioned observations and bundles separately from contiguous segments and executable task versions; retain producer and selection rationale.
  - [x] Bundles: numbered immutable revisions with objective, status (draft,
    reviewed, analysis only, rejected), rationale, missing evidence, origin, and
    producer; stale saves return 409 (`/api/v1/bundles`, migration `0004`).
    A rejected bundle must carry a rationale; the list route filters by the
    latest revision's `origin` and by `status`.
  - [x] Generated revisions: `POST`/`PUT /api/v1/bundles` accept `origin` and a
    nonblank `producer`; a human correction of a generated bundle is a new
    `human` revision over the generated one.
  - [ ] Observations and interpretations as separate records
  - [x] Store run-level provenance with generated revisions: run id, workflow,
    harness version, provider, model, thinking level, and the run report path
    (`RunProvenance`, migration `0005`). Raw usage stays in the run report,
    which is only complete after the run; `GET /api/v1/bundles?run_id=` groups
    a run's bundles and the editor links each proposal to its run.
- [x] Add deterministic conversation outlines from available roles, sizes, tools, branches, and configuration/compaction events. Do not infer missing timing or tool names.
  `benchwarmer.outline` (pydantic, strict) measures each event, finds ATX
  headings with code-point ranges that are valid evidence references, and
  derives exchanges (per user turn) and segments (between compaction and
  configuration boundaries) per path. `GET /api/v1/conversations/{id}/outline`
  serves it; `tool_name` repeats a tool-call block's text only when it is a bare
  identifier.
- [x] Support human bundle assembly and correction with source expansion before automating extraction.
  Select messages or highlighted text in the reader, create or extend a bundle,
  then edit roles, notes, order, and status with jump-to-source links.
- [ ] Propose bundles with a model under the pilot exception
  - [x] `harness/` tools over the API: `list_conversations`, `get_outline`,
    `read_events`, `list_bundles`, `propose_bundle`; the `propose-bundles`
    workflow runs one durable conversation per library conversation and writes
    a JSON run report with per-conversation usage.
  - [x] Review proposed drafts in the web app: the bundle list shows origin and
    the producing model with a "Proposed drafts" view and count, the editor
    names the producer per revision, flags an unreviewed proposal, and accepts
    (status Reviewed) or rejects (status Rejected with a required reason) as a
    human revision over the generated one.
  - [ ] First operator run against the synthetic demo library, then against a
    private import; record what the model proposed, what review removed or
    added, and token cost per conversation here.
    - [x] Synthetic run, 2026-10-22: `anthropic/claude-sonnet-5-5` through a
      pass-through gateway (`ANTHROPIC_BASE_URL`), no thinking, on the
      41-event ledger debugging fixture. Three drafts in 29 seconds covering
      diagnosis (8 items), fix with tests (12 items), and verification plus
      summary (6 items); every reference resolved, spans were disjoint and in
      order, and each carried a rationale and `missing_evidence`. Catalog
      estimate 0.14 USD: 3.9k output tokens, 23.5k cache-write, 28.4k
      cache-read, 10 uncached input. Review of the drafts is pending.
    - [x] Second synthetic run, 2026-10-22, on the 45-event branched sensor
      backfill fixture with the goal/objective instructions: five drafts in
      about a minute, the run recorded in the application (98.5k tokens,
      estimate 0.18 USD). Two bundles on sibling branches received the same
      objective, "check existing data for constraint violations before adding
      a unique index and write the migration", which is the grouping the
      objective exists for. Goals proved too dense for a list, which led to
      the summary field; these drafts predate it and show their goal until a
      reviewer adds a summary. The title falls back to the objective, never
      to the goal.
    - [x] Third synthetic run, 2026-10-23, over all four fixtures after the
      summary field landed: 16 drafts, run recorded (`/api/v1/runs`). Every
      draft carried a readable summary that now serves as its title, and
      objectives stayed general enough to group: two sibling-branch drafts
      again shared one objective. Review surfaced two gaps fixed the same
      day: whole-event citations of tool turns resolved to no excerpt (now
      the tool output, shown as code, and every cited turn lists its tool
      calls), and reviewers had no way to step through drafts (now
      previous/next in the editor).
    - [ ] Remaining two synthetic fixtures (compaction, no headings), then a
      private import once anonymized.
  - [ ] Decide whether the model should receive shortened event ids. Current
    ids repeat the conversation id in every event and block reference, which
    inflates prompts on long conversations.
  - [x] Idempotency for `propose_bundle`: `POST /api/v1/bundles` accepts a
    `request_id` and returns the existing bundle (200) on repeat; the harness
    derives the id from run id, conversation, and a digest of the proposal, so
    a retry after an interrupted call cannot create a near-duplicate.
- [ ] Review a bounded pilot of roughly 20–50 conversations when available, including successes, failures, and recoveries. Record context omissions, invalid references, and whether bundles support useful judgments; no model work is implied.

## Interface follow-ups

The first review surface is the bundle list's "Proposed drafts" view plus the
editor: accept is a human revision with `status=reviewed`, reject is a human
revision with `status=rejected` and a rationale, and edit is the editor as it
stands. Defer is implicit (leave the draft). The accepted
[suggestion review decision](../evaluation-workbench-ui/decisions/suggestion-review.md)
covers the fuller queue; these notes record what remains, with the
review-console shape of
[offgrid-review](https://github.com/jd-santos/offgrid-review) as a reference:

- The list filters by run (`?run=<run id>`). The editor's run link opens the
  run's page under Runs, which lists every recorded model run by workflow with
  tokens and estimated cost, and per run shows usage by model and each input's
  outcome, produced bundles, and usage. Usage is per input, not per bundle; a
  per-bundle figure would need the harness to record usage per proposal call,
  which is a run record contract change. The Proposed view groups drafts by
  run, naming each run's model and start time.
- Each item already shows objective, rationale, missing evidence, excerpts with
  roles (marked with a speaker glyph) in conversation order, gaps, producer,
  jump-to-source, and an "Earlier import" mark (with a header count) when the
  cited conversation revision is no longer latest.
- Fingerprint what was reviewed: the bundle revision number is the fingerprint,
  and a decision taken against an older revision must be rejected, which the
  409 on stale saves already enforces.
- Batch accept or reject should stay within one run so cost and coverage stay
  legible. The editor reviews one bundle at a time, with previous/next links
  that follow the order of the list it was opened from (view and run carry in
  the URL) and a "Next bundle" link after a save.
- The reader marks cited turns from `GET /conversations/{id}/bundles`, which
  lists each citing bundle's latest status, origin, run, and event ids.
  Pending generated drafts, accepted or human bundles, and rejected bundles
  carry distinct marks, so inline review does not read as approval.
- Rejected proposals are evidence for improving the proposer. The "Rejected"
  view keeps them queryable; nothing deletes a bundle.

## Verification

Manual bundles, 2026-10-19: `uv run pytest` 224 passed; ruff check and format
clean; web check, lint, and 50 vitest tests pass. A local browser pass against
the synthetic demo library confirmed select, highlight, create, edit, save, the
sibling-branch rejection, and no horizontal overflow at phone width.

Outlines and the generated path, 2026-10-19: `tests/test_outline.py`,
`tests/api/test_outline_api.py`, and the generated-origin case in
`tests/api/test_bundle_api.py` pass with the full suite; ruff clean. In
`harness/`, `npm run check` and `npm test` pass. A tool smoke run against a
disposable demo data root listed conversations, outlined one, read events,
received `event_not_found` for a bad reference, and created a generated draft
bundle. No model call was made at that point.

First operator run, 2026-10-22: `propose-bundles` against the pilot API with
`anthropic/claude-sonnet-5-5` on one synthetic conversation produced three
generated drafts with run provenance and request ids, listed under the
"Proposed drafts" view with the run link, and a run report under
`reports/harness/` recording the gateway override. Harness `npm run check`
and `npm test` pass with the base URL override tests.

Goal/objective split and run records, 2026-10-22: the full Python suite
(254 tests, including the version 1 upgrade, goal round trip, and run record
tests), ruff, harness `check` and `test`, and the web suite (62 tests with
the goal field, objective column, and run usage line) pass. The pilot data
root migrated to `0006`; the three first-run drafts read back with their
objective copied into the goal. A second operator run with the new analyst
instructions, which should produce general objectives and specific goals,
is pending a provider key.

## Supporting material

- [Current priorities](../../TODO.md)
- [Analysis harness](../analysis-harness/README.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
