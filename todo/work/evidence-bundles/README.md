# Define evidence references and review conversation bundles

Status: In progress on `task/evidence-bundles`. Manual bundle assembly is
implemented; the pilot, observations, and deterministic outlines are pending.

## Path to running evaluations

Decided with the user on 2026-10-19: build one thin path from excerpt to judged
result before deepening any stage. Each slice lands in its owning work record.

1. Evidence references and manual excerpt bundles (this record)
2. Bundle → task draft → immutable task version with a leakage check
   ([task preparation](../task-preparation/README.md))
3. Criteria and judge definitions scored 0–1 in 0.1 steps, deterministic or
   stub judges first ([evaluation planning](../evaluation-planning/README.md))
4. Test-plan task × configuration matrix with exact approval, no dispatch
5. Durable bounded execution with a direct-API harness
   ([bounded model work](../bounded-model-work/README.md))
6. Results grid with human scoring ([judged experiments](../judged-experiments/README.md))

Agent-proposed bundles, model judges, native harnesses, partitions, and
estimates deepen these stages afterward.

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

- [x] Define reusable references to conversation revision, event, content block, and optional text offsets, with explicit evidence roles and missing context.
  Text ranges count Unicode code points, half-open (`src/benchwarmer/evidence.py`).
- [x] Validate reference resolution and branch ancestry using synthetic examples, including continuations, compactions, missing content, and noncontiguous evidence.
  Items from one conversation pin one revision and lie on one path; conversations
  must be joined by captured relationships (`tests/api/test_bundle_api.py`).
- [ ] Define versioned observations and bundles separately from contiguous segments and executable task versions; retain producer and selection rationale.
  - [x] Bundles: numbered immutable revisions with objective, status (draft,
    reviewed, analysis only), rationale, missing evidence, origin, and producer;
    stale saves return 409 (`/api/v1/bundles`, migration `0004`).
  - [ ] Observations and interpretations as separate records
- [ ] Add deterministic conversation outlines from available roles, sizes, tools, branches, and configuration/compaction events. Do not infer missing timing or tool names.
- [x] Support human bundle assembly and correction with source expansion before automating extraction.
  Select messages or highlighted text in the reader, create or extend a bundle,
  then edit roles, notes, order, and status with jump-to-source links.
- [ ] Review a bounded pilot of roughly 20–50 conversations when available, including successes, failures, and recoveries. Record context omissions, invalid references, and whether bundles support useful judgments; no model work is implied.

## Verification

Manual bundles, 2026-10-19: `uv run pytest` 224 passed; ruff check and format
clean; web check, lint, and 50 vitest tests pass. A local browser pass against
the synthetic demo library confirmed select, highlight, create, edit, save, the
sibling-branch rejection, and no horizontal overflow at phone width.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
