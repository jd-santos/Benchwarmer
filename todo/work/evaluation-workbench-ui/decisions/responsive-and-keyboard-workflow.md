# Define responsive transformations and the keyboard workflow

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocked by: [Shape long-conversation reading and navigation](long-conversation-navigation.md), [Design evidence selection and bundle assembly](evidence-selection-and-bundles.md), [Design test-plan authoring and applied-judge preview](test-plan-authoring.md), and [Design trial, judgment, and disagreement review](judgment-review.md)\
Blocks: [Place the accepted UI slices in the delivery sequence](implementation-sequence.md)

## Question

How should the accepted desktop workspaces transform for phone-sized screens,
touch, keyboard-heavy review, zoom, text scaling, and assistive technology while
preserving every consequential action and source relationship?

Prototype the cross-flow responsive rules rather than merely stacking columns.
Decide what becomes a drawer, sheet, focused route, or progressive disclosure;
how outline, transcript, selection, and annotation context remain recoverable;
which authoring interactions are deliberately desktop-optimized; and which
keyboard commands materially accelerate repeated review without hiding actions
from pointer, touch, or screen-reader users.

## Resolution

Decided with the user on 2026-10-15.

On a phone, the user can browse, read, annotate, triage suggestions, approve,
and monitor runs. Bundle editing, the task wizard, and the test-plan matrix are
optimized for desktop. Keyboard shortcuts cover j/k message navigation,
annotating, and accept/reject in triage. Every shortcut also has a visible
control. A rendered check at desktop and phone sizes happens during
implementation of each screen.
