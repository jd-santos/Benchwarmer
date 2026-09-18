# Evidence bundles and pattern discovery

This design extends Benchwarmer's conversation library with source-linked
analysis. It is planned work, not a claim that enrichment, grouping, or task
execution is implemented. The first delivery stays focused on importing and
browsing useful history.

## Three different objects

A **segment** identifies a stretch of conversation on an actual branch. An
**evidence bundle** connects the information needed to understand an objective,
decision, or observed behavior. A **task version** prepares starting inputs,
capabilities, fixtures, and criteria for another configuration to attempt.

A bundle may select nonadjacent messages, preceding requirements, tool results,
and later corrections. A conversation can yield several bundles, and a bundle
may cite several source sessions when their relationship is explicit. A bundle
is an analytical view over retained evidence, not a fabricated transcript.
Missing starting files may make it useful for review but unsuitable for reruns.

For example, a requirement to preserve input order may occur early, a faulty
implementation much later, and a correction after a failed test. A bundle links
those observations and records both the initial failure and the recovery. The
derived task exposes only the requirement and appropriate starting code to the
candidate. Historical answers, tests discovered later, and corrections remain
separate judging evidence unless deliberately rebuilt into a new task with that
change disclosed.

## Evidence references

Promote precise evidence references from extension data into a versioned shared
enrichment contract before broad generated analysis. References identify the
conversation and immutable revision, event, content block, and optional text
range. Block IDs are scoped to their event. Define offset units and validate
range bounds rather than assuming byte and character offsets are interchangeable.

References carry a role such as requirement, action, result, correction, or
supporting context. Validate source resolution, branch ancestry, and any explicit
continuation relationship. An unresolved reference is a visible coverage gap.
Sibling branches can be compared, but must not be rendered as one execution.
Compaction and configuration changes remain context boundaries.

## Observations and bundles

Keep observations distinct from interpretations. An observation records what the
retained evidence supports. A judgment or root-cause hypothesis adds an
interpretation, its producer, and uncertainty. Absence of captured evidence does
not establish that an event never happened.

A versioned bundle records objective, selected evidence and roles, context
requirements, selection rationale, coverage gaps, provenance, and review state.
Keep requested capability, subject matter, behavior, outcome, recovery, and
evaluation suitability as separate dimensions. Unknown and ambiguous remain
valid values. Human corrections and original generated revisions remain
available; regeneration never rewrites native evidence.

Start with manual assembly and a bounded review of roughly 20–50 conversations
when available. Include ordinary successes, failures, recoveries, and uncertain
outcomes. Use what reviewers omit or restore to refine the schema before asking
a model to extract bundles at scale. The pilot authorizes no inference by itself.

## Selective inspection

Generate a deterministic outline from available event roles, content sizes,
tool activity, branches, compactions, and configuration changes. Do not invent
missing latency, tool names, or hidden execution details. The outline helps
navigate evidence; it is not sufficient to judge all semantic behavior.

Within an approved model-work plan, separate screening from deeper inspection.
Record which content was inspected and which was omitted. Measure missed cases
by reviewing a bounded sample of unflagged work, alongside reviewer agreement
and analysis cost. Choose model tiers from measured results rather than the
model's self-reported confidence. All deeper reads sent to models, retries, and
escalations must remain inside approved input and disclosure scope and limits.

## Patterns across conversations

Patterns are versioned analytical groups over bundles. Start with inspectable
facets and saved queries; introduce model-generated grouping when it improves
discovery on a fixed sample. The extraction question and attributes determine
what similarities grouping can reveal. Grouping by topic and grouping by
behavior should remain separate views.

Allow overlapping membership. Give each pattern a description, representative
examples, supporting and contradicting evidence, input/producer revisions, and
coverage. Reviewed merges and splits create new revisions. Count both bundles
and distinct source conversations, and disclose overlaps rather than presenting
their sum as independent evidence. A failure pattern alone does not prove a
shared root cause.

Use patterns to suggest representative datasets and regression cases. Include
successful work and recoveries so failure discovery does not define the entire
benchmark. Freeze membership, selection rules, exclusions, and source,
enrichment, bundle, and pattern revisions used by an experiment. New imports or
pattern revisions never modify an existing run or start inference.

## From evidence to tests

Promoting a bundle produces a reviewable task draft with separately typed
candidate inputs and judge-only historical evidence. Check reconstruction gaps,
branch compatibility, and answer leakage before approving the task. Derive
assertions about acceptable behavior rather than prescribing incidental wording
from the historical response. Pin criteria before candidate execution.

Validate proposed evaluators against failures, successful cases, and ambiguous
or inapplicable examples. Catching the source failure alone is insufficient.
Keep criterion results, calibration evidence, and judge disagreements. Judge
failure remains unjudged, not candidate failure. Source lineage stays attached
to tasks and dataset membership. Partition evaluation data by the complete
source-lineage family so branches, continuations, derived bundles and tasks, and
near-duplicate fixtures cannot cross from development or evaluator calibration
into the final holdout.

## Scope and delivery

- [Evidence references and manual bundles](../todo/work/evidence-bundles/README.md)
  precede broad automated enrichment.
- [Enrichment](../todo/work/conversation-enrichment/README.md) adds measured
  screening and source-linked extraction within approved work plans.
- [Pattern discovery](../todo/work/behavior-patterns/README.md) follows useful
  reviewed bundles; embeddings and a full tracing platform are not prerequisites.
- [Task preparation](../todo/work/task-preparation/README.md) can use manually
  selected bundles without waiting for automated grouping.

Autonomous prompt/code repair, automatic memory rewriting, and an always-running
analysis agent are outside this design. Benchwarmer compares configurations on
representative work; it does not need Engine's full production-repair lifecycle.

## Research basis

The following sources informed this adaptation; they do not establish that
Benchwarmer implements the same system or that its grouping algorithm is known.

- [Vivek Trivedy's talk](https://www.youtube.com/watch?v=CvRngaQZQ3Y): analysis of
  agent histories, useful feedback, and consolidating experience over time.
- [Engine architecture](https://www.langchain.com/blog/how-we-built-langsmith-engine-our-agent-for-improving-agents):
  compact outlines, selective investigation, and proposed evaluation artifacts.
- [Insights documentation](https://docs.langchain.com/langsmith/insights):
  question-directed summaries, extracted attributes, and hierarchical grouping.
- [Judge calibration](https://docs.langchain.com/langsmith/improve-judge-evaluator-feedback):
  comparison with diverse human-labeled examples.

The evidence-bundle contract and delivery order above are Benchwarmer design
choices. Retain native snapshots and the existing approval boundary.
