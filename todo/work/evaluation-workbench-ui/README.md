# Design the evidence-to-evaluation workbench UI

Status: Stopped on 2026-10-15 after the first decision. The user chose to proceed
to implementation instead of further Markdown prototypes. The remaining decision
records stay as reference questions for the implementing work records; they are
no longer a gate.

Current role: None claimed. Existing work records remain authoritative for
implementation.

## Destination

Produce a human-reviewable interaction specification, connected low-fidelity
wireframes, and a sequenced implementation map for the path from conversation
review through evidence bundles, task preparation, test planning, execution,
and judgment review.

The conversation review workbench establishes the interaction language. The
finished design must support rapid navigation through long conversations,
source-anchored review, and explicit progression from evidence to approved
experiments without hiding uncertainty, provenance, disclosure, or cost.

## Notes

This is a local Markdown adaptation of a Wayfinder decision map. Each linked
record asks one decision-sized question. Open, unclaimed records whose blockers
are resolved form the frontier. Claim a record before working it, resolve no
more than one non-research decision per session, and record its answer in that
record before checking it here. The map indexes resolutions with a one-line gist;
it does not duplicate their detail.

Use the grilling and domain-modeling workflows for conceptual decisions and the
UI-design workflow for every prototype. Prototype records should use realistic
long-form content, show important states, and link their assets from the decision
record. Preserve the product rules in the maintained architecture and evaluation
documents.

The following starting commitments were confirmed while charting the map:

- Cover the complete evidence-to-evaluation journey, while leaving source setup,
  deployment, and general usage reporting outside this design except where they
  affect the journey.
- Use a comment-like presentation for distinct typed annotations rather than
  collapsing notes, classifications, observations, judgments, and bundle
  membership into a generic comment record.
- Anchor whole blocks by default, with optional text ranges and noncontiguous
  selection. Preserve visible gaps and links back to the original conversation.
- Keep a global conversation library and optional evaluation projects. Manual
  review remains useful without first creating a project.
- Stage generated suggestions for human review. Never let generated work silently
  replace approved records or bypass bounded model-work approval.
- Promote evidence through explicit, reversible stages rather than one test
  creation wizard.
- Support browsing, annotation, review, approval, and run monitoring on phone-sized
  screens. Dense construction workflows may be desktop-optimized while remaining
  accessible on narrow screens.

## Dependencies and authority

This record coordinates interaction decisions across existing delivery slices;
it does not replace their implementation checklists:

- [Browse, search, and annotate conversations](../conversation-library/README.md)
  owns the first conversation-reading and human-review implementation.
- [Define evidence references and review conversation bundles](../evidence-bundles/README.md)
  owns evidence-reference and bundle implementation.
- [Turn selected evidence into runnable tasks](../task-preparation/README.md)
  owns task preparation and leakage safeguards.
- [Define judges, success measures, and test plans](../evaluation-planning/README.md)
  owns judge-definition and test-plan implementation planning.
- [Run, judge, and compare repeatable experiments](../judged-experiments/README.md)
  owns execution, applied judging, and trial comparison.

Real-data validation depends on reliable imports. Conceptual work and sanitized
prototypes may proceed before [Hermes import](../hermes-import/README.md) is
complete.

## Acceptance criteria

- The primary reading and review loop is clear for both long conversations and
  short exchanges, including branches, continuations, compactions, source gaps,
  long tool output, and preserved scroll position.
- Typed annotations, evidence bundles, task drafts and versions, test plans,
  applied judges, runs, trials, judgments, and human corrections have distinct
  visible meanings and transitions.
- Low-fidelity desktop and narrow-screen wireframes cover the complete journey,
  including empty, loading, partial, unknown, unavailable, read-only, pending,
  failed, unjudged, and disagreement states where relevant.
- Generated suggestions, disclosure permission, estimated cost, exact approval
  scope, execution progress, cancellation, recovery, and possible in-flight
  overrun are visible at the moment they matter.
- The implementation sequence assigns each accepted slice to one existing work
  record with dependencies and acceptance criteria, without creating competing
  checklists or empty routes.
- The user reviews the connected workflow and confirms that the design is ready
  to hand off for implementation.

## Decision frontier

The unresolved records below are not being worked as standalone prototypes.
Settle each question inside the work record that implements it, starting with
[Browse, search, and annotate conversations](../conversation-library/README.md).

- [x] [Shape long-conversation reading and navigation](decisions/long-conversation-navigation.md)
  - Type: Prototype, human in the loop
  - Blocked by: Nothing
