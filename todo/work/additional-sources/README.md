# Add the other conversation sources

Status: In progress. Pi JSONL and ChatGPT account-export adapters have synthetic
validation. Pi read/normalize and two private temp imports passed; ChatGPT
actual-export validation and collector delivery are pending.

## Purpose

Bring Pi, Codex, Hermes, and available Claude Cowork history from the desktop
app into one library while testing that shared records preserve their different
source structures. Standard Claude chat is a desirable later source if
accessible. Claude is gradually unifying chat and Cowork in its UI, so source
research must identify the actual session type rather than rely on a mode label.

## Dependencies and order

The local Pi installation supplied version 3 session files, so Pi was selected
for the second read/import seam. The Hermes private-source gate and enrolled
collector remain open. The ChatGPT macOS cache was not selected as an interface;
an account export is the supported input. Codex and Claude work still depend on
[additional-source research](../additional-source-research/README.md).

## Acceptance criteria

Each added source adapter preserves the native evidence it can access, identity,
branches or continuations where present, and explicit capture gaps. Idempotent
updates and reconciliation pass source-specific tests without assuming import
implies execution support. Unavailable Claude Cowork fields or export
paths remain documented gaps rather than invented parity.

## Work

- [x] Add Pi v3 session and v1 run-log read/import seams
  - Files: `src/benchwarmer/adapters/pi/reader.py`, shared file-source
    persistence, and `tests/adapters/test_file_conversations.py`
  - Preserve the full parsed native content in private snapshots, v3 branch
    parents in normalized revisions, and usage with source-specific cost
    provenance. V1 records use `runId` plus calculated record ordinals and mark
    content coverage partial. Import one explicit file or directory at a time.
    File truncation or unsupported versions fail closed. No Pi process,
    credentials, or model call is involved. A mixed directory records native
    versions in the cursor and uses state schema `0` to mean mixed; each native
    session keeps its own schema version.

- [x] Add ChatGPT account-export read and import seam
  - Files: `src/benchwarmer/adapters/chatgpt/reader.py`, shared file-source
    persistence, synthetic ZIP fixture, and
    [source report](../../../docs/sources/chatgpt-macos.md)
  - Accept an explicit export ZIP or conversation JSON. Keep full native
    conversation snapshots and normalize supported text/branch fields. Unknown
    content remains private and marks coverage partial. The undocumented macOS
    cache is not an import interface.

- [ ] Complete ChatGPT export verification and broader source reconciliation
  - Compare only schema keys, bounded counts, coverage, and pass/fail in Git.
    Do not commit private content or machine-specific paths.
  - The local read/normalize pass accepted 207 Pi v3 sessions and 51 v1 run
    logs. One file from each layout passed a private temp database import, and
    the temp directory was removed automatically. Full directory persistence
    and source rewrite/deletion reconciliation are still pending.
  - Reconcile Pi file rewrite/truncation and ChatGPT missing/exported subjects
    without deleting retained evidence.

- [ ] Deliver configured source collection through the enrolled push topology
  - Coordinate with [cross-machine collection](../cross-machine-collection/README.md).
    No source adapter implies central collection is live.

- [ ] Add Codex conversation history
  - Gate: refresh source evidence and name exact adapter tasks before launch.

- [ ] Investigate and add Claude Cowork history where access is feasible
  - Dependencies: [Inspect Claude Desktop and Claude Code evidence](../additional-source-research/README.md)
  - Scope: preserve native content and available settings, usage, and cost with
    provenance; report inaccessible fields explicitly
  - Gate: verify the actual source interface before committing to an adapter

## Verification

Synthetic checks on this branch:

- `tests/adapters/test_file_conversations.py`: Pi tree, edited revision,
  repeat import, mixed-version directory import, ChatGPT ZIP branch import,
  unsupported Pi version, and ChatGPT cycle checks pass.
- Full `pytest`: 208 passed, one upstream Starlette/AnyIO warning, 52 subtests.
  The test process needs `UV_CACHE_DIR` under a writable temp directory because
  subprocess checks invoke `uv` and the default cache is outside this sandbox.
- `ruff check .`, `ruff format --check .`, `compileall`, and `git diff --check`
  pass.

No private Pi row or ChatGPT export was retained. The connector APIs accept
explicit source paths and source identities; collector configuration, source
delivery, reconciliation, and actual-export compatibility remain open.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Claude Cowork and chat are one Claude](https://support.claude.com/en/articles/16761823-claude-cowork-and-chat-are-one-claude)
