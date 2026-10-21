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
- Register every pi-ai provider in the harness (Anthropic, OpenAI, OpenRouter,
  Google, xAI, Groq, Mistral, and the rest); the operator supplies whichever
  provider key matches the chosen `provider/model-id`.
- Add the fixture anonymizer groundwork: `benchwarmer.anonymize` scrubs
  normalized events with stable placeholders and reports spans without the
  original values, plus fidelity and leak checks for candidate fixtures.
  `POST /api/v1/fixtures/scrub-pi-session` and `POST /api/v1/fixtures/check`
  take raw Pi session content and store nothing. The harness gains an
  `anonymize-fixture` workflow with an explicit `--disclose-to` gate that
  writes fixture drafts under `reports/harness/fixtures/` for human review.

### Changed

- Prioritize the conversation library and expand the roadmap and design records
  for recovery, enrolled cross-machine push collection, and reviewed evidence
  bundles.
- Replace the legacy task list with a P1–P5 priority workbench and readable,
  durable work records.
