# Conversation library and evaluation workflow

## Product goal

Benchwarmer collects conversations from the user's Codex, Pi, Hermes, and later
sources into a private, searchable library. The library is useful before any
evaluation runs: browse full conversations, find relevant work, assemble
collections, and inspect shared metadata and source evidence.

The product workflow is:

**Collect → normalize → enrich → discover → select → evaluate.**

Usage and cost are metadata in this workflow. Detailed reporting, public
benchmark evidence, and model dashboards follow the useful conversation library.
This priority supersedes the usage-dashboard-first delivery sequence, not the
existing persistence, provenance, reconciliation, or execution-safety rules.

## Collection across machines

Source histories are not all on the central Mac mini. A collection service is
part of Benchwarmer, not an assumed external log-sync prerequisite. One central
private installation remains authoritative; collection from personal machines
does not imply multi-user hosting or bidirectional application synchronization.

The service must support initial backfill, incremental capture, restart recovery,
and offline catch-up. Identify records by source installation/profile and native
IDs, not by hostname, path, title, timestamp, or content similarity alone. Keep
capture time distinct from source event time. Acknowledgments must reflect
durable central receipt, not merely successful transmission. Interrupted or
repeated delivery must not duplicate evidence. Source deletion is an observed
event, not an instruction to delete retained snapshots.

Collectors are read-only toward their sources. They must not resume sessions,
execute captured commands, or acquire execution credentials. Private spool,
transport, retention, and deletion behavior need an explicit design. Live SQLite
sources need a consistent read or backup, not a copy of the database file alone.

### Collection planning gate

The user has approved this service's scope, not a deployment topology. `COL-001`
must clarify:

- Which operating systems and source locations need collection; which machines
  sleep or are intermittently connected; desired freshness and backfill scale.
- Whether software may run on each source machine and how it is updated.
- Push collectors, central pull, or explicit export/transfer, with tradeoffs for
  source access, offline spooling, authentication, and ongoing maintenance.
- Device enrollment, revocation, transport authorization, and source allowlists.
  Tailscale reachability alone is not a complete ingestion authorization design.
- Attachment limits, secret exclusion, redaction evidence, local retention, and
  central acknowledgment semantics. Secret scrubbing is not anonymization.

Do not choose SSH access, shared folders, public ingestion, or a remote daemon by
implication. Transport and live-source rollout stay blocked on this conversation.
The first shared-record slice uses synthetic inputs and needs none of these
choices. Hermes remains the selected first adapter; Pi and Codex are explicit
library targets, not promised to have identical capabilities.

## Native evidence and shared records

Retain source-native snapshots alongside a versioned normalized representation.
Neither replaces the other. Normalization must preserve source provenance and
coverage rather than pretending all harnesses expose the same data.

Shared records cover:

- Source installation/profile, conversation/session identity, revisions, native
  IDs, capture times, source versions, and adapter versions.
- Ordered events/messages, roles, text and reasoning blocks where exposed,
  tool calls/results and their linkage, attachments, and artifacts.
- Parent/branch relationships, continuation links, compaction events, and context
  boundaries. A display path through a conversation is not the complete graph.
- Prompt/configuration evidence, model/provider changes, project context, usage,
  cost provenance, source-specific extensions, and explicit coverage gaps.

Use opaque private artifact references, not executable paths or commands. Preserve
unknown native fields in private evidence/extensions without inventing normalized
semantics. Missing reasoning, tool schemas, files, or prompts stay unknown,
unavailable, partial, or redacted as appropriate. No snapshot proves exact replay.

## Enrichment

Import and deterministic normalization may run unattended after a source is
configured. They do not authorize model calls. Costs are enriched without asking
a model to guess prices: preserve reported usage/charges and derive estimates
from identified price snapshots. Reconcile overlaps before aggregating them.

| Evidence class | Examples | Rule |
| --- | --- | --- |
| Imported | Source short summary/title, timestamps, model, project, usage | Keep native provenance and observed gaps |
| Calculated | Price-backed cost estimates, durations, counts | Record inputs, formula/version, units, and assumptions |
| Generated | Description, labels, inferred outcome, suggested criteria | Keep model/prompt/version and supporting evidence; not source facts |
| Human | Corrections, ratings, labels, rubric edits | Preserve revisions without erasing other evidence |

Generated metadata targets include a short summary when needed, a longer
searchable description, topics, task types, project/repository, technologies,
entities, outcomes, interventions/retries, quality signals, segmentation, and
suggested evaluation criteria. Document the whole target while shipping bounded
subsets; do not require every field before the library becomes useful.

Start model selection by task shape, then measure accuracy and cost on synthetic
or explicitly approved samples:

- Small classifiers for constrained labels and bounded extraction.
- Larger configurable models for long-context descriptions, task segmentation,
  ambiguous outcomes, and rubric drafting.
