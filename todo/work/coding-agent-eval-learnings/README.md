# Adopt the coding-agent eval learnings from the Hermes case

Status: Planned. These are recommendations distilled from a one-case eval run
in June 2026. Nothing here is implemented in Benchwarmer.

## Purpose

Carry forward what the Hermes tab-move eval proved useful before the source
material is lost. That eval reran one Overdrive task under two instruction
variants, captured diffs and metrics, and judged the runs with a rubric. Most of
the value was in how it measured scope, not in the tooling. The recommendations
below name which existing record should absorb each idea; this record is the
review surface, not a competing plan.

Source evidence lives outside this repo and is untracked there:
`overdrive/docs/agent-evals/hermes-tab-move/` (plan, expected-scope,
reviewer-issues, comparison, runbook, judge prompt, metrics, scripts). Copy or
link anything worth keeping before that tree disappears.

## Dependencies and order

None of this blocks current P2 work. Fold items into their target records when
those records move from planning to design. The rubric item should be settled
before any model judge runs in [judged experiments](../judged-experiments/README.md).

## Recommendations

Ranked by value. Each names its target record.

- [ ] Add diff-based metrics as a first-class run artifact.
  Target: [judged experiments](../judged-experiments/README.md).
  Files changed, lines added and deleted, and out-of-scope files, computed from
  the workspace diff against a pinned start commit. In the Hermes runs these
  separated the variants cleanly where token and cost metrics did not. Planned
  metrics today cover tokens, cost, duration, counts, and retries only.

- [ ] Give each coding task an expected-scope spec.
  Target: [task preparation](../task-preparation/README.md).
  Three tiers: in-scope paths, approval-gated areas (shared components, global
  patterns, unrelated routes), and process artifacts excluded from app output
  (TODO files, transcripts, eval configs). Keep it as path globs plus a short
  prose tier list. The approval-gated tier turns "should have asked" into a
  deterministic check and feeds the diff metrics above.

- [ ] Birth cases from real code-review complaints.
  Target: [task preparation](../task-preparation/README.md) and
  [evidence bundles](../evidence-bundles/README.md).
  Each reviewer issue records observed behavior, reviewer expectation, and
  severity. That shape is both the case definition and a human label for judge
  calibration. The review queue produces these for free.

- [ ] Write anti-reward-hacking rules into the judge style guide.
  Target: [evaluation planning](../evaluation-planning/README.md).
  Do not reward unnecessary edits because they are valid. Do not penalize
  reporting a finding instead of fixing it. Penalize edits outside expected
  scope unless requested or approved. Prefer generalizable behavior over fixes
  tailored to the case.

- [ ] Require negative controls before promoting an instruction change.
  Target: [judged experiments](../judged-experiments/README.md), promotion step.
  One passing case promotes a change to more testing, never to policy. Before
  adoption run at least one case where the tool or linter finds a real issue
  that should be fixed, and one where out-of-scope edits are explicitly
  approved. Guards against overfitting the instruction to one failure.

- [ ] Name the plan-then-approve two-turn case format.
  Target: [advanced comparisons](../advanced-comparisons/README.md), fixed
  multi-turn simulation.
  Turn one asks what the change requires. Turn two approves the simple version.
  No coaching between turns. Cheap, preserves the planning-to-implementation
  handoff, and avoids simulated users.

- [ ] Keep the runner and the judge separate.
  Target: [judged experiments](../judged-experiments/README.md), execution step.
  The judge only reads artifacts. Worktree setup, variant application, running
  the agent, exporting the session, capturing the diff, and classifying files
  are runner steps. A human-written diff summary as judge input is optional and
  a leakage risk; prefer raw diff plus metrics.

- [ ] Record reproducibility metadata per run.
  Target: [judged experiments](../judged-experiments/README.md), requested vs
  observed configuration.
  Start commit, the commit the instruction variant was applied at, instruction
  file hash, worktree path, model, thinking level, session file reference, and
  capture status. Instruction files (AGENTS.md, skills) are configuration and
  belong in the configuration record alongside model and prompt.

- [ ] Classify validation failures as pre-existing or introduced.
  Target: [judged experiments](../judged-experiments/README.md), deterministic
  checks.
  Record linter, type check, and test outcomes separately, and mark a failure
  outside touched files as pre-existing. Drop tool-specific counts unless they
  generalize to "malformed tool calls".

## Rejected

- Human semantic diff summary as a required judge input. Bottleneck and
  leakage risk. Optional only.
- Autofixer-specific metrics or rubric lines. The general lesson, blocking vs
  advisory tool output, lives inside the rubric.
- Cost as a comparison axis for scope cases. The source docs say not to weight
  it, and quality and economics stay separate here already.

## Supporting material

- [Current priorities](../../TODO.md)
- [Experiment semantics](../../../docs/experiments.md)
- Hermes case source tree: `overdrive/docs/agent-evals/hermes-tab-move/`
  (untracked in that repo as of October 2026)
