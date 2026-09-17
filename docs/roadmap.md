# Buildout roadmap

The [priority index](../todo/TODO.md) owns live work. Each linked work README
owns its checklist, execution status, dependencies, and verification. This
roadmap explains sequencing; [architecture.md](architecture.md) and the other
maintained design documents own product rules.

## Delivery principles

- Prioritize collect → normalize → enrich → discover → select → evaluate.
  Browsing and manual selection become useful before model enrichment.
- Deliver usable paths through storage, API, and UI. The Python service owns
  persistence and policy; Svelte is a typed client over the same-origin `/api`
  boundary. Do not create empty future routes or idle worker scaffolding.
- Keep retained native observations, generated interpretations, and human review
  distinct. Source gaps, branches, and revisions remain visible.
- Imports and deterministic processing do not authorize inference. Model work
  requires exact bounded approval and separately valid disclosure permission.
- Preserve data privately outside the checkout. Use synthetic fixtures in Git
  and disposable workspaces for tool-capable trials.
- Accessibility, mobile behavior, migration recovery, idempotency, and restart
  persistence belong to each relevant slice's acceptance criteria.

## First useful library

1. [Finish the application foundation](../todo/work/application-foundation/README.md).
   Complete import records, fixture-backed source status, UI integration, browser
   verification, restart persistence, and development instructions. Existing
   runtime, source, health, shell, and contract implementations remain the base.
2. [Import Hermes conversations reliably](../todo/work/hermes-import/README.md).
   Follow the accepted first-adapter decision, refresh source evidence, and prove
   incremental import and reconciliation before private-source validation.
3. [Browse, search, and annotate](../todo/work/conversation-library/README.md).
   Support readable branches and continuations, source-linked search, freshness,
   coverage, and durable human review. Cost charts and inference are not gates.
4. [Define evidence references and review bundles](../todo/work/evidence-bundles/README.md).
   Synthetic contract work can begin earlier. Use the real library for manual
   assembly and review before committing to broad automated extraction.

Gate: real conversations import without duplication, retain native evidence,
remain readable and searchable after restart, and support durable annotations.
Foundation checks must pass first; bundle work must not postpone basic browsing.

## Operational collection and reusable selections

[Private deployment](../todo/work/private-deployment/README.md) follows foundation
verification and ADR 0003. [Cross-machine collection](../todo/work/cross-machine-collection/README.md)
follows the first importer and ADR 0005's manual-first enrolled push protocol.
Operational collector rollout requires both transport/security checks and
verified deployment. Local fixture work does not imply that histories all live
on the central host or authorize remote access.

[Additional sources](../todo/work/additional-sources/README.md) prove that shared
records preserve Pi, Codex, and Hermes structure and source-specific coverage.
Refresh each source report before implementation. Import and execution support
remain separate capabilities.

[Collections, frozen datasets, and private query access](../todo/work/collections-and-datasets/README.md)
can ship after browsing, without automated enrichment or semantic search. Pin
membership and applicable evidence revisions. Bundle selection follows the
bundle contract. A growing collection never changes a frozen experiment.

Gate: duplicate delivery and offline recovery preserve evidence; selected
datasets reproduce their membership and disclose exclusions and coverage;
private exports are never presented as sanitized public data.

## Approved enrichment and discovery

[Durable model-work execution](../todo/work/bounded-model-work/README.md) must
precede provider dispatch. The current validator is not a reservation service or
scheduler. Test cancellation, bounded retries, and outcome-unknown reconciliation
before paid work; unlike idempotent imports, uncertain paid attempts cannot be
blindly retried.

[Enrichment](../todo/work/conversation-enrichment/README.md) starts with descriptions
and constrained classification, then adds evidence-linked task context and
bundles. Measure tier quality and cost, inspect some unflagged examples, and keep
all escalation within the approved plan. Human corrections remain revisions.

[Semantic discovery](../todo/work/semantic-discovery/README.md) and
[patterns across bundles](../todo/work/behavior-patterns/README.md) follow useful
text search and reviewed data. Group by capability and behavior as well as topic;
keep overlapping membership, successes, recoveries, and uncertain examples
visible. These features do not block manual task selection.

Gate: model work has exact approval and valid disclosure scope, generated
findings cite evidence, coverage and omissions are visible, and regenerated
metadata does not overwrite source facts or frozen datasets.

## Safe tasks and judged experiments

[Task preparation](../todo/work/task-preparation/README.md) turns selected bundles
into reviewed starting inputs, fixtures, capabilities, and assertions. Preserve
reconstruction gaps and correlated source lineage. Historical solutions belong
in separate judging evidence, not candidate context. Use successes and ordinary
work as well as failures.

[Judged experiments](../todo/work/judged-experiments/README.md) establish disposable
workspaces, durable attempt reservation, capability checks, cancellation, and
applied-judge configuration before dispatching trials. Start with native harness
configurations and compatible direct Python API baselines. Pin criteria, record
all attempts, and compare criterion-level quality separately from economics.
Promote useful tasks into repeatable suites after the first comparisons work.

Gate: unsupported capabilities and judge failures are distinct from poor
candidate quality; recovery does not silently repeat paid attempts; candidate
inputs exclude later historical discoveries. Calibration covers successful,
failing, and inapplicable cases.

## Later capabilities

- [Usage reconciliation and detailed economics](../todo/work/usage-reconciliation/README.md)
  retain overlap decisions and distinguish charges, estimates, subscriptions,
  and quotas. Do not publish combined totals before reconciliation.
- [Trusted external evidence and model views](../todo/work/external-evidence/README.md)
  retain dates, methods, configuration, revisions, and identity uncertainty.
- [Controlled comparisons and adaptive follow-ups](../todo/work/advanced-comparisons/README.md)
  follow proven fixed trials and explicit policy decisions. Adaptive results
  describe the candidate and simulator together.
- [Sanitized exports and portable reports](../todo/work/portable-reports/README.md)
  follow private evaluations and deliberate privacy review.

These capabilities do not block the useful library. No combined winner score is
introduced.

## Application map

Routes arrive with working behavior, not as empty navigation placeholders.

| Route | Purpose |
| --- | --- |
| `/`, `/sources` | Health/source status first, then recent work and freshness |
| `/sessions`, `/sessions/[id]` | Browsing, search, branches, evidence, and human review |
| `/projects` | Questions, live collections, and frozen datasets |
| `/enrichment` | Approved previews, progress, evidence, and coverage |
| `/tasks` | Reviewable task drafts and versions |
| `/experiments`, `/experiments/[id]` | Approved runs, per-trial judgments, and economics |
| `/evidence`, `/models/[id]` | Later external evaluation evidence and model views |

Keep narrow-screen layouts readable and controls keyboard accessible and touch
friendly. Follow the maintained interface principles rather than selecting a
container style from this roadmap.

## Work and handoff

Read the index, the selected work README, applicable agent instructions, and the
linked design evidence. Pick work whose dependencies are satisfied. Record a
bounded role and branch in the work README when starting; ownership text is not
a lock. Keep one writer per checkout and use separate worktrees if parallel
writers are explicitly assigned.

The work README owns status and the detailed checklist; the index retains its
priority. Broad steps need exact files or discovery outputs, acceptance criteria,
and verification commands before implementation. Update the existing record at
handoff with remaining steps, actual checks, and blockers. Keep checked work
until reviewed shipping closeout; do not create a Done section, opaque task
codes, or timestamped handoff files. The [workbench](../todo/README.md) links the
full workflow.
