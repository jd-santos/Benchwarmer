import type {
	Branch,
	BundleDetail,
	BundleDocument,
	BundleOrigin,
	BundlesResponse,
	HarnessRunRecord,
	BundleStatus,
	BundleSummary,
	EvidenceIssue,
	ContentBlock,
	ConversationDetail,
	ConversationEvent,
	ConversationSummary,
	ConversationsResponse,
	CoverageValue,
	HealthResponse,
	SourceCoverage,
	SourceStatus,
	SourcesResponse
} from './types';

export type ApiErrorKind = 'network' | 'http' | 'malformed-json' | 'invalid-contract';

interface ApiClientErrorOptions {
	kind: ApiErrorKind;
	status?: number;
	cause?: unknown;
	body?: unknown;
}

export class ApiClientError extends Error {
	readonly kind: ApiErrorKind;
	readonly status?: number;
	readonly body?: unknown;

	constructor(message: string, { kind, status, cause, body }: ApiClientErrorOptions) {
		super(message, { cause });
		this.name = 'ApiClientError';
		this.kind = kind;
		this.status = status;
		this.body = body;
	}

	/** Evidence problems reported by a rejected bundle save, if any. */
	get issues(): EvidenceIssue[] {
		if (!isRecord(this.body) || !Array.isArray(this.body.issues)) return [];
		return this.body.issues.filter(
			(item): item is EvidenceIssue =>
				isRecord(item) &&
				(item.item_index === null || isCount(item.item_index)) &&
				typeof item.code === 'string' &&
				typeof item.message === 'string'
		);
	}
}

export interface ApiRequestOptions {
	signal?: AbortSignal;
	fetch?: typeof globalThis.fetch;
}

const coverageValues: ReadonlySet<CoverageValue> = new Set([
	'available',
	'partial',
	'unavailable',
	'unknown'
]);

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isCoverageValue(value: unknown): value is CoverageValue {
	return typeof value === 'string' && coverageValues.has(value as CoverageValue);
}

function isSourceCoverage(value: unknown): value is SourceCoverage {
	return (
		isRecord(value) &&
		isCoverageValue(value.sessions) &&
		isCoverageValue(value.token_usage) &&
		isCoverageValue(value.request_ids) &&
		isCoverageValue(value.actual_charges) &&
		isCoverageValue(value.list_price_estimates) &&
		isCoverageValue(value.subscription_expense) &&
		isCoverageValue(value.quota) &&
		isCoverageValue(value.credits) &&
		isCoverageValue(value.prompts) &&
		isCoverageValue(value.classifications)
	);
}

function isSourceStatus(value: unknown): value is SourceStatus {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		typeof value.kind === 'string' &&
		typeof value.display_name === 'string' &&
		(value.last_successful_import_at === null ||
			typeof value.last_successful_import_at === 'string') &&
		isSourceCoverage(value.coverage)
	);
}

function isHealthResponse(value: unknown): value is HealthResponse {
	return (
		isRecord(value) &&
		value.status === 'ok' &&
		(value.alembic_revision === null || typeof value.alembic_revision === 'string') &&
		typeof value.data_root_writable === 'boolean'
	);
}

function isSourcesResponse(value: unknown): value is SourcesResponse {
	return isRecord(value) && Array.isArray(value.items) && value.items.every(isSourceStatus);
}

const captureValues: ReadonlySet<string> = new Set([...coverageValues, 'redacted']);

function isNullableString(value: unknown): value is string | null {
	return value === null || typeof value === 'string';
}

function isCount(value: unknown): value is number {
	return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isStringRecord(
	value: unknown,
	check: (entry: unknown) => boolean
): value is Record<string, never> {
	return isRecord(value) && Object.values(value).every(check);
}

function isConversationSummary(value: unknown): value is ConversationSummary {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		isRecord(value.source) &&
		typeof value.source.id === 'string' &&
		typeof value.source.kind === 'string' &&
		typeof value.source.display_name === 'string' &&
		typeof value.native_id === 'string' &&
		typeof value.revision === 'string' &&
		typeof value.captured_at === 'string' &&
		isNullableString(value.title) &&
		isNullableString(value.preview) &&
		isNullableString(value.started_at) &&
		isNullableString(value.last_activity_at) &&
		isCount(value.event_count) &&
		isCount(value.message_count) &&
		isCount(value.branch_count) &&
		isStringRecord(value.relationship_counts, isCount) &&
		isStringRecord(
			value.coverage,
			(state) => typeof state === 'string' && captureValues.has(state)
		) &&
		isCount(value.match_count) &&
		Array.isArray(value.matches) &&
		value.matches.every(
			(hit) =>
				isRecord(hit) &&
				isNullableString(hit.event_id) &&
				isNullableString(hit.block_id) &&
				typeof hit.field === 'string' &&
				typeof hit.snippet === 'string'
		)
	);
}

