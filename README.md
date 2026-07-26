# Benchwarmer

Benchwarmer is a local-first toolkit for comparing language models and agent
configurations on repeatable tasks. It records quality, cost, latency, and
behavior separately so the report shows tradeoffs instead of declaring one
winner.

The project is currently a design scaffold. The first implementation will
compare models and reasoning levels through an OpenAI-compatible API, with
OpenRouter as the initial provider.

## Goals

- Define shareable benchmark tasks independently of any agent harness.
- Run the same task against a matrix of models and reasoning levels.
- Support fixed multi-turn scenarios and a small controlled agent loop.
- Combine deterministic checks with criterion-level model and human review.
- Record API list-price estimates, cache use, batch use, tokens, and latency.
- Generate a self-contained HTML report for comparison and human feedback.
- Keep raw trial results available instead of collapsing them into one score.

## Initial scope

The first benchmark pack will cover:

- implementation and debugging, including project-pattern fit
- planning and architecture
- documentation and editing
- research over a bounded source set
- pedagogical explanation tasks
- fixed multi-turn personal workflows

System prompts, skills, tool sets, temperature, additional harnesses, and
LLM-simulated users are extension points, not MVP variables.

## Project setup

Benchwarmer uses Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

The package does not have runtime dependencies or a command-line interface
yet. See [docs/architecture.md](docs/architecture.md) for the agreed design and
MVP boundaries.
