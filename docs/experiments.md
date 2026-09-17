# Tasks, harnesses and comparisons

## What an experiment asks

Experiments test whether another configuration can do useful work better or more
cheaply. Successful everyday sessions are valid task seeds. The goal is to
simulate representative work, including broad sweeps over inexpensive models,
rather than repair sessions inside Benchwarmer.

Keep model, provider, reasoning, harness, system prompts, skills, tools and
sampling settings as distinct dimensions. An experiment may vary several
together, but its result then describes that complete configuration. Do not
attribute a harness or prompt change to the model alone.

## Harness is a first-class dimension

Represent Pi, Nous Research's Hermes Agent, Codex where feasible, and a direct
Python API call as harness choices. Import support and execution support are
separate capabilities. Reading a session does not imply we can replay it.

The direct API harness makes minimal provider calls from Python. Record adapter
version, message construction, retries, transformations and parameters. It has
no implicit agent loop, filesystem tools or hidden Benchwarmer prompt. Any later
tool loop is a distinct execution mode/configuration. Direct execution does not
make provider-side hidden behavior observable.

Native configurations capture harness version/build, execution mode, relevant
settings, installed skills, tool definitions and permissions where available.
Tasks declare required capabilities so an incompatible harness is marked
unsupported, not scored as a quality failure. A text-only request and a coding
agent with shell access are not equivalent controlled treatments.

## System-prompt provenance

Track system prompts whenever accessible, including layered instructions such as
harness defaults, user configuration, project instructions, skill content and
task-specific additions. Capture order and message role when available.

For each prompt snapshot, record:

- Origin, capture time, harness/configuration version and associated trial.
- Exact accessible content in private storage and a content hash for comparison.
- Whether content was captured from the effective request, reconstructed from
  configuration, partially observed, unavailable or redacted.
- Layer ordering and dynamic inputs when known, including changes during a run.

Requested configuration and observed effective configuration are separate facts.
A configuration file does not prove the exact request sent to the provider.
Unknown hidden instructions must not be represented as an empty prompt or exact
match. Exclude credentials and record redaction. Hashes do not make private
prompts safe for public release.

Two experiment modes are useful:

- **Native configuration:** Keep each harness's normal instructions and tools.
  This tests the setup the user might actually adopt.
- **Controlled configuration:** Align explicit prompts and capabilities where
  supported and hold other dimensions fixed. Record remaining differences.

Native configuration is the agreed initial mode. Controlled comparisons remain
a later capability, with explicit prompt overrides, matched tools where possible,
and records of variables held fixed or changed. Neither mode guarantees
equivalence where a harness cannot expose or override relevant behavior.

## From conversation units to task versions

Projects can select live collections and create frozen datasets of conversation
revisions and meaningful segments. A task unit may cover one decision or a few
exchanges; it must include enough preceding context to define the question.
Record segment boundaries, source/branch lineage, segmentation producer/version,
selection rationale, and reconstruction gaps. Units from the same conversation
are correlated observations, not automatically independent data points.

Freeze dataset membership and source/enrichment revisions for each experiment.
A live query gaining new matches never changes an existing run or starts work.
Private programmatic dataset access supports ad hoc scripts and notebooks without
requiring UI automation or public export.

Tasks describe intent, starting inputs, fixture/environment needs, permitted
capabilities, conversation script and criteria independently of the harness.
Adapters translate those requirements into concrete execution settings.

Task derivation produces a reviewable draft linked to source sessions and
[evidence bundles](evidence-bundles.md). A bundle can support analysis without
being reconstructable as a runnable task. Candidate starting inputs and
judge-only historical evidence have distinct typed roles and validated references.
Prefer assertions about acceptable behavior over requiring the historical answer.
Preserve the selected bundle and criterion revisions with the task. Separate
initial context from subsequent answers, tool activity and outcomes. Do not leak
the original solution or later workspace state into a fresh attempt. The
original result is comparison evidence without being a canonical answer.

Record reconstruction level explicitly:

| Form | What the run can establish |
| --- | --- |
| Prompt and context simulation | Response to prepared input, possibly without original environment |
| Fixture-backed task simulation | Performance against known starting workspace and tools |
| Fixed multi-turn simulation | Behavior through defined user messages and decision points |

If original state is missing, prepare a new fixture or narrow the question and
record the change. A transcript alone does not prove reproducibility. A selected
intermediate segment must pin its starting context rather than silently inheriting
later source state.

### Follow-up behavior

Start with single-response/action units, then fixed multi-turn sequences whose
follow-ups remain applicable to the new response. A follow-up that assumes an
absent candidate action is incompatible, not proof of poor model quality. Report
that condition rather than forcing the historical script through it.

Adaptive continuation is an intended later mode. A simulated user may pursue the
original objective with follow-ups responsive to the new candidate. Historical
follow-ups inform intent, not instructions to reproduce the original outcome.
Record simulator model, prompt, allowed knowledge, policy, messages, usage, and
cost separately. Preserve task versions and distinguish simulator-assisted
results from fixed tests; they measure the candidate and simulator together.

Do not expose original solutions or later discoveries to a simulator that can
leak them to the candidate. Reference answers and historical outcomes may be
available to judges in a separate evidence channel, never as candidate context.
Review generated criteria for answer-specific bias; pin rubrics before a run.
Simulator reliability and human comparison need validation before conclusions
are treated as evidence about the candidate alone.

## Execution and review

Record task versions, candidates, repetitions, limits, execution order and
environment snapshots. Freeze settings before each trial and capture actual
model identity or routing changes where exposed. Failed requests, retries and
their usage remain part of the evidence.

No import, saved query, restart, or enrichment update starts a trial. Explicitly
approve a frozen model-work plan covering candidates, applied judges, input and
output allowances, request counts, retries, disclosure permissions, and a total
cost policy. The same rule covers descriptions, classifiers, embeddings, and
later simulators. No numeric budget or permission to send private content to a
remote provider is assumed. See
[conversation-library.md](conversation-library.md#model-work-requires-bounded-approval).

Use fresh disposable workspaces for tool-capable trials. Establish capability,
credential and network policy before execution. Budget controls need experiment
and per-trial limits, including turns/time where cost cannot be measured reliably.
Distinguish enforceable limits from estimated checks and possible in-flight cost
overrun. Retries and recovery must be explicit.

### Applied judges

Every rerun presents its applied judges before approval: task-specific rubrics,
model/configuration, evidence access, deterministic checks where applicable,
and the budget reserved for judging. Once approved, judging runs automatically
within that operation; it does not require a manual step after every trial.
Additional judging or changed rubrics require a new bounded approval.

Record judge model, reasoning, prompt, rubric version, usage, cost, and evidence.
Judge error or budget exhaustion leaves a result unjudged rather than scoring the
candidate as failed. Preserve disagreement, uncertainty, criterion-level results,
failures, and per-trial variation. A single attempt is evidence about that attempt,
not proof of general reliability. Human notes, corrections, and calibration remain
available without making human review a prerequisite for each judgment.

Offer side-by-side outputs/artifacts and separate usage/cost views. Calibrate model
judges against human review before treating their judgments as reliable. Test
proposed evaluators against successful, failing, and ambiguous or inapplicable
examples; catching only the case that motivated the evaluator is insufficient.
Retain the calibration evidence and links to motivating bundles or patterns.

## Decisions needed before execution

Choose the first task family and harness, minimum reconstruction requirements,
run permission/budget policy and review
criteria. Track these in [decisions.md](decisions.md); source inspection can
proceed before every experiment detail is settled.
