// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { ConversationsResponse } from '$lib/api/types';
import { summary } from '$lib/conversations/fixtures';
import Page from './+page.svelte';

const noFilters = { q: '', sourceId: '', offset: 0 };

function renderPage(
	conversations: Promise<ConversationsResponse>,
	filters: { q: string; sourceId: string; offset: number } = noFilters
) {
	return render(Page, {
		props: {
			data: { filters, conversations, sources: Promise.resolve(null) },
			params: {}
		}
	});
}

afterEach(cleanup);

describe('conversation list page', () => {
	it('lists conversations with captured metadata', async () => {
		const { findByRole, getByText } = renderPage(
			Promise.resolve({ items: [summary], total: 1, limit: 50, offset: 0 })
		);

		expect(await findByRole('link', { name: 'Refund investigation' })).toBeTruthy();
		expect(getByText('1 conversation')).toBeTruthy();
		expect(getByText('Mar 1, 2026, 11:18 AM UTC')).toBeTruthy();
		expect(getByText('2 branches')).toBeTruthy();
		expect(getByText('Capture: usage unknown')).toBeTruthy();
	});

	it('shows anchored, highlighted search matches', async () => {
		const hit = {
			event_id: 'e1',
			block_id: 'e1:b0',
			field: 'text',
			snippet: 'I need a refund for the second item.'
		};
		const { findByRole, container, getByText } = renderPage(
			Promise.resolve({
				items: [{ ...summary, match_count: 3, matches: [hit] }],
				total: 1,
				limit: 50,
				offset: 0
			}),
			{ ...noFilters, q: 'refund' }
		);

		const matches = await findByRole('list', { name: 'Matches in Refund investigation' });
		expect(matches.querySelector('a')?.getAttribute('href')).toBe(
			'/conversations/conversation-a?q=refund#e1'
		);
		expect(container.querySelector('mark')?.textContent).toBe('refund');
		expect(getByText('2 more matches in this conversation')).toBeTruthy();
	});

	it('distinguishes an empty library from a search with no matches', async () => {
		const empty = { items: [], total: 0, limit: 50, offset: 0 };
		const library = renderPage(Promise.resolve(empty));
		expect(await library.findByRole('heading', { name: 'No conversations imported' })).toBeTruthy();
		cleanup();

		const search = renderPage(Promise.resolve(empty), { ...noFilters, q: 'missing' });
		expect(await search.findByRole('heading', { name: 'No matching conversations' })).toBeTruthy();
	});

	it('shows a recovery path when the API fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = renderPage(request);

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('Conversations unavailable')).toBeTruthy();
	});
});
