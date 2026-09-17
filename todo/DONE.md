# Done

Use `git log` for development history and `git log --all -- docs/TODO.md todo/`
for task-tracking changes. There is no separate completed-task ledger.

The legacy queue, including its checked entries and completion notes, is
recoverable with `git show 832c5bb4fdcacc73bf970ded0de56286bf6259c2:docs/TODO.md`. Its content matched HEAD
before migration. This is a migration baseline, not a release reference.

Retained evidence:

- [Conversation and approval contracts](work/conversation-contracts/README.md)
- [Workbench migration](work/task-workbench/README.md)
- [Accepted decisions](../docs/decisions/README.md)
- [Source inspection reports](../docs/sources/README.md)

No changelog or verified release/merged-PR references were established during
this migration. Add links when they exist; do not infer delivery from checkboxes.
