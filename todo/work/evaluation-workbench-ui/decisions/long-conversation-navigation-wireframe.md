# Long conversation navigation wireframe

Status: Draft for human review\
Decision: [Shape long-conversation reading and navigation](long-conversation-navigation.md)

## Interaction proposal

Keep the conversation itself as the main reading surface. A persistent table of
contents gives the reader a map through the captured structure, with optional
navigation aids clearly separated from the source. Selecting an outline item
moves the transcript to its source anchor; it does not replace the transcript
with a summary. The selected anchor and scroll position remain stable while the
reader opens notes, searches, or switches between related branches.

Captured structure is authoritative for message order, speaker, tool calls,
branch and continuation links, compaction boundaries, and known capture gaps.
Human headings and generated chapter suggestions are secondary navigation
labels. Each carries its origin; generated suggestions remain pending until a
person accepts or edits them. No generated text is quoted as if it were a
captured message.

## Desktop: reading a long conversation

```text
┌────────────────────────────────────────────────────────────────────────────────────┐
│ Conversations / Refund investigation · 184 turns · 3 branches      Find in chat  ⋯ │
├─────────────────────────┬────────────────────────────────────────────┬─────────────┤
│ CONTENTS                │ TRANSCRIPT                                 │ AT THIS SPOT│
│                         │                                            │             │
│ Overview                │ User · 10:42                               │ Anchor      │
│ ▾ Refund investigation  │ I need to return the second item, but…     │ Turn 48     │
│   1. Return policy      │                                            │ Branch A    │
│   2. Order lookup       │ Assistant · 10:43                          │             │
│   3. Item mismatch      │ I can help check that. Which item…          │ Selection   │
│   4. Refund options     │                                            │ 2 messages  │
│   5. Escalation         │ Tool · order_lookup · 2.1s                 │             │
│                         │   Order found; item names differ…          │ Evidence    │
│ Branches                │   [Expand output · 14 lines]                │ In 1 bundle │
│   Main path             │                                            │             │
│   ├─ A · refund check ◉ │ Assistant · 10:44                          │ Annotation  │
│   └─ B · replacement    │ The order shows two items…                 │ 1 note      │
│                         │                                            │             │
│ Captured events         │ ── Compacted context · source marker ──     │ [Open note]│
│   Compaction · turn 91  │                                            │ [Add note] │
│   Continued · turn 132  │ User · 11:18                               │             │
│   Gap · turns unknown   │ The first item was correct; the second…     │             │
│                         │                                            │             │
│ Suggested chapters · 2  │ [Jump to next match: “refund” · 3 of 8]    │             │
│   Review suggestions    │                                            │             │
│                         │                                            │             │
│                         │                    [← Prev] 48 / 184 [Next →]│             │
└─────────────────────────┴────────────────────────────────────────────┴─────────────┘
```

The left outline is scrollable independently from the transcript. Its hierarchy
is: conversation, captured branch/continuation paths, then optional chapters.
Captured structural events appear in their own small section rather than being
invented as messages or chapter titles. A gap is shown at its actual position
with the coverage state (for example, “content unavailable” or “turn count
unknown”). Long tool activity is collapsed to a readable summary of captured
metadata, with the original output one action away.

The right context panel follows the selected source anchor. It reports the
active branch, annotation, and existing evidence-bundle membership. It is
contextual, not a second conversation pane; closing it gives the transcript more
room. Selecting a different anchor updates the panel without changing the
outline's expansion state.

### Outline labels and provenance

```text
1. Return policy                    Captured heading
2. “Can this order be refunded?”    Suggested chapter · pending review
3. Escalation                       Human heading · edited Sep 24
```

Only captured structural facts are presented without an origin label. A human
can add, rename, reorder, or remove a heading without changing source content.
A model may suggest chapter boundaries and short labels, but those remain in a
review queue, visibly marked as suggestions. Accepting one adds a navigation
label; it does not create an annotation, evidence bundle, or task.

### Jumping and keeping your place

- Selecting a chapter, branch event, search result, annotation, or evidence link
  jumps to its source anchor and highlights the target briefly.
- The outline stays at its current scroll position and keeps the same branches
  expanded. The transcript's current anchor remains in view when the side panel
  opens or closes.
- Search results show message/turn anchors and branch identity. Moving to a hit
  does not filter source messages out of the transcript.
- Back/forward returns to the previous source anchor, branch, and transcript
  position, including after opening a linked annotation or bundle.
- On reload, restore the conversation, branch, source anchor, outline expansion,
  and transcript position. A changed conversation revision may require a
  visible “position moved” notice with a link to the closest surviving anchor.

## Phone: navigation before transcript

```text
┌────────────────────────────────┐
│ ‹ Conversations  Refund check ⋯ │
│ 184 turns · Branch A of 3       │
├────────────────────────────────┤
│ [Contents] [Search] [Notes · 4] │
├────────────────────────────────┤
│ Turn 48 of 184 · Refund options│
│ ◉ Branch A                      │
│                                │
│ User · 10:42                    │
│ I need to return the second     │
│ item, but the order page…       │
│                                │
│ Assistant · 10:43               │
│ I can help check that. Which…   │
│                                │
│ Tool · order_lookup · 2.1s     │
│ Order found; item names differ │
│ [Show 14 captured lines]        │
│                                │
│ [Select messages] [Add note]    │
├────────────────────────────────┤
│ [← Previous]       [Next →]    │
└────────────────────────────────┘
```

“Contents” opens a full-height outline sheet. Choosing an item closes the sheet,
returns to the transcript at that anchor, and announces the destination to
assistive technology. Search and notes use similarly focused sheets so the
transcript remains readable at phone width. Branch selection is always visible
near the current turn; switching branches asks before discarding an active
selection, and otherwise preserves the last reading position in each branch.

## Short conversation

For a short exchange, keep the same transcript and source anchors but omit the
empty contents rail. A compact “Contents” control can still appear when there
are branches, a continuation, annotations, search hits, or evidence links. The
interaction should not force a chapter hierarchy onto a five-message exchange.

## States this proposal needs to preserve

| Situation | Reading behavior |
|---|---|
| Loading | Keep the shell and current location; show transcript loading in place. |
| Partial capture | Mark the known coverage boundary and let the reader continue through available source. |
| Unknown turn count | Use next/previous and anchors without a fabricated total. |
| Missing source content | Show a gap marker and its known reason; do not render a placeholder as a message. |
| Branch unavailable | Keep its label and explain that its source is unavailable. |
| Read-only snapshot | Permit navigation and inspection; disable edits with a visible read-only reason. |
| No suggested chapters | Keep captured structure and human headings; do not imply analysis ran. |
| Suggestion pending/failed | Show review status or failure where suggestions live; never replace source headings. |
| Search with no hits | Keep the transcript position and show “No matches in this conversation.” |
| Anchor removed by revision | Offer nearest surviving source location and explain the changed revision. |

## Questions for review

1. Does the persistent left table of contents plus central transcript match how
   you want to move through a long history, or should the outline be a
   show/hide overlay by default?
2. Should suggested chapters appear inline in the outline as above, or in a
   separate review-only area until accepted?
3. Is the contextual right panel useful while reading, or should annotations
   and evidence membership stay in a separate inspector opened on demand?
4. When switching branches, should each branch remember its own last position?

This prototype remains open until the reading model is reviewed and the selected
defaults are recorded in the decision file.
