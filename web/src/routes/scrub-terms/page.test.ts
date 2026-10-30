// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { TermListsResponse } from '$lib/api/types';
import Page from './+page.svelte';

afterEach(cleanup);

function renderPage(lists: Promise<TermListsResponse>) {
	return render(Page, { props: { data: { lists }, params: {} } });
}

describe('scrub terms page', () => {
	it('announces a stable loading state', () => {
		const { getByRole } = renderPage(new Promise(() => undefined));

		expect(getByRole('heading', { name: 'Scrub terms' })).toBeTruthy();
		expect(getByRole('heading', { name: 'Loading term lists' })).toBeTruthy();
	});

	it('hands the loaded lists to the manager', async () => {
		const { findByRole, getByText } = renderPage(
			Promise.resolve({
				items: [
					{
						name: 'program',
						version: 1,
						term_count: 2,
						notes: null,
						created_at: '2026-10-27T09:00:00Z',
						retired_at: null
					}
				]
			})
		);

		expect(await findByRole('rowheader', { name: 'program' })).toBeTruthy();
		expect(getByText('1 term list')).toBeTruthy();
	});

	it('shows a recovery path when the API fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = renderPage(request);

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('Term lists unavailable')).toBeTruthy();
	});
});
