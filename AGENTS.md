# AGENTS.md

> This file provides context for AI agents working in this codebase.
> Prefer retrieval-led reasoning. Read the local design document before making
> architectural changes.

## Project Context

- **Project**: Benchwarmer, a portable evaluation toolkit for comparing model
  utility and economics
- **Tech stack**: Python 3.12+, uv, self-contained HTML reports
- **Architecture**: Harness-neutral task definitions with swappable execution,
  provider, grader, pricing, and reporting adapters
- **Status**: Design scaffold. The agent loop and evaluation runner are not yet
  implemented.

## Critical Rules

- Keep benchmark task definitions independent of Pi or any other agent harness.
- Do not combine quality and economics into a single winner score. Preserve
  criterion-level and per-trial results.
- Treat model, reasoning level, prompts, skills, and tool sets as separate
  experimental variables, even when a later benchmark tests them together.
- Preserve raw provider usage and record the pricing source used for estimates.
  Track cache and batch behavior separately when providers expose them.
- Use fixed conversation scripts before adding LLM-simulated users.
- Run agent-loop tasks only in disposable fixture workspaces.
- Keep private traces, generated artifacts, reports, and human annotations out
  of git unless they were intentionally sanitized for the public benchmark.
- Never commit API keys, private prompts, personal traces, or provider response
  payloads containing private data.
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
design: {architecture.md}

## File-Specific Notes

- **`docs/architecture.md`**: Records the chosen design, MVP boundary,
  alternatives, acceptance criteria, and open questions.
- **`src/benchwarmer/`**: Keep domain models independent from provider and
  harness adapters.
- **Generated reports**: Write to `reports/`; this directory is gitignored.
- **Run artifacts**: Write to `artifacts/` or `.benchwarmer/`; both are
  gitignored.
