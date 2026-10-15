# Define the anchored annotation grammar

Type: Grilling, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocks: [Design evidence selection and bundle assembly](evidence-selection-and-bundles.md) and [Design generated-suggestion review and bulk triage](suggestion-review.md)

## Question

What domain grammar and lifecycle should sit beneath the comment-like annotation
rail?

Define the canonical distinctions among a human note, semantic classification,
evidence-supported observation, judgment, correction, and evidence-bundle
membership. Decide what each can anchor to, whether it can span noncontiguous
evidence, which provenance and uncertainty it exposes, how revisions and
supersession work, which review states are shared or type-specific, and whether
any item needs replies rather than revision history. Preserve imported,
calculated, generated, and human origins without turning a convenient visual
metaphor into an undifferentiated record.

## Resolution

Decided with the user on 2026-10-15.

- **One shared record shape.** Every annotation is a typed record (note, label,
  rating, observation, judgment, correction, bundle membership) with shared
  anchor, origin, review-state, and revision fields, plus type-specific fields.
  The interface shows them in one comment-like list that can be filtered by type.
  The type is required, so the visual metaphor never becomes an untyped comment.
- **Judgment scale.** Every judge or grader returns judgments from 0 to 1 in
  0.1 increments, per criterion. A missing judgment stays unjudged (no value),
  never 0. Criterion scores are not combined with each other or with economics
  into a single winner score. Human ratings use the same 0 to 1 scale in 0.1
  steps, so human and judge scores can be compared directly for calibration.
- **Revisions, not replies.** Editing creates a new revision and keeps earlier
  revisions viewable. There are no reply threads. Generated suggestions do not
  supersede anything until a person accepts them.
- **Anchors.** An annotation attaches to a whole message or block, or to a text
  range inside one message. Noncontiguous evidence is collected through
  evidence bundles rather than multi-anchor annotations.
