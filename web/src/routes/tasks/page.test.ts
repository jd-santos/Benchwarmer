// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PartitionAssignment, TasksResponse } from '$lib/api/types';
import { partitionAssignment, taskSummary } from '$lib/tasks/fixtures';
import Page from './+page.svelte';
import { _viewFrom } from './+page';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

afterEach(() => {
	cleanup();
	vi.unstubAllGlobals();
});

function renderPage(
	tasks: Promise<TasksResponse>,
	view = 'all' as const,
	bundle: string | null = null,
	partitions: Promise<PartitionAssignment | null> = Promise.resolve(null)
) {
	return render(Page, { props: { data: { view, bundle, tasks, partitions }, params: {} } });
}

describe('tasks page', () => {
	it('lists each task with its bundle, kind, status, partition, and criterion count', async () => {
		const approved = {
			...taskSummary,
			id: 'task-2',
			summary: 'Alert burst traced to one re-fired event',
			status: 'approved' as const,
			kind: 'agent' as const,
			partition: 'development' as const,
			partition_assignment_id: 'partition-1',
			criterion_count: 3
		};
		const analysisOnly = {
			...taskSummary,
			id: 'task-3',
			summary: 'Migration needs the repo to check',
			kind: 'coding' as const,
			analysis_only: true
		};
		const { findByRole, getByRole, getAllByText } = renderPage(
			Promise.resolve({ items: [taskSummary, approved, analysisOnly] })
		);

		const table = await findByRole('table');
		expect(table.querySelectorAll('tbody tr').length).toBe(3);
		expect(getByRole('link', { name: 'Refund request and the offered resolution' })).toBeTruthy();
		expect(getAllByText(/Bundle revision 2/).length).toBe(3);
		expect(getAllByText('Approved').length).toBeGreaterThan(0);
		expect(getByRole('columnheader', { name: 'Partition' })).toBeTruthy();
		// The partition cell on wide screens and the meta line on narrow ones both render.
		const rows = [...table.querySelectorAll('tbody tr')];
		expect(rows[1]!.textContent).toContain('Development');
		expect(rows[0]!.textContent).toContain('Not assigned');
		expect(rows[2]!.textContent).toContain('Analysis only');
		expect(rows[1]!.textContent).not.toContain('Analysis only');
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

	it('shows the latest assignment and assigns partitions by family from a seed and split', async () => {
		const user = userEvent.setup();
		const run = { ...partitionAssignment, id: 'partition-2', seed: 'winter-2', moved_families: 1 };
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
			new Response(JSON.stringify(run), {
				status: 201,
				headers: { 'Content-Type': 'application/json' }
			})
		);
		vi.stubGlobal('fetch', fetchMock);
		const { findByText, getByRole, getByLabelText, container } = renderPage(
			Promise.resolve({ items: [taskSummary] }),
			'all',
			null,
			Promise.resolve(partitionAssignment)
		);

		const latest = await findByText(/Last assigned/);
		expect(latest.textContent).toContain('autumn-1');
		expect(latest.textContent).toContain('5 families across 8 tasks');
		expect(latest.textContent).toContain('3 development (5 tasks)');

		const button = getByRole('button', { name: 'Assign partitions by family' });
		expect(button.hasAttribute('disabled')).toBe(true);
		await user.type(getByLabelText('Seed'), 'winter-2');
		expect(button.hasAttribute('disabled')).toBe(false);

		const holdout = getByLabelText('Holdout') as HTMLInputElement;
		await user.clear(holdout);
		await user.type(holdout, '0.5');
		expect(await findByText(/must add up to 1/)).toBeTruthy();
		expect(button.hasAttribute('disabled')).toBe(true);
		await user.clear(holdout);
		await user.type(holdout, '0.2');

		await user.click(button);

		await waitFor(() => expect(fetchMock).toHaveBeenCalled());
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/tasks/partitions');
		expect(JSON.parse(String(init?.body))).toEqual({
			seed: 'winter-2',
			split: { development: 0.6, calibration: 0.2, holdout: 0.2 },
			scope: { statuses: ['draft', 'approved'] }
		});
		await waitFor(() =>
			expect(container.querySelector('[data-latest-assignment]')?.textContent).toContain('winter-2')
		);
		expect(container.querySelector('[data-latest-assignment]')?.textContent).toContain(
			'1 family changed side'
		);
	});
});
