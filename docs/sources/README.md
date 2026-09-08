# Source inspection reports

Each source inspection is an independent evidence-gathering task. This directory
allows Pi, Hermes, Codex, and OpenRouter investigations to run concurrently
without sharing an output file.

## Ownership

- A source worker edits only its assigned file.
- Source workers do not edit `docs/TODO.md`, `docs/source-coverage.md`, or another
  source report.
- The `SRC-001` coordinating task reads all completed reports, builds
  `docs/source-coverage.md`, and records status transitions in `docs/TODO.md`.
- Reports describe observed capability; they do not select the first adapter.

## Required report shape

```markdown
# Source: Name

- Task: SOURCE-TASK-ID
- Observed version/account scope: ...
- Inspected: YYYY-MM-DD

## Evidence boundary

What was inspected, what access was available, and what remained unavailable.

## Session and request identity

Stable IDs, relationships, timestamps, and deletion/retention behavior.

## Incremental import

Cursor or watermark options, ordering guarantees, and duplicate keys.

## Usage and economics

Raw token categories, cached/batch/reasoning usage, actual charges, estimates,
subscription/quota/credit information, currency, and time zone.

## Classification and prompt visibility

Available classifications and accessible system-prompt/configuration layers,
including unknown or partial capture.

## Import and execution support

Read/import interfaces separately from automation/execution interfaces.

## Reconciliation identifiers

Request IDs or other evidence that can link harness and provider observations.

## Unknowns and risks

Explicit gaps and follow-up checks.
```

## Privacy rules

- Record schemas, field names, redacted examples, and aggregate capability—not
  private payloads.
- Never commit credentials, prompt bodies, session text, account identifiers, or
  raw provider responses.
- Commands in a report must be safe to repeat and must not embed private paths.
- If useful evidence cannot be sanitized, record that it was observed privately
  and describe only the conclusion and limitations.
