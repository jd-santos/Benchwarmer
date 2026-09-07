# Design decisions

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

| Decision | Why it matters | Proposed starting point |
| --- | --- | --- |
| Initial import source | Determines the first usable slice and real schema constraints | Inspect Pi, Hermes, Codex and provider coverage, then choose the richest accessible session source |
| Tailscale serving and access | Determines binding, authentication and deployment work | Private access to the Mac mini; choose serving mechanism and access configuration before deployment |
| Data location and recovery | Records and artifact files must remain consistent | Configurable root outside the checkout, migrations and coordinated backup/restore |

Source inspection should establish stable IDs, incremental imports, token/cost
granularity, classifiers, historical coverage, prompt visibility and request IDs
for reconciliation. Verify installed versions and account access. Do not assume
OpenRouter classification access or Codex history is complete.

## Before the first simulation

| Decision | Why it matters | Proposed starting point |
| --- | --- | --- |
| First task family | Coding, research and text tasks need different fixtures and tools | Select representative everyday tasks after inspecting sessions |
| First execution harness | Establishes process control and capture requirements | Pi or Hermes based on supported automation; direct API baseline where capabilities fit |
| Reconstruction threshold | Transcripts may lack starting files or external state | Reviewed inputs and fixtures, with approximations labeled before a sweep |
| Scope and budget of broad sweeps | Cheap calls multiply across tasks and retries | Explicit count/time limits and total spend policy; no unbounded runs on import |
| Meaning of good enough | Enables useful comparison without a universal score | Task-specific human criteria and notes, then verifiable checks |

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
