# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
This project does not currently declare a Semantic Versioning policy.

## Unreleased

### Added

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

- Mark evidence items whose conversation changed in a later import, with a
  count in the bundle header, so a reviewer knows the cited version is pinned.
- Group the Proposed drafts view by the run that proposed each draft, naming
  the run's model and start time with links to the run page and to that run
  alone.
- Mark each evidence item's speaker with a small user, assistant, or tool glyph
  beside the role name, drop the "Whole message" scope label (a narrower scope
  is still named), and remove the item reorder arrows. Token and cost figures
  leave the bundle pages for a dedicated runs page.
- Prioritize the conversation library and expand the roadmap and design records
  for recovery, enrolled cross-machine push collection, and reviewed evidence
  bundles.
- Replace the legacy task list with a P1–P5 priority workbench and readable,
  durable work records.