- Escalation only within an approved plan, using validation failures or measured
  task difficulty rather than model-reported confidence alone.

Record producer/model, prompt and schema versions, input revision, evidence
references, coverage, generation time, usage, and cost. Regeneration creates a new
revision. Human corrections and original source summaries remain available.
Generated metadata and summaries can be wrong and must link back to source text.

### Model work requires bounded approval

No automatic model work on import, search, source updates, restart, or a changed
live collection. This includes embeddings, query embeddings, classifiers,
summaries, reruns, judges, and later simulated users, whether local or remote.

A model-work preview identifies the frozen input set, data to be sent, provider
and model for each stage, prompts/configuration, maximum item/request counts,
input/output allowances, retry/escalation policy, concurrency, and a total cost
policy. Approval covers that exact plan, not future collection growth. Changed
inputs, models, prompts, judges, or limits invalidate approval. No numeric spend
limit is chosen on the user's behalf.

Keep content-disclosure permission separate from spend permission: approving a
price does not itself authorize sending private conversations to a new provider.
Remote processing sends selected content outside the machine; local processing
still consumes resources. Both need visible scope and controls.

Actual execution requires durable budget reservation and cancellation, bounded
retries, and recovery that never silently repeats an uncertain paid request.
Disclose estimated limits and possible in-flight overrun; do not promise a hard
provider billing cap. Unknown pricing blocks priced work until the user approves
an explicit non-monetary limit policy. A plan validator is not a scheduler or an
exactly-once execution guarantee.

A rerun includes its applied judges by default. Once the bounded operation is
approved, judgments run automatically inside its budget. New judge passes,
regeneration, escalations, and retries beyond that scope need another approval.

## Discovery and ad hoc access

The primary interface is a scrollable conversation list and readable transcript
with filters, source freshness, coverage, short summaries, and useful metadata.
Expose branches and continuations without merging them into false history. Keep
tool details and long content accessible without crowding the reading path.

Support keyword search and metadata filters, then semantic search over available
messages, descriptions, tool activity, and extracted attachment/artifact content.
Index coverage, stale enrichment, unsupported content, and pending embeddings
must be visible. No hidden query-embedding call is triggered by typing. Start with
text/filter fallback; semantic search needs approved precomputation or an explicit
bounded query action. Search hits cite the relevant source passage.

Provide a documented, versioned local query/read interface and private dataset
export for scripts and notebooks, so ad hoc evaluation projects do not depend on
UI automation or internal SQLite tables. This is separate from deliberately
sanitized public exports. Querying existing data does not launch inference.

A project groups a question, collections, datasets, task units, runs, and results:

- A **live collection** is a saved query that can include newly imported work.
- A **frozen dataset** pins selected records/segments and their source and
  enrichment revisions, selection rules, exclusions, and capture time.
- An **evaluation run** references a frozen dataset, task versions, candidate
  configurations, applied judges, and approved execution policy.

For example, a live collection can find software work across all sources; a
frozen dataset records exactly which examples a particular comparison used.
Generated classifications should be inspectable and correctable so a filter is
not mistaken for a complete or unbiased sample.

## Evaluation units and applied judges

A meaningful unit is an objective or decision with enough starting context, often
one to a few exchanges. It is not an arbitrary token window or a promise that
every exchange is independent. Keep the source segment, preceding context,
segmentation method/version, reconstruction gaps, and selection rationale.
Multiple decisions in one conversation may yield correlated units; report that
lineage rather than presenting them as independent sessions.

Start with single-response/action tests and applicable fixed follow-ups. Later
adaptive continuation may generate user follow-ups pursuing the original intent
while reacting to the new candidate. Record the simulator's instructions,
configuration, outputs, and cost separately. Its results describe candidate plus
simulator behavior, not exact historical replay. See
[experiments.md](experiments.md) for leakage and execution constraints.

Each rerun exposes **Applied judges**: rubric versions, criterion-level checks,
judge models/configuration, and evaluation cost. Include deterministic checks
where useful. Judge failure is unjudged, not a candidate failure. Preserve
uncertainty, disagreement, and evidence. Human review and judge calibration
measure reliability without requiring manual approval of every judgment. Never
collapse quality and economics into a single winner score.

## Delivery boundaries

The first contract slice is specified in
[plans/2026-09-15-conversation-contracts.md](plans/2026-09-15-conversation-contracts.md).
It establishes normalized synthetic evidence and a pure bounded model-work
approval contract. It is not an operational collector, browser, or inference
service. The next useful vertical release must collect and browse real history,
not merely add more infrastructure. [roadmap.md](roadmap.md) tracks that sequence.

Rejected priorities: keep usage reporting first (delays the requested library),
build all replay modes now (couples useful ingestion to unresolved simulation),
and enrich every import automatically (unbounded spend and disclosure risk).
