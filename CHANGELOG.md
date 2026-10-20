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

### Changed

- Prioritize the conversation library and expand the roadmap and design records
  for recovery, enrolled cross-machine push collection, and reviewed evidence
  bundles.
- Replace the legacy task list with a P1–P5 priority workbench and readable,
  durable work records.
