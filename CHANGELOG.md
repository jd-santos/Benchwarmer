# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
This project does not currently declare a Semantic Versioning policy.

## Unreleased

### Added

- Define the Benchwarmer conversation file (format v1), one JSON document per
  conversation that any system can write for import, with a reference doc, a
  JSON Schema, a `benchwarmer-validate` CLI that needs no database, a Python
  builder, and a reference converter from a synthetic agent product log. The
  file carries system prompts, tool definitions, per-turn model provenance,
  attached context, feedback, and rewinds as branches; these survive import as
  typed extension keys on the unchanged normalized conversation v1.
- Import conversation files as kind `conversation_file` from a host path or
  by `POST /api/v1/imports/conversation-files`, which stages the file under
  the data root and returns the batch, conversation id, and revision. Imports
  are idempotent by content; a changed file adds a revision.
- Add `benchwarmer.registry`, one place naming import kinds, export sinks
  (`file`), and scrub detector kinds; `/api/v1/imports/config` lists what it
  registers.
- Pull approved task versions without the web app: `GET /api/v1/task-versions`
  lists them with digest-relevant fields, and
  `GET /api/v1/tasks/{id}/export/{version}?terms=...` returns the same case
  record as the POST export.
- Prepare a reviewed bundle as a versioned task (`/api/v1/tasks`, Tasks page):
  a cut point that ends the candidate's view, criteria of acceptable behavior
  with a method (human, model judge, deterministic) and rubric version, the
  reconstruction level with its gaps, a family and partition, and a leakage
  review. Deterministic leakage flags (an answer cited before the cut, a
  criterion quoting the historical answer, a cut on an assistant turn, judge
  text already in the candidate section) must each be accepted before
  approval; approved versions are immutable in content and retired is final.
- Export an approved task version as a case record (`POST
  /api/v1/tasks/{id}/export`): case metadata, a candidate section cut at the
  cut point with reasoning dropped, and a judge section with the historical
  turns and cited items. One scrub pass covers both sections with the given
  terms plus the built-in kinds; the record carries a manifest of counts and a
  digest, never the original values.
- Add Pi session and run-log import plus ChatGPT account-export import, with
  private native snapshots, normalized branch structure, and explicit coverage
  for fields the source does not expose.
- Add canonical conversation and bounded model-work validation contracts with
  synthetic fixtures.
- Add a schema-gated, WAL-aware, read-only Hermes schema-30 adapter with a
  synthetic upstream-pinned fixture and bounded private-data failures.
- Add incremental Hermes persistence with private content-addressed snapshots,
  source-native upserts, normalized conversation revisions, cursor state, and
  durable failed-batch records.
- Add private data-root configuration, Alembic migrations, source and import-batch
  records, synthetic fixture loading, and database-backed health and source-status
  APIs.
- Add responsive overview and source-coverage pages with unit and disposable
  desktop and mobile browser tests.
- Serve the built Svelte application and versioned API from one FastAPI origin
  with strict SPA fallback and API restart-persistence coverage.
- Add deterministic conversation outlines (`GET /api/v1/conversations/{id}/outline`)
  with per-event sizes, captured tool activity, heading ranges that double as
  evidence references, and per-path exchanges and segments.
- Accept generated-origin bundle revisions with a named producer, so
  model-proposed bundles land as drafts beside human ones.
- Add the `harness/` Pi Durable package with API-backed library tools and a
  manually run `propose-bundles` workflow that writes a per-conversation usage
  report.
- Review proposed bundles in the web app: the list shows each bundle's origin
  and producing model with a "Proposed drafts" view, the editor flags
  unreviewed proposals, and a new `rejected` status keeps declined proposals
  with a required reason. `GET /api/v1/bundles` filters by `origin` and
  `status`.
- Record run provenance (run id, workflow, harness version, provider, model,
  thinking level, report path) on generated bundle revisions, filter the
  bundle list by `run_id`, and link each proposal to its run in the web app.
- Make bundle creation idempotent with a client `request_id`; the harness
  derives one from the run and proposal content so an interrupted
  `propose_bundle` retry returns the existing bundle instead of a duplicate.
- Register the pi-ai provider catalog in the harness (Anthropic, OpenAI,
  OpenRouter, Google, Mistral, and the rest) behind an explicit exclusion
  list; the operator supplies whichever provider key matches the chosen
  `provider/model-id`.
- Let a harness provider be routed through a pass-through gateway with a base
  URL variable such as `ANTHROPIC_BASE_URL`; run reports record the override.