function isConversationsResponse(value: unknown): value is ConversationsResponse {
	return (
		isRecord(value) &&
		Array.isArray(value.items) &&
		value.items.every(isConversationSummary) &&
		isCount(value.total) &&
		isCount(value.limit) &&
		isCount(value.offset)
	);
}

function isContentBlock(value: unknown): value is ContentBlock {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		typeof value.kind === 'string' &&
		isNullableString(value.text) &&
		isNullableString(value.tool_call_id) &&
		isNullableString(value.artifact_id)
	);
}

function isConversationEvent(value: unknown): value is ConversationEvent {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		typeof value.native_id === 'string' &&
		isCount(value.ordinal) &&
		isNullableString(value.parent_id) &&
		typeof value.kind === 'string' &&
		typeof value.role === 'string' &&
		isNullableString(value.occurred_at) &&
		Array.isArray(value.content) &&
		value.content.every(isContentBlock)
	);
}

function isBranch(value: unknown): value is Branch {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		typeof value.leaf_event_id === 'string' &&
		Array.isArray(value.event_ids) &&
		value.event_ids.every((id) => typeof id === 'string') &&
		isNullableString(value.fork_event_id) &&
		isNullableString(value.divergent_event_id) &&
		typeof value.is_original === 'boolean' &&
		value.origin === 'captured' &&
		Array.isArray(value.models) &&
		value.models.every((model) => typeof model === 'string')
	);
}

function isConversationDetail(value: unknown): value is ConversationDetail {
	return (
		isRecord(value) &&
		isConversationSummary(value.summary) &&
		typeof value.is_latest === 'boolean' &&
		Array.isArray(value.revisions) &&
		value.revisions.every(
			(item) =>
				isRecord(item) && typeof item.revision === 'string' && typeof item.captured_at === 'string'
		) &&
		Array.isArray(value.events) &&
		value.events.every(isConversationEvent) &&
		Array.isArray(value.artifacts) &&
		Array.isArray(value.metadata) &&
		Array.isArray(value.relationships) &&
		value.relationships.every(
			(item) =>
				isRecord(item) &&
				typeof item.kind === 'string' &&
				typeof item.target_native_id === 'string' &&
				isNullableString(item.target_conversation_id)
		) &&
		Array.isArray(value.referenced_by) &&
		value.referenced_by.every(
			(item) =>
				isRecord(item) && typeof item.kind === 'string' && typeof item.conversation_id === 'string'
		) &&
		Array.isArray(value.branches) &&
		value.branches.every(isBranch)
	);
}

function isAbort(error: unknown, signal: AbortSignal | undefined): boolean {
	return (
		(signal?.aborted === true && error === signal.reason) ||
		(error instanceof DOMException && error.name === 'AbortError')
	);
}

async function getJson(
	path: string,
	signal: AbortSignal | undefined,
	request: typeof globalThis.fetch = globalThis.fetch
): Promise<unknown> {
	return requestJson(path, { method: 'GET' }, signal, request);
}

async function requestJson(
	path: string,
	init: { method: 'GET' | 'POST' | 'PUT'; body?: unknown },
	signal: AbortSignal | undefined,
	request: typeof globalThis.fetch = globalThis.fetch
): Promise<unknown> {
	let response: Response;
	try {
		response = await request(path, {
			method: init.method,
			headers:
				init.body === undefined
					? { Accept: 'application/json' }
					: { Accept: 'application/json', 'Content-Type': 'application/json' },
			body: init.body === undefined ? undefined : JSON.stringify(init.body),
			signal
		});
	} catch (error) {
		if (isAbort(error, signal)) {
			throw error;
		}
		throw new ApiClientError('The API request could not reach the server.', {
			kind: 'network',
			cause: error
		});
	}

	if (!response.ok) {
		let body: unknown;
		if (response.status === 409 || response.status === 422) {
			body = await response.json().catch(() => undefined);
		}
		throw new ApiClientError(`The API returned HTTP ${response.status}.`, {
			kind: 'http',
			status: response.status,
			body
		});
	}

	try {
		return await response.json();
	} catch (error) {
		if (isAbort(error, signal)) {
			throw error;
		}
		if (!(error instanceof SyntaxError)) {
			throw new ApiClientError('The API response body could not be read.', {
				kind: 'network',
				cause: error
			});
		}
		throw new ApiClientError('The API returned malformed JSON.', {
			kind: 'malformed-json',
			cause: error
		});
	}
}

