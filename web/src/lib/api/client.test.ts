import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	ApiClientError,
	exportTask,
	getHealth,
	getRuns,
	getSources,
	getTermList,
	getTermLists,
	retireTermList,
	saveTermList,
	startImport
} from './client';
import type { HealthResponse, RunsResponse, SourcesResponse } from './types';

const healthResponse: HealthResponse = {
	status: 'ok',
	alembic_revision: '0002',
	data_root_writable: true
};

const sourcesResponse: SourcesResponse = {
	items: [
		{
			id: 'fixture-hermes',
			kind: 'hermes',
			display_name: 'Hermes fixture',
			last_successful_import_at: '2026-09-07T12:00:00Z',
			coverage: {
				sessions: 'available',
				token_usage: 'partial',
				request_ids: 'partial',
				actual_charges: 'unavailable',
				list_price_estimates: 'unavailable',
				subscription_expense: 'unavailable',
				quota: 'unknown',
				credits: 'unknown',
				prompts: 'partial',
				classifications: 'unknown'
			}
		}
	]
};

function jsonResponse(body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status: 200,
		headers: { 'content-type': 'application/json' }
	});
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('getHealth', () => {
	it('requests the exact relative same-origin health path and forwards the signal', async () => {
		const signal = new AbortController().signal;
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(healthResponse));
		vi.stubGlobal('fetch', fetchMock);

		await expect(getHealth({ signal })).resolves.toEqual(healthResponse);
		expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', {
			method: 'GET',
			headers: { Accept: 'application/json' },
			signal
		});
		expect(fetchMock.mock.calls[0]?.[0]).not.toMatch(/^https?:\/\//);
	});

	it('uses a load-scoped fetch implementation when provided', async () => {
		const request = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(healthResponse));

		await expect(getHealth({ fetch: request })).resolves.toEqual(healthResponse);
		expect(request).toHaveBeenCalledOnce();
	});

	it('preserves the original abort reason and identity', async () => {
		const controller = new AbortController();
		const abortReason = new DOMException('request cancelled', 'AbortError');
		controller.abort(abortReason);
		const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(abortReason);
		vi.stubGlobal('fetch', fetchMock);

		let thrown: unknown;
		try {
			await getHealth({ signal: controller.signal });
		} catch (error) {
			thrown = error;
		}

		expect(thrown).toBe(abortReason);
		expect((thrown as DOMException).name).toBe('AbortError');
	});

	it('wraps network failures in a typed client error', async () => {
		const networkError = new TypeError('fetch failed');
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(networkError));

		await expect(getHealth()).rejects.toMatchObject({
			name: 'ApiClientError',
			kind: 'network',
			cause: networkError
		});
	});

	it('captures a non-2xx status without parsing an HTML error body', async () => {
		const response = new Response('<html>bad gateway</html>', {
			status: 502,
			headers: { 'content-type': 'text/html' }
		});
		const jsonSpy = vi.spyOn(response, 'json');
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response));

		await expect(getHealth()).rejects.toMatchObject({
			name: 'ApiClientError',
			kind: 'http',
			status: 502
		});
		expect(jsonSpy).not.toHaveBeenCalled();
	});

	it('preserves an abort raised while reading the response body', async () => {
		const controller = new AbortController();
		const abortReason = new DOMException('body read cancelled', 'AbortError');
		const response = jsonResponse(healthResponse);
		vi.spyOn(response, 'json').mockImplementation(async () => {
			controller.abort(abortReason);
			throw abortReason;
		});
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response));

		let thrown: unknown;
		try {
			await getHealth({ signal: controller.signal });
		} catch (error) {
			thrown = error;
		}

		expect(thrown).toBe(abortReason);
		expect((thrown as DOMException).name).toBe('AbortError');
	});

	it('wraps a response body read failure as a typed network error', async () => {
		const bodyReadError = new TypeError('response body terminated');
		const response = jsonResponse(healthResponse);
		vi.spyOn(response, 'json').mockRejectedValue(bodyReadError);
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response));

		await expect(getHealth()).rejects.toMatchObject({
			name: 'ApiClientError',
			message: 'The API response body could not be read.',
			kind: 'network',
			cause: bodyReadError
		});
	});

	it('rejects malformed JSON with a typed response error', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				new Response('{not valid json', {
					status: 200,
					headers: { 'content-type': 'application/json' }
				})
			)
		);

		let thrown: unknown;
		try {
			await getHealth();
		} catch (error) {
			thrown = error;
		}

		expect(thrown).toBeInstanceOf(ApiClientError);
		expect(thrown).toMatchObject({ kind: 'malformed-json' });
	});

	it('rejects JSON that does not match the documented health contract', async () => {
		vi.stubGlobal(
			'fetch',
			vi
				.fn<typeof fetch>()
				.mockResolvedValue(jsonResponse({ ...healthResponse, data_root_writable: 'yes' }))
		);

		await expect(getHealth()).rejects.toMatchObject({
			name: 'ApiClientError',
			kind: 'invalid-contract'
		});
	});
});

describe('getSources', () => {
	it('requests the exact relative same-origin sources path', async () => {
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(sourcesResponse));
		vi.stubGlobal('fetch', fetchMock);

		await expect(getSources()).resolves.toEqual(sourcesResponse);
		expect(fetchMock).toHaveBeenCalledWith('/api/v1/sources', {
			method: 'GET',
			headers: { Accept: 'application/json' },
			signal: undefined
		});
		expect(fetchMock.mock.calls[0]?.[0]).not.toMatch(/^https?:\/\//);
	});

	it('rejects undocumented coverage values instead of fabricating source data', async () => {
		const invalid = structuredClone(sourcesResponse) as unknown as {
			items: Array<{ coverage: { actual_charges: string } }>;
		};
		invalid.items[0]!.coverage.actual_charges = 'zero';
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(invalid)));

		await expect(getSources()).rejects.toMatchObject({
			name: 'ApiClientError',
			kind: 'invalid-contract'
		});
	});
});

