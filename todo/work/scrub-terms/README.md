# Store scrub term lists and document the redaction layer

Status: In progress on `task/scrub-term-lists`. Named, versioned term lists,
export by list reference, the redaction reference, and the web management
page are implemented. A first operator list and a pipeline run that exports
by reference have not happened.

## Purpose

The case-record export scrubs with the built-in detector kinds plus a term
list sent in the request, so Benchwarmer carries no program-specific words in
code. A pipeline that exports many cases should not resend the same list each
time, and an operator should be able to see which list version a record was
scrubbed with. This work stores lists as operator data, lets an export name
one, and writes down what the scrubber does and does not catch.

## Dependencies and order

Builds on the case export from
[task preparation](../task-preparation/README.md) and the scrubber from the
[fixture anonymizer](../fixture-anonymizer/README.md). A concurrent change
adds a pull route for exports and a registry around the built-in detector
kinds; this record keeps its `anonymize.py` changes additive and its task
route changes to the export request model.

## Decisions

- One table, `scrub_term_lists`, keyed by `(name, version)`. Versions are
  immutable; a save whose terms or notes differ from the latest version
  creates the next version, and an unchanged save returns the latest without
  writing. Names are 1 to 64 letters, digits, dots, dashes, or underscores.
- Terms are operator data. The list route and the record carry counts, never
  words; only `GET /api/v1/scrub-terms/{name}` returns terms. Validation
  messages count terms and never quote them.
- Retiring marks every version of a name. A retired list is hidden from the
  default listing and refuses new saves, but an export that pins
  `{name, version}` still resolves, so an old record can be reproduced.
- The export request takes `term_list: {name, version?}` alongside or
  instead of inline `terms`; both combine and are deduplicated
  case-insensitively. The scrubber's `MAX_TERMS` (200) caps a stored list and
  the combination; an export over the cap is refused with `too_many_terms`.
- `case.redaction.term_list` records the list name and resolved version, or
  `null`. It is an additive, optional field; `schema_version` stays 1 because
  no field changed meaning. Records written before this change exist without
  the key, and their digests differ from a re-export only because of it.
- Terms stay out of the scrubbed text's provenance: the record names the
  list, never its contents, and nothing logs a term.

## Acceptance criteria

- Saving a changed list creates the next version; the previous version is
  still readable by number and unchanged.
- The list route, retire response, and every error response carry no term.
- Exporting with `term_list` scrubs the same spans as the equivalent inline
  export, names the list and version under `case.redaction`, and repeats
  byte-for-byte for the same task version, list version, and inline terms.
- An export that names a missing list or exceeds the cap is refused with a
  typed issue, never a partial record.
- The export panel offers stored lists with their version and term count and
  keeps the inline field; a page lists, shows, saves, and retires lists.
- `docs/redaction.md` covers every detector kind, the one-pass rule, the
  manifest, `scrub_version`, the leak check, the term cap, and the gaps, with
  no company, customer, or product names.

## Work checklist

- [x] Migration `0009_scrub_term_lists` and the `ScrubTermList` model.
- [x] `services/scrub_terms.py`: list, get, save (next version), retire,
  `normalize_terms` under `MAX_TERMS`.
- [x] Routes `GET/PUT /api/v1/scrub-terms/{name}`, `GET /api/v1/scrub-terms`,
  `POST /api/v1/scrub-terms/{name}/retire`.
- [x] Export request accepts `term_list`; `case_export.resolve_terms` combines
  and caps; the record carries `redaction.term_list`.
- [x] `docs/redaction.md`, linked from the AGENTS.md index and the evidence
  bundles design.
- [x] Web: term list picker in the export panel; `/scrub-terms` page to list,
  show, save, and retire lists; navigation link.
- [ ] First operator list saved on the private host and one export by
  reference compared by digest against the inline export.
- [ ] Decide whether the fixture anonymizer's harness command should accept a
  list name in place of `--terms-file`.

## Verification

2026-10-27: `uv run pytest` 285 passed, 1 skipped (new
`tests/api/test_scrub_terms_api.py` covers versioning, retirement, validation
without echo, and term-free summaries; `tests/api/test_task_api.py` gains the
export-by-list case with pinning, combination, retirement, and the two
refusals); `uv run ruff check .` and `uv run ruff format --check .` clean.
Web: `npm run check`, `npm run lint`, and `npm run build` clean; 109 vitest
tests pass (new `TermListManager`, scrub-terms page, and client tests; the
editor's export tests cover the picker and the pinned list reference). A
Playwright pass against a disposable API with the demo library showed the
Scrub terms page (list, open, editor) and the export panel with a stored list
at 400px and 1280px with no horizontal overflow and no page errors, and two
exports with the same list version and inline term produced the same digest.
The repository's `tests/foundation.spec.ts` e2e suite fails on `main` before
this change (it expects a `System overview` heading and revision `0002` that
no longer exist) and was not changed here.

## Supporting material

- [Redaction reference](../../../docs/redaction.md)
- [Task preparation work record](../task-preparation/README.md)
- [Fixture anonymizer work record](../fixture-anonymizer/README.md)
- [Evidence bundles design](../../../docs/evidence-bundles.md)
