import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClientError, getHealth, getSources } from './client';
import type { HealthResponse, SourcesResponse } from './types';

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
