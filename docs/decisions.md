# Design decisions

Independently authored proposals live under [decisions/](decisions/README.md).
This document remains the canonical summary after a coordinating task reviews
and integrates those records.

The product direction is agreed: a private conversation library with a Python
backend, SQLite/Svelte application, cross-machine collection, normalized evidence,
search, collections, and model evaluations. Usage/cost are shared metadata;
detailed reporting and trusted external evidence follow the useful library.
Harness and system prompts remain explicit dimensions; direct Python API
execution is a harness. The approved workflow is in
[conversation-library.md](conversation-library.md).

## Confirmed starting choices

- **Library priority:** Retain native snapshots plus versioned shared conversation
  structure, including messages, tool activity, branches, and artifact references.
  Build browsing and text/metadata search before detailed usage reports; semantic
  search and the wider enrichment field set remain explicit planned capabilities.
- **Enrichment:** Separate imported, calculated, generated, and human evidence.
  Use task-appropriate configurable model tiers, with provenance and revisions.
  Compute cost estimates from price evidence, not model judgments.
- **Model-work approval:** Import does not authorize inference. Preview and
  explicitly approve frozen batches with request/resource/cost limits. Include
  embeddings, query embeddings, reruns, applied judges, retries, and escalations.
  No automatic work from growing collections; no default numeric spend limit.
  Content/provider disclosure permission is separate from spending approval.
- **Collections:** Support live saved queries and frozen datasets, plus versioned
  private read/query/export access for ad hoc projects. Runs pin input revisions.
- **Evaluation units:** Meaningful one-to-few-exchange segments with sufficient
  context. Single-response/action and applicable fixed follow-ups precede later
  adaptive user continuation. Preserve correlated lineage and leakage boundaries.
- **Applied judges:** Judging runs automatically within an explicitly approved
  rerun plan. Expose rubric/model/configuration and cost; unjudged is not failure.

- **Application foundation:** Use FastAPI/Uvicorn, synchronous SQLAlchemy 2 with
  explicit Alembic migrations, and a TypeScript SvelteKit client under `web/`.
  JSON routes live under `/api/v1`; Python remains authoritative for domain
  rules and persistence. Pin Svelte CLI `0.17.0` and npm's lockfile. See
  [ADR 0001](decisions/0001-application-foundation.md).
- **Access:** Build the frontend with `adapter-static` and a `200.html` fallback,
  then serve it and `/api/v1` from one loopback-only Python process. Use private
  Tailscale Serve HTTPS and Docker Compose restart supervision. Live target-host
  checks remain [private deployment verification](../todo/work/private-deployment/README.md). See
  [ADR 0003](decisions/0003-serving-supervision.md).
- **Session storage:** Keep private source snapshots plus normalized metadata
  beneath a configurable root outside the checkout. The database, artifacts,
  and snapshots are durable; jobs, logs, and locks are transient. Back up SQLite
  through its Online Backup API under an application write gate, with manifested
  artifacts and staged restore. See
  [ADR 0002](decisions/0002-data-recovery.md).
- **SQLite safety:** WAL is prohibited unless the process-linked SQLite includes
  the WAL-reset fix: `3.51.3+`, `3.50.7+` on the 3.50 branch, or `3.44.6+` on the
  3.44 branch. [The pinned runtime](runtime-recovery.md) uses source-built
  Python 3.13.15 with SQLite
  3.53.4, validates required modules, and fails closed when its immutable runtime
  path or recovery state is not safe to use.
- **First import adapter:** Use a schema-gated, read-only Hermes SQLite adapter.
  Namespace source-native session, message, and usage keys by installation and
  profile; combine a committed message watermark with mutable-row rereads and
  full reconciliation. Keep source payloads private and preserve unavailable and
  unknown fields explicitly. See
  [ADR 0004](decisions/0004-first-import-adapter.md).
- **Cross-machine collection:** Use one manually invoked push collector per Mac,
  with source-specific adapters, explicit path allowlists, device enrollment,
  private spooling, and acknowledgment only after durable central commit. Add an
  optional three-or-four-times-daily `launchd` schedule after the manual path is
  reliable. Keep browsing central over Tailscale; desktop sync is deferred. See
  [ADR 0005](decisions/0005-cross-machine-collection.md).
