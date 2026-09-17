# Finish the application foundation

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Complete the fixture-backed path through SQLite, the Python API, and the responsive web application. This is the next executable work and unblocks the first importer.

## Dependencies and order

The existing source records, health boundary, runtime, shell, and API client are present. Follow the remaining sections of [the implementation plan](plan.md); completed sections are reference material.

## Acceptance criteria

A fresh checkout can migrate and seed disposable state, browse source status on desktop and mobile, and restart the API without losing records. All checks in the plan’s final integration gate pass.

## Work

- [ ] Add import-batch records and migration
  - Dependencies: Add source records and migration (already recorded)
  - Plan: [Implementation details](plan.md#add-import-batch-records-and-migration)
  - Verify: migration round-trip and focused model tests

- [ ] Verify the real database revision in health
  - Dependencies: Add truthful unmigrated API health (already recorded), [Add import-batch records and migration](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-the-real-database-revision-in-health)
  - Verify: health tests for unmigrated and migrated temporary databases

- [ ] Add sanitized source fixture loading
  - Dependencies: [Add import-batch records and migration](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#add-sanitized-source-fixture-loading)
  - Verify: deterministic, idempotent fixture-load command and focused tests

- [ ] Expose fixture-backed source status
  - Dependencies: [Verify the real database revision in health](../application-foundation/README.md), [Add sanitized source fixture loading](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#expose-fixture-backed-source-status)
  - Verify: service/API contract tests plus all Python checks

- [ ] Add the first useful home page
  - Dependencies: Build the responsive application shell (already recorded), Add the typed API client and `/api` proxy (already recorded)
  - Plan: [Implementation details](plan.md#add-the-first-useful-home-page)
  - Verify: loading/healthy/unmigrated/error UI tests and frontend checks

- [ ] Connect the source status page
  - Dependencies: [Expose fixture-backed source status](../application-foundation/README.md), [Add the first useful home page](../application-foundation/README.md), Add the typed API client and `/api` proxy (already recorded)
  - Plan: [Implementation details](plan.md#connect-the-source-status-page)
  - Verify: populated/empty/error UI tests, frontend checks, and Svelte MCP
    autofixer review where available

- [ ] Add the disposable browser process harness
  - Dependencies: [Expose fixture-backed source status](../application-foundation/README.md), [Connect the source status page](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#add-the-disposable-browser-process-harness)
  - Verify: Playwright starts, migrates, seeds, stops, and cleans up disposable
    processes/state

- [ ] Verify desktop and mobile browser flows
  - Dependencies: [Add the disposable browser process harness](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-desktop-and-mobile-browser-flows)
  - Verify: `npm --prefix web run test:e2e` at desktop and 375px viewports

- [ ] Verify API restart persistence
  - Dependencies: [Verify desktop and mobile browser flows](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#verify-api-restart-persistence)
  - Verify: migrated fixture records survive an API process restart; the
    stateless frontend does not own persistence

- [ ] Document development and final integration
  - Dependencies: [Verify API restart persistence](../application-foundation/README.md)
  - Plan: [Implementation details](plan.md#document-development-and-final-integration)
  - Output: `docs/development.md`
  - Acceptance: a fresh checkout can migrate disposable state, start both
    processes, and pass desktop/mobile/restart flows with no private or
    generated artifacts tracked

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Implementation plan](plan.md), including completed foundations as reference
