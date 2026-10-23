// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { RunSummary } from '$lib/api/types';
import Page from './+page.svelte';

const proposeRun: RunSummary = {
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
};

// A workflow the UI has no label for yet: it still lists, with its id as written.
const judgeRun: RunSummary = {
	...proposeRun,
	run_id: 'judge-trials-2026-10-20T09-00-00-000Z',
	workflow: 'judge-trials',
	started_at: '2026-10-20T09:00:00Z',
	finished_at: '2026-10-20T09:04:12Z',
	bundle_count: 0,
	total_tokens: 1200,
	estimated_cost: 0.004
};

afterEach(cleanup);

describe('runs page', () => {
	it('lists every run with its workflow, usage, and a way to the output', async () => {
		const { findByRole, getAllByRole, getByRole, getByText, container } = render(Page, {
			props: {
				data: { workflow: null, runs: Promise.resolve({ items: [judgeRun, proposeRun] }) },
				params: {}
			}
		});

		expect(await findByRole('heading', { name: 'Runs', level: 1 })).toBeTruthy();
		expect(container.querySelector('[data-run-totals]')?.textContent).toContain('2 runs');
		expect(container.querySelector('[data-run-totals]')?.textContent).toContain('57,010 tokens');
		expect(getByRole('cell', { name: 'Propose bundles' })).toBeTruthy();
		expect(getByRole('cell', { name: 'judge-trials' })).toBeTruthy();
		expect(getAllByRole('link', { name: '2 bundles' })[0].getAttribute('href')).toBe(
			'/bundles?view=proposed&run=propose-bundles-2026-10-19T10-00-00-000Z'
		);
		expect(getByText('4m 12s')).toBeTruthy();
		// Two workflows are present, so the reader can narrow to one.
		const workflows = getByRole('navigation', { name: 'Workflows' });
		expect(workflows.querySelector('a[href="/runs?workflow=judge-trials"]')).toBeTruthy();
	});

	it('explains the empty state without implying runs start on their own', async () => {
		const { findByRole, getByText, queryByRole } = render(Page, {
			props: { data: { workflow: null, runs: Promise.resolve({ items: [] }) }, params: {} }
		});

		expect(await findByRole('heading', { name: 'No runs recorded' })).toBeTruthy();
		expect(getByText(/runs a harness workflow by hand/)).toBeTruthy();
		expect(queryByRole('navigation', { name: 'Workflows' })).toBeNull();
	});

	it('shows a recovery path when the API fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole } = render(Page, {
			props: { data: { workflow: null, runs: request }, params: {} }
		});

		expect(await findByRole('alert')).toBeTruthy();
	});
});
