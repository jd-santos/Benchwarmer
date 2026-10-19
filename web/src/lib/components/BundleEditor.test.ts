// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { bundle } from '$lib/bundles/fixtures';
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

	it('requires an objective before review', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText } = render(BundleEditor, { props: { detail: bundle } });

		await user.click(getByRole('radio', { name: /Reviewed/ }));

		expect(getByText(/Add an objective before marking the bundle reviewed/)).toBeTruthy();
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

		await user.type(getByLabelText('Objective'), 'Refund handling');
		await user.selectOptions(getByLabelText('Role of item 2'), 'correction');
		await user.click(getByRole('button', { name: 'Save revision' }));

		expect(await findByText('Saved revision 2.')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/bundles/bundle-1');
		const body = JSON.parse(String(init?.body));
		expect(body.base_revision).toBe(1);
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
