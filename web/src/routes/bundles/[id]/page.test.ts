// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { BundleSummary } from '$lib/api/types';
import { proposedBundle } from '$lib/bundles/fixtures';
import Page from './+page.svelte';
import { _navigationFor } from './+page';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

afterEach(cleanup);

const summaries: BundleSummary[] = ['bundle-1', 'bundle-2', 'bundle-3'].map((id) => ({
	id,
	revision: 1,
	summary: `Summary ${id}`,
	objective: 'Resolve a customer refund request',
	goal: '',
	status: 'draft',
	origin: 'generated',
	producer: proposedBundle.producer,
	run_id: proposedBundle.provenance?.run_id ?? null,
	item_count: 2,
	conversation_ids: ['conversation-a'],
	updated_at: '2026-10-19T11:00:00Z'
}));

describe('bundle page navigation', () => {
	it('finds the neighbours of a bundle in the list it was opened from', () => {
		const middle = _navigationFor(summaries, 'bundle-2', 'proposed', null);
		expect(middle).toMatchObject({
			position: 2,
			total: 3,
			previousId: 'bundle-1',
			nextId: 'bundle-3'
		});
		const last = _navigationFor(summaries, 'bundle-3', 'all', 'run-1');
		expect(last).toMatchObject({ position: 3, previousId: 'bundle-2', nextId: null, run: 'run-1' });
		// A bundle that left the list (reviewed, say) keeps the way back but has no arrows.
		expect(_navigationFor(summaries, 'bundle-9', 'proposed', null)).toMatchObject({
			position: null,
			total: 3,
			previousId: null,
			nextId: null
		});
	});

	it('links back to the view and to the previous and next bundle in it', async () => {
		const navigation = _navigationFor(summaries, 'bundle-2', 'proposed', 'run-1');
		const { findByRole, getByRole, getByText } = render(Page, {
			props: {
				data: {
					revision: null,
					bundle: Promise.resolve(proposedBundle),
					navigation: Promise.resolve(navigation)
				},
				params: { id: 'bundle-2' }
			}
		});

		const nav = await findByRole('navigation', { name: 'Bundles in this view' });
		expect(nav).toBeTruthy();
		expect(getByText('2 of 3')).toBeTruthy();
		expect(getByRole('link', { name: '← Proposed drafts' }).getAttribute('href')).toBe(
			'/bundles?view=proposed&run=run-1'
		);
		expect(getByRole('link', { name: '← Previous' }).getAttribute('href')).toBe(
			'/bundles/bundle-1?view=proposed&run=run-1'
		);
		expect(getByRole('link', { name: 'Next →' }).getAttribute('href')).toBe(
			'/bundles/bundle-3?view=proposed&run=run-1'
		);
	});
});