- **Experiments:** Start with native harness configurations, capturing accessible
  system prompts, tools, skills and differences. Controlled comparisons remain
  a later capability, rather than an initial requirement.

## Evidence analysis direction

Use [evidence references and bundles](evidence-bundles.md) between retained
conversations and task versions. Promote exact event/block references into the
shared enrichment contract, review manual bundles before broad extraction, and
keep patterns overlapping and versioned. Preserve successes and recoveries in
dataset selection. Candidate context and historical judging evidence stay separate.
Deterministic outlines and approved selective inspection can reduce analysis cost;
sample unflagged cases to measure what screening misses. These are planned
capabilities and do not authorize model dispatch or change frozen runs.

## Before collector implementation

[ADR 0005](decisions/0005-cross-machine-collection.md) selects the topology.
The [collection work record](../todo/work/cross-machine-collection/README.md)
must decompose the manual
collector, versioned push protocol, enrollment, durable acknowledgment, bounded
spool, and optional `launchd` schedule before implementation. Pin exact resource
ceilings, credential rotation, packaging, and source-specific cursor behavior in
those plans.

No live transport is authorized by the shared-record schema or the accepted ADR.
Collector rollout still depends on its synthetic security/recovery tests and the
private deployment gate. Do not assume all histories are on the Mac mini or grant
it remote shell, Docker, or arbitrary filesystem access to a source machine.

## Before model-powered enrichment

Choose the first field set, configured small/large model tiers, explicit batch
limits, price evidence, and permitted content/provider scope. Unknown pricing
requires a separately agreed non-monetary policy, not unbounded execution.
Durable budget reservations, cancellation, and outcome-unknown recovery must
exist before any paid stage is dispatched. A pure preview/approval validator is
only a prerequisite, not that execution service.

## Before the first simulation

### First task family

- **Why it matters:** Coding, research, and text tasks need different fixtures
  and tools.
- **Proposed starting point:** Select representative everyday tasks after
  inspecting sessions.

### First execution harness

- **Why it matters:** Establishes process control and capture requirements.
- **Proposed starting point:** Use Pi or Hermes based on supported automation,
  with a direct API baseline where capabilities fit.

### Reconstruction threshold

- **Why it matters:** Transcripts may lack starting files or external state.
- **Proposed starting point:** Require reviewed inputs and fixtures, with
  approximations labeled before a sweep.

### Scope and budget of broad sweeps

- **Why it matters:** Cheap calls multiply across tasks and retries.
- **Proposed starting point:** Require explicit count/time limits and a total
  spend policy; never run unbounded work on import.

### Meaning of good enough

- **Why it matters:** Enables useful comparison without a universal score.
- **Proposed starting point:** Pin task-specific criteria before a run; apply
  selected model judges and verifiable checks inside its approved budget. Human
  notes and calibration provide a reliability check, not a mandatory per-run step.

A direct API baseline cannot replace a tool-using harness on tasks that require
it, even when both are represented through the same experiment interface.

## Can wait until the relevant feature

- Initial external evaluation sources and their APIs, exports or permitted snapshots.
- Annotation scales, blind comparison and review ordering.
- Controlled comparison support: prompt overrides, tool/capability alignment,
  fixed variables and disclosure of remaining differences between harnesses.
- Historical pricing sources and optional API-equivalent subscription estimates.
  Keep actual charges and estimates separate from the beginning.
- Exact attachment metadata limits and any future selective raw-content deletion;
  ADR 0005 retains accepted central history indefinitely by default.
- Which simulations warrant promotion into named evaluation suites.
- Specific deterministic graders and judge calibration protocol before the first
  rerun; portable reports and sanitized public exports can follow private access.
- Adaptive-continuation simulator policy, allowed knowledge, and validation after
  single-unit and applicable fixed-sequence tests.
- Repository visibility/license verification before distributing third-party
  fixtures or source material. Public code does not make personal data public.

Implementation tasks live in [the priority index](../todo/TODO.md). This document records choices
and rationale rather than duplicating execution status.
