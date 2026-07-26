# Benchwarmer architecture

## Problem

Model selection is an economic decision as well as a quality decision. A large
model may perform better, but the useful question is how models and reasoning
levels trade quality, cost, latency, and behavior across different task types.

Benchwarmer will provide a shareable and repeatable benchmark suite for those
comparisons. It will not choose a winner or reduce every result to one utility
score. The report should leave the tradeoffs visible for human judgment.

The toolkit also needs room to evaluate system prompts, tools, skills, agent
harnesses, and complete configurations later. Those variables must not be baked
into the core task format.

## Chosen approach

Use a portable task format with a script-driven Python runner. The core owns
task definitions, trial records, grader results, price estimates, and reports.
Adapters connect that core to model providers and agent harnesses.

OpenRouter will be the first provider through an OpenAI-compatible API. Provider
base URLs and authentication must remain configurable so another compatible
endpoint can replace it without changing task definitions.

Pi is a possible future harness adapter and simulation runner. It is not an MVP
dependency, extension, or canonical execution environment.

## Alternatives considered

### Promptfoo as the core

Promptfoo already supports configurable prompts, providers, and rubric-based
evaluation. It would reduce the first implementation effort, but it would make
Benchwarmer's task and result semantics depend on another evaluation framework.
That becomes limiting when repository state, agent tools, fixed conversations,
and interactive human feedback become primary evaluation inputs.

Promptfoo can still be supported through an adapter or export later.

### Pi-native evaluation

A Pi extension could replay realistic personal workflows and capture native
traces. It would be useful for Pi-specific regression testing, but it would
couple the benchmark to one harness and make it harder to compare full agent
configurations elsewhere.

Pi remains a candidate adapter after the harness-neutral runner works.

### Historical-trace grading

Existing traces are useful for discovering realistic task shapes and failure
modes. They are not the canonical dataset because they contain private context,
mix multiple requests into long sessions, and do not provide controlled trials
across candidate configurations.

Public tasks may be inspired by historical patterns only after they are
rewritten as self-contained fixtures.

## Design principles

### Keep experimental variables explicit

A candidate configuration may eventually include:

- provider and model
- reasoning or thinking level
- temperature and sampling controls
- system prompt
- skills or injected instructions
- available tools
- agent harness and harness configuration

The MVP varies only model and reasoning level. Other fields should have stable
places in the schema without becoming active sweep dimensions yet.

### Preserve trials before aggregating

Every attempt should remain independently inspectable. Aggregation may show
means, ranges, confidence intervals, distributions, and category summaries, but
it must not discard the original trial or grader evidence.

### Separate observations from judgments

Observed data includes outputs, file changes, tool calls, token counts, cache
use, latency, and provider-reported usage. Judgments include rubric scores,
human feedback, and model-judge feedback. Store them separately so a grader can
be replaced without rerunning the candidate when the original artifacts are
sufficient.

### Make economics auditable

Store raw usage alongside the price catalog entry used for each estimate. A
result should distinguish:

- uncached input tokens
- cached input tokens
- output tokens
- provider-reported reasoning tokens when available
- batch execution
- API list-price estimate
- actual API charge when the provider returns one
- whether a subscription-backed harness was used, when known

Subscription usage is descriptive only. Benchwarmer will not try to allocate a
subscription price across trials.

### Prefer reproducible conversations

Multi-turn tasks begin as fixed scripts with defined decision points. An
LLM-simulated user may be added later as a separate scenario type because it
introduces another source of cost and variance.

## Core concepts

The initial domain model should cover these concepts without committing to a
serialization syntax yet:

- **Suite**: A versioned collection of tasks and shared configuration.
- **Task**: A prompt, fixture, evaluation criteria, and task metadata.
- **Scenario**: A single-turn request or fixed multi-turn script.
- **Candidate**: The provider, model, reasoning level, and stubbed future
  configuration fields being evaluated.
- **Trial**: One execution of one task against one candidate.
- **Artifact**: Output text, trace, changed files, command results, or other
  evidence produced by a trial.
- **Grader**: A deterministic, model-based, or human evaluation of a criterion.
- **Observation**: Usage, latency, tool activity, and environment outcomes that
  do not require subjective judgment.
- **Result**: The trial, observations, grader outputs, provenance, and errors.
- **Report**: An aggregated view that links back to individual trials.

Serialized forms should include schema versions from the start.

## Execution pipeline

1. Load a benchmark suite and validate its task definitions.
2. Expand the selected model and reasoning-level matrix.
3. Run repeated trials for every task and candidate combination.
4. Capture artifacts, provider usage, timing, errors, and pricing provenance.
5. Apply deterministic graders to outcomes that can be verified directly.
6. Apply criterion-level model judges where subjective review is required.
7. Preserve human feedback entered through the report.
8. Aggregate results by trial, task, category, model, and reasoning level.
9. Generate a self-contained HTML report without selecting a winner.

The number of repetitions should be configurable by suite, task, and candidate.

## Small agent loop

