# Define evidence references and review conversation bundles

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Connect separated requirements, actions, results, and corrections without turning them into a false transcript or prematurely assuming they can be rerun.

## Dependencies and order

Contract design and synthetic examples can begin now. The manual review pilot
waits for [browsing and annotations](../conversation-library/README.md). The
user-facing [history and cost dashboards](../history-and-cost-dashboards/README.md)
precede suggested-group approval in the product sequence. This is the last P2
slice, ahead of broad model-powered enrichment.

## Acceptance criteria

Evidence resolves against pinned conversation revisions and valid branch
ancestry. Bundles distinguish observed events from interpretations and remain
useful when a task cannot be reconstructed. Coherent phases may overlap; their
membership does not make them independent examples. A manually reviewed pilot
informs the extraction schema and later in-app review of suggested groups.

## Work

- [ ] Define reusable references to conversation revision, event, content block, and optional text offsets, with explicit evidence roles and missing context.
- [ ] Validate reference resolution and branch ancestry using synthetic examples, including continuations, compactions, missing content, and noncontiguous evidence.
- [ ] Define versioned observations and bundles separately from contiguous segments and executable task versions; retain producer and selection rationale.
- [ ] Add deterministic conversation outlines from available roles, sizes, tools, branches, and configuration/compaction events. Do not infer missing timing or tool names.
- [ ] Support human bundle assembly and correction with source expansion before automating extraction.
- [ ] Review a bounded pilot of roughly 20–50 conversations when available, including successes, failures, and recoveries. Record context omissions, invalid references, and whether bundles support useful judgments; no model work is implied.

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
