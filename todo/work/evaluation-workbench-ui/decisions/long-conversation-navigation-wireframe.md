# Long conversation navigation wireframe

Status: Reviewed; defaults recorded in the decision\
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

The contents outline is closed by default. The `▤` drawer icon at the far left
of the header opens and closes it.

```text
Outline closed (default)
┌────────────────────────────────────────────────────────────────────────────────────┐
│ ▤  Conversations / Refund investigation · 184 turns · 3 branches   Find in chat  ⋯ │
├────────────────────────────────────────────────────────────────────────────────────┤
│                 User · 10:42                                                       │
│                 I need to return the second item, but…                             │
│                                                                                    │
│                 Assistant · 10:43                                                  │
│                 I can help check that. Which item…                    ◆ 1 note     │
│                                                                       ▣ 1 bundle   │
│                 Tool · order_lookup · 2.1s                                         │
│                   Order found; item names differ…                                  │
│                   [Expand output · 14 lines]                                       │
│                                                                                    │
│                 ── Compacted context · source marker ──                            │
│                                                                                    │
│                 User · 11:18                                                       │
│                 The first item was correct; the second…                            │
│                                                                                    │
│                 [Jump to next match: “refund” · 3 of 8]                            │
│                                                  [← Prev] 48 / 184 [Next →]        │
└────────────────────────────────────────────────────────────────────────────────────┘

Outline open, with a note opened from its marker
┌────────────────────────────────────────────────────────────────────────────────────┐
│ ▤  Conversations / Refund investigation · 184 turns · 3 branches   Find in chat  ⋯ │
├─────────────────────────┬──────────────────────────────────────────────────────────┤
│ CONTENTS          [Edit]│ User · 10:42                                             │
│                         │ I need to return the second item, but…                   │
│ Overview                │                                                          │
│ ▾ Refund investigation  │ Assistant · 10:43                                        │
│   1. Return policy      │ I can help check that. Which item…   ◆ 1 note ┌──────────┴──┐
│   2. Order lookup ·sugg.│                                      ▣ 1 bundle│ Note · Turn 48│
│   3. Item mismatch      │ Tool · order_lookup · 2.1s                     │ Branch A      │
│   4. Refund options     │   Order found; item names differ…              │ “Lookup used  │
│   5. Escalation         │   [Expand output · 14 lines]                   │  wrong SKU”   │
│                         │                                                │ [Open] [Edit] │
│ Branches                │ ── Compacted context · source marker ──        └──────────┬──┘
│   Main path             │                                                          │
│   ├─ A · refund check ◉ │ User · 11:18                                             │
│   └─ B · replacement    │ The first item was correct; the second…                  │
│                         │                                                          │
│ Captured events         │                                                          │
│   Compaction · turn 91  │                                                          │
│   Continued · turn 132  │                                                          │
│   Gap · turns unknown   │                                                          │
│                         │                          [← Prev] 48 / 184 [Next →]      │
└─────────────────────────┴──────────────────────────────────────────────────────────┘
```

When open, the outline scrolls independently from the transcript. Its hierarchy
is: conversation, captured branch/continuation paths, then optional chapters.
Captured structural events appear in their own small section rather than being
invented as messages or chapter titles. A gap is shown at its actual position
with the coverage state (for example, “content unavailable” or “turn count
unknown”). Long tool activity is collapsed to a readable summary of captured
metadata, with the original output one action away.

There is no persistent context drawer. Messages with annotations or evidence
membership carry small markers. Activating a marker opens a floating element
anchored to that message, or a separate panel for longer work. Closing it
returns focus to the marker and leaves the transcript where it was. The exact
inspector form belongs to the annotation grammar and evidence selection
prototypes.

### Outline labels and provenance

```text
1. Return policy                    Captured heading
2. “Can this order be refunded?”    Suggested chapter · pending review
3. Escalation                       Human heading · edited Sep 24
```

Only captured structural facts are presented without an origin label. A human
can add, rename, reorder, or remove a heading without changing source content.
A model may suggest chapter boundaries and short labels. They appear inline in
the outline, visibly marked as pending suggestions, and the outline's Edit
control gives quick access to accepting, renaming, or removing them. Accepting one adds a navigation
label; it does not create an annotation, evidence bundle, or task.

### Jumping and keeping your place

- Selecting a chapter, branch event, search result, annotation, or evidence link
  jumps to its source anchor and highlights the target briefly.
- The outline stays at its current scroll position and keeps the same branches
  expanded. The transcript's current anchor remains in view when the outline or
  an inspector opens or closes.
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
If per-branch positions prove complex or unidiomatic to implement, fall back to
one position per conversation and record why.

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

## Review outcome

The user answered the review questions; see the
[decision record](long-conversation-navigation.md#resolution) for the recorded
defaults.
