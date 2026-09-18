# Deploy and verify the private application

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Serve the central application privately on the target host with verified supervision and access controls.

## Dependencies and order

Blocked on [the application foundation](../application-foundation/README.md). This is required for operational rollout, but does not block fixture development or local importer implementation.

## Acceptance criteria

All target-host checks in [ADR 0003](../../../docs/decisions/0003-serving-supervision.md) pass with sanitized verification evidence. A design or rendered configuration alone is not a deployment claim.

## Work

- [ ] Implement and validate private deployment
  - Dependencies:
    [Integrate the initial decision records](../../../docs/decisions.md)
    (already recorded),
    [Document development and final integration](../application-foundation/README.md)
  - Output: build the Svelte application into the image at
    `/opt/benchwarmer/ui`, set `BENCHWARMER_UI_ROOT` to that immutable path,
    implement the application container and declarative Tailscale Serve route,
    then record sanitized deployment verification in the same PR
  - Verify: render Compose, confirm no published app port, test
    authorized/unauthorized reachability, compare Alembic head, and exercise
    crash restart, operator stop, and unhealthy alert
  - Acceptance: all checks in ADR 0003 pass on the Mac mini before deployment is
    called operational

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