The MVP may include a controlled agent loop rather than depending on an existing
harness. Its purpose is to expose enough behavior to evaluate implementation,
tool judgment, and repository outcomes while keeping the loop understandable.

The loop should eventually support:

- a disposable workspace created from a fixture
- a bounded set of file and shell tools
- explicit turn and cost limits
- complete tool-call and tool-result capture
- fixed multi-turn user messages where the scenario requires them
- final workspace artifacts for deterministic grading

The exact tool set and isolation mechanism remain open design questions. The
loop should not attempt to reproduce every feature of a production coding
agent.

## Grading

Benchwarmer should report criteria individually. Likely starting dimensions
include:

- task correctness and completeness
- implementation quality and project-pattern fit
- planning usefulness
- documentation quality
- source use and synthesis quality
- pedagogical clarity
- communication quality
- tool-use judgment
- efficiency observations such as turns, calls, tokens, latency, and cost

Each task selects only the criteria that apply. Rubrics should use behavioral
anchors and short evidence rather than a generic overall-quality prompt.

GPT-5.6 Sol will be the initial model judge. Its reasoning level must be recorded
and calibrated on the seed suite instead of treated as an invisible constant.

### Evaluating the judge

Judge selection is itself an economic evaluation problem. Early development
should create a small meta-evaluation set containing human-reviewed candidate
outputs and intentional perturbations. Judge candidates can then be compared on:

- agreement with human criterion labels
- pairwise ordering consistency
- repeated-run stability
- sensitivity to answer order and verbosity
- cost and latency

The production judge should not grade its own fitness. Human labels remain the
calibration reference even if a less expensive judge eventually handles routine
runs.

## Initial benchmark pack

The first target is roughly 20 carefully reviewed tasks:

- 5 implementation and debugging tasks, including project-pattern fit
- 3 planning and architecture tasks
- 3 documentation and editing tasks
- 3 research tasks over bounded source sets
- 3 pedagogical explanation tasks with named audiences and learning goals
- 3 fixed multi-turn personal-workflow scenarios

The categories are starting slices, not a permanent taxonomy. Some tasks may
carry more than one category, but each should have a clear primary purpose.

## HTML report and human feedback

The primary output will be a self-contained HTML report. It should support:

- filtering by task category, model, reasoning level, and trial status
- side-by-side candidate outputs
- criterion-level scores and evidence
- cost, token, cache, batch, latency, and tool-use views
- per-trial inspection rather than summaries alone
- human ratings, corrections, and notes
- export of human annotations for later judge calibration

A standalone HTML file cannot silently write changes back to the filesystem.
The design must choose between browser-local persistence, downloading an
annotation file, or an optional local server for annotation sessions. The
delivered report should remain viewable without that server.

## MVP boundary

The MVP includes:

- Python 3.12+ managed with uv
- a versioned portable task and result format
- an OpenAI-compatible provider interface
- an initial OpenRouter configuration
- model and reasoning-level sweeps
- repeated trials
- single-turn and fixed multi-turn scenarios
- a small controlled agent loop
- deterministic and model-based graders
- API list-price estimation with cache and batch metadata
- a self-contained HTML comparison report
- human feedback collection through the report workflow

The MVP does not include:

- automatic model routing or a recommended winner
- subscription-cost allocation
- a Pi extension or required Pi adapter
- LLM-simulated users
- automatic import of private historical traces
- active sweeps across system prompts, skills, tool sets, or temperature

Those deferred variables should fit the data model without requiring a redesign.

## Acceptance criteria

The MVP is complete when it can:

1. Load a public benchmark suite with versioned task definitions.
2. Run at least two models and two reasoning levels through the same tasks.
3. Repeat trials and preserve every raw result.
4. Execute a repository task in a disposable workspace through the small agent
   loop.
5. Run deterministic graders and GPT-5.6 Sol rubric graders on applicable
   criteria.
6. Record tokens, latency, cache use, batch use, and price provenance.
7. Generate one self-contained HTML report showing quality and economic
   tradeoffs without a composite winner.
8. Collect human criterion ratings and export them in a reusable format.
9. Swap OpenRouter for another OpenAI-compatible endpoint through configuration.
10. Keep private traces and local run artifacts outside the public repository.

## Open questions

- Which file and shell tools belong in the first agent loop?
- What isolation mechanism should disposable repository fixtures use?
- How should provider-specific reasoning levels map into a common schema?
- Which price catalog should be authoritative, and how should historical prices
  remain reproducible?
- What reasoning level should the initial GPT-5.6 Sol judge use?
- How should human annotations persist from a self-contained report?
- Which public license should the project use?
- Which concrete tasks should make up the first calibration set?

## Later phases

After the MVP, likely extensions are:

1. System-prompt, skill, tool-set, and temperature benchmarks.
2. Judge meta-evaluation and cheaper calibrated judges.
3. Harness adapters, with Pi as an early candidate.
4. LLM-simulated user scenarios.
5. Historical-trace mining and task distillation tools.
6. Optional routing experiments built from benchmark results.
