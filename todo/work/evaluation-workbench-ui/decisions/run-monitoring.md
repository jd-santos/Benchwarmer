# Design run monitoring, interruption, and recovery

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocked by: [Design test-plan authoring and applied-judge preview](test-plan-authoring.md)

## Question

What run view lets the user follow approved candidate and judge work, understand
what is pending or consuming budget, intervene safely, and recover after browser,
worker, provider, or machine interruption?

Prototype queued, reserved, running, retrying, cancel-requested, canceled,
completed, failed, outcome-unknown, budget-exhausted, and unjudged states. Decide
how plan scope, progress, actual and estimated usage, possible in-flight overrun,
worker recovery, duplicate-paid-work protection, unsupported configurations, and
safe next actions appear without requiring the browser to remain open.

## Resolution

Decided with the user on 2026-10-15.

A run page shows counts per state, spend against budget, and per-trial status
with safe actions such as cancel and retry. It reads from server state, so the
browser does not need to stay open.
