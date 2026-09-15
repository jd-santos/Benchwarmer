import type {
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

function isAbort(error: unknown, signal: AbortSignal | undefined): boolean {
	return (
		(signal?.aborted === true && error === signal.reason) ||
		(error instanceof DOMException && error.name === 'AbortError')
	);
}

async function getJson(path: string, signal: AbortSignal | undefined): Promise<unknown> {
	let response: Response;
	try {
		response = await fetch(path, {
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
	const value = await getJson('/api/v1/health', options.signal);
	if (!isHealthResponse(value)) {
		throw new ApiClientError('The API health response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}

export async function getSources(options: ApiRequestOptions = {}): Promise<SourcesResponse> {
	const value = await getJson('/api/v1/sources', options.signal);
	if (!isSourcesResponse(value)) {
		throw new ApiClientError('The API sources response did not match its contract.', {
			kind: 'invalid-contract'
		});
	}
	return value;
}
