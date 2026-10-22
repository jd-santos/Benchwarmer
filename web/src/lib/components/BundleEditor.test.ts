// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { bundle, proposedBundle, proposedRun } from '$lib/bundles/fixtures';
import BundleEditor from './BundleEditor.svelte';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));

afterEach(() => {
	cleanup();
	vi.unstubAllGlobals();
});

function respond(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('bundle editor', () => {
	it('shows each cited excerpt, its scope, and the gap before it', () => {
		const { getByText, getByRole } = render(BundleEditor, { props: { detail: bundle } });

		expect(getByRole('heading', { name: 'Untitled bundle', level: 1 })).toBeTruthy();
		expect(getByText('I need a refund for the second item.')).toBeTruthy();
		expect(getByText('Whole message')).toBeTruthy();
		expect(getByText('Selected text')).toBeTruthy();
		expect(getByText('2 events not included')).toBeTruthy();
		expect(getByRole('button', { name: 'Save revision' }).hasAttribute('disabled')).toBe(true);
	});

	it('requires a general objective before review; a goal alone is not enough', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText, getByLabelText } = render(BundleEditor, {
			props: { detail: bundle }
		});

		await user.type(getByLabelText('Goal'), 'Find the duplicate credits');
		await user.click(getByRole('radio', { name: /Reviewed/ }));

		expect(getByText('Add an objective before changing the status.')).toBeTruthy();
		expect(getByRole('button', { name: 'Save revision' }).hasAttribute('disabled')).toBe(true);
	});

	it('saves edits as a new revision against the loaded one', async () => {
		const user = userEvent.setup();
		const saved = {
			...bundle,
			revision: 2,
			latest_revision: 2,
			document: { ...bundle.document, objective: 'Refund handling' }
		};
		const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(respond(200, saved));
		vi.stubGlobal('fetch', fetchMock);
		const { getByRole, getByLabelText, findByText } = render(BundleEditor, {
			props: { detail: bundle }
		});

		await user.type(getByLabelText('Goal'), 'Refund for the second item');
		await user.type(getByLabelText('Objective'), 'Refund handling');
		await user.selectOptions(getByLabelText('Role of item 2'), 'correction');
		await user.click(getByRole('button', { name: 'Save revision' }));

		expect(await findByText('Saved revision 2.')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/bundles/bundle-1');
		const body = JSON.parse(String(init?.body));
		expect(body.base_revision).toBe(1);
		expect(body.document.goal).toBe('Refund for the second item');
		expect(body.document.objective).toBe('Refund handling');
		expect(body.document.items[1].role).toBe('correction');
	});

	it('keeps edits and explains a conflicting save', async () => {
		const user = userEvent.setup();
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(respond(409, { latest_revision: 3 }))
		);
		const { getByRole, getByLabelText, findByRole } = render(BundleEditor, {
			props: { detail: bundle }
		});

		await user.type(getByLabelText('Objective'), 'Mine');
		await user.click(getByRole('button', { name: 'Save revision' }));

		expect((await findByRole('alert')).textContent).toContain('now revision 3');
		expect((getByLabelText('Objective') as HTMLInputElement).value).toBe('Mine');
	});

	it('reports invalid evidence on the item it concerns', async () => {
		const user = userEvent.setup();
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				respond(422, {
					issues: [{ item_index: 1, code: 'sibling_branches', message: 'Different branch.' }]
				})
			)
		);
		const { getByRole, getByLabelText, findByText } = render(BundleEditor, {
			props: { detail: bundle }
		});

		await user.type(getByLabelText('Objective'), 'x');
		await user.click(getByRole('button', { name: 'Save revision' }));

		expect(await findByText('Different branch.')).toBeTruthy();
	});
});

describe('reviewing a proposed bundle', () => {
	it('names the model, flags the draft as unreviewed, and requires a reason to reject', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText, getByLabelText, queryByText } = render(BundleEditor, {
			props: { detail: proposedBundle }
		});

		expect(getByText('Proposed by anthropic/claude-sonnet-5-5')).toBeTruthy();
		expect(getByRole('status').textContent).toContain('no one has reviewed it');

		await user.click(getByRole('radio', { name: /Rejected/ }));
		expect(queryByText('Add an objective before changing the status.')).toBeNull();
		const reason = getByLabelText('Why it was rejected');
		await user.clear(reason);
		expect(getByText('Say why before rejecting; the reason stays with the bundle.')).toBeTruthy();
		expect(getByRole('button', { name: 'Save revision' }).hasAttribute('disabled')).toBe(true);

		await user.type(reason, 'Two unrelated requests');
		expect(getByRole('button', { name: 'Save revision' }).hasAttribute('disabled')).toBe(false);
	});

	it('titles a proposal by its goal and shows what its pass cost', async () => {
		const { getByRole, findByText } = render(BundleEditor, {
			props: { detail: proposedBundle, run: Promise.resolve(proposedRun) }
		});

		expect(
			getByRole('heading', { name: 'Refund request and the offered resolution', level: 1 })
		).toBeTruthy();
		const usage = await findByText(/55,810 tokens/);
		expect(usage.textContent).toContain('and 1 other');
		expect(usage.textContent).toContain('about $0.136');
	});

	it('does not flag a human bundle as awaiting review', () => {
		const { queryByRole, getByText } = render(BundleEditor, { props: { detail: bundle } });

		expect(getByText('Human, in the web app')).toBeTruthy();
		expect(queryByRole('status')).toBeNull();
	});
});
