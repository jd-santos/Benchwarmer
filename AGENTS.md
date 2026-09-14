# AGENTS.md

> This file provides context for AI agents working in this codebase.
> Prefer retrieval-led reasoning. Read the local design document before making
> architectural changes.

## Project Context

- **Project**: Benchwarmer, a local app for personal model evaluations, task
  simulations, trusted external evidence, and consolidated usage economics
- **Tech stack**: Python 3.12+, uv, SQLite and Svelte (planned application)
- **Architecture**: Local API and worker, private artifact storage, harness-neutral
  tasks, and adapters for harnesses, providers, pricing and published evaluations
- **Status**: Design scaffold. Application, importers and execution are not yet
  implemented. Target host is an always-on Mac mini alongside Hermes Agent.
- **Access and UI**: Private hosting over Tailscale, with a mobile-friendly Svelte
  interface. Exact serving configuration remains open.

## Critical Rules

- Keep benchmark task definitions independent of Pi or any other agent harness.
- Do not combine quality and economics into a single winner score. Preserve
  criterion-level and per-trial results.
- Treat model, reasoning level, harness, prompts, skills, and tool sets as separate
  experimental variables, even when a later benchmark tests them together.
- Treat direct Python API execution as its own harness. Track harness versions
  and accessible system prompts, including provenance and incomplete capture.
- Start experiments with native harness configurations; retain controlled
  comparisons as a later capability with explicit overrides and differences.
- Derive simulations from everyday work regardless of whether sessions succeeded.
  Preserve starting context separately from original answers and later state.
- Preserve raw provider usage and record the pricing source used for estimates.
  Track cache and batch behavior separately when providers expose them.
- Reconcile overlapping harness/provider usage before aggregating. Keep actual
  charges, estimates, subscription expense and quota usage distinguishable.
- Use fixed conversation scripts before adding LLM-simulated users.
- Run agent-loop tasks only in disposable fixture workspaces.
- Keep private traces, generated artifacts, reports, and human annotations out
  of git unless they were intentionally sanitized for the public benchmark.
- Never commit API keys, private prompts, personal traces, or provider response
  payloads containing private data.
- Keep application databases and private artifacts outside the checkout by
  default. Source imports must be idempotent and retain coverage/provenance.
- Retain private snapshots of imported session content alongside metadata rather
  than relying on source logs remaining available.
- Version serialized task and result schemas when their meaning changes.
- Avoid adding dependencies until an implemented feature needs them.

## UI Design Rules

For frontend work, follow the
[UI design skill](https://github.com/jd-santos/Skills/blob/main/skills/ui-design/SKILL.md)
and the interface principles in [docs/architecture.md](docs/architecture.md).

- Start with the user's primary task, information hierarchy, and reading order.
  Add styling only after the structure is clear.
- Prefer proximity, alignment, typography, whitespace, and subtle dividers over
  borders, cards, and strong containers. A component does not need a visible box.
- Avoid generic generated-UI patterns: card grids for ordinary content, large
  radii, pill-shaped buttons, gradients, decorative blobs, repeated eyebrow
  labels, oversized spacing, and marketing copy.
- Use familiar controls and information shapes. Prefer tables for comparison,
  lists for list-shaped data, and visible labels for form fields.
- Keep copy concise and information-dense without crowding. Give one primary task
  clear emphasis and keep supporting information quiet.
- Give color a specific semantic job. Never rely on color alone for status, and
  keep focus indicators and important text at accessible contrast.
- Treat loading, empty, partial, unknown, zero, none, offline, disabled,
  read-only, success, and error as distinct states where the domain distinguishes
  them.
- Reconsider hierarchy on small screens instead of only stacking columns. Use
  desktop width effectively rather than stretching a mobile layout.
- Before finishing UI work, check subtraction, hierarchy, generated-UI patterns,
  and accessibility as defined by the UI design skill.

## Commands

- **Install**: `uv sync --dev`
- **Package check**: `uv run python -m compileall src`
- **Tests**: `uv run pytest`
- **Lint**: `uv run ruff check .`; `uv run ruff format --check .`

## Documentation Index

> Read the file below before changing architecture, scope, or evaluation
> semantics.

[Root]: ./docs/
design: {architecture.md,experiments.md,decisions.md}
delivery: {roadmap.md,plans/}
evidence: {sources/,source-coverage.md}
decisions: {decisions.md,decisions/}
tasks: {TODO.md}

## File-Specific Notes

- **`docs/architecture.md`**: Records the chosen design, MVP boundary,
  alternatives, acceptance criteria, and open questions.
- **`docs/experiments.md`**: Defines simulation, harness and prompt semantics.
- **`docs/decisions.md`**: Records unresolved choices and proposed defaults.
- **`docs/decisions/`**: Stores independently authored ADR proposals and their
  index. A coordinator reconciles accepted records into `docs/decisions.md`.
- **`docs/sources/`**: Stores one evidence report per inspected source. A
  coordinator synthesizes them into `docs/source-coverage.md`.
- **`docs/roadmap.md`**: Records delivery slices, dependencies, milestone gates
  and the agent handoff protocol.
- **`docs/plans/`**: Contains executable plans with exact paths, commands,
  acceptance criteria and verification steps. Follow the plan linked by a TODO
  task rather than inventing missing implementation details.
- **`docs/TODO.md`**: Tracks work using In Progress, Up Next, Backlog and Done.
- **`src/benchwarmer/`**: Keep domain models independent from provider and
  harness adapters.
- **Generated reports**: Write to `reports/`; this directory is gitignored.
- **Run artifacts**: Write to `artifacts/` or `.benchwarmer/`; both are
  gitignored.
