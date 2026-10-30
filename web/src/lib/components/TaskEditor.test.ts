// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { task, taskDraft } from '$lib/tasks/fixtures';
import TaskEditor from './TaskEditor.svelte';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({
	invalidateAll: vi.fn(),
	goto: (...args: unknown[]) => goto(...args)
}));

afterEach(() => {
	cleanup();
	vi.unstubAllGlobals();
	goto.mockReset();
});

function respond(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('task editor', () => {
	it('shows the split around the cut point and moves it without a round trip', async () => {
		const user = userEvent.setup();
		const { getByRole, getAllByRole, getByText } = render(TaskEditor, {
			props: { detail: task }
		});

		expect(getByRole('heading', { name: /Candidate sees/ })).toBeTruthy();
		expect(getByRole('heading', { name: /Judge only/ })).toBeTruthy();
		const radios = getAllByRole('radio', { name: /Candidate sees through/ });
		expect(radios.length).toBe(5);
		expect((radios[2] as HTMLInputElement).checked).toBe(true);
		expect(getByText('Cut point: the candidate answers next')).toBeTruthy();
		// The cited answer sits on the judge side, marked by its evidence role.
		expect(getByText('result')).toBeTruthy();

		await user.click(radios[0]);

		const candidate = getByRole('heading', { name: /Candidate sees/ }).closest('.split-column');
		expect(candidate?.querySelectorAll('.split-turn').length).toBe(1);
		expect(
			getByText('The cut point moved. Save to refresh the flags before approving.')
		).toBeTruthy();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(false);
	});

	it('blocks approval until every flag is accepted and a reviewer is named', async () => {
		const user = userEvent.setup();
		const flagged = {
			...task,
			flags: [
				{
					id: 'answer_before_cut:1',
					code: 'answer_before_cut',
					message: 'Item 2 is cited as a result but lies before the cut point.',
					event_id: 'e2',
					criterion_id: null,
					item_index: 1
				}
			]
		};
		const { getByRole, getByLabelText, getByText, queryByText } = render(TaskEditor, {
			props: { detail: flagged }
		});

		await user.click(getByRole('radio', { name: 'Approved' }));

		expect(
			getByText('1 leakage flag still open. Check each one above or move the cut.')
		).toBeTruthy();
		expect(getByText('Approval records who checked the candidate section for leaks.')).toBeTruthy();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(true);

		await user.click(getByRole('checkbox', { name: /Item 2 is cited as a result/ }));
		await user.type(getByLabelText('Reviewed by'), 'jd');

		expect(queryByText(/leakage flag still open/)).toBeNull();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(false);
	});

	it('saves a new version with the accepted flags and a review timestamp', async () => {
		const user = userEvent.setup();
		const saved = { ...task, version: 2, latest_version: 2 };
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(respond(200, saved));
		vi.stubGlobal('fetch', fetchMock);
		const { getByRole, getByLabelText, findByText } = render(TaskEditor, {
			props: { detail: task }
		});

		await user.type(getByLabelText('Reviewed by'), 'jd');
		await user.click(getByRole('radio', { name: 'Approved' }));
		await user.click(getByRole('button', { name: 'Save version' }));

		expect(await findByText('Saved version 2.')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/tasks/task-1');
		const body = JSON.parse(String(init?.body));
		expect(body.base_version).toBe(1);
		expect(body.document.status).toBe('approved');
		expect(body.document.leakage_review.by).toBe('jd');
		expect(body.document.leakage_review.accepted_flags).toEqual([]);
		expect(typeof body.document.leakage_review.at).toBe('string');
		expect(body.document.criteria[0].reviewer_label).toBe('pass');
	});

	it('creates a task from a draft and opens it', async () => {
		const user = userEvent.setup();
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(respond(201, task));
		vi.stubGlobal('fetch', fetchMock);
		const { getByRole, getByLabelText } = render(TaskEditor, {
			props: { draft: taskDraft }
		});

		await user.click(getByRole('button', { name: 'Add criterion' }));
		await user.type(
			getByLabelText('Statement 1'),
			'Asks for the order number before promising a refund.'
		);
		await user.click(getByRole('button', { name: 'Create task' }));

		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/tasks');
		expect(init?.method).toBe('POST');
		const body = JSON.parse(String(init?.body));
		expect(body.document.criteria[0].id).toBe('asks-for-the-order-number');
		expect(body.document.criteria[0].method).toBe('human');
		expect(body.document.leakage_review).toBeNull();
		expect(goto).toHaveBeenCalledWith('/tasks/task-1');
	});

	it('reports a criterion issue on the criterion it concerns', async () => {
		const user = userEvent.setup();
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				respond(422, {
					issues: [
						{
							code: 'unaccepted_leakage_flag',
							message: 'Quotes the answer.',
							criterion_id: 'offers-refund-path'
						}
					]
				})
			)
		);
		const { getByRole, getByLabelText, findByText } = render(TaskEditor, {
			props: { detail: task }
		});

		await user.type(getByLabelText('Notes for the judge'), 'x');
		await user.click(getByRole('button', { name: 'Save version' }));

		expect(await findByText('Quotes the answer.')).toBeTruthy();
	});

	it('offers export only for an approved version and shows the manifest', async () => {
		const user = userEvent.setup();
		const approved = {
			...task,
			document: {
				...task.document,
				status: 'approved' as const,
				leakage_review: { by: 'jd', at: '2026-10-26T10:00:00Z', accepted_flags: [], notes: null }
			}
		};
		const record = {
			schema_version: 1,
			case: {
				id: 'task-1',
				version: 1,
				redaction: {
					scrub_version: 'benchwarmer.anonymize-1',
					term_count: 1,
					manifest: { term: 2 }
				}
			},
			candidate: { messages: [] },
			judge: { historical: [] },
			digest: 'abcdef1234567890'
		};
		const fetchMock = vi
			.fn<typeof fetch>()
			.mockImplementation(async (input) =>
				String(input).endsWith('/scrub-terms') ? respond(200, { items: [] }) : respond(200, record)
			);
		vi.stubGlobal('fetch', fetchMock);
		const { queryByRole } = render(TaskEditor, { props: { detail: task } });
		expect(queryByRole('button', { name: 'Export case record' })).toBeNull();
		expect(fetchMock).not.toHaveBeenCalled();
		cleanup();

		const view = render(TaskEditor, { props: { detail: approved } });
		expect(await view.findByText(/No stored lists yet/)).toBeTruthy();
		expect((view.getByLabelText('Stored term list') as HTMLSelectElement).disabled).toBe(true);
		await user.type(view.getByLabelText('Terms to scrub'), 'Acme');
		await user.click(view.getByRole('button', { name: 'Export case record' }));

		expect(await view.findByText('Scrubbed 2 term')).toBeTruthy();
		const exportCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/export'))!;
		expect(exportCall[0]).toBe('/api/v1/tasks/task-1/export');
		expect(JSON.parse(String(exportCall[1]?.body))).toEqual({ version: 1, terms: ['Acme'] });
		expect(view.getByRole('button', { name: 'Download JSON' })).toBeTruthy();
	});

	it('exports with a stored term list pinned to the version shown', async () => {
		const user = userEvent.setup();
		const approved = {
			...task,
			document: {
				...task.document,
				status: 'approved' as const,
				leakage_review: { by: 'jd', at: '2026-10-26T10:00:00Z', accepted_flags: [], notes: null }
			}
		};
		const lists = {
			items: [
				{
					name: 'program',
					version: 3,
					term_count: 12,
					notes: 'Customer names',
					created_at: '2026-10-27T09:00:00Z',
					retired_at: null
				}
			]
		};
		const record = {
			schema_version: 1,
			case: {
				id: 'task-1',
				version: 1,
				redaction: {
					scrub_version: 'benchwarmer.anonymize-1',
					term_count: 13,
					term_list: { name: 'program', version: 3 },
					manifest: { term: 4, hostname: 1 }
				}
			},
			candidate: {},
			judge: {},
			digest: 'fedcba9876543210'
		};
		const fetchMock = vi
			.fn<typeof fetch>()
			.mockImplementation(async (input) =>
				String(input).endsWith('/scrub-terms') ? respond(200, lists) : respond(200, record)
			);
		vi.stubGlobal('fetch', fetchMock);
		const view = render(TaskEditor, { props: { detail: approved } });

		await view.findByRole('option', { name: 'program' });
		await user.selectOptions(view.getByLabelText('Stored term list'), 'program');
		expect(view.getByText(/Version 3 · 12 terms · Customer names/)).toBeTruthy();
		await user.type(view.getByLabelText('Terms to scrub'), 'Extra');
		await user.click(view.getByRole('button', { name: 'Export case record' }));

		expect(await view.findByText('Scrubbed 4 term, 1 hostname')).toBeTruthy();
		expect(view.getByText(/List program version 3/)).toBeTruthy();
		const exportCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/export'))!;
		expect(JSON.parse(String(exportCall[1]?.body))).toEqual({
			version: 1,
			terms: ['Extra'],
			term_list: { name: 'program', version: 3 }
		});
		// Only the list's name and version travel; its terms are never fetched here.
		expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/scrub-terms/'))).toBe(false);
	});
});
