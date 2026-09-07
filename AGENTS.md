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

## Commands

- **Install**: `uv sync`
- **Package check**: `uv run python -m compileall src`
- **Tests**: Not configured yet. Add pytest with the first executable feature.
- **Lint**: Not configured yet. Add Ruff with the first executable feature.

## Documentation Index

> Read the file below before changing architecture, scope, or evaluation
> semantics.

[Root]: ./docs/
design: {architecture.md,experiments.md,decisions.md}
tasks: {TODO.md}

## File-Specific Notes

- **`docs/architecture.md`**: Records the chosen design, MVP boundary,
  alternatives, acceptance criteria, and open questions.
- **`docs/experiments.md`**: Defines simulation, harness and prompt semantics.
- **`docs/decisions.md`**: Records unresolved choices and proposed defaults.
- **`docs/TODO.md`**: Tracks work using In Progress, Up Next, Backlog and Done.
- **`src/benchwarmer/`**: Keep domain models independent from provider and
  harness adapters.
- **Generated reports**: Write to `reports/`; this directory is gitignored.
- **Run artifacts**: Write to `artifacts/` or `.benchwarmer/`; both are
  gitignored.
