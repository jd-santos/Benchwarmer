# Benchwarmer harness

Pi Durable workflows for Benchwarmer's model-driven analysis: work that reads
the conversation library, calls a model, and writes generated records back.
Deterministic parsing stays in Python under `src/benchwarmer`; this package
only orchestrates models around it.

The harness reaches library data exclusively through `/api/v1`. It never opens
Benchwarmer's SQLite database. Python remains authoritative for conversation
contracts, evidence resolution, and bundle revisions.

## Why Pi Durable

[`@earendil-works/pi-durable`](https://github.com/earendil-works/pi/tree/main/packages/durable)
commits every model turn and tool call before showing it, so an interrupted
run resumes from its last checkpoint instead of repeating paid work. Tools are
declared replay-safe or not; a write that was cut off reports `interrupted`
to the model rather than silently running twice. Usage is kept per
`provider/model` and per tool.

The package is experimental and its API changes without notice between
releases, so it is pinned exactly in `package.json`. Upgrade deliberately and
re-run `npm run check` and `npm test`.

## Layout

- `src/benchwarmer/client.ts`: typed client for the API routes the harness uses
- `src/format.ts`: compact model-facing renderings of outlines and events
- `src/tools/library.ts`: the `benchwarmer-library` extension: `list_conversations`,
  `get_outline`, `read_events`, `list_bundles`, `propose_bundle`
- `src/workflows/propose-bundles.ts`: one Pi Durable conversation per library
  conversation, sequential, with a JSON run report
- `src/cli.ts`: operator entry point

## Approval boundary

Running a workflow by hand is the approval for its model work: the operator
names the conversations, the model, and supplies provider keys through the
environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Nothing in the Benchwarmer
application starts a harness run, and generated bundles land as
`origin=generated`, `status=draft` revisions that a human reviews in the app.
This is the pilot exception recorded in
[the evidence bundle work record](../todo/work/evidence-bundles/README.md);
the bounded model-work service replaces it later.

## Run

Start the API on a development data root (see
[docs/development.md](../docs/development.md)), then:

```bash
cd harness
npm ci
npm run list-models -- anthropic
npm run propose-bundles -- \
  --api http://127.0.0.1:8000 \
  --model anthropic/<model-id> \
  --conversation <conversation-id> --conversation <conversation-id>
```

Options: `--thinking <level>`, `--instructions "<operator notes>"`,
`--storage <sqlite file>` (default `.benchwarmer/harness/propose-bundles.sqlite`,
gitignored), `--reports <dir>` (default `reports/harness`, gitignored).

Each run writes `reports/harness/propose-bundles-<timestamp>.json` with the
conversations processed, the bundles created, and per-conversation usage. Cost
figures there are pi-ai catalog estimates, not provider charges. The durable
storage file is owned by one process at a time.

## Checks

```bash
npm run check
npm test
```
