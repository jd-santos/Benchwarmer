# Benchwarmer architecture

## Product direction

Benchwarmer is a local app for choosing models using personal experience,
task simulations, trusted public evaluations, and usage economics. It runs on
the user's always-on Mac mini alongside Nous Research's Hermes Agent. The
repository is intended to be public; personal data stays local.

The main questions are:

- What am I using and spending across Pi, Hermes, and Codex where accessible?
- Can a cheaper model do the kinds of work I already do well enough?
- Could another model or harness do better, even when the original session worked?
- How do my observations compare with published evaluations I trust?

Everyday sessions supply candidate tasks. Initially, personal evaluation means
ratings and notes. Repeatable evaluations should emerge from useful simulations
and reviewed sessions rather than a predetermined benchmark pack. Benchwarmer
supports experimentation; the user's actual work continues in their harnesses.

This direction supersedes the original standalone benchmark-runner MVP. A custom
agent loop, fixed 20-task pack, named model judge, and self-contained HTML as the
primary interface are no longer initial requirements. Harness-neutral tasks,
preserved trials, and separate quality and economics remain core.

## Application shape

Use SQLite for structured data, a Svelte frontend, and a Python 3.12+ backend
managed with uv. Large private artifacts live in local files referenced by the
database. The exact backend framework and Svelte tooling remain open.

The intended runtime has a local API and a background execution worker. Import
and experiment state persist independently of the browser. Start with one local
installation; multi-user hosting and synchronization are outside the initial
scope. Plan for private access over Tailscale from other devices, with a
mobile-friendly frontend. The serving mechanism, process binding and access
configuration remain implementation decisions in [decisions.md](decisions.md).

Core workflows must work on phone-sized screens: browsing usage, filtering
sessions, adding ratings and notes, viewing experiment progress and reviewing
results. Charts and navigation must support touch. Comparisons should offer
stacked or switchable views on narrow screens; wide tables and code panes should
not force the whole page to scroll horizontally. The database and execution
worker remain on the Mac mini.

| Component | Responsibility |
| --- | --- |
| Svelte frontend | Usage charts, session inspection, annotations, experiments and saved evidence |
| Python API | Queries, validation, configuration, annotations and experiment operations |
| Worker | Imports, reconciliation, execution, progress and recovery |
| SQLite | Versioned records, relationships, provenance, annotations and durable job state |
| Private artifact directory | Transcripts, prompt snapshots, fixtures, outputs and raw source records |
| Adapters | Harness imports/execution, provider usage, pricing and published evidence |

This is a design, not an implemented service. Add dependencies when an implemented
feature needs them. Choose job scheduling and SQLite concurrency details during
implementation; interrupted jobs must never silently rerun paid work.

## Application areas

### Activity and usage

Import sessions and usage from Pi, Hermes, and Codex to the extent each source
allows. Combine harness observations with provider records when useful. Support
date, harness, provider, model, project and classification filters, charts, and
drill-down to sessions or individual usage records.

Show source coverage, last successful import, and unavailable fields. A source
may offer account totals without session attribution. Keep those totals useful
without inventing a breakdown.

### Personal review

Attach ratings, labels and notes to sessions and trials. Successful sessions are
valid simulation seeds. Record interventions and retries when available, but the
product is not a workflow for rescuing failed tasks.

### Experiments

Prepare tasks from imported work and run alternative model/harness configurations.
Broad sweeps across inexpensive candidates are a first-class use case. Each task
needs reviewed starting context and an explicit definition of what it tests;
an arbitrary transcript is not automatically executable.

Compare outputs and artifacts with usage and criterion-level judgments. Keep all
attempts, including failures and incomplete runs. See
[experiments.md](experiments.md) for harness, prompt and simulation semantics.

### Trusted external evidence

Keep a dated collection of evaluations the user trusts. Begin with saved links,
notes and published results where available. Record publisher, publication and
retrieval dates, benchmark/version, model/configuration, methodology, units, and
source artifact or permitted excerpt when available.

Preserve updated publications as distinct revisions. Missing configuration
details remain unknown. Do not merge unrelated benchmark scores into a common
ranking or treat a model-only result as evidence about every harness using it.

Automated fetching is source-specific and optional. Published APIs, exports,
access terms and reuse permissions need verification before building importers.
The initial product does not require broad scraping or a news feed.

### Model views

Bring activity, experiments, and saved evidence together for a model. Preserve
provider-specific IDs, versions and aliases; uncertain identity mappings remain
visible. A shared display name is insufficient to merge records or conclude that
configurations are equivalent.

## Core records

These are conceptual boundaries, not a finalized SQL schema.

| Record | Meaning |
| --- | --- |
| Source / import batch | Source identity, cursor, coverage, timestamps and import outcome |
| Session | Observed harness session, source ID, metadata and linked artifacts |
| Usage observation | Raw and normalized usage at request, session or account scope |
| Price snapshot | Effective date, source, currency, rates and estimation assumptions |
| Classification | Label, subject, origin, classifier/version and confidence if supplied |
| Annotation | Human rating, note or correction with subject and revision history |
| Task version | Harness-neutral intent, starting inputs, fixture and success criteria |
| Task source link | Sessions or evidence used to derive a task, with extraction notes |
| Harness configuration | Harness identity/version, execution mode and settings snapshot |
| Candidate configuration | Model, provider, reasoning, harness, prompts, skills, tools and sampling |
| Experiment | Task/configuration matrix, repetitions, budgets and execution policy |
| Trial | One attempt with status, observed configuration, artifacts and usage |
| Judgment | Criterion-level human, deterministic or model assessment with evidence |
| External evaluation | Published result or reference, its provenance and revisions |
| Job | Durable import/execution work, progress, cancellation and recovery state |

