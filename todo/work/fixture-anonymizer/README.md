# Anonymize real sessions into synthetic fixtures

Status: Groundwork on `task/fixture-anonymizer`. The deterministic scrub,
fidelity, and leak layer, its routes, and the harness workflow scaffold exist
and are tested on synthetic data. No model run has happened and no real session
has been scrubbed.

## Purpose

Give Benchwarmer a confidentiality layer between the operator's real coding
sessions and any model request. A raw Pi session on disk is parsed in memory,
scrubbed deterministically, rewritten by a model into an invented analog with
exactly the same structure, checked for structural drift and leaks, and written
as a draft for human diff review. Later model work (bundle proposals, evals)
runs against the reviewed fixtures instead of the real conversations. Nothing
private enters the library, the database, or a snapshot on the way.

## Dependencies and order

Builds on the [analysis harness](../analysis-harness/README.md) conventions
(typed routes in Python, Pi Durable workflows around them) and the Pi session
reader. The first operator run waits on a running API over a disposable data
root and a real Pi session named by the operator.

## Decisions

Decided with the user on 2026-10-21:

- Anonymize before import. The input is a raw Pi session file (or files) on
  disk, parsed with the existing Pi reader in memory. The scrub and check
  routes take the session content in the request body and store nothing. The
  harness reads the file the operator names and sends it to the route; it
  never opens the database.
- Scrub-only output is not a fixture tier. The model rewrite is mandatory: the
  placeholders are an intermediate form, and the draft tool refuses a
  candidate that still contains any. The rewrite must also disguise how the
  user talks to the model (register, casing, typos, greeting habits, sentence
  length) while keeping every request, because writing style is identifying.
  Structural fidelity stays exact.
- Disclosure is decided: scrubbed sessions may be sent to any provider the
  operator names. Each run still acknowledges the recipient explicitly with
  `--disclose-to <provider>`, which must match the `--model` provider; the
  command refuses to start otherwise and prints the rule.

Working decisions in this groundwork, open to revision:

- Placeholders are stable per conversation (`<email-1>`, `<url-2>`,
  `/scrubbed/path-3/file-3.py`), keep file extensions, and the report never
  carries original values. Spans are located by event, block, and code-point
  offsets in the original text.
- The fidelity check compares positionally in ordinal order and follows parent
  positions rather than names, so a candidate may rename native ids. It checks
  event count, ordinals, parent graph, kinds, roles, block kinds and order,
  which blocks have captured text, tool call/result pairing, extension keys,
  relationship kinds, and title presence.
- The leak check scans every string in the candidate, including extensions
  and usage, for operator terms (whole word, case-insensitive) and for any
  scrubbed original text (case-insensitive substring). Issues name the
  location and offsets, never the text, so they can be shown to the model.
- Drafts go to gitignored `reports/harness/fixtures/<runId>/<native_id>.json`
  in the `tests/fixtures` file format. Entering `tests/fixtures/` is a separate
  human step after a diff review.
- Fixture usage entries keep `entry_id`, `provider`, `model`, and the raw
  counts; `response_id` is dropped.

## Proposed pipeline

1. Operator runs `npm run anonymize-fixture -- --session <path> --model
   <provider>/<model> --disclose-to <provider> --term <name> ...` against an
   API on a disposable data root. Terms can also come from a local
   `--terms-file` kept outside the checkout.
2. The harness reads the file, and the model's `read_scrubbed_session` tool
   posts it to `POST /api/v1/fixtures/scrub-pi-session`, which parses it with
   `parse_pi_session`, scrubs the title and every captured block text, and
   returns the scrubbed events, a fixture-shaped conversation, and a
   `ScrubReport`.
3. The model invents an analog scenario, rewrites every text in the new voice
   and domain, keeps structure exact, and calls `check_fixture`
   (`POST /api/v1/fixtures/check`) until it reports no fidelity issues, no
   leaks, and no placeholders.
4. `write_fixture_draft` writes the draft document and the run report records
   checks, drafts, and usage per session.
5. A human diffs the draft against the scrubbed original, then copies it into
   `tests/fixtures/` and registers its source id if accepted.

## Acceptance criteria

The scrub never changes anything but matched spans and the report never
contains an original value. The check reports every structural difference and
every reappearance of scrubbed text as typed issues. A real session can be
anonymized without being imported, snapshotted, or logged. The harness refuses
to run without an explicit disclosure matching the model provider. Drafts
never land in `tests/fixtures/` without a human step.

## Work

- [x] `benchwarmer.anonymize`: strict pydantic scrub pass (terms, emails,
  URLs, hostnames, absolute and `~` paths, IPv4/IPv6, prefixed and random
  secrets), `ScrubReport`, fixture shaping, `fidelity_issues`, `leak_issues`.
- [x] `parse_pi_session` split out of `read_pi_session` so content can be
  parsed in memory.
- [x] Routes `POST /api/v1/fixtures/scrub-pi-session` and
  `POST /api/v1/fixtures/check`, read-only, with API tests over a synthetic Pi
  session (`tests/fixtures/pi-session-synthetic.jsonl`).
- [x] Harness: `anonymize-fixture` workflow and CLI, `benchwarmer-fixtures`
  extension (`read_scrubbed_session`, `check_fixture`, `write_fixture_draft`),
  disclosure gate, run report, vitest coverage for the gate and document
  shape. Shared usage helpers moved to `harness/src/usage.ts`; provider
  registration goes through the shared `harness/src/providers.ts`.
- [ ] First operator run on one real session against a disposable data root;
  record the diff review, cost, and which detector categories missed anything
  the reviewer caught. Extend the detectors or the terms file accordingly.
- [ ] Decide how reviewed fixtures are named and registered in
  `tests/fixtures/sources.json`, and whether the review step gets a script
  that diffs the draft against the scrubbed original.
- [ ] Pi v1 run-event logs: the reader supports them, but the scrub has not
  been exercised on one.

## Open questions for the user

- Should fixtures preserve real timestamps, durations between events, and
  token counts? The scrub passes them through unchanged today, and the
  analyst instructions ask the model to shift dates while keeping shape. Usage
  counts could identify a session when combined with other data.
- Who reviews the draft diff before a fixture enters `tests/fixtures/`, and is
  one reviewer enough for sessions that include other people's names?
- Should the operator's standing terms list live in a documented location
  outside the checkout (for example under the private data root) so every run
  uses the same list, or stay per-run?
- Should this also be exposed as a Claude Code skill wrapping the CLI? It
  would be a `SKILL.md` that prompts for the session path, the terms file, and
  the disclosure provider, then runs `npm --prefix harness run
  anonymize-fixture` and opens the draft for review. Not created here.
- The leak check compares case-insensitive substrings of scrubbed originals.
  Should it also catch simple transformations (hyphen removal, reordering of
  a name's parts)?

## Verification

2026-10-21: `uv run pytest` (243 passed, 1 skipped), `uv run ruff check .`,
`uv run ruff format --check .`, `npm run check` and `npm test` (8 tests) in
`harness/` pass. The workflow was not run; no model was called.

## Supporting material

- [Analysis harness work record](../analysis-harness/README.md)
- [Harness README](../../../harness/README.md)
- [Conversation library design](../../../docs/conversation-library.md)
  (private access versus sanitized export)
- [Evidence bundles design](../../../docs/evidence-bundles.md)
