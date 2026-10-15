import type {
	Branch,
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
}

export class ApiClientError extends Error {
	readonly kind: ApiErrorKind;
	readonly status?: number;

	constructor(message: string, { kind, status, cause }: ApiClientErrorOptions) {
		super(message, { cause });
		this.name = 'ApiClientError';
		this.kind = kind;
		this.status = status;
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
		isNullableString(value.fork_event_id)
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
	let response: Response;
	try {
		response = await request(path, {
			method: 'GET',
			headers: { Accept: 'application/json' },
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
		throw new ApiClientError(`The API returned HTTP ${response.status}.`, {
			kind: 'http',
			status: response.status
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
