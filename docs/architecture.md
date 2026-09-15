# Benchwarmer architecture

## Product direction

Benchwarmer is a private conversation library and evaluation app. It collects
work from Codex, Pi, Hermes, and later sources across the user's machines into a
central installation on an always-on Mac mini. Native transcripts and normalized
records support browsing, metadata enrichment, search, ad hoc projects, and
model comparisons. The repository is public; personal evidence stays private.

The main questions are:

- Where is the conversation or decision I want to revisit across my tools?
- What kinds of work am I doing, with which models and at what cost?
- Can I collect relevant examples, such as software work, for an evaluation?
- Could another model or harness do that work better or more cheaply?
- How do automatic judgments compare with human review and trusted evaluations?

The delivery priority is collect, normalize, enrich, discover, select, then
evaluate. Usage and cost are metadata; detailed reporting and external-evidence
dashboards follow the useful library. Everyday sessions supply task units and
frozen datasets rather than a predetermined benchmark pack. The user's actual
work continues in their harnesses. See
[conversation-library.md](conversation-library.md) for the approved workflow,
collection topology, enrichment scope, and spending controls.

This direction supersedes the original standalone benchmark-runner MVP. A custom
agent loop, fixed 20-task pack, fixed named judge model, and self-contained HTML
as the primary interface are not initial requirements. Configurable applied
judges are part of approved reruns, not a requirement to choose one judge today. Harness-neutral tasks,
preserved trials, and separate quality and economics remain core.

## Application shape

Use SQLite for structured data and a Python 3.12+ FastAPI backend managed with
uv. SQLAlchemy 2 provides persistence and Alembic manages migrations. The
SvelteKit frontend uses TypeScript, npm, ESLint, Prettier, Vitest, and a static
adapter with a `200.html` SPA fallback. Large private artifacts live in local
files referenced by the database.

The intended runtime has a local API and a background execution worker. Import
and experiment state persist independently of the browser. Start with one local
installation; multi-user hosting and bidirectional application synchronization
are outside the initial scope. Collection from the user's other machines is in
scope through the push topology in
[ADR 0005](decisions/0005-cross-machine-collection.md): manual collectors first,
then optional scheduled runs with durable offline spooling. Private browsing from
other devices uses the mobile-friendly web interface over Tailscale. Native
desktop UI, offline application replicas, and cloud synchronization are outside
the initial scope. Serving and process details are recorded in
[decisions.md](decisions.md).

Core workflows must work on phone-sized screens: browsing usage, filtering
sessions, adding ratings and notes, viewing experiment progress and reviewing
results. Charts and navigation must support touch. Comparisons should offer
stacked or switchable views on narrow screens; wide tables and code panes should
not force the whole page to scroll horizontally. The database and execution
worker remain on the Mac mini.

| Component | Responsibility |
| --- | --- |
| Svelte frontend | Conversation browsing/search, collections, enrichment previews, experiments and review |
| Python API | Queries, validation, configuration, annotations and experiment operations |
| Worker | Imports, reconciliation, approved enrichment/execution, progress and recovery |
| Collection service | Read-only capture from configured machines, durable delivery and offline catch-up |
| SQLite | Versioned records, relationships, provenance, annotations and durable job state |
| Private artifact directory | Transcripts, prompt snapshots, fixtures, outputs and raw source records |
| Adapters | Harness imports/execution, provider usage, pricing and published evidence |

This is a design, not an implemented service. Add dependencies when an implemented
feature needs them. Choose job scheduling and SQLite concurrency details during
implementation; interrupted jobs must never silently rerun paid work.

## Interface design principles

Benchwarmer is software for repeated daily use, not a landing page. Its interface
should provide high information clarity with low visual overhead.

- Design each route around its primary task. Establish hierarchy, reading order,
  alignment, and spacing before adding visual containers.
- Use the least visual structure that communicates the relationship. Prefer
  sections, rows, lists, tables, definition grids, and subtle dividers over a
  collection of cards.
- Use cards only for content that is independently interactive, selectable,
  movable, or meaningfully separate. Keep radius and shadow scales restrained,
  and reserve pills for tags, filters, statuses, tokens, and segmented controls.
