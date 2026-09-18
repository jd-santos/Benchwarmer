# Source: OpenRouter

- Work: [Inspect OpenRouter capabilities](openrouter.md)
- Observed version/account scope: OpenRouter production API; published OpenAPI
  `3.1.0` with API info version `1.0.0`; public endpoints only; no account
  credential was available
- Inspected: 2026-09-08

## Evidence boundary

This report uses OpenRouter's current official documentation, published
[OpenAPI specification][openapi], and three bounded, read-only public API
requests. A Python standard-library probe fetched
`GET /api/v1/models?output_modalities=all`, `GET /api/v1/endpoints/zdr`, and
`GET /api/frontend/v1/all-providers`; it emitted only HTTP status, record counts,
and field-name coverage. All three returned HTTP 200. The snapshots contained
579 model records, 845 ZDR endpoint records, and 83 provider records at
`2026-09-08T06:46:28Z`. These counts are observations, not stable API promises.
No payload was saved in this repository.

A separate environment-presence check reported no `OPENROUTER_API_KEY` and no
environment-variable name containing `OPENROUTER`. Therefore no private
requests, generations, account balances, classifiers, keys, workspace settings,
or historical coverage were inspected. In particular, the shapes below come
from the published schema; account-dependent population and nullability remain
unverified. No inference request was made and no credits were spent.

The API changes independently of this repository. Importers should retain the
retrieval time and source URL with every snapshot and decode additive fields
permissively, as recommended for [router metadata][router-metadata].

## Session and request identity

OpenRouter and the selected API protocol have distinct identifier layers. The
The [streaming reference][streaming] documents an `X-Generation-Id` HTTP
response header for chat completions, legacy completions, OpenAI Responses, and
Anthropic Messages, including streamed responses. Its OpenRouter generation ID
is the cross-interface identifier for the documented
[`GET /api/v1/generation?id=...`][generation] lookup; published examples use the
`gen-...` namespace.

The response body's top-level `id` is instead shaped by the selected protocol.
The [OpenAI Responses schema][responses] uses `resp_...`, while the
[Anthropic Messages schema][messages] uses `msg_...`; chat/completion examples
are not a safe contract for the other interfaces. Preserve the protocol response
ID, but do not assume it equals the `X-Generation-Id` value or pass it to the
generation lookup. That lookup returns request metadata for the OpenRouter
generation ID, including:

- `id`, `created_at`, `api_type`, `streamed`, `cancelled`, `finish_reason`, and
  `native_finish_reason`;
- `request_id`, described as grouping all generations from one API request;
- `upstream_id`, the upstream provider's generation identifier;
- optional caller-supplied `session_id` and `external_user` (`user` on the
  request), plus `app_id`, `origin`, `http_referer`, `user_agent`, `preset_id`,
  `workspace_id`, and `data_region`;
- `response_cache_source_id` when a response-cache hit points to the original
  generation; and
- `provider_responses`, which may describe fallback attempts.

Generation-detail `data.id`, correlated from `X-Generation-Id`, is the provider
observation's primary duplicate key. A protocol response `id` must be stored
separately and namespaced by interface. `request_id` is a request-group key, not
a substitute for the generation ID; one request can be associated with multiple
generations. `upstream_id` is nullable and provider-defined, so it should be
retained as secondary evidence rather than assumed globally unique. The
published schema does not promise ordering for ID lookups.

Callers may supply `session_id` in the request body (or `x-session-id` header);
OpenRouter documents a 256-character maximum and uses the body value when both
are present. It is not passive grouping metadata. OpenRouter uses it directly
as a sticky routing key: after a successful request, subsequent requests with
the same value are preferentially routed to the same provider endpoint to
increase prompt-cache hits. Router models may also reuse the resolved model on
a best-effort basis. A configured `provider.order` takes precedence, routing can
fall back when the sticky provider is unavailable, and stickiness expires after
10 minutes of inactivity.

OpenRouter also uses `session_id` for observability grouping, but it remains a
caller-selected execution input rather than an OpenRouter conversation export
or server-generated harness-session identity. Supplying it can change route,
cache usage, latency, and cost, so integrations must treat it as an explicit
execution/configuration choice and record whether and how it was derived. See
the [prompt-caching documentation][prompt-caching] for routing behavior and the
[Broadcast documentation][broadcast] for observability behavior.

