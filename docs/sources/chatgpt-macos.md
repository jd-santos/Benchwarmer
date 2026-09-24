# Source: ChatGPT macOS conversations

**Evidence date:** 2026-09-23. This report covers ChatGPT chat history accessed
through an account export. It does not describe Codex task history.

## Supported access

OpenAI documents a user-requested ZIP export that includes chat history. The
settings export is available to signed-in Free, Go, Plus, Pro, and eligible Edu
accounts. Business, Enterprise, and Healthcare workspaces do not have this
self-service export. An export may take up to seven days, and its download link
expires after 24 hours. The macOS app follows the web service's chat retention
policy. [Export documentation][export] and [macOS retention][retention].

This source adapter accepts an explicitly supplied export ZIP or a
`conversations.json` / numbered conversation JSON file from that export. It
does not request an export, authenticate to ChatGPT, or read the app cache. The
account export is a full observation, not a live change feed. A later export may
add or change conversations; missing entries are not treated as deletions.

## Local observation and format boundary

A metadata-only check on the current Mac found `conversations-v3-*/*.data`
files under the app support directory. A sample did not parse as JSON. Their
format and completeness are undocumented, so the adapter does not interpret
them. No cache content, account identifier, or conversation text was inspected.

OpenAI documents the ZIP export, but does not publish a stable schema for each
conversation JSON object in the cited export instructions. The parser supports
the `id`, `mapping`, node `parent`, `message`, text `content.parts`, and
`current_node` fields used by its synthetic fixture. It fails closed on missing identity, invalid parents,
cycles, or duplicate conversations. Unknown node content stays in the private
native snapshot, and normalized message coverage becomes partial.

Private validation against an actual export remains pending. Until then, the
synthetic fixture proves parser behavior, not compatibility with the user's
current export. Usage, cost, model, effective prompts, and attachment contents
are unknown from this parser. A temporary chat that was not saved does not
appear in normal chat history. [Data controls][controls].

[export]: https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data
[retention]: https://help.openai.com/en/articles/9268871-how-is-data-retained-in-the-macos-app
[controls]: https://help.openai.com/en/articles/7730893-data-controls-in-chatgpt
