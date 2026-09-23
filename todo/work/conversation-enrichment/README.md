# Enrich conversations with evidence and measured model tiers

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Improve discovery using descriptions, classifications, and task-aware extraction
while keeping generated interpretations distinguishable from source facts.
Suggest coherent, potentially overlapping task phases that the user can review
in the app as possible test artifacts.

## Dependencies and order

Blocked on [bounded model execution](../bounded-model-work/README.md) and [evidence references and bundles](../evidence-bundles/README.md). Start with a small field set, then expand only after reviewed samples show useful results.

## Acceptance criteria

Every generated observation cites source evidence and records its input, prompt,
schema, model, coverage, and generation revision. Group suggestions link source
exchanges and context, allow overlap, and support individual and batch review,
correction, and approval in the app. Approved groups are not automatically
runnable tasks. Tier selection is measured; deeper inspection and escalation
stay within the approved plan.

## Work

- [ ] Add approved description and classification enrichment
  - Dependencies: [Run approved model work with durable limits and recovery](../bounded-model-work/README.md)
  - Scope: choose first fields and small/large model tiers using approved samples;
    preserve source short summaries, generated revisions, evidence, usage/cost

- [ ] Extract task context, behavior, and evidence bundles
  - Dependencies: [Add approved description and classification enrichment](../conversation-enrichment/README.md)
  - Scope: topics, task types, projects, technologies, entities, outcomes,
    interventions/retries, quality signals, segmentation and suggested criteria;
    measured model-tier routing, no unapproved automatic escalation

  - [ ] Extract subject, requested capability, observed behavior, outcome, recovery/intervention, and evaluation suitability as separate fields. Preserve unknown and ambiguous values.
  - [ ] Keep initial descriptions narrow; require source-linked bundles before promoting richer generated findings.
  - [ ] Separate low-cost screening from deeper evidence inspection. Measure missed semantic failures using an approved sample of unflagged work; track review accuracy and cost before choosing model tiers.
  - [ ] Permit deeper inspection or escalation only inside the exact approved input, provider, request, and resource scope. Version generated artifacts and preserve human corrections.

- [ ] Suggest coherent task-phase groups and review them in the app
  - Dependencies: [Extract task context, behavior, and evidence bundles](../conversation-enrichment/README.md), [Define evidence references and review conversation bundles](../evidence-bundles/README.md)
  - Scope: overlapping source-linked groups, preview and correction, individual
    or batch approval, versioned producer/configuration, and review accuracy and
    cost measurement before considering more automated approval

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
