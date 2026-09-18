# Discover patterns across conversation bundles

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Find recurring capabilities, behaviors, and recovery patterns across conversations to improve discovery and dataset selection.

## Dependencies and order

Blocked on [evidence bundles](../evidence-bundles/README.md), [reviewed enrichment](../conversation-enrichment/README.md), and [frozen datasets](../collections-and-datasets/README.md). Begin with reviewed facets and saved queries; automated grouping follows evidence that it helps.

## Acceptance criteria

One bundle can belong to multiple interpretable groups. Membership and grouping instructions are revisioned, every claim links to evidence, and updates never mutate frozen datasets or launch unapproved model work.

## Work

- [ ] Start with separate subject, capability, behavior, outcome, recovery, and evaluation-suitability views over reviewed bundles.
- [ ] Define versioned groups with readable descriptions, representative examples, supporting and contradicting evidence, and overlap-aware membership.
- [ ] Keep interpretations and root-cause hypotheses separate from observed events; allow reviewed merges, splits, and corrections without rewriting native evidence.
- [ ] Compare grouping strategies on a fixed approved sample; retain the input revisions, extracted attributes, prompts, model configuration, and selection coverage. Do not require an embedding service to try grouping.
- [ ] Use groups to propose balanced datasets, including successes, failures, recoveries, and uncertain cases. Show both bundle counts and distinct conversation counts; do not count overlapping membership as independent sessions.
- [ ] Connect accepted patterns to task drafts and regression assertions. New observations can produce a new pattern revision, but never mutate frozen runs or trigger background inference.

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
