# Source inspection reports

Each source inspection is an independent evidence-gathering task. This directory
allows Pi, Hermes, Codex, OpenRouter, and ChatGPT investigations to run concurrently
without sharing an output file.

## Ownership

An assigned worker owns one report and its work record. An integrator maintains
the shared [coverage matrix](../source-coverage.md) and
[priority index](../../todo/TODO.md). Use separate worktrees for concurrent
writers. Reports describe dated observed capability; the accepted adapter
decision determines implementation order.

## Completed reports

- [Pi](pi.md)
- [Hermes](hermes.md)
- [Codex](codex.md)
- [OpenRouter](openrouter.md)
- [ChatGPT macOS conversations](chatgpt-macos.md)
- [Cross-source coverage matrix](../source-coverage.md)

## Required report shape

```markdown
# Source: Name

- Work: Readable source-inspection task name
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