export async function getHealth(options: ApiRequestOptions = {}): Promise<HealthResponse> {
	const value = await getJson('/api/v1/health', options.signal, options.fetch);
	if (!isHealthResponse(value)) {
		throw new ApiClientError('The API health response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

export async function getSources(options: ApiRequestOptions = {}): Promise<SourcesResponse> {
	const value = await getJson('/api/v1/sources', options.signal, options.fetch);
	if (!isSourcesResponse(value)) {
		throw new ApiClientError('The API sources response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

export interface ConversationQuery {
	q?: string;
	sourceId?: string;
	limit?: number;
	offset?: number;
}

export async function getConversations(
	query: ConversationQuery = {},
	options: ApiRequestOptions = {}
): Promise<ConversationsResponse> {
	const params = new URLSearchParams();
	if (query.q) params.set('q', query.q);
	if (query.sourceId) params.set('source_id', query.sourceId);
	if (query.limit !== undefined) params.set('limit', String(query.limit));
	if (query.offset) params.set('offset', String(query.offset));
	const search = params.toString();
	const value = await getJson(
		`/api/v1/conversations${search ? `?${search}` : ''}`,
		options.signal,
		options.fetch
	);
	if (!isConversationsResponse(value)) {
		throw new ApiClientError('The API conversations response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

export async function getConversation(
	id: string,
	revision: string | null = null,
	options: ApiRequestOptions = {}
): Promise<ConversationDetail> {
	const search = revision ? `?${new URLSearchParams({ revision })}` : '';
	const value = await getJson(
		`/api/v1/conversations/${encodeURIComponent(id)}${search}`,
		options.signal,
		options.fetch
	);
	if (!isConversationDetail(value)) {
		throw new ApiClientError('The API conversation response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

const evidenceRoles: ReadonlySet<string> = new Set([
	'requirement',
	'action',
	'result',
	'correction',
	'context'
]);
const bundleStatuses: ReadonlySet<string> = new Set([
	'draft',
	'reviewed',
	'analysis_only',
	'rejected'
]);
const bundleOrigins: ReadonlySet<string> = new Set(['human', 'generated']);

function isBundleDocument(value: unknown): value is BundleDocument {
	return (
		isRecord(value) &&
		typeof value.summary === 'string' &&
		typeof value.objective === 'string' &&
		typeof value.goal === 'string' &&
		typeof value.status === 'string' &&
		bundleStatuses.has(value.status) &&
		isNullableString(value.rationale) &&
		Array.isArray(value.missing_evidence) &&
		value.missing_evidence.every((item) => typeof item === 'string') &&
		Array.isArray(value.items) &&
		value.items.every(
			(item) =>
				isRecord(item) &&
				typeof item.role === 'string' &&
				evidenceRoles.has(item.role) &&
				isRecord(item.ref) &&
				typeof item.ref.conversation_id === 'string' &&
				typeof item.ref.revision === 'string' &&
				typeof item.ref.event_id === 'string' &&
				isNullableString(item.ref.block_id)
		)
	);
}

function isBundleDetail(value: unknown): value is BundleDetail {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		isCount(value.revision) &&
		isCount(value.latest_revision) &&
		typeof value.updated_at === 'string' &&
		isBundleDocument(value.document) &&
		Array.isArray(value.items) &&
		value.items.length === value.document.items.length &&
		value.items.every(
			(item) =>
				isRecord(item) &&
				isRecord(item.item) &&
				isNullableString(item.conversation_title) &&
				typeof item.conversation_is_latest === 'boolean' &&
				typeof item.event_role === 'string' &&
				typeof item.event_kind === 'string' &&
				isNullableString(item.occurred_at) &&
				isNullableString(item.block_kind) &&
				isNullableString(item.excerpt) &&
				(item.omitted_before === null || isCount(item.omitted_before)) &&
				Array.isArray(item.tool_calls) &&
				item.tool_calls.every(
					(call) =>
						isRecord(call) &&
						typeof call.tool_call_id === 'string' &&
						isNullableString(call.arguments)
				)
		) &&
		Array.isArray(value.revisions) &&
		value.revisions.every(
			(item) => isRecord(item) && isCount(item.number) && typeof item.created_at === 'string'
		)
	);
}

function isBundleSummary(value: unknown): value is BundleSummary {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		isCount(value.revision) &&
		typeof value.summary === 'string' &&
		typeof value.objective === 'string' &&
		typeof value.goal === 'string' &&
		typeof value.status === 'string' &&
		bundleStatuses.has(value.status) &&
		typeof value.origin === 'string' &&
		bundleOrigins.has(value.origin) &&
		typeof value.producer === 'string' &&
		isNullableString(value.run_id) &&
		isCount(value.item_count) &&
		Array.isArray(value.conversation_ids) &&
		value.conversation_ids.every((item) => typeof item === 'string') &&
		typeof value.updated_at === 'string'
	);
}

function bundleDetail(value: unknown): BundleDetail {
	if (!isBundleDetail(value)) {
		throw new ApiClientError('The API bundle response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

export interface BundleFilters {
	conversationId?: string;
	/** Origin of the latest revision, so a reviewed proposal no longer counts as generated. */
	origin?: BundleOrigin;
	status?: BundleStatus;
	/** Only bundles whose latest revision came from this harness run. */
	runId?: string;
}

export async function getBundles(
	filters: BundleFilters = {},
	options: ApiRequestOptions = {}
): Promise<BundlesResponse> {
	const params = new URLSearchParams();
	if (filters.conversationId) params.set('conversation_id', filters.conversationId);
	if (filters.origin) params.set('origin', filters.origin);
	if (filters.status) params.set('status', filters.status);
	if (filters.runId) params.set('run_id', filters.runId);
	const query = params.toString();
	const search = query ? `?${query}` : '';
	const value = await getJson(`/api/v1/bundles${search}`, options.signal, options.fetch);
	if (!isRecord(value) || !Array.isArray(value.items) || !value.items.every(isBundleSummary)) {
		throw new ApiClientError('The API bundles response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return { items: value.items };
}

export async function getBundle(
	id: string,
	revision: number | null = null,
	options: ApiRequestOptions = {}
): Promise<BundleDetail> {
	const search = revision ? `?${new URLSearchParams({ revision: String(revision) })}` : '';
	return bundleDetail(
		await getJson(
			`/api/v1/bundles/${encodeURIComponent(id)}${search}`,
			options.signal,
			options.fetch
		)
	);
}

export async function createBundle(
	document: BundleDocument,
	options: ApiRequestOptions = {}
): Promise<BundleDetail> {
	return bundleDetail(
		await requestJson(
			'/api/v1/bundles',
			{ method: 'POST', body: { document } },
			options.signal,
			options.fetch
		)
	);
}

/** Save a new revision; rejects with HTTP 409 if `baseRevision` is stale. */
export async function updateBundle(
	id: string,
	document: BundleDocument,
	baseRevision: number,
	options: ApiRequestOptions = {}
): Promise<BundleDetail> {
	return bundleDetail(
		await requestJson(
			`/api/v1/bundles/${encodeURIComponent(id)}`,
			{ method: 'PUT', body: { document, base_revision: baseRevision } },
			options.signal,
			options.fetch
		)
	);
}

function isRunUsage(value: unknown): value is HarnessRunRecord['usage_total'] {
	const isModelUsage = (usage: unknown): boolean =>
		isRecord(usage) &&
		isCount(usage.input) &&
		isCount(usage.output) &&
		isCount(usage.cache_read) &&
		isCount(usage.cache_write) &&
		isCount(usage.total_tokens) &&
		isRecord(usage.cost) &&
		typeof usage.cost.total === 'number';
	return (
		isRecord(value) &&
		isRecord(value.models) &&
		Object.values(value.models).every(isModelUsage) &&
		isRecord(value.tools) &&
		Object.values(value.tools).every(isModelUsage)
	);
}

function isHarnessRunRecord(value: unknown): value is HarnessRunRecord {
	return (
		isRecord(value) &&
		typeof value.run_id === 'string' &&
		typeof value.workflow === 'string' &&
		typeof value.started_at === 'string' &&
		typeof value.finished_at === 'string' &&
		isRecord(value.model) &&
		typeof value.model.provider === 'string' &&
		typeof value.model.model_id === 'string' &&
		isNullableString(value.model.base_url_override) &&
		typeof value.producer === 'string' &&
		typeof value.pricing_source === 'string' &&
		isRunUsage(value.usage_total) &&
		Array.isArray(value.inputs) &&
		value.inputs.every(
			(input) =>
				isRecord(input) &&
				typeof input.id === 'string' &&
				typeof input.status === 'string' &&
				Array.isArray(input.bundle_ids) &&
				input.bundle_ids.every((id) => typeof id === 'string') &&
				isRunUsage(input.usage)
		)
	);
}

/** The record of one hand-run harness workflow, with raw usage and catalog cost estimates. */
export async function getRun(
	runId: string,
	options: ApiRequestOptions = {}
): Promise<HarnessRunRecord> {
	const value = await getJson(
		`/api/v1/runs/${encodeURIComponent(runId)}`,
		options.signal,
		options.fetch
	);
	if (!isHarnessRunRecord(value)) {
		throw new ApiClientError('The API run response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}