- [ ] [Define the anchored annotation grammar](decisions/anchored-annotation-grammar.md)
  - Type: Grilling, human in the loop
  - Blocked by: Nothing
- [ ] [Define evaluation-project navigation and artifact relationships](decisions/project-navigation.md)
  - Type: Grilling, human in the loop
  - Blocked by: Nothing
- [ ] [Design evidence selection and bundle assembly](decisions/evidence-selection-and-bundles.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Shape long-conversation reading and navigation](decisions/long-conversation-navigation.md) and [Define the anchored annotation grammar](decisions/anchored-annotation-grammar.md)
- [ ] [Design generated-suggestion review and bulk triage](decisions/suggestion-review.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Define the anchored annotation grammar](decisions/anchored-annotation-grammar.md) and [Design evidence selection and bundle assembly](decisions/evidence-selection-and-bundles.md)
- [ ] [Design bundle-to-task promotion and readiness review](decisions/task-promotion.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Design evidence selection and bundle assembly](decisions/evidence-selection-and-bundles.md)
- [ ] [Design test-plan authoring and applied-judge preview](decisions/test-plan-authoring.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Define evaluation-project navigation and artifact relationships](decisions/project-navigation.md) and [Design bundle-to-task promotion and readiness review](decisions/task-promotion.md)
- [ ] [Design run monitoring, interruption, and recovery](decisions/run-monitoring.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Design test-plan authoring and applied-judge preview](decisions/test-plan-authoring.md)
- [ ] [Design trial, judgment, and disagreement review](decisions/judgment-review.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Design test-plan authoring and applied-judge preview](decisions/test-plan-authoring.md)
- [ ] [Define responsive transformations and the keyboard workflow](decisions/responsive-and-keyboard-workflow.md)
  - Type: Prototype, human in the loop
  - Blocked by: [Shape long-conversation reading and navigation](decisions/long-conversation-navigation.md), [Design evidence selection and bundle assembly](decisions/evidence-selection-and-bundles.md), [Design test-plan authoring and applied-judge preview](decisions/test-plan-authoring.md), and [Design trial, judgment, and disagreement review](decisions/judgment-review.md)
- [ ] [Place the accepted UI slices in the delivery sequence](decisions/implementation-sequence.md)
  - Type: Grilling, human in the loop
  - Blocked by: Every preceding decision

## Decisions so far

- [Shape long-conversation reading and navigation](decisions/long-conversation-navigation.md):
  The outline is hidden behind a left-drawer toggle. Suggested chapters appear
  inline with an edit control, and details open on demand rather than in a
  persistent drawer. Each branch remembers its own reading position.

## Not yet specified

- The project overview or dashboard hierarchy cannot be specified until project
  navigation, test-plan authoring, and run review reveal which state deserves
  emphasis.
- The visual language for patterns, taxonomy maintenance, and representative
  sampling depends on the reviewed bundle workflow and remains beyond the current
  frontier.
- Saved views, personal queues, activity history, and notification behavior need
  the core review loops before their exact questions can be stated.
- Configuration templates and reusable judge libraries may become necessary
  after the first test-plan prototype shows which repetition is real.
- Exact comparison charts and summary measures depend on the criterion-level
  review model; they must not collapse quality and economics into one score.

## Out of scope

- Production implementation, migrations, API contracts, or dispatching real and
  paid model work during this planning effort.
- Redesigning source enrollment, import administration, deployment, backup, or
  general usage and cost dashboards.
- Multi-user collaboration, real-time discussion, public sharing, and cloud
  synchronization. Comment-like annotations serve a private single-user app.
- Automatic routing, autonomous prompt or code repair, automatic memory
  rewriting, and always-running analysis agents.
- Final visual branding or a new component library before the interaction model
  is accepted.

## Verification

For each resolved prototype, inspect the rendered desktop and phone-sized states
with representative long content and exercise the actual interactions. At map
closeout, verify links and blockers, reconcile accepted decisions into the
authoritative work records, and run the repository's documentation checks if
available. No application test result is implied by this planning record.

## Supporting material

- [Current priorities](../../TODO.md)
- [Architecture and interface principles](../../../docs/architecture.md)
- [Conversation library and evaluation workflow](../../../docs/conversation-library.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
- [Task, harness, and comparison semantics](../../../docs/experiments.md)
- [Buildout roadmap](../../../docs/roadmap.md)