const runsResponse: RunsResponse = {
	items: [
		{
			run_id: 'propose-bundles-2026-10-19T10-00-00-000Z',
			workflow: 'propose-bundles',
			provider: 'anthropic',
			model: 'claude-sonnet-5-5',
			thinking_level: null,
			base_url_override: null,
			started_at: '2026-10-19T10:00:00Z',
			finished_at: '2026-10-19T10:00:29Z',
			input_count: 1,
			bundle_count: 2,
			total_tokens: 55810,
			estimated_cost: 0.136,
			pricing_source: 'pi-ai model catalog estimate'
		}
	]
};

describe('getRuns', () => {
	it('lists every run, or one workflow when asked', async () => {
		const fetchMock = vi
			.fn<typeof fetch>()
			.mockImplementation(() => Promise.resolve(jsonResponse(runsResponse)));
		vi.stubGlobal('fetch', fetchMock);

		await expect(getRuns()).resolves.toEqual(runsResponse);
		expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/runs');
		await getRuns({ workflow: 'propose-bundles' });
		expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/runs?workflow=propose-bundles');
	});

	it('rejects a run summary missing its cost rather than showing a blank figure', async () => {
		const invalid = structuredClone(runsResponse) as unknown as {
			items: Array<{ estimated_cost: unknown }>;
		};
		delete invalid.items[0]!.estimated_cost;
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(invalid)));

		await expect(getRuns()).rejects.toMatchObject({ kind: 'invalid-contract' });
	});
});

describe('startImport', () => {
	it('posts the path to the source and returns what the import did', async () => {
		const run = {
			batch_id: 'pi-ui-1',
			outcome: 'succeeded',
			conversations: 2,
			revisions: 2,
			snapshots: 2,
			error_summary: null
		};
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(run));
		vi.stubGlobal('fetch', fetchMock);

		await expect(startImport('pi-a', '/srv/inbox/sessions')).resolves.toEqual(run);
		expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/sources/pi-a/imports');
		expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
			method: 'POST',
			body: JSON.stringify({ path: '/srv/inbox/sessions' })
		});
	});

	it('keeps the 422 reason on the error so the form can show it', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				new Response(JSON.stringify({ detail: 'path is outside the configured import roots' }), {
					status: 422,
					headers: { 'content-type': 'application/json' }
				})
			)
		);

		await expect(startImport('pi-a', '/elsewhere')).rejects.toMatchObject({
			status: 422,
			body: { detail: 'path is outside the configured import roots' }
		});
	});
});

describe('term lists', () => {
	const summary = {
		name: 'program',
		version: 2,
		term_count: 3,
		notes: null,
		created_at: '2026-10-27T09:00:00Z',
		retired_at: null
	};

	it('lists, reads, saves, and retires lists at their exact paths', async () => {
		const fetchMock = vi
			.fn<typeof fetch>()
			.mockResolvedValueOnce(jsonResponse({ items: [summary] }))
			.mockResolvedValueOnce(jsonResponse({ ...summary, version: 1, terms: ['Tallis'] }))
			.mockResolvedValueOnce(jsonResponse({ ...summary, version: 3, terms: ['Tallis', 'Brae'] }))
			.mockResolvedValueOnce(jsonResponse({ ...summary, retired_at: '2026-10-27T10:00:00Z' }));
		vi.stubGlobal('fetch', fetchMock);

		await expect(getTermLists(true)).resolves.toEqual({ items: [summary] });
		expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/scrub-terms?include_retired=true');

		await expect(getTermList('program', 1)).resolves.toMatchObject({ terms: ['Tallis'] });
		expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/scrub-terms/program?version=1');

		await expect(saveTermList('program', ['Tallis', 'Brae'], null)).resolves.toMatchObject({
			version: 3
		});
		expect(fetchMock.mock.calls[2]?.[0]).toBe('/api/v1/scrub-terms/program');
		expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
			method: 'PUT',
			body: JSON.stringify({ terms: ['Tallis', 'Brae'], notes: null })
		});

		await expect(retireTermList('program')).resolves.toMatchObject({
			retired_at: '2026-10-27T10:00:00Z'
		});
		expect(fetchMock.mock.calls[3]?.[0]).toBe('/api/v1/scrub-terms/program/retire');
		expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({ method: 'POST' });
	});

	it('rejects a list without its terms', async () => {
		vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(summary)));
		await expect(getTermList('program')).rejects.toMatchObject({ kind: 'invalid-contract' });
	});

	it('sends the list reference with an export only when one is chosen', async () => {
		const record = {
			schema_version: 1,
			case: { id: 't', version: 1, redaction: { scrub_version: 'x', term_count: 0, manifest: {} } },
			candidate: {},
			judge: {},
			digest: 'd'
		};
		const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => jsonResponse(record));
		vi.stubGlobal('fetch', fetchMock);

		await exportTask('t', 1, ['a']);
		expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
			version: 1,
			terms: ['a']
		});
		await exportTask('t', 1, [], { name: 'program', version: 2 });
		expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
			version: 1,
			terms: [],
			term_list: { name: 'program', version: 2 }
		});
	});
});
