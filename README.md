# Benchwarmer

Benchwarmer is a local app for choosing language models using personal sessions,
task simulations, trusted public evaluations, and usage economics. It brings
usage across Pi, Nous Research's Hermes Agent, and Codex where accessible into
one place, then helps compare whether alternative models can do everyday work
better or more cheaply.

The project is a design scaffold. The planned application uses a Python backend,
SQLite database and mobile-friendly Svelte frontend on an always-on Mac mini,
with private access over Tailscale. Importers, the UI and experiment execution
are not implemented yet.

## Scope

- Aggregate usage, spend and classifications with source provenance.
- Add personal ratings and notes to real sessions.
- Prepare task simulations from successful or unsuccessful work.
- Compare models, reasoning levels, harnesses, prompts, skills and tools as
  distinct dimensions. Direct Python API execution is a harness too.
- Track accessible system prompts and make missing or partial capture visible.
- Start with native harness configurations; add controlled comparisons later.
- Keep trusted external evaluations with dates, sources and configuration details.
- Preserve trial results and quality/cost tradeoffs without one combined score.

Imported session content is retained as private snapshots alongside metadata.
Application data stays on the Mac mini and outside the public checkout by
default. Private sessions, prompts, databases, artifacts and annotations must
not be committed.
Tool-capable simulations run only in disposable fixture workspaces.

## Design and tasks

- [Architecture](docs/architecture.md): product direction, application components,
  data boundaries and delivery stages.
- [Experiments](docs/experiments.md): task derivation, harness dimensions and
  system-prompt provenance.
- [Design decisions](docs/decisions.md): accepted choices and remaining
  decisions.
- [Decision records](docs/decisions/README.md): independent ADR proposals and
  coordinator integration rules.
- [Source reports](docs/sources/README.md): per-source evidence and privacy
  requirements.
- [Source coverage](docs/source-coverage.md): cross-source identity, import,
  usage, economics, prompt, execution, and retention comparison.
- [Buildout roadmap](docs/roadmap.md): delivery slices, dependencies, acceptance
  gates and agent handoff protocol.
- [TODO](docs/TODO.md): implementation queue and completed work.

## Project setup

The Python scaffold uses Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

There are no runtime dependencies, application commands or frontend setup yet.
