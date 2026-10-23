// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { BundlesResponse, BundleSummary, RunSummary } from '$lib/api/types';
import Page from './+page.svelte';
import { _filtersFor, _typeFrom, _viewFrom, type BundleView } from './+page';

const human: BundleSummary = {
	id: 'bundle-1',
	revision: 2,
	summary: 'Refund handling',
	objective: 'Resolve a customer refund request',
	objective_type: 'unknown',
	goal: 'Refund the second item',
	status: 'reviewed',
	origin: 'human',
	producer: 'web',
	run_id: null,
	item_count: 3,
	conversation_ids: ['conversation-a'],
	updated_at: '2026-10-19T10:00:00Z'
};

const proposed: BundleSummary = {
	id: 'bundle-2',
	revision: 1,
	summary: 'Refund request and the offered resolution',
	objective: 'Resolve a customer refund request',
	objective_type: 'unknown',
	goal: 'Get the second item refunded',
	status: 'draft',
	origin: 'generated',
	producer: 'benchwarmer-harness/propose-bundles@0.0.1 anthropic/claude-sonnet-5-5',
	run_id: 'propose-bundles-2026-10-19T10-00-00-000Z',
	item_count: 2,
	conversation_ids: ['conversation-a'],
	updated_at: '2026-10-19T11:00:00Z'
};

function renderPage(
	bundles: Promise<BundlesResponse>,
	view: BundleView = 'all',
	proposedCount: Promise<number | null> | null = Promise.resolve(null),
	run: string | null = null,
	runs: Promise<RunSummary[]> | null = null
) {
	return render(Page, {
		props: { data: { view, run, type: null, bundles, proposedCount, runs }, params: {} }
	});
}

const runSummary: RunSummary = {
	run_id: proposed.run_id ?? '',
	workflow: 'propose-bundles',
	provider: 'anthropic',
	model: 'claude-sonnet-5-5',
	thinking_level: null,
	base_url_override: null,
	started_at: '2026-10-19T10:00:00Z',
	finished_at: '2026-10-19T10:00:29Z',
	input_count: 1,
	bundle_count: 1,
	total_tokens: 55810,
	estimated_cost: 0.136,
	pricing_source: 'pi-ai model catalog estimate'
};

afterEach(cleanup);

