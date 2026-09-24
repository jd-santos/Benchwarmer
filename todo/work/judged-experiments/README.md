# Run, judge, and compare repeatable experiments

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Compare useful work across native harness configurations and compatible direct API baselines, preserving each trial and criterion.

## Dependencies and order

Blocked on [task preparation](../task-preparation/README.md), [evaluation planning](../evaluation-planning/README.md), and [bounded model execution](../bounded-model-work/README.md). Execution safety and applied-judge configuration precede real trials.

## Acceptance criteria

Trials use compatible capabilities and disposable fixtures, retain requested and
observed configurations and usage, and recover without silently repeating paid
work. Applied judges run inside the approved budget; errors remain unjudged.
Reusable suites pin tasks, judges, dataset revisions, and lineage-family split
assignments. Final-holdout evidence does not guide candidate or evaluator tuning.

## Work

- [ ] Prepare safe and recoverable experiment execution
  - Dependencies: [Prepare meaningful task units from frozen datasets](../task-preparation/README.md), [Run approved model work with durable limits and recovery](../bounded-model-work/README.md)
  - Scope: disposable workspaces, fixed scripts, capability checks, credential
    and network policy, budgets, cancellation, durable progress, attempt
    reservation, outcome-unknown reconciliation, and duplicate-paid-work
    protection
  - Promotion requirement: no real or paid trial may be dispatched before this
    task is complete

- [ ] Add applied-judge configuration and automatic bounded judging
  - Dependencies: [Prepare meaningful task units from frozen datasets](../task-preparation/README.md), [Run approved model work with durable limits and recovery](../bounded-model-work/README.md)
  - Scope: frozen rubrics, judge model/configuration, deterministic checks where
    useful, evidence, disagreement, calibration and unjudged states

  - [ ] Validate proposed evaluators against known failures, successful cases, and ambiguous or inapplicable cases before attaching them to a suite. Preserve calibration evidence and judge disagreement.

- [ ] Run native harness and compatible direct-API trials
  - Dependencies: [Prepare safe and recoverable experiment execution](../judged-experiments/README.md), [Add applied-judge configuration and automatic bounded judging](../judged-experiments/README.md)
  - Scope: automatic applied judges inside the same approved rerun budget
  - Promotion requirement: the coordinator names harness, permission, and
    budget decision records before implementation

- [ ] Compare criterion-level quality and economics per trial
  - Dependencies: [Run native harness and compatible direct-API trials](../judged-experiments/README.md)

- [ ] Promote useful tasks into repeatable evaluation suites
  - Dependencies: [Compare criterion-level quality and economics per trial](../judged-experiments/README.md)

  - [ ] Link regression cases back to the motivating bundle or pattern while keeping ordinary successful work in representative comparisons.
  - [ ] Separate development, evaluator-calibration, and final-holdout families;
    prevent branches, derived tasks, and near-duplicate fixtures from crossing
    partitions. Record any holdout exposure and replace a contaminated holdout
    before making another final comparison claim.

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