One session may yield several tasks, and one task may draw on several sessions.
Task versions and trial configuration snapshots remain stable after execution.
Keep observations separate from judgments so later review does not rewrite what
was recorded. Version serialized schemas from the start and use database
migrations when their structure or meaning changes.

## Usage and cost semantics

Keep raw provider usage and the pricing source behind each estimate. Preserve
input, cached input, output, reasoning and other token categories when exposed,
along with batch behavior, latency and provider-specific fields. Do not sum
overlapping token categories as if they were disjoint.

Distinguish actual provider charges, API list-price estimates, subscription
payments, quota consumption, credits and remaining capacity. An API-equivalent
estimate is not an actual subscription charge. Initially, subscription expense
belongs at account/period scope; do not allocate it across tasks without an
explicit later decision.

Imports must be idempotent. Harness and provider observations can refer to the
same request: retain both sources but reconcile their relationship before
aggregating. Account totals may also overlap session totals. Unmatched records
and reconciliation differences should be inspectable rather than silently added
together. Store currency and reporting time zone explicitly.

Track provider classifications, user labels and Benchwarmer-generated labels
with separate provenance. OpenRouter's recently introduced classifications are a
requested integration target; their interface, granularity and historical
availability have not yet been verified for this project.

## Source feasibility

Pi and Hermes imports and execution adapters require inspection of their actual
local versions, storage formats and supported interfaces. Codex import and
execution are separate capabilities; neither is a prerequisite for the initial
app. Build a source coverage matrix before promising parity.

The official [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server),
reviewed on 2026-09-07, documents `account/usage/read` for account token summaries
and optional daily buckets, `account/rateLimits/read` for quota information, and
`thread/tokenUsage/updated` for active-thread usage. These are potential data
sources, not proof of complete historical coverage or per-model billing access.
Availability in the installed version and account remains to be tested.

## Local data boundary

The application data root should default outside the repository and be
configurable. Its exact location, backup and retention policy remain open.
Retain private snapshots of imported session content alongside normalized
metadata, so source-log deletion or changes do not erase comparison evidence.
Record source identity and capture time; retention and deletion rules remain open.

SQLite databases, journal/WAL files, raw usage, session content, system prompts,
annotations, fixtures, outputs and logs belong within that private boundary.
Backups need to preserve database/artifact consistency.

The existing gitignored `.benchwarmer/`, `artifacts/` and `reports/` directories
remain available for development data. Public fixtures or exports require
deliberate sanitization. Keep credentials out of imported snapshots, logs and
exports; use configured credential references for execution.

Run simulations with file or shell tools only in disposable fixture workspaces.
Live project paths and captured commands are evidence, not instructions to run
against the user's working environment. Network access, external mutations and
credential availability need an explicit run policy.

## Delivery stages and acceptance criteria

### 1. Data feasibility and application foundation

Document coverage for each harness/provider and select the first import source.
Establish the Python API, SQLite migrations, private artifact root and Svelte UI.
Use sanitized fixtures for development. Establish private access over Tailscale
and verify responsive layouts on phone and desktop viewports. No custom agent
loop is required.

### 2. Useful activity and personal review

The first useful release imports at least one real source without duplicates,
supports incremental updates, and shows usage charts and session detail. Ratings
and notes survive restart. Costs retain provenance; missing fields remain visible.
Add a second source to verify consolidated totals and reconciliation rather than
assuming one adapter generalizes.

### 3. Saved external evidence

Save and retrieve trusted evaluations with source dates, model identity and
notes. Attach structured results where available without forcing a common score.

### 4. Task simulations and comparisons

Derive and version a task from actual work, select a harness configuration, and
run at least two candidate models using native harness configurations first.
Preserve prompt capture status and all trials,
compare quality and economics independently, and keep workspaces disposable.
Budget limits, cancellation and restart recovery work without duplicate paid
attempts. Add another harness, including direct API execution, to verify the
cross-harness representation.

### 5. Organic evaluation collections

Promote useful tasks into repeatable suites, add fixed multi-turn scripts and
deterministic checks, and assess whether model judges would help. If introduced,
calibrate judges against human labels and record their configuration and cost.

## Alternatives and deferred work

- A usage-only dashboard is smaller but leaves simulation context and review
  disconnected. Usage remains the first delivery slice within the broader app.
- A notebook or static HTML report cannot serve as the primary durable workflow
  for imports, annotations and jobs. Portable reports may follow as exports.
- An evaluation-first platform postpones useful everyday data and commits too
  early to a task taxonomy and agent loop.
- A Pi-only core prevents independent harness comparisons. Pi and Hermes remain
  adapters, with direct Python API execution represented as another harness.
- Hosted multi-user deployment adds identity, access and maintenance work that
  the initial personal Mac mini installation does not need.
- Automatic routing, LLM-simulated users, subscription-cost allocation, a custom
  agent loop, automated source discovery and public sharing are deferred.

See [decisions.md](decisions.md) for unresolved choices and [TODO.md](TODO.md) for
the implementation queue.