describe('bundle list page', () => {
	it('reads the view from the URL and maps it to API filters', () => {
		expect(_viewFrom(new URLSearchParams(''))).toBe('all');
		expect(_viewFrom(new URLSearchParams('view=proposed'))).toBe('proposed');
		expect(_viewFrom(new URLSearchParams('view=nonsense'))).toBe('all');
		expect(_filtersFor('proposed')).toEqual({ origin: 'generated', status: 'draft' });
		expect(_filtersFor('rejected')).toEqual({ status: 'rejected' });
		expect(_filtersFor('all')).toEqual({});
		expect(_filtersFor('proposed', 'run-1')).toEqual({
			origin: 'generated',
			status: 'draft',
			runId: 'run-1'
		});
	});

	it('names the run being shown and links back to every run', async () => {
		const { findByText, getByRole, queryByText } = renderPage(
			Promise.resolve({ items: [proposed] }),
			'proposed',
			null,
			'propose-bundles-2026-10-19T10-00-00-000Z'
		);

		expect(await findByText('propose-bundles-2026-10-19T10-00-00-000Z')).toBeTruthy();
		// Cost and token figures belong to the runs page, not the list.
		expect(queryByText(/tokens/)).toBeNull();
		expect(getByRole('link', { name: 'Show every run' }).getAttribute('href')).toBe(
			'/bundles?view=proposed'
		);
		expect(getByRole('link', { name: /Proposed drafts/ }).getAttribute('href')).toBe(
			'/bundles?view=proposed&run=propose-bundles-2026-10-19T10-00-00-000Z'
		);
		// Opening a bundle keeps the view, so its previous/next arrows step through this list.
		expect(getByRole('link', { name: proposed.summary }).getAttribute('href')).toBe(
			'/bundles/bundle-2?view=proposed&run=propose-bundles-2026-10-19T10-00-00-000Z'
		);
	});

	it('reads the type filter from the URL and shows the type of work per bundle', async () => {
		expect(_typeFrom(new URLSearchParams('type=bug'))).toBe('bug');
		expect(_typeFrom(new URLSearchParams('type=chores'))).toBeNull();
		expect(_filtersFor('proposed', null, 'bug')).toEqual({
			origin: 'generated',
			status: 'draft',
			objectiveType: 'bug'
		});

		const { findByRole, getByRole, getAllByText } = render(Page, {
			props: {
				data: {
					view: 'all',
					run: null,
					type: 'bug',
					runs: null,
					bundles: Promise.resolve({
						items: [{ ...human, objective_type: 'bug' as const }, proposed]
					}),
					proposedCount: Promise.resolve(null)
				},
				params: {}
			}
		});

		expect(await findByRole('columnheader', { name: 'Type' })).toBeTruthy();
		// The filter option, the desktop cell, and the folded phone line name the type; unknown stays quiet.
		expect(getAllByText(/^Bug/).length).toBe(3);
		// The unknown row shows its type only in the desktop cell (plus the filter option).
		expect(getAllByText('Unknown').length).toBe(2);
		const filter = getByRole('combobox', { name: 'Type of work' }) as HTMLSelectElement;
		expect(filter.value).toBe('bug');
		// Other links keep the type so the filter survives changing views.
		expect(getByRole('link', { name: /Proposed drafts/ }).getAttribute('href')).toBe(
			'/bundles?view=proposed&type=bug'
		);
	});

	it('shows who produced each bundle and counts proposals awaiting review', async () => {
		const { findByRole, getByRole, getByText, getAllByText, getAllByTitle, queryByText } =
			renderPage(
				Promise.resolve({ items: [{ ...proposed, summary: '' }, human] }),
				'all',
				Promise.resolve(1)
			);

		expect(await findByRole('link', { name: 'Refund handling' })).toBeTruthy();
		// Without a summary the title falls back to the objective, never the goal.
		expect(await findByRole('link', { name: 'Resolve a customer refund request' })).toBeTruthy();
		// The objective groups bundles: a column at desktop width, a folded line at phone width.
		expect(getAllByText('Resolve a customer refund request').length).toBe(5);
		expect(getByText('Human')).toBeTruthy();
		// The origin cell at desktop width and the folded line at phone width both name the producer.
		const cells = getAllByTitle(proposed.producer);
		expect(cells.length).toBe(2);
		expect(cells.every((cell) => cell.textContent?.includes('Proposed'))).toBe(true);
		expect(getAllByText('claude-sonnet-5-5').length).toBe(1);
		// The goal is metadata for the editor, not a list column.
		expect(queryByText('Get the second item refunded')).toBeNull();
		const views = getByRole('navigation', { name: 'Bundle views' });
		const link = getByRole('link', { name: /Proposed drafts/ });
		expect(link.getAttribute('href')).toBe('/bundles?view=proposed');
		expect(views.querySelector('.view-links__count')?.textContent).toBe('1');
		expect(getByRole('link', { name: 'All bundles' }).getAttribute('aria-current')).toBe('page');
	});

	it('groups proposed drafts by run, naming each run and linking to it', async () => {
		const older: BundleSummary = {
			...proposed,
			id: 'bundle-3',
			summary: 'An older proposal',
			run_id: 'propose-bundles-2026-10-18T09-00-00-000Z'
		};
		const { findAllByRole, getByRole, getAllByRole } = renderPage(
			Promise.resolve({ items: [proposed, older] }),
			'proposed',
			null,
			null,
			Promise.resolve([runSummary])
		);

		const headings = await findAllByRole('columnheader', { name: /Run / });
		expect(headings.length).toBe(2);
		expect(headings[0].textContent).toContain('claude-sonnet-5-5');
		expect(headings[0].textContent).toContain('1 draft');
		// The second run has no record, so it is named by its id alone.
		expect(headings[1].textContent).not.toContain('claude-sonnet-5-5');
		expect(getByRole('link', { name: 'Run 2026-10-19T10-00-00-000Z' }).getAttribute('href')).toBe(
			'/runs/propose-bundles-2026-10-19T10-00-00-000Z'
		);
		expect(getAllByRole('link', { name: 'Only this run' })[1].getAttribute('href')).toBe(
			'/bundles?view=proposed&run=propose-bundles-2026-10-18T09-00-00-000Z'
		);
		expect(getByRole('link', { name: 'An older proposal' })).toBeTruthy();
	});

	it('explains the proposed view and its empty state separately', async () => {
		const { findByRole, getByText } = renderPage(Promise.resolve({ items: [] }), 'proposed', null);

		expect(await findByRole('heading', { name: 'No proposed drafts to review' })).toBeTruthy();
		expect(getByText(/Nothing here is approved until a person saves it/)).toBeTruthy();
	});

	it('shows a recovery path when the API fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = renderPage(request);

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('Bundles unavailable')).toBeTruthy();
	});
});
