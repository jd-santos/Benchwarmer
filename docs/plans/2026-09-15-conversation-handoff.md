# Conversation-library handoff

> Historical handoff, superseded on 2026-09-15. `LIB-001` and `ENR-001` were
> implemented in commit `d434703`; `COL-001` was resolved by
> [ADR 0005](../decisions/0005-cross-machine-collection.md). Use
> [the task ledger](../TODO.md) for current status.

## Resume here

The user requested a handoff to another model after fixing the delegation depth
setting and retrying the pending reviews. Stop before implementation in this
session. The earlier authorization to implement the first slice remains valid,
but the next coordinator must resolve the launch and worktree blockers below.

- Branch: `task/conversation-library`.
- Signed design commit: `4ed9a45` (`design: prioritize the conversation library`).
- No conversation-contract or model-work implementation exists yet.
- No reviewer has produced findings. All three review workflows failed before
  child startup; there are no resumable child sessions or running agents.
- No private source histories were read and no application inference was run.

Read in order:

1. [Conversation-library goals](../conversation-library.md).
2. [Executable first-slice plan](2026-09-15-conversation-contracts.md).
3. [Live task status](../TODO.md), especially `LIB-001`, `ENR-001`, and `COL-001`.
4. [Experiment semantics](../experiments.md), [decisions](../decisions.md), and
   [roadmap](../roadmap.md).

The architecture, README, and AGENTS instructions were reconciled with this
product direction in the signed design commit. This handoff does not add a new
architecture or authorize more scope.

## User intent and remaining decisions

The priority is a usable conversation library across Codex, Pi, and Hermes:
collect, normalize, enrich, discover, select, and evaluate. Preserve native
snapshots alongside normalized messages, tools, branches, and artifact references.
Usage and price-backed cost estimates are metadata; detailed reporting can wait.

Include short source summaries, richer generated descriptions, classification,
keyword/metadata and later semantic search, live saved queries, frozen datasets,
and private programmatic access for ad hoc projects such as software-only work.
Small classifiers and larger description/segmentation models should be selected
by task and measured utility, not hard-coded to a speculative model name.

The user is concerned about accidental model spend. Imports must not launch
inference. Explicitly approve bounded input/stage/request/resource/cost plans,
including embeddings and judging. Applied judges run automatically only inside
an approved rerun's scope and budget. Disclosure to remote providers needs its
own permission; no provider or numeric spend limit has been selected.

Start evaluations with meaningful single-response/action or short applicable
fixed-sequence units. Adaptive user follow-ups are intended later and must remain
distinct from exact replay. Avoid leaking original answers or later state.

`COL-001` is still a user planning step: histories are on multiple machines and
the collection service belongs in Benchwarmer. Clarify OS/device availability,
installation rights, offline behavior, freshness/backfill scale, push/pull/transfer,
enrollment, source access, secret exclusion, retention, and acknowledgments before
implementing transport. Do not assume all logs are on the Mac mini.

## Delegation: disk fixed, session still stale

The user explicitly approved changing only `maxSubagentDepth` from `0` to `1` in
`~/.pi/agent/extensions/subagent/config.json`. The edit is complete and JSON
validation passed. Existing session/run/concurrency caps and all other settings
were preserved. This is a local tooling change, not a Benchwarmer source change.

The installed depth guard blocks when `depth >= maxDepth`, so `0` prevents even
main-session delegation. `1` permits main-session children but blocks their
further delegation. The installed extension reads config once during
`registerSubagentExtension`; a retry after the file edit still reported
`depth=0, max=0` and failed before starting either reviewer.

Have the user run `/reload` in Pi before retrying. If the old value persists,
restart Pi and resume this branch. Merely switching model is not evidence that
extension configuration reloaded. Verify actual child startup rather than taking
an async workflow receipt as proof that its agents ran. Do not raise the limit
further, change internal depth variables, or retry in a loop.

## Repository and validation blockers

- Initial signing failed through 1Password; retry succeeded without disabling
  signing. Keep normal signed commits; no push has been performed.
- There is an uncommitted one-line removal of `[Root]: ./docs/` from `AGENTS.md`.
  Its origin is not established. This handoff leaves it untouched and outside
  the handoff commit. Inspect it before any clean-worktree requirement; do not
  silently revert, stash, or commit someone else's work.
- Managed implementation worktrees require a clean baseline. Reconcile that
  remaining change with the user before starting the planned isolated lanes.
- The pinned Python runtime is absent from this checkout. Baseline `uv run
  pytest`, `uv run ruff check .`, and `uv run ruff format --check .` could not
  start. No Python test pass or lint pass is claimed.
- Available `python3` reported Python 3.14.7. The first-slice plan permits
  `PYTHONPATH=src python3 -m unittest ...` only as supplemental verification for
  the new pure standard-library modules, not a substitute for the runtime/WAL
  gate or repository-wide checks. No new tests exist to run yet.
- Do not provision or repair Python/SQLite as part of either contract lane. Keep
  the missing-runtime blocker visible rather than returning to infrastructure
  work without a separate request.
- Documentation relative links and `git diff --check` passed during preparation.
  Those checks do not establish source-adapter or application functionality.

## Bounded continuation packets

### 1. Restore review launch

**Type:** Focused change `[context: small]`.

After reload/restart, list executable agents and retry the two read-only reviews
below in one async workflow with distinct keys. Use fresh context and inspect
startup status once because earlier workflows misleadingly settled successfully
while both children failed. Consume the actual results before implementation.

- Library reviewer: inspect `LIB-001` for source-scoped identity, preserved
  branch/continuation structure, tool-result linkage, metadata provenance,
  private-value-safe errors, and meaningful synthetic tests.
- Model-work reviewer: inspect `ENR-001` for immutable inputs, exact Decimal
  ceilings/canonicalization, digest coverage, stale approvals, and false claims
  of authentication, price validation, or durable spend reservation.

Both are read-only. Return at most five material findings each with file/section,
severity, and smallest correction. Neither should demand the deferred database,
network, UI, scheduler, or provider service as part of these pure contracts.
The parent reconciles findings into the existing plan before implementation.

### 2. Implement shared conversation contract

**Type:** Future-subagent packet `[context: medium]`.

Task `LIB-001`. Follow its exact interface, envelope, negative cases, and fixture
requirements in the first-slice plan. Own only `src/benchwarmer/conversations.py`,
`tests/test_conversations.py`, and `tests/fixtures/conversations/`. No dependencies,
private logs, database, network, execution, or changes to shared docs/task status.
Use synthetic normalized Pi/Hermes/Codex examples without claiming live-adapter
compatibility. Return patch, tests, validation blockers, and residual risks.

### 3. Implement bounded approval contract

**Type:** Future-subagent packet `[context: medium]`.

Task `ENR-001`. Own only `src/benchwarmer/model_work.py` and
`tests/test_model_work.py`. Implement the immutable priced-work plan and exact
approval seam from the first-slice plan. No provider calls, implicit inference,
scheduler, permission lookup, or durable-reservation claims. Return patch, tests,
validation blockers, and residual risks. This lane does not import `LIB-001`.

### 4. Integrate and validate

**Type:** Focused change `[context: medium]`.

One coordinator applies the disjoint patches, inspects real diffs, runs combined
checks, and obtains fresh implementation review. Use the plan's canonical commands
and honestly label supplemental checks or runtime blockers. Keep tasks In Progress
until their acceptance criteria pass. Update TODO status only as coordinator.

Do not execute future-subagent packets merely because this handoff lists them.
After the model switch, resume the approved first-slice workflow deliberately,
with the launch, review, and clean-worktree prerequisites satisfied.