- Split a bundle's `goal` (what this piece of work tried to achieve) from its
  `objective` (the kind of work in general terms, for grouping bundles later).
  Add a human-readable `summary` as the bundle's title. Bundle documents are
  version 2; version 1 documents are read with their objective carried into
  the goal. The proposer, list, and editor use all three.
- Show tool calls and tool output cited as evidence as code in the bundle
  editor instead of "Text not captured": a whole-event citation of a turn with
  no prose resolves to its tool output, and every whole-event citation lists
  the turn's tool calls under its prose, one line each and expandable to the
  indented arguments. Each item's source line and note sit above its excerpt.
  Step through bundles from the editor with previous/next links in the order
  of the list the bundle was opened from, with the way back to that view.
- Import conversation files already on the host from the Sources page: a Pi
  session file or directory, or a ChatGPT export, into a configured source.
  The server accepts only paths under the directories listed in
  `BENCHWARMER_IMPORT_ROOTS`, records every attempt (including refusals it
  could read but not import), and skips files it has already imported
  unchanged. Importing never starts model work.
- Add a Runs page to the web app: every recorded model-driven run by workflow,
  most recent first, with raw token usage and catalog cost estimates, and a
  per-run page with usage by model or tool and each input's outcome, produced
  bundles, and usage. Bundle proposals are one workflow among those listed.
- Record each hand-run harness workflow in the application
  (`PUT /api/v1/runs/{run_id}`, `GET /api/v1/runs`) with raw usage and the
  catalog cost estimate; the bundle list and editor show what a run or a
  conversation's pass cost beside its proposals.
- Add the fixture anonymizer groundwork: `benchwarmer.anonymize` scrubs
  normalized events with stable placeholders and reports spans without the
  original values, plus fidelity and leak checks for candidate fixtures.
  `POST /api/v1/fixtures/scrub-pi-session` and `POST /api/v1/fixtures/check`
  take raw Pi session content and store nothing. The harness gains an
  `anonymize-fixture` workflow with an explicit `--disclose-to` gate that
  writes fixture drafts under `reports/harness/fixtures/` for human review.
- Add `tests/fixtures/demo-long-conversations.json`: four long synthetic
  coding-agent sessions (debugging with a rejected hypothesis, a feature build
  across a compaction and model change, a branched session with a failed tool
  call, and a prose plan review that continues the debugging session) for
  outline and bundle-proposal work, loaded by the foundation demo script.

### Changed

- Classify each evidence bundle by type of work from a closed vocabulary
  (`bug`, `feature`, `refactor`, `test`, `performance`, `infrastructure`,
  `analytics`, `research`, `design`, `writing`, `review`, `unknown`). The
  bundle document is now schema version 3; earlier versions read as
  `unknown`. The proposer types each new bundle in a separate step after
  drafting it, a reviewer can change the type in the editor, and the list
  shows and filters by it.
- Start the bundle proposer from the Bundles page: choose conversations and
  a model, preview the frozen plan with its digest, approve exactly that
  plan, and watch it run, cancel it, or open its run. Only an application
  with `BENCHWARMER_HARNESS_DIR` set can start a run; others preview and show
  how to run the plan by hand. Plans left running when the application stops
  are marked interrupted and never rerun on their own (ADR 0006, proposed).
- Choose the model for an app-started run from a list instead of typing it:
  the harness lists the providers whose keys the server holds and merges each
  provider's own model list, models.dev, and the pinned pi-ai catalog
  (`npm run list-models -- --json`, `GET /api/v1/model-work/models`). The
  thinking selector offers only the chosen model's levels, a model missing from
  the pinned catalog runs with its nearest sibling's settings and records which
  price estimate applied, and a typed `provider/model-id` remains available.
- Mark evidence items whose conversation changed in a later import, with a
  count in the bundle header, so a reviewer knows the cited version is pinned.
- Group the Proposed drafts view by the run that proposed each draft, naming
  the run's model and start time with links to the run page and to that run
  alone.
- Mark turns that evidence bundles cite in the conversation reader, with a
  link to each bundle. Pending generated drafts are marked apart from human
  or reviewed bundles, and rejected ones apart again, so an inline mark never
  reads as approval. Backed by a new read route listing the bundles that cite
  a conversation and the events they cite.
- Mark each evidence item's speaker with a small user, assistant, or tool glyph
  beside the role name, drop the "Whole message" scope label (a narrower scope
  is still named), and remove the item reorder arrows. Token and cost figures
  leave the bundle pages for a dedicated runs page.
- Prioritize the conversation library and expand the roadmap and design records
  for recovery, enrolled cross-machine push collection, and reviewed evidence
  bundles.
- Replace the legacy task list with a P1–P5 priority workbench and readable,
  durable work records.
