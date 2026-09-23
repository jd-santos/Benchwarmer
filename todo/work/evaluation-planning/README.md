# Define judges, success measures, and test plans

Status: Planned. This record captures product scope and open design work; judge
execution and trial dispatch are not implemented.

## Purpose

Use the user's history to learn which model, reasoning level, harness, prompt,
skills, and tools deliver acceptable quality for different kinds of software,
planning, and automation work at an acceptable token cost, money cost, and speed.
Judge definitions and test plans should be app constructs that the user can
inspect, revise, and reuse. The longer-term result may be task-based
configuration recommendations and, after evidence warrants it, automatic
routing.

## Dependencies and order

Design this as a cohesive slice after the
[history and cost dashboards](../history-and-cost-dashboards/README.md) are
useful. Reviewed [evidence bundles](../evidence-bundles/README.md),
[frozen datasets](../collections-and-datasets/README.md), and
[task preparation](../task-preparation/README.md) supply candidate tasks.
Model-powered suggestions require [bounded model work](../bounded-model-work/README.md).
Judge execution and reruns remain in [judged experiments](../judged-experiments/README.md).

## Product requirements to design

- Define task families from actual history. A testable group represents a
  coherent phase of a larger task, may overlap another group, and links its
  source exchanges and needed starting context. A group is a draft test artifact
  until its inputs and evaluation suitability are reviewed.
- Let an agent suggest groups and criteria with cited source evidence. In the
  app, review examples, correct boundaries or context, and approve suggestions
  individually or in batches. Keep the suggestion, approval, correction, and
  producer revisions. Measure usefulness before moving toward automatic
  approval; perfect segmentation is not the goal.
- Define judges in the app, rather than hardcoding a model or rubric. A judge
  definition should name its criteria, evidence access, method, version, and
  configuration. Support deterministic checks and future model judges; preserve
  unjudged, inapplicable, uncertain, and disagreement states. Stub the judge
  interface before implementing judge execution.
- Help propose success criteria by task family from source evidence and user
  review. For coding work, consider functional correctness, tests, idiomatic use
  of the language and framework, maintainability, and appropriate pattern
  selection. Do not assume the historical solution is the sole acceptable answer
  or that an agent's proposed rubric is authoritative without review.
- Create a reviewable test plan from selected task groups, candidate model and
  reasoning settings, harness and prompt/configuration variants, repetitions,
  judges, and planned budget. Estimate candidate and judge tokens, money cost,
  and elapsed time as ranges with stated assumptions and coverage gaps. The plan
  should later be executable from the app through explicit approval and safe
  trial execution.
- Capture comparable configuration dimensions separately and retain versioned
  source-specific settings and unavailable fields. Distinguish requested from
  observed effective settings. A multi-variable change describes a whole
  configuration; it does not isolate the effect of one variable.
- Compare criterion-level quality, token use, money cost, and speed separately.
  A primary efficiency view can use all candidate tokens spent across attempts,
  including retries and failures, divided by the number of completed task
  instances meeting a stated quality bar. Keep input, cached input, output, and
  reasoning tokens separate where exposed; show judge overhead separately.
  Compare on the same task set and report unknown completion rather than
  treating it as failure.

## Open decisions

- Which first task families from the user's history have enough evidence to
  define useful success criteria and starting context?
- What minimum review makes a suggested group and proposed criterion usable?
- Which judge types and rubric revisions should the first app interface support
  before any model judge runs?
- What historical usage can anchor test-plan estimates, and how wide should the
  estimate range be when a new configuration has no observations?
- Which quality bar and task mix make a routing recommendation credible? When
  would recommending a configuration be safe enough to automate routing?

## Work

- [ ] Review representative real work from software, planning, and automation
  before fixing task-family labels or metrics.
- [ ] Define the group review, judge definition, and test-plan workflows in the
  app, including versioned records and explicit unknown states.
- [ ] Define token-per-accepted-task, money cost, and speed reporting with failed
  attempts and judge overhead visible.
- [ ] Reconcile the agreed product direction in the maintained README,
  architecture, roadmap, and relevant work records before implementation.
- [ ] Split implementation into bounded slices with acceptance criteria after
  the dashboard workflow and sample history are available.

## Supporting material

- [Current priorities](../../TODO.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles](../../../docs/evidence-bundles.md)
- [Judged experiments](../judged-experiments/README.md)