The documented Generations API exposes lookup by a known generation ID and a
separate management-key-only content lookup, not a cursor-based list of all
generations. Activity and Analytics are also management-key-only historical
aggregate surfaces. Ordinary API keys receive HTTP 403 from Activity and the
content lookup according to the published OpenAPI specification. No live key
was available to verify the account, organization, or workspace visibility of
any authenticated endpoint.

## Incremental import

There is no single incremental interface covering all OpenRouter activity.
Viable strategies differ by data type:

1. **Capture at execution time.** Read the HTTP `X-Generation-Id` as soon as
   response headers arrive, before an SDK or stream abstraction discards them,
   and persist it with the interface, protocol response `id`, response `model`,
   `usage`, and any opted-in router metadata. This applies to non-streaming and
   streaming calls: the generation ID is a response header, not an SSE field.
   Preserve it whenever present on non-2xx paths too, but do not require it from
   requests rejected before a generation exists. Errors before streaming starts
   are ordinary error responses; errors after streaming starts arrive in SSE
   events under the already-established HTTP 200 response, so retain the header
   captured when that stream opened. Header capture is required for Responses
   and Messages because their body IDs can be `resp_...` and `msg_...` rather
   than OpenRouter generation IDs. Then upsert generation detail by `data.id`
   and verify it against the captured header. This has the strongest
   request-level identity and does not depend on a provider history listing. The
   [usage-accounting guide][usage-accounting] says usage is always returned in
   non-streaming responses and in the final SSE chunk for streaming responses.
2. **Enrich known generation IDs.** Fetch `GET /api/v1/generation?id=...` for
   OpenRouter generation IDs captured from `X-Generation-Id`, not arbitrary
   protocol body IDs. This metadata endpoint is distinct from the
   management-key-only content lookup. It documents no update cursor or
   conditional retrieval. Re-fetching by ID should therefore be treated as an
   upsert, not an append. Its live key and account scope remain unverified.
3. **Import recent daily aggregates with a management key.**
   [`GET /api/v1/activity`][activity] accepts a UTC `date`, API-key hash,
   organization user ID, and workspace filters. The OpenAPI specification marks
   it management-key-only and returns HTTP 403 to an ordinary key. It returns
   only the last 30 completed UTC days and groups rows by date, model, and
   endpoint (optionally workspace). It has no documented cursor. A safe importer
   should re-read an overlap window and upsert a composite such as
   `(date, model_permaslug, endpoint_id, workspace scope)`. Ordering,
   immutability of completed-day rows, late adjustments, and the exact
   account/organization/workspace scope of a management key are undocumented or
   unverified.
4. **Query analytics windows.** The management-key-only
   [`POST /api/v1/analytics/query`][analytics-query] accepts an explicit time
   range, metrics, up to two dimensions, filters, optional granularity, ordering,
   and row limits. [`GET /api/v1/analytics/meta`][analytics-meta] is the source
   of truth for the currently available metrics, dimensions, operators, and
   granularities. The [official Activity announcement][activity-announcement]
   says dimensions include generation and session as well as model, provider,
   key, app, workspace, and classifier dimensions. This is a bounded aggregate
   query, not a documented append-only event feed; use overlapping time windows
   and upsert returned groups. Live permissions, maximum history, and
   per-generation coverage are unknown for this account.
5. **Import batches separately.** The beta [Batch API][batches] lists batches
   newest first with an `after` cursor, `last_id`, and `has_more`; it also accepts
   `created_after`, `created_before`, and repeated status filters. OpenRouter
   explicitly warns that whole-second `created_at` values can lose subsecond
   precision and says to use `after`, not timestamps, for gap-free pagination.
   Use batch `id` as the batch key and each caller-defined `custom_id` within
   that batch as the input key. For chat, Responses, and Messages batch results,
   the Batch API specifically documents `response.body.id` as the OpenRouter
   generation ID; preserve the batch `endpoint` with it and do not generalize
   that batch-only contract to synchronous protocol response IDs. Embedding
   result bodies do not have such an ID.
6. **Snapshot catalog prices.** The [Models API][models] supports opt-in
   `offset`/`limit` pagination with `links.next`, while an RSS mode advertises
   new models. It does not document a price-change cursor or historical price
   endpoint, so retain complete timestamped snapshots rather than overwriting
   prior rates.

