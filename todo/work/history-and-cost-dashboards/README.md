# Build history, usage, and cost dashboards

Status: Planned. Implementation and delivery are pending.

## Purpose

Make Benchwarmer a useful daily view of work across agent tools before building
model-suggested groups or judged experiments. The single user should be able to
find a conversation, understand the work around it, and see how activity, token
use, and cost change over time.

## Dependencies and order

Follow [conversation browsing and human review](../conversation-library/README.md)
and the first real [Hermes import](../hermes-import/README.md). One source is
enough to begin. Add source comparisons as Pi, Codex, and feasible Claude Cowork
history become available. This slice precedes suggested-group approval
and judge architecture in the product sequence. It does not depend on model work.

Detailed cross-source reconciliation and economics remain in
[usage reconciliation](../usage-reconciliation/README.md). A dashboard can show
known per-source observations before that work, but cannot sum overlapping
provider and harness observations or present estimates as charges.

## Acceptance criteria

The app provides a coherent path from activity and cost summaries to filtered
conversation lists and source evidence. Basic time-series charts show activity,
available token categories, and cost observations over selectable periods.
Filters cover at least date, source, model, and available project or task tags;
views explain missing coverage and distinguish actual charges, price-based
estimates, subscription expense, and quota usage. Charts and tables work on
desktop and phone-sized screens, and unknown values are not displayed as zero.
No import, filter, or dashboard visit triggers model work.

## Work

- [ ] Define the first navigation and reporting questions from real imported
  history; use them to shape the overview, list, and detail views.
- [ ] Expose source freshness, capture gaps, available usage categories, pricing
  provenance, and reporting time zone through the API and UI.
- [ ] Add activity, token, and cost time series with drilldown to the underlying
  conversations or usage observations. Choose Chart.js or D3 after the chart
  interactions and accessibility needs are concrete.
- [ ] Add filters and comparisons across available source, model, harness, and
  configuration fields without implying unavailable settings are equal.
- [ ] Show partial, unknown, unavailable, and overlapping data explicitly. Defer
  aggregate totals that require reconciliation.
- [ ] Verify the reading path, charts, table alternatives, filters, and empty or
  partial states on desktop and narrow screens.

## Verification

Before implementation, name the data source and exact dashboard questions for
the first slice. Use sanitized fixtures for layout and source-specific coverage
cases, then verify against an authorized real import. Record actual checks here.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation library design](../../../docs/conversation-library.md)
- [Usage reconciliation](../usage-reconciliation/README.md)
- [Source coverage](../../../docs/source-coverage.md)
