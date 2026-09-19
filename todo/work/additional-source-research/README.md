# Verify additional conversation sources

Status: Planned. Official-source search and full-page retrieval must succeed before this record becomes accepted evidence.

## Purpose

Determine what conversation, usage, cost, quota, prompt, tool, artifact, identity, lineage, export, and retention data is actually available to this user from Codex, Claude Desktop and Claude Code, and OpenRouter. Use that evidence to choose later adapters and decide whether normalized conversation schema version 1 needs a versioned successor.

## Dependencies and order

This research can proceed after search and fetch tooling is available. It does not block the Hermes schema-30 reader. Complete it before selecting the next source adapter or promoting source-specific fields into a shared schema.

Authenticated read-only probes require separate approval and must follow successful documentation research. No probe may read or print credentials, private conversation content, account identifiers, or raw provider responses.

## Acceptance criteria

Current official pages are fetched and cited directly. The resulting source reports distinguish:

- supported interfaces from undocumented local formats;
- individual access from organization-admin access;
- subscription or application usage from API billing;
- conversation content from aggregate usage and quota state;
- imported, estimated, calculated, and actual cost observations;
- source-native, protocol, provider, and account identifiers;
- incremental cursors from overlapping-window or full-rescan strategies;
- retention, deletion, archive, and unavailable semantics; and
- verified behavior from claims that still need an authenticated probe.

The source-coverage matrix is updated with explicit unknowns. Any shared-schema proposal identifies migration and compatibility consequences rather than changing version 1 in place.

## Work

- [ ] Refresh official Codex evidence
  - Scope: Codex CLI and app-server, Codex desktop/web or ChatGPT export surfaces, ChatGPT-plan usage, and OpenAI API usage/cost endpoints
  - Verify: current full official pages, installed-version boundaries, individual versus administrator access, and a documented list of probe-only unknowns

- [ ] Inspect Claude Desktop and Claude Code evidence
  - Scope: supported exports, documented local session storage, Claude Code structured output and monitoring, consumer retention, and Anthropic API/admin usage surfaces
  - Verify: distinguish consumer, Pro/Max, API, Team, and Enterprise availability without inferring access from organization-only documentation

- [ ] Refresh OpenRouter evidence
  - Scope: generation metadata, actual request cost, activity and analytics windows, credits and key limits, management-key boundaries, logging, exports, and retention
  - Verify: distinguish ordinary API keys from management keys and known-ID enrichment from complete historical coverage

- [ ] Compare source evidence with normalized conversation version 1
  - Output: identify safely common fields, source-extension fields, provider-link opportunities, incompatible semantics, and explicit unknowns
  - Gate: preserve version 1 unless a separately reviewed versioned schema proposal is justified

- [ ] Plan bounded authenticated read-only probes
  - Scope: exact endpoint or export, account authority, returned field names, retention of results, redaction boundary, and stop conditions for each provider
  - Gate: obtain explicit approval before running any probe; never place credentials or private payloads in Git or ordinary logs

## Verification

The prior research attempt produced provisional notes but could not fetch and verify full official pages because its search providers were unavailable. Do not treat those notes as project evidence or copy their claims into maintained source reports without successful retrieval.

Before completion:

- every consequential claim links to a fetched primary source;
- publication or retrieval dates and version boundaries are recorded;
- contradictory documentation and unknown account population remain visible;
- no private values or machine-specific paths appear in committed files; and
- Markdown and repository link checks pass.

## Supporting material

- [Current priorities](../../TODO.md)
- [Source coverage matrix](../../../docs/source-coverage.md)
- [Existing source reports](../../../docs/sources/README.md)
- [Conversation contract](../conversation-contracts/design.md)
- [Hermes implementation plan](../hermes-import/plan.md)
- [Additional adapters](../additional-sources/README.md)
