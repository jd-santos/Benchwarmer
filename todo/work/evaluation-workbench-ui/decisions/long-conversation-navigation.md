# Shape long-conversation reading and navigation

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocks: [Design evidence selection and bundle assembly](evidence-selection-and-bundles.md) and [Define responsive transformations and the keyboard workflow](responsive-and-keyboard-workflow.md)

## Question

What reading model lets the user scan and move through a very long conversation,
understand their current location, focus a passage, annotate or collect it, and
continue without losing position?

Prototype the conversation table of contents and transcript together. Decide
which outline levels come from captured structure and which may be human- or
model-authored; how branches, continuations, compactions, configuration changes,
search hits, annotations, bundles, long tool activity, and coverage gaps appear;
how the user moves between outline and source; and which reading state persists
across filtering, selection, navigation, and reload. Test a routine short exchange
and a realistically long, branch-bearing conversation on desktop and phone-sized
screens without treating generated summaries as source facts.

## Prototype draft

See [Long conversation navigation wireframe](long-conversation-navigation-wireframe.md).

## Resolution

The user reviewed the wireframe and chose these defaults:

1. **Contents outline:** Hidden by default and toggled with a dedicated
   left-drawer icon that both opens and closes it. The transcript keeps its
   anchor when the outline opens or closes.
2. **Suggested chapters:** Shown inline in the outline with their pending
   origin label, plus an easy-to-reach edit control for accepting, renaming, or
   removing them. They still never replace captured structure.
3. **Context for the current anchor:** No persistent right drawer. Annotation,
   branch, and bundle details open on demand in a separate panel or as floating
   elements attached to the message. The exact form is left to the
   [annotation grammar](anchored-annotation-grammar.md) and
   [evidence selection](evidence-selection-and-bundles.md) prototypes.
4. **Branch position:** Each branch remembers its own last reading position,
   unless implementing it would add significant complexity or require
   unidiomatic code. In that case, fall back to one remembered position per
   conversation and record the reason.

The remaining wireframe behavior (captured-structure authority, gap markers,
jump and back/forward behavior, reload restoration, phone sheets, the short
conversation layout, and the states table) is accepted as drafted.

No rendered prototype has been checked at desktop and phone sizes yet. That
check moves to the
[responsive and keyboard workflow](responsive-and-keyboard-workflow.md) record.
