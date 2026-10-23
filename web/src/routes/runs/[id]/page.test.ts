// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import { proposedRun } from '$lib/bundles/fixtures';
import Page from './+page.svelte';

afterEach(cleanup);

describe('run page', () => {
	it('shows the run, its usage by model, and what each input produced', async () => {
		const run = {
			...proposedRun,
			inputs: [
				...proposedRun.inputs,
				{
					id: 'conversation-b',
					kind: 'conversation' as const,
					status: 'unanswered' as const,
					reason: 'no headings',
					bundle_ids: [],
					usage: { models: {}, tools: {} }
				}
			]
		};
		const { findByRole, getByRole, getByText, getAllByText } = render(Page, {
			props: { data: { run: Promise.resolve(run) }, params: { id: run.run_id } }
		});

		expect(
			await findByRole('heading', { name: 'Propose bundles · 2026-10-19T10-00-00-000Z', level: 1 })
		).toBeTruthy();
		expect(getByText('55,810 tokens')).toBeTruthy();
		expect(getByText(/about \$0\.136 \(pi-ai model catalog estimate\)/)).toBeTruthy();
		expect(getByRole('link', { name: '2 bundles proposed' }).getAttribute('href')).toBe(
			'/bundles?view=proposed&run=propose-bundles-2026-10-19T10-00-00-000Z'
		);
		// Usage rows are keyed as the record keys them.
		expect(getByRole('rowheader', { name: 'anthropic/claude-sonnet-5-5' })).toBeTruthy();
		// Inputs link to their conversation and to each bundle they produced.
		expect(getByRole('link', { name: 'conversation-a' }).getAttribute('href')).toBe(
			'/conversations/conversation-a'
		);
		expect(getByRole('link', { name: 'bundle-3' }).getAttribute('href')).toBe('/bundles/bundle-3');
		expect(getAllByText('Nothing produced').length).toBe(2);
		expect(getByText('no headings')).toBeTruthy();
		expect(getAllByText('Nothing').length).toBe(1);
	});

	it('shows a recovery path when the run cannot be read', async () => {
		const request = Promise.reject(new Error('missing'));
		request.catch(() => undefined);
		const { findByRole } = render(Page, {
			props: { data: { run: request }, params: { id: 'run-x' } }
		});

		expect(await findByRole('alert')).toBeTruthy();
	});
});