The Activity UI can manually export aggregated CSV or PDF for fixed periods,
but the [export guide][activity-export] does not document that UI export as an
API contract. It is a fallback for manual evidence, not a reliable automated
cursor.

## Usage and economics

### Request and generation usage

The [API response schema][api-overview] and
[usage-accounting guide][usage-accounting] expose these categories:

- `prompt_tokens`, `completion_tokens`, and `total_tokens`;
- `prompt_tokens_details.cached_tokens` for cache reads,
  `cache_write_tokens` for explicit cache writes, and optional input audio/video
  tokens;
- `completion_tokens_details.reasoning_tokens` and optional output audio/image
  tokens;
- optional `server_tool_use.web_search_requests`; and
- `cost`, `is_byok`, and `cost_details`, including upstream prompt/completion
  inference components and optional server-tool cost.

The top-level totals overlap their detail fields. In particular, the Activity
export documentation says reasoning tokens are included in completion tokens,
and the response schema describes cached/audio/video counts as prompt-token
breakdowns. Benchwarmer must preserve the raw hierarchy and must not add detail
fields to their parent totals.

Generation detail supplies normalized `tokens_prompt` and
`tokens_completion` plus provider-native `native_tokens_prompt`,
`native_tokens_completion`, `native_tokens_reasoning`,
`native_tokens_cached`, and native completion-image tokens. It also includes
media/search/fetch counts. Native values are nullable; their presence and
relationship to normalized totals are provider dependent.

`usage.cost` is documented as the total amount charged to the OpenRouter
account. Generation detail exposes `total_cost`, `usage`, and a nullable
`cache_discount` in USD; treat the first two as overlapping representations of
the same provider observation, not additive charges. OpenRouter's base currency
and API pricing are US dollars according to its [FAQ][faq]. Retain source
currency as USD and timestamp every observation.

`cost_details.upstream_inference_cost` is only available for BYOK generation
lookups; for non-BYOK requests the documentation says it is zero or null. BYOK
billing needs special treatment: OpenRouter may charge only its BYOK fee while
the upstream provider bills inference separately. The Activity export labels
its BYOK spend as an estimate based on market rates that does not include a
customer's discounts. Consequently, do not record OpenRouter's BYOK estimate as
an actual upstream charge without reconciliation to the upstream provider.

### Batch usage

A completed batch reports aggregate `prompt_tokens`, `completion_tokens`,
`total_tokens`, `cost`, and `is_byok`. OpenRouter says batch requests are
*typically* billed at 50% of standard per-token prices, while web search is not
uniformly discounted and cache pricing varies by model. Preserve the actual
batch `usage.cost`; do not infer a universal 50% adjustment. There is no
separate batch-token category to add to normal tokens. Batch is an execution
and pricing mode that should be recorded separately.

### List-price snapshots

The public model catalog documents `pricing` as current USD per
token/request/unit from the model's top provider, including `prompt`,
`completion`, `request`, `image`, `web_search`, `internal_reasoning`,
`input_cache_read`, `input_cache_write`, and conditional `overrides`. Overrides
can depend on prompt-token thresholds, UTC time windows, and UTC weekdays.
Consumers must retain and evaluate the matching override rather than assuming
one timeless rate.

The live all-modality snapshot populated `pricing`, `prompt`, and `completion`
for all 579 models. It also showed optional cache, reasoning, audio, image, web,
and override fields with partial coverage; `request` was absent from every live
record despite being allowed by the documentation. Field absence must stay
unknown/unsupported, not become zero. The model catalog is list-price evidence,
not proof of a particular request's route or debit; generation `cost` is the
actual OpenRouter charge to prefer for completed requests.

### Credits, budgets, and quotas

[`GET /api/v1/key`][current-key] works with the current inference key and
reports per-key `limit`, `limit_remaining`, `limit_reset`, all-time/current-UTC-
day/week/month OpenRouter usage, equivalent BYOK usage fields,
`include_byok_in_limit`, key expiration/tier/type metadata, and creator identity.
The `rate_limit` object is deprecated and documented as safe to ignore.

