# Design decisions

Independently authored proposals live under [decisions/](decisions/README.md).
This document remains the canonical summary after a coordinating task reviews
and integrates those records.

The product direction is agreed: a local SQLite/Svelte app with a Python backend,
personal session review, consolidated usage, trusted external evidence and task
simulations. Harness and system prompts are explicit dimensions; direct Python
API execution is a harness.

## Confirmed starting choices

- **Access:** Plan for private hosting over Tailscale from the Mac mini. The UI
  must be mobile friendly. Exact serving and access configuration remains open.
- **Session storage:** Keep private snapshots of imported session content plus
  normalized metadata. The app should not depend on original logs remaining
  available. Retention, deletion and backup details remain open.
- **Experiments:** Start with native harness configurations, capturing accessible
  system prompts, tools, skills and differences. Controlled comparisons remain
  a later capability, rather than an initial requirement.

## Before the first implementation slice

### Initial import source

- **Why it matters:** Determines the first usable slice and real schema
  constraints.
- **Proposed starting point:** Inspect Pi, Hermes, Codex, and provider coverage,
  then choose the richest accessible session source.

### Tailscale serving and access

- **Why it matters:** Determines binding, authentication, and deployment work.
- **Proposed starting point:** Keep access private to the Mac mini and choose the
  serving mechanism and access configuration before deployment.

### Data location and recovery

- **Why it matters:** Database records and artifact files must remain
  consistent.
- **Proposed starting point:** Use a configurable root outside the checkout,
  migrations, and coordinated backup/restore.

Source inspection should establish stable IDs, incremental imports, token/cost
granularity, classifiers, historical coverage, prompt visibility and request IDs
for reconciliation. Verify installed versions and account access. Do not assume
OpenRouter classification access or Codex history is complete.

## Before the first simulation

### First task family

- **Why it matters:** Coding, research, and text tasks need different fixtures
  and tools.
- **Proposed starting point:** Select representative everyday tasks after
  inspecting sessions.

### First execution harness

- **Why it matters:** Establishes process control and capture requirements.
- **Proposed starting point:** Use Pi or Hermes based on supported automation,
  with a direct API baseline where capabilities fit.

### Reconstruction threshold

- **Why it matters:** Transcripts may lack starting files or external state.
- **Proposed starting point:** Require reviewed inputs and fixtures, with
  approximations labeled before a sweep.

### Scope and budget of broad sweeps

- **Why it matters:** Cheap calls multiply across tasks and retries.
- **Proposed starting point:** Require explicit count/time limits and a total
  spend policy; never run unbounded work on import.

### Meaning of good enough

- **Why it matters:** Enables useful comparison without a universal score.
- **Proposed starting point:** Use task-specific human criteria and notes, then
  verifiable checks.

A direct API baseline cannot replace a tool-using harness on tasks that require
it, even when both are represented through the same experiment interface.

## Can wait until the relevant feature

- Initial external evaluation sources and their APIs, exports or permitted snapshots.
- Backend framework, Svelte versus SvelteKit integration, and worker supervision.
- Annotation scales, blind comparison and review ordering.
- Controlled comparison support: prompt overrides, tool/capability alignment,
  fixed variables and disclosure of remaining differences between harnesses.
- Historical pricing sources and optional API-equivalent subscription estimates.
  Keep actual charges and estimates separate from the beginning.
- Retention durations, attachment limits and selective raw-content deletion.
- Which simulations warrant promotion into named evaluation suites.
- Deterministic graders, judge calibration, portable reports and sanitized exports.
- Repository visibility/license verification before distributing third-party
  fixtures or source material. Public code does not make personal data public.

Implementation tasks live in [TODO.md](TODO.md). This document records choices
and rationale rather than duplicating execution status.
