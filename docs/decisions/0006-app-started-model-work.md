# ADR 0006: Approved model work started from the application

- Status: Proposed
- Work: [Run approved model work with durable limits and recovery](../../todo/work/bounded-model-work/README.md)
- Date: 2026-10-23

## Context and evidence

Until now nothing in the Benchwarmer application started a model run. The
analysis harness (`harness/`) is run by hand: the operator names the
conversations, the model, and supplies the provider key in the shell. That
command was the whole approval, and the harness README, the evidence bundle
work record, and `AGENTS.md` record it as the pilot exception.

The design records (`docs/conversation-library.md`, "Model work requires
bounded approval"; `docs/decisions.md`, "Before model-powered enrichment")
require a preview of the frozen input set, provider and model, limits, and a
cost policy; approval of exactly that plan; and, before paid dispatch, durable
reservation, cancellation, bounded retries, and recovery that never silently
repeats an uncertain paid request. The pure approval validator in
`src/benchwarmer/model_work.py` exists; no execution service did.

Reviewing proposed bundles now happens in the web app, and the operator asked
to start the proposer from there too, choosing which conversations it runs
against, so that the review loop does not leave the browser.

## Decision

The application may start one harness workflow, `propose-bundles`, from an
explicitly approved plan. The flow is:

1. **Preview.** The operator chooses conversations and a model in the Bundles
   page. The API freezes a plan: workflow, each conversation with its current
   revision, provider and model id, thinking level, operator notes, and the
   input count as the only limit. The plan's sha256 digest is returned with
   it. Cost is shown as unknown; nothing is priced before the run reports its
   usage.
2. **Approve.** The operator approves by sending that digest back. A digest
   that does not match, or a plan that is no longer `proposed`, is refused.
   Approval of one plan never covers another; changing inputs or model means
   a new plan.
3. **Run.** The API launches the harness as one subprocess for the plan,
   through the same command an operator would type (`npm --prefix <harness>
   run propose-bundles -- ...`), passing the plan's run id so the run record
   and the plan link. Provider keys stay in the API process environment; they
   never pass through the browser or the database. Output goes to a log under
   the private data root.
4. **Observe.** The plan is `running`, then `finished` or `failed` by exit
   status. The operator can cancel, which terminates the process and records
   that work already sent may still be billed. A plan found `running` when the
   application starts is marked `interrupted` and is never rerun on its own.

Host-side configuration gates execution: without `BENCHWARMER_HARNESS_DIR`
the app previews plans but refuses to approve them, and the UI says how to
run the plan by hand instead.

Hand-run harness commands remain valid and are recorded the same way.

## Alternatives considered

- **Keep runs hand-only.** Simplest and already documented, but the review
  loop then requires a terminal beside the browser, and the operator asked
  for the launcher in the Bundles page.
- **Build the full bounded model-work service first** (durable budget
  reservation, bounded retries, exactly-once recovery), then expose it. That
  service has no pricing source yet for this harness, so a reservation would
  reserve an unknown number. The plan-digest approval, cancellation, and
  interrupted-not-rerun rule are implemented now; reservation and retries are
  deferred to the same work record.
- **An in-process job queue** rather than a subprocess. It would couple the
  API to the Node runtime and break the rule that the harness never opens the
  database. A subprocess keeps the harness boundary exactly as it is.

## Consequences

- `docs/conversation-library.md`, `docs/decisions.md`, the harness README, and
  `AGENTS.md` change from "nothing in the app starts a run" to "the app starts
  only an approved plan".
- A new table, `model_work_plans`, holds plans and their outcome; migration
  `0007`.
- The run record for an app-started run looks exactly like a hand-run one,
  so the Runs page needs no change.
- Budget reservation, retries, and outcome-unknown recovery remain open in the
  bounded model-work record; until then the input count is the only limit and
  the operator is told so in the preview.

## Unresolved questions

- Whether other workflows (judges, anonymizer) use the same plan shape or need
  per-workflow limits before they are offered from the UI.
- How the plan should carry a cost policy once a pricing source exists for
  the harness's catalog estimates.

## Verification

- `uv run pytest tests/api/test_model_work_api.py`: preview, digest-bound
  approval, run to completion through a fake harness package, failure by exit
  status, cancellation, refusal without a harness directory, and startup
  marking a running plan interrupted.
- On the pilot: preview a plan without approving it; approval was not
  exercised against a real provider in review.
