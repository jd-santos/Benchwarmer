# Export sanitized benchmarks and portable reports

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Support deliberate sharing after private evaluation is useful.

## Dependencies and order

Blocked on [judged experiments](../judged-experiments/README.md). Private query/export remains earlier work under datasets.

## Acceptance criteria

Stable export schemas, deliberate sanitization, privacy review, provenance, and portability checks precede public release. Private access or hashes alone never imply safe publication.

## Work

- [ ] Add deliberately sanitized exports and portable reports
  - Dependencies: [Compare criterion-level quality and economics per trial](../judged-experiments/README.md)
  - Promotion requirement: the coordinator adds stable-schema and privacy
    review named work records before implementation

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
