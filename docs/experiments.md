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

## From sessions to task versions

Tasks describe intent, starting inputs, fixture/environment needs, permitted
capabilities, conversation script and criteria independently of the harness.
Adapters translate those requirements into concrete execution settings.

Task derivation produces a reviewable draft linked to source sessions. Separate
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
record the change. A transcript alone does not prove reproducibility. Branching
from intermediate context may be useful later, but is not the default purpose
or required first workflow.

Use fixed scripts before LLM-simulated users. Preserve task versions so later
changes do not silently alter comparisons.

## Execution and review

Record task versions, candidates, repetitions, limits, execution order and
environment snapshots. Freeze settings before each trial and capture actual
model identity or routing changes where exposed. Failed requests, retries and
their usage remain part of the evidence.

Use fresh disposable workspaces for tool-capable trials. Establish capability,
credential and network policy before execution. Budget controls need experiment
and per-trial limits, including turns/time where cost cannot be measured reliably.
Distinguish enforceable limits from estimated checks and possible in-flight cost
overrun. Retries and recovery must be explicit.

Start with human notes, ratings and task-specific definitions of good enough.
Offer side-by-side outputs/artifacts and separate usage/cost views. Preserve
criterion-level judgments, uncertainty, failures and per-trial variation. A single
attempt is evidence about that attempt, not proof of general reliability.

Deterministic graders and model judges can follow when tasks justify them. Record
judge model, reasoning, prompt, rubric version and cost. Calibrate model judges
against human review before treating their judgments as reliable.

## Decisions needed before execution

Choose the first task family and harness, minimum reconstruction requirements,
run permission/budget policy and review
criteria. Track these in [decisions.md](decisions.md); source inspection can
proceed before every experiment detail is settled.
