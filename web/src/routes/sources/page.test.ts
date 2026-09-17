// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { SourcesResponse } from '$lib/api/types';
import Page from './+page.svelte';

const sources: SourcesResponse = {
	items: [
		{
			id: 'source-a',
			kind: 'hermes',
			display_name: 'Hermes profile',
			last_successful_import_at: '2026-09-16T11:55:02Z',
			coverage: {
				sessions: 'available',
				token_usage: 'partial',
				request_ids: 'unavailable',
				actual_charges: 'unknown',
				list_price_estimates: 'unavailable',
				subscription_expense: 'unknown',
				quota: 'unknown',
				credits: 'unknown',
				prompts: 'partial',
				classifications: 'available'
			}
		},
		{
			id: 'source-b',
			kind: 'codex',
			display_name: 'Codex profile',
			last_successful_import_at: null,
			coverage: {
				sessions: 'unknown',
				token_usage: 'unknown',
				request_ids: 'unknown',
				actual_charges: 'unknown',
				list_price_estimates: 'unknown',
				subscription_expense: 'unknown',
				quota: 'unknown',
				credits: 'unknown',
				prompts: 'unknown',
				classifications: 'unknown'
			}
		}
	]
};

function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((resolvePromise) => {
		resolve = resolvePromise;
	});
	return { promise, resolve };
}

afterEach(cleanup);

describe('source status page', () => {
	it('announces a stable loading state', () => {
		const pending = deferred<SourcesResponse>();
		const { getByRole, getByText } = render(Page, {
			props: { data: { sources: pending.promise }, params: {} }
		});

		expect(getByRole('heading', { name: 'Sources' })).toBeTruthy();
		expect(getByRole('heading', { name: 'Loading sources' })).toBeTruthy();
		expect(getByText('Reading source and coverage status…')).toBeTruthy();
	});

	it('shows source freshness and every coverage dimension', async () => {
		const { findByText, getByRole, getAllByText, getByText } = render(Page, {
			props: { data: { sources: Promise.resolve(sources) }, params: {} }
		});

		expect(await findByText('2 sources configured')).toBeTruthy();
		expect(getByRole('heading', { name: 'Hermes profile' })).toBeTruthy();
		expect(getByText('Sep 16, 2026, 11:55 AM UTC')).toBeTruthy();
		expect(getByText('Never imported')).toBeTruthy();
		for (const label of [
			'Sessions',
			'Token usage',
			'Request IDs',
			'Actual charges',
			'List-price estimates',
			'Subscription expense',
			'Quota',
			'Credits',
			'Prompts',
			'Classifications'
		]) {
			expect(getAllByText(label).length).toBe(2);
		}
		expect(getAllByText('Partial').length).toBe(2);
		expect(getAllByText('Unavailable').length).toBe(2);
		expect(getAllByText('Unknown').length).toBe(14);
	});

	it('shows an actionable empty state', async () => {
		const { findByRole, getByText } = render(Page, {
			props: { data: { sources: Promise.resolve({ items: [] }) }, params: {} }
		});

		expect(await findByRole('heading', { name: 'No sources configured' })).toBeTruthy();
		expect(getByText(/Load a fixture or add an importer/)).toBeTruthy();
	});

	it('shows a recovery path when the API fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = render(Page, {
			props: { data: { sources: request }, params: {} }
		});

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('Sources unavailable')).toBeTruthy();
		expect(getByText(/Check that it is running/)).toBeTruthy();
	});
});
