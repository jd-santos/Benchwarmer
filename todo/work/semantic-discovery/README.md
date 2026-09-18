# Add semantic search alongside text and filters

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Improve retrieval when text and metadata search cannot express the question well.

## Dependencies and order

Blocked on [conversation browsing](../conversation-library/README.md) and [bounded model execution](../bounded-model-work/README.md). Text search and manual datasets remain usable without embeddings.

## Acceptance criteria

Approved indexing and query actions return source-linked results and show stale, pending, unsupported, and incomplete coverage. Typing never silently launches a query embedding.

## Work

- [ ] Add semantic discovery alongside text/filter search
  - Dependencies: [Run approved model work with durable limits and recovery](../bounded-model-work/README.md), [Browse conversations and search their text and metadata](../conversation-library/README.md)
  - Scope: approved embeddings/query actions; message, description, tool and
    extracted artifact search; visible index coverage and source-passage links

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
