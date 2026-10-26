// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { TasksResponse } from '$lib/api/types';
import { taskSummary } from '$lib/tasks/fixtures';
import Page from './+page.svelte';
import { _viewFrom } from './+page';

afterEach(cleanup);

function renderPage(
	tasks: Promise<TasksResponse>,
	view = 'all' as const,
	bundle: string | null = null
) {
	return render(Page, { props: { data: { view, bundle, tasks }, params: {} } });
}

describe('tasks page', () => {
	it('lists each task with its bundle, kind, status, and criterion count', async () => {
		const approved = {
			...taskSummary,
			id: 'task-2',
			summary: 'Alert burst traced to one re-fired event',
			status: 'approved' as const,
			kind: 'agent' as const,
			partition: 'development' as const,
			criterion_count: 3
		};
		const { findByRole, getByRole, getAllByText } = renderPage(
			Promise.resolve({ items: [taskSummary, approved] })
		);

		const table = await findByRole('table');
		expect(table.querySelectorAll('tbody tr').length).toBe(2);
		expect(getByRole('link', { name: 'Refund request and the offered resolution' })).toBeTruthy();
		expect(getAllByText(/Bundle revision 2/).length).toBe(2);
		expect(getAllByText('Approved').length).toBeGreaterThan(0);
		expect(table.textContent).toContain('development');
		expect(table.textContent).toContain('3');
	});

	it('shows an empty state and the bundle filter note', async () => {
		const { findByRole, getByText } = renderPage(Promise.resolve({ items: [] }), 'all', 'bundle-1');

		expect(await findByRole('heading', { name: 'No tasks yet' })).toBeTruthy();
		expect(getByText('Showing tasks prepared from one bundle.')).toBeTruthy();
	});

	it('reads a view from the URL and falls back to all', () => {
		expect(_viewFrom(new URLSearchParams('view=approved'))).toBe('approved');
		expect(_viewFrom(new URLSearchParams('view=nonsense'))).toBe('all');
	});
});
