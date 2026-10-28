# Turn selected evidence into runnable tasks

Status: In progress on `task/task-versions`. The task version (cut point,
candidate/judge split, criteria, reconstruction level, leakage flags and
review, versioning) and the case-record export are implemented with an
editor in the web app. Fixture-backed reconstruction, frozen-dataset
membership, and model-assisted drafting are pending.

## Purpose

Prepare representative work from successes, failures, recoveries, and ambiguous outcomes for comparing configurations.

## Dependencies and order

Reviewed [evidence bundles](../evidence-bundles/README.md) are the input; the
first slice works from individual reviewed bundles without waiting for
[frozen datasets](../collections-and-datasets/README.md). Manual task drafting
does not depend on automated clustering; model-assisted drafting also needs
bounded execution.

## Decisions

Decided with the user on 2026-10-26, for the evaluation program this feeds
(a private case store and runners outside this repository):

- A task version pins one bundle revision and adds the test. The bundle keeps
  the evidence; the task keeps the cut point, criteria, reconstruction,
  family, partition, leakage review, and status.
- The cut point is the last event the candidate sees. The split is computed
  from the stored conversation path, never trusted from the document. Events
  the bundle cites in other conversations are always judge-only.
- Leakage flags are deterministic and carry stable ids: `answer_before_cut`,
  `criterion_quotes_answer` (an 8-word run shared with a historical assistant
  turn after the cut), `cut_after_assistant`, `judge_text_in_candidate` (a
  12-word run), and `no_historical_answer`. The leakage review lists accepted
  flag ids; approval requires every current flag accepted and the bundle
  revision `reviewed`.
- Criteria have a method (`human`, `llm_judge`, `deterministic`) and a
  `rubric_version`. Only a human criterion carries the reviewer's label; a
  deterministic criterion reads no judge evidence. The model judge stays a
  definition here; nothing in this repo runs it.
- Statuses are `draft`, `approved`, `retired`. An approved version's content
  is immutable: a content change must be saved as a new draft version.
  Retired is terminal. Runners fetch approved versions only.
- The export is a case record with `case`, `candidate`, and `judge` sections
  plus a digest, scrubbed in one pass so a term maps to the same placeholder in
  both sections. Reasoning blocks are dropped from the candidate section. The
  export takes its terms from the request, inline or by naming a stored
  [term list](../scrub-terms/README.md); Benchwarmer carries no
  program-specific terms. It refuses anything but an approved version and
  re-checks flags before writing.
- Benchwarmer writes the file. Upload, storage, and running belong to the
  consuming program; no adapter or route for an external store lives here.

## Acceptance criteria

A reviewed task version declares intent, starting context, capability and fixture needs, reconstruction gaps, and criterion-level assertions. Historical answers and later workspace state remain outside candidate inputs; correlated source lineage is retained.

## Work

- [ ] Prepare meaningful task units from frozen datasets
  - Dependencies: [Add projects, live collections and frozen datasets](../collections-and-datasets/README.md)
  - Scope: one-to-few-exchange units, sufficient context, segmentation provenance,
    correlated source lineage, reconstruction gaps and leakage checks

  - [x] Give candidate inputs and judge-only historical evidence distinct typed roles; validate that references cannot leak the original answer or later discoveries into a rerun.
    `benchwarmer.tasks` (document shape), `services.task_versions` (split,
    flags, versions), migration `0008`, `/api/v1/tasks`,
    `GET /api/v1/bundles/{id}/task-draft` for a proposed starting document.
  - [x] Derive reviewable assertions about acceptable behavior, rather than requiring the historical answer or incidental wording. Keep source evidence and criterion revisions attached.
    Criteria with method and rubric version; the quoting flag catches verbatim
    runs of the historical answer; the bundle revision stays pinned.
  - [x] Export an approved version as a case record with a redaction manifest
    and digest (`services.case_export`, `POST /api/v1/tasks/{id}/export`).
  - [x] Edit tasks in the web app: Tasks list, "Prepare as task" from a reviewed
    bundle, the two-column cut-point picker, criteria, leakage flags with
    per-flag acceptance, status, and export with download.
  - [ ] Record analysis-only bundles when starting state is missing; do not silently convert them into runnable tasks. Retain correlated conversation and branch lineage.
    Today `reconstruction.level` records the limit; nothing yet blocks
    approval of a `prompt_only` task whose criteria need a workspace.
  - [ ] Fixture-backed reconstruction: attach a prepared workspace and tool
    definitions to a task version (`expected_scope` exists for coding tasks;
    nothing fills `candidate.tools` or `candidate.context` yet).
  - [ ] Assign partitions by family across tasks, with the frozen membership
    and seed recorded, instead of per task by hand.
  - [ ] Model-assisted criterion drafting under bounded approval.

## Verification

2026-10-26: `uv run pytest` 282 passed (new `tests/test_tasks.py` and
`tests/api/test_task_api.py` cover the draft, flags, approval rules,
immutability and retirement, and the export's split, scrubbing, and
determinism); ruff check and format clean. Web: `npm run check`, `npm run
lint`, `npm run build`, and 98 vitest tests pass, including the task editor
(local cut move, approval gating on flags and reviewer, save body, create from
draft, criterion issue placement, export panel) and the Tasks page. A
Playwright pass against a disposable API with the demo library showed the task
editor, the Tasks list, the new-task page, and the bundle's "Prepare as task"
link at 400px and 1280px with no horizontal overflow and no page errors.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
