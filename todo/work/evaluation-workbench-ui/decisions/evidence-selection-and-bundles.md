# Design evidence selection and bundle assembly

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocked by: [Shape long-conversation reading and navigation](long-conversation-navigation.md) and [Define the anchored annotation grammar](anchored-annotation-grammar.md)\
Blocks: [Design generated-suggestion review and bulk triage](suggestion-review.md), [Design bundle-to-task promotion and readiness review](task-promotion.md), and [Define responsive transformations and the keyboard workflow](responsive-and-keyboard-workflow.md)

## Question

How should the user collect whole blocks, precise text ranges, and noncontiguous
evidence into a coherent bundle while remaining oriented in the original history?

Prototype creation, editing, comparison, and source expansion for bundles that
may cross distant points or explicitly related sessions. Show evidence roles,
visible gaps, branch compatibility, required context, missing evidence, objective,
selection rationale, origin, review status, and jump-to-source behavior. Decide
how overlapping bundles appear without duplicating or rewriting source evidence,
and how analysis-only or evaluation-unsuitable bundles remain useful rather than
being forced toward execution.

## Resolution

Decided with the user on 2026-10-15.

Select first, then bundle: the user selects messages or text ranges in the
transcript and creates or extends a bundle from that selection. Most bundle
assembly is expected to come from a scripted agent, so the bundle editing
interface (roles, ordering, gaps, rationale, jump-to-source) still matters.
Agent-proposed bundles are generated suggestions: they go through suggestion
review and run only under bounded model-work approval.