Account-level [`GET /api/v1/credits`][credits] requires a management key and
returns `total_credits` and `total_usage`; remaining account credit can be
computed without allocating it to requests. The [limits guide][limits]
distinguishes account balance and per-key spending caps from request-rate
limits. Successful inference responses do not carry rate-limit headers;
OpenRouter platform 429 responses may carry `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, and `X-RateLimit-Reset`, while `Retry-After` may appear
when provider attempts supply retry hints.

No account key was available, so actual balance, purchased-credit history,
per-key limits, workspace budgets, subscription/enterprise terms, free-tier
status, auto-top-up state, and quota headroom are unknown. These account-level
values must remain separate from request charges and list-price estimates.

## Classification and prompt visibility

OpenRouter [Custom Classifiers][classifiers] are workspace-scoped,
administrator-configured, asynchronous post-generation jobs. A classifier has a
chosen model and taxonomy of up to eight dimensions; an optional sampling rate
means coverage can intentionally be incomplete. The classifier receives a
serialized transcript with tool names but not full tool schemas, and each turn
is truncated to 5,000 characters. Failed classifier jobs leave the original
generation untagged. Classifier inference is separately billed to the
administrative user who configured it, not to the request's API key.

Tags are documented in the Logs generation panel and Activity analysis.
Analytics query schema supports classifier dimensions and filters, including an
option to include untagged generations. However, the documented generation
metadata schema has no classification field, and the classifier guide exposes
setup through the workspace UI rather than a documented classifier CRUD/import
API. Complete per-generation tag extraction, classifier/version provenance,
sampling status, failure status, historical backfill, and retention are unknown
without management access and a configured workspace. OpenRouter's public
[task-classification market-share API][task-classifications] is sampled, omits
absolute volumes, and is not an account's custom-classifier history.

OpenRouter stores request metadata but says prompt and response content is not
stored by default. Opt-in beta [Input & Output Logging][io-logging] applies only
to generations after it is enabled and can be filtered by API key. Logged
content is available in Logs and, with a management key, through the documented
[generation-content lookup][generation-content] by known generation ID. The
published OpenAPI response explicitly returns HTTP 403 to an ordinary key. The
management key's account, organization, and workspace visibility was not tested
and is not specified by the lookup schema. Logged content is retained for at
least three months and may be kept longer at OpenRouter's discretion unless the
account owner requests deletion. Regional `eu.openrouter.ai` and
`us.openrouter.ai` requests currently skip this logging feature.

OpenRouter's [ZDR guide][zdr] says the router itself does not retain prompts
unless logging is enabled. Upstream providers have separate, endpoint-specific
retention and training policies; the guide exposes the current ZDR subset at
`GET /api/v1/endpoints/zdr`, while the [provider-policy guide][provider-logging]
warns that provider policies differ. Neither current-state catalog establishes
the policy that applied to a historical generation.

At execution time, `debug.echo_upstream_body` can echo the transformed upstream
request on supported streaming requests. This can help record an observed
provider request privately, but it is opt-in, not historical, and may expose
prompts or tool definitions; it must never be written to the public repository.
No provider-side hidden system instructions were documented or observed; treat
them as unavailable. An absent logged prompt must be represented as unavailable,
not as an empty prompt.

## Import and execution support

**Read/import interfaces:** public model/price and ZDR endpoint catalogs;
authenticated known-ID generation metadata with unverified key/account scope;
management-key-only known-ID logged content when logging was enabled;
management-key-only recent Activity aggregates, Analytics, credit, and
key-management interfaces; and cursor-paginated beta batch listings/results.
The current API has no documented general generation-history cursor or
provider-side conversation export. Manual Activity CSV/PDF export is available
but is not a stable programmatic contract. Ordinary keys cannot substitute for
a management key for Activity or generation content; the OpenAPI contract gives
those attempts HTTP 403.

**Execution interfaces:** OpenRouter provides OpenAI-compatible chat and legacy
completion routes, Responses and Anthropic Messages routes, plus asynchronous
batch execution. Usage is returned with inference responses, and
`X-Generation-Id` is documented across the four synchronous interfaces;
request-time capture should therefore retain the initial response headers as
well as the decoded body or events for streaming and non-streaming calls. Error
handling must retain the header whenever present without requiring it on
pre-generation failures; an error delivered after a stream starts is an SSE
event under the existing HTTP 200 response. This report did not execute any of
the interfaces. Import support must not be interpreted as replay support: stored
metadata or content does not capture all harness prompts, retries, tools, local
artifacts, or hidden provider behavior.

The beta batch list is workspace-scoped, so every key in a workspace can see
batches submitted by other keys in that workspace. Batch inputs/results are
stored as JSONL artifacts and deleted 30 days after creation. A private importer
must snapshot needed results before that deadline.

## Reconciliation identifiers

Preserve these fields without normalizing them into one identifier:

- **OpenRouter generation ID:** The `X-Generation-Id` response-header value and
  generation-detail `data.id`; primary provider duplicate key and argument to
  generation lookup and, with a management key, content lookup.
- **Protocol response `id`:** Interface-shaped body/event identity, including
  `resp_...` for Responses and `msg_...` for Messages. Retain it with the
  interface for trace replay and protocol correlation, but do not substitute it
  for the OpenRouter generation ID.
- **`request_id`:** Groups generations produced by one OpenRouter API request.
- **`upstream_id`:** Nullable upstream-provider generation ID; strongest direct
  provider cross-check when exposed.
- **`provider_responses`:** Fallback-attempt evidence. Retain its provider and
  status detail rather than counting attempts as independent successful usage.
- **Response `model` / generation `model`:** Observed model slug after routing;
  compare with the harness-requested slug.
- **`provider_name`:** Serving provider identity for the generation or Activity
  endpoint row.
- **`router` and router metadata `requested`, `strategy`, `attempts`, and
  `endpoints`:** Distinguish requested alias/router from the selected
  model/provider and fallbacks.
- **`response_cache_source_id`:** Links a cache replay to the generation that
  produced the cached response.
- **`endpoint_id` + `model_permaslug`:** Stable-looking Activity row dimensions
  for provider endpoint and permanent model version. Retain source semantics
  rather than assuming global identity.
- **`session_id`:** Caller-supplied sticky routing and observability-grouping
  input. A stable value can alter provider selection, prompt-cache reuse, and
  economics; retain it with the execution configuration when the harness sends
  one rather than treating it as a neutral reconciliation label.
- **`external_user`, `app_id`, `origin`, `http_referer`, `preset_id`, and
  `workspace_id`:** Secondary attribution and scope checks; some are nullable,
  account-specific, or private.
- **API-key hash:** Joins management key inventory to Activity filtering without
  storing the secret key; it is still private account metadata.
- **Batch identifiers:** Batch `id`, item `custom_id`, result `id`, result
  `response.request_id`, and the inference result's `response.body.id` join the
  submission, caller item, batch result, request, and OpenRouter generation. The
  last field is a batch-specific documented generation ID, not evidence that a
  synchronous Responses or Messages body `id` has the same semantics.

For new harness integrations, capture `X-Generation-Id` directly from the HTTP
response and retain any protocol response ID separately. Ensure the client
exposes initial headers for streaming and non-streaming calls and preserves a
generation ID whenever an error response provides one, instead of retaining
only a decoded body or event iterator. Decide explicitly whether to send a
pseudonymous `session_id` that maps to the local harness session. Do not add one
solely for reconciliation: enabling it changes routing and cache behavior and
must be recorded as an execution variable for reproducibility and economic
comparison. A local session-to-generation mapping is sufficient when sticky
routing is not intended. Opt in to `X-OpenRouter-Metadata: enabled` when routing
evidence is needed: it records the requested slug, strategy, selected
endpoint/provider/model, attempts, BYOK status, region, and material pipeline
stages. Cache hits intentionally omit this metadata, so absence does not prove
no routing occurred. Store this evidence privately because caller/user/session
attribution can be sensitive.

Never reconcile on display name alone. The live model snapshot had unique `id`
values, while populated `canonical_slug` values were not unique across all 579
records. Preserve requested slug, observed response model, catalog `id`,
`canonical_slug`, provider, endpoint, and snapshot time as distinct facts.

## Unknowns and risks

- Activity and generation-content access are known to require management keys;
  the OpenAPI contract specifies HTTP 403 for ordinary keys. Account-dependent
  field population, the exact account/organization/workspace visibility granted
  to a management key, other endpoint permissions, balances, quotas, key scopes,
  workspace budgets, classifiers, and historical coverage were not tested
  because no credential was available.
- Metadata retention duration and deletion behavior are not documented as a
  stable generation-history guarantee. Prompt/content retention applies only to
  opt-in logging; provider retention is endpoint-specific and can change.
- There is no documented cursor over ordinary generations. Activity is only a
  management-key-only 30-completed-UTC-day aggregate window; its visibility,
  Analytics history limits, and per-generation completeness need a bounded
  management-key test.
- Custom-classifier tags are visible in product UI and analytics, but a complete,
  versioned, per-generation import path and historical backfill behavior remain
  unknown. Sampling and failures create real missingness.
- `provider_name`, endpoint policy, aliases, routes, and catalog prices can change.
  Save raw private observations and timestamped public catalog snapshots; do not
  rewrite old generations from the current catalog.
- Model-level catalog pricing is from the top provider and may include conditional
  overrides. It does not prove the route-specific price actually charged.
- BYOK costs can span two billing systems. OpenRouter's charge and estimated
  market-rate upstream spend must not replace the upstream provider's actual
  bill.
- Router metadata is opt-in, additive, and omitted on response-cache hits and
  some early/internal errors. A missing metadata object is not evidence of a
  direct, single-attempt route.
- `session_id` is an execution control, not only a join key. It can pin a
  provider endpoint, affect cache hits and charges, and for router models may
  influence resolved-model reuse. Record its presence and derivation; do not
  silently enable it in import-only or controlled-comparison paths.
- `X-Generation-Id` is documented across the four synchronous interfaces, but
  no live success or failure response was tested. Importers should capture
  initial headers for streamed calls and tolerate its absence on errors that do
  not establish a generation.
- Batch is beta, workspace-scoped, and has a 30-day artifact lifetime. Import it
  with its own cursor and preserve terminal failures as evidence.
- The live catalog exposed fields not all enumerated in the prose documentation
  and omitted the documented `request` price field. Import schemas must retain
  unknown fields and distinguish absent/null from numeric zero.
- Provider privacy policy records are current-state evidence, not proof of the
  policy in effect for an old generation. The public ZDR list had 845 endpoint
  rows during inspection, but no historical policy endpoint was found.

[activity]: https://openrouter.ai/docs/api/api-reference/analytics/get-user-activity-grouped-by-endpoint
[activity-announcement]: https://openrouter.ai/blog/announcements/activity-dashboard/
[activity-export]: https://openrouter.ai/docs/cookbook/administration/activity-export
[analytics-meta]: https://openrouter.ai/docs/api/api-reference/analytics/get-available-analytics-metrics-and-dimensions
[analytics-query]: https://openrouter.ai/docs/api/api-reference/analytics/query-analytics-data
[api-overview]: https://openrouter.ai/docs/api_reference/overview
[batches]: https://openrouter.ai/docs/batch-quickstart
[broadcast]: https://openrouter.ai/docs/guides/features/broadcast
[classifiers]: https://openrouter.ai/docs/guides/features/classifiers
[credits]: https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits
[current-key]: https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key
[faq]: https://openrouter.ai/docs/faq
[generation]: https://openrouter.ai/docs/api/api-reference/generations/get-request-%26-usage-metadata-for-a-generation
[generation-content]: https://openrouter.ai/docs/api/api-reference/generations/get-stored-prompt-completion-and-error-content-for-a-generation
[io-logging]: https://openrouter.ai/docs/guides/features/input-output-logging
[limits]: https://openrouter.ai/docs/api_reference/limits
[messages]: https://openrouter.ai/docs/api/api-reference/anthropic-messages/create-a-message
[models]: https://openrouter.ai/docs/guides/overview/models
[openapi]: https://openrouter.ai/openapi.json
[prompt-caching]: https://openrouter.ai/docs/guides/best-practices/prompt-caching
[provider-logging]: https://openrouter.ai/docs/guides/privacy/provider-logging
[responses]: https://openrouter.ai/docs/api/api-reference/responses/create-a-response
[router-metadata]: https://openrouter.ai/docs/guides/features/router-metadata
[streaming]: https://openrouter.ai/docs/api/reference/streaming
[task-classifications]: https://openrouter.ai/docs/api/api-reference/classifications/task-classification-market-share
[usage-accounting]: https://openrouter.ai/docs/cookbook/administration/usage-accounting
[zdr]: https://openrouter.ai/docs/guides/features/zdr
