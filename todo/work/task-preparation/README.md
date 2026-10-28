# Turn selected evidence into runnable tasks

Status: In progress on `task/task-partitions-guard`. The task version (cut
point, candidate/judge split, criteria, reconstruction level, leakage flags
and review, versioning), the case-record export, family-level partition
assignment, and the analysis-only approval guard are implemented with an
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
  export takes its term list from the request; Benchwarmer carries no
  program-specific terms. It refuses anything but an approved version and
  re-checks flags before writing.
- Benchwarmer writes the file. Upload, storage, and running belong to the
  consuming program; no adapter or route for an external store lives here.

Decided 2026-10-27 (partitions and the analysis-only guard):

- The partition lives on the task (`tasks.partition`,
  `tasks.partition_assignment_id`), not in the version document. Approved
  versions are immutable in content, so writing the partition into the
  document would have forced a new draft version for every assignment run and
  stripped the approval. Consequences: a task's partition can change without a
  new version; the export's `case.partition` comes from the task and the
  record's digest changes when the assignment does; `TaskDocument.partition`
  is a legacy read used only for a task that has never been assigned, and the
  editor no longer offers it as an input. `TASK_SCHEMA_VERSION` stays at 1:
  the field kept its type and meaning, it is only no longer authoritative.
- Assignment is `POST /api/v1/tasks/partitions` with a `seed`, a `split`
  (fractions of families; default development 0.6, calibration 0.2, holdout
  0.2, must sum to 1) and a `scope` (latest-version statuses; default `draft`
  and `approved`, so retired tasks keep what they had). Each family lands at
  `sha256(seed + "\n" + family)` scaled to [0, 1) against the cumulative split,
  so the same seed never moves a family and new families fill in without
  rebalancing the old ones; a new seed reshuffles everything. Every run is a
  row in `task_partition_assignments` (migration `0009`) with the seed, split,
  scope, time, family-to-partition map, and task and family counts; `GET
  /api/v1/tasks/partitions` returns the latest. The Tasks list shows the
  partition column and the assignment form with its result counts.
- Criteria gain an optional `needs` list (`workspace`, `tools`, `multi_turn`;
  default empty; additive, so no schema bump). A `coding` task needs a
  workspace whatever its criteria say. Reconstruction levels satisfy
  `prompt_only` → nothing, `fixture_backed` → workspace and tools,
  `fixed_multi_turn` → all three. Approving a version whose needs exceed its
  level fails with issue code `needs_exceed_reconstruction` (per criterion,
  or with no criterion id for the kind's own need). It is not a leakage flag
  and cannot be accepted away. No new status: the task stays `draft`, the API
  reports `unmet_needs` on the detail and `analysis_only` on the summary, and
  the editor and Tasks list mark it "Analysis only".

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
  - [x] Record analysis-only bundles when starting state is missing; do not silently convert them into runnable tasks. Retain correlated conversation and branch lineage.
    Criteria declare `needs`; a coding task needs a workspace. Approval of a
    version whose needs exceed `reconstruction.level` is refused with
    `needs_exceed_reconstruction` (`TaskDocument.unmet_needs`,
    `services.task_versions._approval_issues`). The task stays a draft,
    the detail carries `unmet_needs`, the summary `analysis_only`, and the
    editor shows the gap on the criterion, the reconstruction field, and the
    status control. Lineage stays on the family and bundle as before.
  - [ ] Fixture-backed reconstruction: attach a prepared workspace and tool
    definitions to a task version (`expected_scope` exists for coding tasks;
    nothing fills `candidate.tools` or `candidate.context` yet). The `needs`
    list now says which tasks are waiting on this.
  - [x] Assign partitions by family across tasks, with the frozen membership
    and seed recorded, instead of per task by hand.
    `services.task_partitions`, migration `0009`, `POST` and `GET
    /api/v1/tasks/partitions`, the partition column and "Assign partitions by
    family" form on the Tasks list, `case.partition` and
    `case.partition_assignment_id` in the export. Frozen-dataset membership
    (pinning which task versions a comparison used) is still the
    collections-and-datasets work; this records the assignment, not the
    dataset.
  - [ ] Model-assisted criterion drafting under bounded approval.

## Field notes

Fields added since the first slice, and where each lives:

| Field | Where | Meaning |
| --- | --- | --- |
| `criteria[].needs` | version document, optional, default `[]` | What the run must provide for the criterion to be checkable: `workspace`, `tools`, `multi_turn`. |
| `unmet_needs` | task detail response | Needs the version's reconstruction level cannot satisfy; `criterion_id` is null for a coding task's own workspace need. Non-empty means analysis-only. |
| `analysis_only` | task summary response | `unmet_needs` is non-empty for the latest version. |
| `partition` | `tasks` table, task detail and summary | Assigned by family; falls back to the document's legacy field only when `partition_assignment_id` is null. |
| `partition_assignment_id` | `tasks` table, detail, summary, `case` | The run that set the partition. |
| `task_partition_assignments` | table | One row per run: `seed`, `split`, `scope`, `families` (family → partition), `counts`, `task_count`, `family_count`, `producer`, `created_at`. |
| `case.partition`, `case.partition_assignment_id`, `case.criteria[].needs` | export | Mirror the above at export time; the digest changes when they do. |

## Verification

2026-10-27: `uv run pytest` 291 passed (new `tests/services/test_task_partitions.py`
covers determinism, proportion, and split validation; `tests/api/test_task_api.py`
adds family-level assignment with recorded runs, scope and split handling, the
export's assigned partition, and the approval guard's refusal; `tests/test_tasks.py`
adds the `needs` rules); ruff check and format clean; migration `0009` round-trips
in the migration tests. Web: `npm run check`, `npm run lint`, `npm run build`,
and 102 vitest tests pass, including the editor's guard messaging on the
criterion and status control, the coding-kind workspace need, the read-only
assigned partition, server-side `needs_exceed_reconstruction` placement, and the
Tasks page's partition column, analysis-only marker, latest-assignment line, and
assignment form with split validation and request body.

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
