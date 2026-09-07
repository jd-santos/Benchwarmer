# TODO

## In Progress

## Up Next

- [ ] Inspect source capabilities and choose the first import adapter
  - [ ] Inspect local Pi and Hermes versions, session formats and automation interfaces
  - [ ] Verify accessible Codex history, token summaries, quotas and prompt metadata
  - [ ] Verify OpenRouter usage, classification access, retention and request identifiers
  - [ ] Document coverage, overlaps, missing fields and reconciliation strategy
- [ ] Resolve the initial app boundaries in [decisions.md](decisions.md)
  - [ ] Choose Tailscale serving mechanism, process binding and access configuration
  - [ ] Choose private data root, retention and backup/restore approach
- [ ] Build the SQLite, Python and Svelte application foundation
  - [ ] Select backend/frontend tooling and worker lifecycle
  - [ ] Define versioned records and migrations using sanitized source fixtures
  - [ ] Establish private artifact storage and source provenance
  - [ ] Retain private session-content snapshots with normalized metadata
  - [ ] Serve the app privately over Tailscale from the Mac mini
  - [ ] Build responsive navigation, charts and review layouts for phone and desktop
  - [ ] Add pytest and Ruff with the first executable feature
- [ ] Deliver activity import, usage views and personal review
  - [ ] Implement idempotent incremental imports for the first source
  - [ ] Add usage charts, filters, session detail, ratings and notes
  - [ ] Preserve actual charges, estimates, quotas and classifier provenance
  - [ ] Add a second source and validate aggregation without double-counting
  - [ ] Show source freshness, coverage and reconciliation gaps

## Backlog

- [ ] Add the trusted external evaluation collection
  - [ ] Save links, dates, model/configuration details, notes and source revisions
  - [ ] Import structured results from selected sources where available and permitted
- [ ] Build task preparation from imported sessions
  - [ ] Select representative task families and define good-enough criteria
  - [ ] Separate starting context from original answers and later artifacts
  - [ ] Version reviewed tasks and record reconstruction limits and source links
- [ ] Implement harness-aware experiments
  - [ ] Choose initial execution harness and implement native configuration runs
  - [ ] Capture harness versions, system-prompt layers, tools, skills and visibility gaps
  - [ ] Add direct Python API execution as its own harness with explicit capabilities
  - [ ] Run model/configuration matrices in disposable workspaces where tools are used
  - [ ] Add budgets, cancellation, durable progress and recovery without duplicate paid work
  - [ ] Compare outputs, human criteria and economics while preserving every trial
- [ ] Add model views connecting activity, experiments and saved evidence
- [ ] Add controlled comparisons with explicit prompt overrides, aligned capabilities and recorded differences
- [ ] Promote useful simulations into repeatable evaluation suites
  - [ ] Add fixed multi-turn scripts and deterministic checks where useful
  - [ ] Assess model judges and calibrate against human review before adoption
- [ ] Add sanitized exports and portable comparison reports

## Done

- [x] Confirm Tailscale access, mobile-friendly UI, private session snapshots and native harness configurations first
- [x] Document the local app direction, usage aggregation, organic evaluations, harness dimensions and system-prompt provenance
