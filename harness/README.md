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
- `src/providers.ts`: the pi-ai provider catalog minus an explicit exclusion list, plus key diagnostics
- `src/catalog.ts`: the merged model list (pinned catalog, models.dev, each provider's own list) and how a model outside the pinned catalog is run
- `src/format.ts`: compact model-facing renderings of outlines and events
- `src/tools/library.ts`: the `benchwarmer-library` extension: `list_conversations`,
  `get_outline`, `read_events`, `list_bundles`, `propose_bundle`,
  `set_objective_type`
- `src/tools/fixtures.ts`: the `benchwarmer-fixtures` extension:
  `read_scrubbed_session`, `check_fixture`, `write_fixture_draft`
- `src/workflows/propose-bundles.ts`: per library conversation, one Pi Durable
  conversation that proposes bundles, then a second short one that types each
  new bundle from the closed objective-type vocabulary; sequential, with a
  JSON run report
- `src/workflows/anonymize-fixture.ts`: one Pi Durable conversation per raw Pi
  session file, producing a synthetic fixture draft for human review
- `src/fixture.ts`: the disclosure gate and the fixture document shape
- `src/usage.ts`: usage deltas and totals shared by workflows
- `src/cli.ts`: operator entry point

## Approval boundary

Running a workflow by hand is the approval for its model work: the operator
names the conversations, the model, and supplies that provider's key through
the environment. The pi-ai provider catalog is registered except for the
providers named in `EXCLUDED_PROVIDERS` (`src/providers.ts`), which can never
be selected and whose keys are never read, so
`--model openrouter/<id>` reads `OPENROUTER_API_KEY`, `--model google/<id>`
reads `GEMINI_API_KEY`, and so on; `npm run list-models` prints which common
providers have keys present, and `npm run list-models -- --json` merges, for
each provider with a key, the pinned pi-ai catalog, models.dev, and the
provider's own model list (Anthropic, OpenAI, OpenRouter, Google) into one
JSON catalog with release dates, prices, and each model's thinking levels; the
application's model picker reads that (`--offline` skips the network sources,
and keys travel only in request headers, never in the output). A provider can be routed through a pass-through
gateway that accepts the vendor's native request format and swaps in real
credentials: set its base URL variable (`ANTHROPIC_BASE_URL`,
`OPENAI_BASE_URL`, `OPENROUTER_BASE_URL`, `GEMINI_BASE_URL`,
`MISTRAL_BASE_URL`) and keep the gateway's virtual key in the usual key
variable. The provider id, catalog, and cost estimates are unchanged, and the
run report records the override under `model.base_url_override`. The
Benchwarmer application can also start `propose-bundles`, but only from a plan
the operator previewed and approved by its digest in the Bundles page; it then
runs this same command as a subprocess with `--run-id` set to the plan's run
and the keys from its own environment (see
[ADR 0006](../docs/decisions/0006-app-started-model-work.md)). Either way,
generated bundles land as `origin=generated`, `status=draft` revisions that a
human reviews in the app.

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

After the proposals for a conversation settle, a second conversation reads
only the new bundles' summary, goal, and objective and calls
`set_objective_type` for each, saving a generated revision with the type
(`bug`, `feature`, `refactor`, `test`, `performance`, `infrastructure`,
`analytics`, `research`, `design`, `writing`, `review`, or `unknown`). Its
usage counts toward that conversation's pass.

Each run writes `reports/harness/propose-bundles-<timestamp>.json` with the
conversations processed, the bundles created, and per-conversation usage. Cost
figures there are catalog estimates, not provider charges, and `pricing_source`
says which: the pinned pi-ai catalog for a model it lists; otherwise the model
runs with the request settings of its nearest catalog sibling and is priced
from models.dev when listed there, or recorded at zero cost when no catalog
prices it. When the run
finishes, the same figures are sent to the application as a run record
(`PUT /api/v1/runs/<run-id>`) so reviewers see what a run or one
conversation's pass cost beside its proposals; if the API refuses the record
the report file stands. Every bundle
the run creates records the run id, model, and report path as provenance, and
`propose_bundle` sends a request id derived from the run and the proposal, so
a retry after an interruption returns the existing bundle. The durable
storage file is owned by one process at a time.

## Anonymize a raw Pi session into a fixture draft

The `anonymize-fixture` workflow takes a Pi session file that has not been
imported. The harness reads the file, the API scrubs it in memory
(`POST /api/v1/fixtures/scrub-pi-session`) and checks candidates
(`POST /api/v1/fixtures/check`) without storing anything, and the model writes
an invented analog with the same structure. Drafts land in
`reports/harness/fixtures/<run-id>/<native_id>.json` for a human diff review;
nothing is written to `tests/fixtures/`.

```bash
npm run anonymize-fixture -- \
  --api http://127.0.0.1:8000 \
  --model <provider>/<model-id> --disclose-to <provider> \
  --session /absolute/path/to/session.jsonl \
  --term "Operator Name" --term "Employer" --terms-file /private/terms.txt
```

Disclosure rule: scrubbed session content is sent to the model provider, so
every run must name that provider with `--disclose-to`, and it must match the
provider in `--model`. The command refuses to start otherwise. Scrub-only
output is not a fixture; the model rewrite is required, and the draft tool
refuses a candidate that still contains placeholders. See
[the work record](../todo/work/fixture-anonymizer/README.md).

Provider keys come from the environment through the registered pi-ai
providers; an unknown model error means the catalog does not list it or its
provider's key is missing.

## Checks

```bash
npm run check
npm test
```
