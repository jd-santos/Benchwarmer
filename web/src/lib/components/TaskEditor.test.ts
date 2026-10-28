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
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(respond(200, record));
		vi.stubGlobal('fetch', fetchMock);
		const { queryByRole } = render(TaskEditor, { props: { detail: task } });
		expect(queryByRole('button', { name: 'Export case record' })).toBeNull();
		cleanup();

		const view = render(TaskEditor, { props: { detail: approved } });
		await user.type(view.getByLabelText('Terms to scrub'), 'Acme');
		await user.click(view.getByRole('button', { name: 'Export case record' }));

		expect(await view.findByText('Scrubbed 2 term')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/tasks/task-1/export');
		expect(JSON.parse(String(init?.body))).toEqual({ version: 1, terms: ['Acme'] });
		expect(view.getByRole('button', { name: 'Download JSON' })).toBeTruthy();
	});

	it('refuses approval when a criterion needs more than the reconstruction provides', async () => {
		const user = userEvent.setup();
		const { getByRole, getAllByRole, getByText, queryByText, getByLabelText } = render(TaskEditor, {
			props: { detail: task }
		});

		// As a draft the gap is informational: the task is still analysis-only evidence.
		await user.click(getAllByRole('checkbox', { name: 'Live tools' })[0]);
		expect(getByText(/Analysis-only at this reconstruction level/)).toBeTruthy();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(false);

		await user.type(getByLabelText('Reviewed by'), 'jd');
		await user.click(getByRole('radio', { name: 'Approved' }));

		expect(
			getByText(/Cannot approve as a runnable test: 1 criterion needs live tools/)
		).toBeTruthy();
		expect(getByText(/Needs live tools, which "Prompt and context" cannot provide/)).toBeTruthy();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(true);

		// A fixture-backed reconstruction provides tools, so the block lifts.
		await user.selectOptions(getByLabelText('Reconstruction'), 'fixture_backed');
		expect(queryByText(/Cannot approve as a runnable test/)).toBeNull();
		expect(getByRole('button', { name: 'Save version' }).hasAttribute('disabled')).toBe(false);
	});

	it('treats a coding task as needing a workspace and shows the assigned partition', async () => {
		const user = userEvent.setup();
		const assigned = { ...task, partition: 'holdout' as const, partition_assignment_id: 'p-1' };
		const { getByRole, getByText, container } = render(TaskEditor, {
			props: { detail: assigned }
		});

		expect(container.querySelector('[data-partition]')?.textContent).toContain('Holdout');
		expect(container.querySelector('select#task-partition')).toBeNull();

		await user.click(getByRole('radio', { name: 'Coding' }));
		expect(getByText(/A coding task needs a workspace/)).toBeTruthy();
		expect(getByText('Analysis only')).toBeTruthy();
	});

	it('places a server-side needs issue on its criterion', async () => {
		const user = userEvent.setup();
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				respond(422, {
					issues: [
						{
							code: 'needs_exceed_reconstruction',
							message: "Criterion 'offers-refund-path' needs tools.",
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

		const issue = await findByText("Criterion 'offers-refund-path' needs tools.");
		expect(issue.closest('.criterion')).not.toBeNull();
	});
});
