# Build the Pi Durable analysis harness

Status: In progress on `task/bundle-parsing-tools`. The package, API client,
library tools, and the first workflow exist; no operator run has happened yet.

## Purpose

Give Benchwarmer's own model-driven workflows one durable runtime instead of a
pile of scripts. The first workflow proposes evidence bundles. Later ones parse
non-Markdown responses into table-of-contents headings, turn real conversations
into anonymized fixtures, and support enrichment. Anything deterministic stays
in Python; the harness orchestrates models around typed API routes.

This harness is Benchwarmer's internal tooling. It is not a candidate harness
under evaluation and must not blur that line: experiments still treat Pi,
Hermes, Codex, and direct API execution as separate harness dimensions.

## Decisions

Decided with the user on 2026-10-19:

- Use `@earendil-works/pi-durable`, pinned exactly (`1.3.0`), in `harness/`
  beside `web/`, with its own `package.json`. It is experimental and its API
  changes without notice; upgrades are deliberate and re-verified.
- The harness reaches data only through `/api/v1`. It never opens the SQLite
  file. Python stays authoritative for contracts, validation, and revisions.
- Read tools are declared replay-safe; write tools are not, so an interrupted
  write is reported to the model instead of silently repeated.
- Durable storage lives under the gitignored `.benchwarmer/harness/`; run
  reports under the gitignored `reports/harness/`. One process owns a storage
  file at a time.
- Running a workflow by hand with named inputs and operator keys is the
  approval for its model work until the bounded model-work service exists.

Decided with the user on 2026-10-21:

- The harness is provider-neutral within an explicit exclusion list
  (`EXCLUDED_PROVIDERS` in `harness/src/providers.ts`; the user has ruled out
  xAI and Groq). Every other pi-ai provider is registered and the
  operator supplies the key for the one named on the command line; nothing
  looks for an Anthropic key specifically.
- Generated revisions carry run provenance, and non-replay-safe writes carry
  a request id derived from the run so retries cannot duplicate records.

## Acceptance criteria

A workflow can be interrupted and resumed without repeating committed model
turns or re-running non-replay-safe writes. Every generated record names its
producer and model, and every run leaves a report with per-input usage. Adding
a workflow does not require new Python unless it needs a new deterministic
capability, which then lands as a typed route first.

## Work

- [x] Package scaffold with pinned dependencies, strict TypeScript, vitest,
  typed API client, and model-facing formatters (`harness/src`).
- [x] `benchwarmer-library` extension: `list_conversations`, `get_outline`,
  `read_events`, `list_bundles`, `propose_bundle`.
- [x] `propose-bundles` workflow and CLI with SQLite storage, per-conversation
  usage deltas, and a JSON run report labeled as a catalog estimate.
- [ ] First operator run; record cost, duration, and resume behavior after a
  deliberate interruption.
- [ ] Shared conventions for later workflows: where instructions live, how a
  workflow names its producer, and how reports are versioned.
  - [x] Providers: `src/providers.ts` registers the pi-ai catalog minus the
    exclusion list; a
    workflow fails fast with a provider-neutral hint when the chosen
    provider's key is absent.
  - [x] Provenance: a workflow passes a `RunProvenance` record to its write
    tools so generated revisions name the run, and derives idempotent request
    ids for writes from the run id and content.
- [ ] Table-of-contents headings for non-Markdown responses: decide what is
  deterministic (candidate line detection in Python) and what needs a model.
- [ ] Fixture-from-conversation workflow that rewrites private details into a
  synthetic fixture. Requires an explicit disclosure decision before any
  private conversation is sent to a provider, and a diff review before the
  fixture enters `tests/fixtures/`.
- [ ] Decide whether harness runs should register as model-work plans once the
  [bounded model-work service](../bounded-model-work/README.md) exists, so the
  pilot exception can end.

## Verification

2026-10-19: `npm run check` and `npm test` pass in `harness/`. Tool smoke run
against a disposable demo data root succeeded without a model call. Node prints
an experimental-feature warning for `node:sqlite`; it is expected.

## Supporting material

- [Harness README](../../../harness/README.md)
- [Evidence bundles work record](../evidence-bundles/README.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Pi Durable package](https://github.com/earendil-works/pi/tree/main/packages/durable)
