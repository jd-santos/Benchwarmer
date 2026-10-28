# Redaction

The redaction layer is `benchwarmer.anonymize`: a deterministic, regex-based
scrubber that replaces private-looking spans in text with stable placeholders.
It runs no model work and stores nothing. Two features use it:

- the **case-record export** (`POST /api/v1/tasks/{id}/export`), which scrubs
  the `candidate` and `judge` sections of an approved task version before a
  consuming evaluation program receives them;
- the **fixture anonymizer** (`POST /api/v1/fixtures/scrub-pi-session` and
  `/fixtures/check`), which scrubs a raw session in memory before a separately
  approved model rewrite turns it into a synthetic fixture.

Benchwarmer carries no program-specific words in code. Everything the
detectors cannot know (people, customers, hosts, project codenames) comes from
the operator as **terms**, either inline with a request or from a named,
versioned term list saved in the app.

## Detector kinds

Each kind has a regular expression, a priority used when spans overlap, and a
placeholder format. Placeholders are numbered per kind in order of first
appearance within one scrub pass.

| Kind | Matches | Placeholder |
| --- | --- | --- |
| `term` | An operator term as a whole word, case-insensitively. Longer terms win over shorter ones that start at the same place. `ACME` and `acme` share one placeholder; `acmeware` is left alone. | `<term-N>` |
| `email` | `local@domain.tld` with a two-letter or longer top-level label. | `<email-N>` |
| `url` | `scheme://` followed by everything up to whitespace, a quote, or a closing bracket. The whole URL is one span, so its host and path are not counted again. | `<url-N>` |
| `path` | A POSIX path with at least two segments: `/a/b`, `/a/b/c.py`, `~/notes/todo.md`. A trailing slash is kept inside the span. | `/scrubbed/path-N/file-N.ext`, keeping the original file extension when there is one |
| `ipv6` | Full and compressed IPv6 addresses, including `::`. | `<ipv6-N>` |
| `ipv4` | A dotted quad whose octets are 0 to 255, not followed by a further `.digit`. | `<ipv4-N>` |
| `secret` | Prefixed credentials (`sk-`, `sk_live_`/`sk_test_`, `gh[pousr]_`, `github_pat_`, `AKIA…`, `xox[abprs]-`, `AIza…`, and three-part `eyJ…` JWTs); hexadecimal runs of 32 or more characters; base64-looking runs of 40 or more characters that mix lower case, upper case, and digits. | `<secret-N>` |
| `hostname` | Dotted labels ending in a known suffix (`com`, `net`, `org`, `io`, `dev`, `ai`, `app`, `cloud`, `co`, two-letter country codes in the list, `local`, `lan`, `internal`, `localhost`, `test`, `example`, `home`, `corp`, and a few more), or the bare word `localhost`. | `<hostname-N>` |

When spans overlap, the scrubber keeps the one that starts first, then the
longest, then the kind with the highest priority in the order above (`term`
first, `hostname` last). A term is therefore replaced as a term even when it
also looks like a hostname.

Numbering counts distinct original values, not occurrences: the second time
`10.0.0.7` appears it is still `<ipv4-1>`. Terms compare case-insensitively;
every other kind compares the exact original text.

## The one-pass rule

A case record is scrubbed by **one scrubber instance** across every field of
the `case`, `candidate`, and `judge` sections, in a fixed order. The same
original value therefore maps to the same placeholder wherever it appears, so
a judge can still see that the host the candidate was asked about is the host
in the historical answer, without seeing the host. The fixture anonymizer
applies the same rule to a conversation's title and every block.

The scrubber rewrites only text: block text, titles, summaries, objectives,
family names, native ids, reconstruction gaps, criterion statements and notes,
cited-item notes, bundle rationale and missing-evidence lines, and reviewer
notes. Identifiers, ordinals, timestamps, roles, kinds, tool linkage, and
section structure pass through unchanged.

## Terms and term lists

Terms are operator data. They are supplied per request as `terms`, or by
reference as `term_list: {name, version}`, or both; the two combine and are
deduplicated case-insensitively before scrubbing. A list reference without a
version resolves to the latest version, and the record names the version it
resolved.

