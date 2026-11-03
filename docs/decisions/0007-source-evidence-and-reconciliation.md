# ADR 0007: Preserve source evidence before reconciling observations

- Status: Accepted
- Work: [Usage reconciliation](../../todo/work/usage-reconciliation/README.md)
  and [additional sources](../../todo/work/additional-sources/README.md)
- Date: 2026-11-02
- Scope: Consolidates existing evidence rules; does not authorize new imports,
  authenticated probes, model work, or automatic record merging.

## Context and evidence

The dated [source coverage matrix](../source-coverage.md) establishes that
harness sessions, protocol responses, provider generations, and account usage
have different identities and coverage. A shared timestamp, model name, token
count, or similar prompt does not prove two observations describe one request.
The [Hermes adapter decision](0004-first-import-adapter.md) already applies
source-scoped keys and reconciliation to one adapter. This record makes the
cross-source contract explicit without changing serialized schemas.

Source reports are evidence about particular versions and inspection dates,
not promises of current installed support. Local installation, successful
parsing, persistent import, collector delivery, and exact replay are distinct
capabilities. Later observations supersede an earlier absence finding only for
the capability actually checked.

## Decision

### Preserve native identity and observations

Namespace source-native keys by stable installation/profile scope. Preserve
native session, entry, thread, turn, protocol, and provider identifiers as
separate fields or source extensions with provenance; do not coerce them into
one universal request key. Source-specific semantics remain in the adapter
records and reports, not a permanently frozen list in this ADR.

Retain native snapshots and normalized revisions when source rows change.
Incremental watermarks are an optimization, not proof of completeness: each
adapter must define full-rescan recovery for rewrite, truncation, cursor loss,
mutable rows, and source replacement where applicable. Source disappearance is
not authority to delete retained Benchwarmer evidence.

### Reconcile without destroying evidence or inflating totals

Keep overlapping observations and attach explicit evidence links and an
inspectable reconciliation decision. Automatic joins require verified identifier
semantics and fixture evidence. Similarity-only matches are labeled candidates,
not merged facts. Unmatched records and coverage gaps remain visible.

Session totals, request details, and token subcategories can overlap. Record
scope and inclusion relationships before aggregation; never sum alternative
views of the same usage. Keep actual charges, calculated estimates, subscription
expense, quota, and current credit balance distinct. A balance snapshot is not
spend history. Historical estimates require timestamped pricing evidence;
a current model catalog cannot establish historical prices.

### Preserve unknowns and capture limits

Unknown, unavailable, unsupported, not applicable, and confirmed zero are
different states. Preserve source/schema version, observation time, origin, and
cost status rather than interpreting an absent field as zero or no capability.
Imported prompt text does not establish exact replay: tools, skills, files,
artifacts, approvals, environment, harness version, and routing may be missing.
Expose those gaps; require reviewed fixtures before claiming reproducibility.

Import remains read-only with respect to the source and never grants execution
or disclosure permission. Capture configuration only through an approved,
secret-safe interface. Routing-affinity fields are experimental configuration
when they affect provider selection or caching, not merely passive labels.

## Alternatives considered

- Merge by timestamp/model/content similarity: rejected because collisions and
  incomplete capture can erase distinct work and double-count charges.
- Normalize missing fields to zero: rejected because it invents evidence.
- Treat all reported costs as charges: rejected because harness estimates,
  provider charges, quotas, and subscriptions have different meanings.
- Rebuild execution settings from the current environment: rejected because
  current configuration does not establish historical execution conditions.

## Consequences

Adapters preserve more provenance and may leave records unmatched. Reports must
show uncertainty instead of manufacturing complete totals or replay guarantees.
This consolidates existing design, not a claim that cross-source reconciliation
or complete capture has been implemented. Any serialized-contract change still
requires explicit versioning and compatibility review.

## Verification

Executable acceptance tests belong to
[usage reconciliation](../../todo/work/usage-reconciliation/README.md),
[additional-source research](../../todo/work/additional-source-research/README.md),
and the source-specific adapter work records. They must cover false-positive
joins, overlapping scopes, unknown versus zero, changed source records, and
partial replay evidence using synthetic fixtures. Private account probes require
separate approval; neither this ADR nor documentation cleanup authorizes them.