- Keep visible copy concise. Put secondary explanations, edge cases, and advanced
  controls behind progressive disclosure unless they affect safety or immediate
  consequences.
- Use conventional controls with visible labels and predictable keyboard order.
  Structured comparisons should remain tables when a table is the clearest
  representation.
- Assign color semantic roles such as action, neutral, success, warning, error,
  and information. Status always needs a non-color indicator.
- Preserve domain distinctions in every state. Unknown, zero, none, loading,
  partial, unavailable, offline, read-only, and error are not interchangeable.
- On narrow screens, reconsider priority and disclosure instead of only stacking
  desktop columns. On wider screens, use available width without turning the
  interface into a stretched phone layout.
- Accessibility is part of the initial structure: semantic landmarks and
  controls, visible focus, sufficient contrast, usable touch targets, sensible
  headings, functional zoom and text scaling, reduced motion, and
  screen-reader-friendly state changes.

Before finishing a screen, remove decoration and copy that do not add meaning,
confirm the primary task is obvious, check for generic generated-UI patterns,
and verify that simplification did not remove an affordance or accessible state.
The detailed workflow is in the
[UI design skill](https://github.com/jd-santos/Skills/blob/main/skills/ui-design/SKILL.md).

## Application areas

### Conversation library, activity and usage

Import native transcripts and normalized conversation structure from Pi, Hermes,
and Codex to the extent each source allows. Preserve messages, tool activity,
branches, continuations, attachments, and artifact references with provenance.
Provide a scrollable conversation browser, transcript detail, keyword/metadata
search, then approved semantic indexing and search with visible coverage.

Enrich descriptions and classifications through explicitly approved bounded
model work. Keep imported, calculated, generated, and human metadata separate.
Combine harness usage with provider records when useful; costs use reported
charges or price-backed calculations, not model guesses. Date, harness, provider,
model, project, and classification filters support discovery. Charts and detailed
reporting follow rather than block the library.

Show source coverage, last successful import, and unavailable fields. A source
may offer account totals without session attribution. Keep those totals useful
without inventing a breakdown.

### Collections and ad hoc projects

Support live saved queries and frozen datasets that pin conversation/segment and
enrichment revisions. Projects connect questions, collections, datasets, task
units, runs, and results. Provide versioned local query/read access and private
exports for scripts and notebooks, separate from sanitized public exports.
Collection updates and searches never silently trigger model work.

### Personal review

Attach ratings, labels and notes to sessions and trials. Successful sessions are
valid simulation seeds. Record interventions and retries when available, but the
product is not a workflow for rescuing failed tasks.

### Experiments

Prepare tasks from imported work and run alternative model/harness configurations.
Broad sweeps across inexpensive candidates are a first-class use case. Each task
needs reviewed starting context and an explicit definition of what it tests;
an arbitrary transcript is not automatically executable.

Select meaningful one-to-few-exchange units with sufficient starting context.
Start with single-response/action tests and applicable fixed follow-ups; adaptive
user continuation is a later, separately labeled experiment mode.

Approved reruns include visible applied judges and automatic criterion-level
judgments inside the approved budget. Compare outputs and artifacts with usage;
keep failures, incomplete runs, unjudged outcomes, and judge disagreements. See
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
| Session / conversation revision | Observed harness session, source scope/ID, native snapshot and normalized evidence |
| Conversation event / content block | Ordered message, branch parent, role, tool linkage and content provenance |
| Enrichment revision | Imported/calculated/generated metadata, inputs, producer/configuration and coverage |
| Collection / dataset | Live selection query or frozen membership with pinned evidence revisions |
| Evaluation project | Question, collections, datasets, task units, runs and results |
| Model-work plan / approval | Frozen inputs, stages, disclosure permissions, request/resource/cost limits and approval |
| Usage observation | Raw and normalized usage at request, session or account scope |
| Price snapshot | Effective date, source, currency, rates and estimation assumptions |
| Classification | Label, subject, origin, classifier/version and confidence if supplied |
| Annotation | Human rating, note or correction with subject and revision history |
| Task version | Harness-neutral intent, starting inputs, fixture and success criteria |
| Task source link | Conversation segments, preceding context, segmentation provenance and reconstruction gaps |
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
with separate provenance. The [source coverage matrix](source-coverage.md)
distinguishes documented OpenRouter classification interfaces from unverified
private account coverage; public aggregate labels are not personal history.

## Source feasibility

The [source coverage matrix](source-coverage.md) and source reports record dated
capability evidence. Hermes is the selected first adapter under ADR 0004; Pi and
Codex remain explicit library targets. Refresh version and installation evidence
on each collection machine before implementation. Earlier absence of a source
on one inspected machine is not proof that the user's history does not exist.

Import and execution are separate capabilities. Installed and upstream interfaces
may differ, and none of the inspected sources alone proves an exact replay
package or complete historical billing coverage. Do not promise parity or make
usage reporting a prerequisite for importing useful conversation evidence.

## Local data boundary

The central application data root is configurable and defaults outside the
repository. ADR 0002 defines storage and coordinated backup/restore. ADR 0005
retains accepted central history indefinitely by default; source deletion does
not propagate as central deletion. A collector keeps private local spool entries
until durable acknowledgment, then deletes them. Exact spool ceilings and any
future explicit central deletion tooling remain open.

Retain private snapshots of imported session content alongside normalized
metadata, so source-log deletion or changes do not erase comparison evidence.
Record source identity and capture time.

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

### 2. Useful conversation library

The first useful release retains and normalizes at least one real source without
duplicates, supports incremental updates, and provides readable conversations,
text/metadata search, source freshness, and coverage. Ratings and notes survive
restart. Usage and costs retain provenance without requiring charts. Collection
from other machines follows ADR 0005's enrolled push protocol, bounded spool, and
durable acknowledgment. Add the second and third target sources to test shared
structure and capabilities.

### 3. Enrichment and reusable collections

Preview and approve bounded description/classification and embedding batches.
Nothing starts on import or collection growth. Add semantic search, live
collections, frozen datasets, and versioned private programmatic access. Preserve
selection bias, coverage, and all metadata origins. Expand enrichment fields and
model tiers only through measured, approved work.

### 4. Task simulations and comparisons

Derive and version a task from actual work, select a harness configuration, and
run at least two candidate models using native harness configurations first.
Preserve prompt capture status and all trials,
compare quality and economics independently, and keep workspaces disposable.
Budget limits, cancellation and restart recovery work without duplicate paid
attempts. Add another harness, including direct API execution, to verify the
cross-harness representation.

Applied judges run automatically within an approved rerun's budget. Record
criterion-level evidence, judge versions/configuration, disagreement, and cost;
calibrate against human labels without requiring manual review of every run.

### 5. Deeper evaluation and reporting

Promote useful tasks into repeatable suites and later adaptive continuations.
Keep simulator-assisted results distinct from fixed tests. Add detailed usage
reporting and saved external evaluations with provenance, revisions, and dates,
without forcing unlike evidence into a common score.

## Alternatives and deferred work

- A usage-only dashboard is smaller but leaves simulation context and review
  disconnected. Conversation collection and discovery are now the first useful
  delivery slice; usage remains part of the shared metadata.
- A notebook or static HTML report cannot serve as the primary durable workflow
  for imports, annotations and jobs. Portable reports may follow as exports.
- An evaluation-first platform postpones useful everyday data and commits too
  early to a task taxonomy and agent loop.
- A Pi-only core prevents independent harness comparisons. Pi and Hermes remain
  adapters, with direct Python API execution represented as another harness.
- Hosted multi-user deployment adds identity, access and maintenance work that
  the initial personal Mac mini installation does not need.
- Automatic routing, subscription-cost allocation, a custom agent loop,
  automated source discovery and public sharing are deferred. LLM-simulated
  follow-ups are an intended later capability, not part of the first test mode.
- Cross-machine collection uses manual push collectors before optional scheduled
  runs. Native desktop UI, offline replicas, cloud synchronization, real-time
  watchers, and central pull remain deferred. No model operation, including
  embeddings or judges, may run without bounded approval.

See [decisions.md](decisions.md) for unresolved choices and [TODO.md](TODO.md) for
the implementation queue.