A named term list is stored in the private database (`scrub_term_lists`),
outside the checkout. Versions are immutable: saving a list whose terms or
notes differ from the latest version creates the next version, and an
unchanged save writes nothing. Retiring a list hides it from the picker and
refuses further saves, but an export that pins `{name, version}` still
resolves, so an old record can be reproduced. Only
`GET /api/v1/scrub-terms/{name}` returns terms; the list route, the record,
the manifest, and error messages carry counts, never the words. Nothing in
the application logs a term.

### Term limit

`MAX_TERMS` in `anonymize.py` is 200 distinct terms per scrub call, each at
most 200 characters after trimming. The same cap applies to a stored list and
to the combination of a stored list with inline terms. An export whose
combined distinct terms exceed the cap is refused with a 422 whose issue code
is `too_many_terms`; a list that does not exist or has no such version is
refused with `term_list_not_found`.

## The manifest and `scrub_version`

Every case record carries `case.redaction`:

```json
{
  "scrub_version": "benchwarmer.anonymize-1",
  "term_count": 2,
  "term_list": { "name": "program", "version": 3 },
  "manifest": { "hostname": 2, "term": 5 }
}
```

- `manifest` counts replaced **spans by kind** (occurrences, not distinct
  values), sorted by kind. It never contains an original value or a
  placeholder.
- `term_count` is the number of distinct terms supplied, inline and stored
  together, after case-insensitive deduplication. It says how many words the
  operator asked to hide, not how many were found; a term that never
  appears still counts here and contributes nothing to `manifest.term`.
- `term_list` names the stored list and the exact version used, or is `null`
  when every term came inline. It was added to `schema_version: 1` as an
  optional, additive field; records written before it exist without the key.
- `scrub_version` is the scrubber's producer and producer version. Changing
  a detector's pattern or a placeholder format changes the bytes a record
  would contain, so `ANONYMIZE_PRODUCER_VERSION` is bumped whenever detector
  behavior changes, and digests are only comparable within one
  `scrub_version`.

The record's `digest` is SHA-256 over the canonical JSON of the three
sections. Exporting the same task version with the same inline terms and the
same list version yields identical bytes and the same digest. Changing any
term, the list version, or the scrubber version changes the digest.

## The leak check

`leak_issues` (exposed through `POST /api/v1/fixtures/check`) scans every
string in a candidate fixture, including extensions, usage, and relationship
fields, for two things:

- any operator term, as a whole word, case-insensitively;
- any **original text the scrubber replaced** that is at least three
  characters long, as a case-insensitive substring. Replaced terms are
  excluded from this second pass because the term pass already covers them.

Each issue names the location (a JSON path), the code-point offsets, and the
kind, and never repeats the text, so issues can be shown to a model or written
to a report. The fixture anonymizer refuses a draft that still has leaks or
placeholders. The case export does not run the leak check today: it is scrub
only, and the task's own leakage flags concern the historical answer appearing
before the cut point, not private text.

## What the scrubber does not catch

- **Windows drive paths** (`C:\Users\…`) and single-segment paths (`/etc`).
- **Hostnames with suffixes outside the list** and bare machine names without
  a dot. Name them as terms.
- **Names, customers, products, and codenames** of any kind. The detectors
  know shapes, not vocabularies; a term list is the only way to hide a word.
- **Transformations of a term**: hyphenation, spacing, possessives joined
  without an apostrophe, or a name split across lines. The leak check does
  not catch these either.
- **Writing style.** Register, habits, and typos identify a person; only the
  fixture anonymizer's model rewrite addresses that, and only for fixtures.
- **Structured fields that are copied rather than scrubbed.** In a case
  record, `leakage_review.by` (the reviewer's name as entered),
  `expected_scope`, criterion ids, and `judge_evidence` references pass
  through as entered. Use neutral reviewer handles and ids.
- **Numbers that identify indirectly**: timestamps, token counts, and
  durations pass through unchanged and can identify a session when combined
  with other data.
- **Short secrets** under the length thresholds, and credentials with
  prefixes not in the list. A high-entropy string that is all one character
  class is not treated as base64.

A reviewer should read the record before it leaves the host. The scrubber
reduces what must be read; it does not replace the reading.
