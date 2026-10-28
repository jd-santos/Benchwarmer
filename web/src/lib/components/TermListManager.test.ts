// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TermListDetail, TermListSummary } from '$lib/api/types';
import TermListManager from './TermListManager.svelte';

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

const program: TermListSummary = {
	name: 'program',
	version: 2,
	term_count: 3,
	notes: 'Customer and host names',
	created_at: '2026-10-27T09:00:00Z',
	retired_at: null
};

const retired: TermListSummary = {
	name: 'old-program',
	version: 1,
	term_count: 1,
	notes: null,
	created_at: '2026-09-01T09:00:00Z',
	retired_at: '2026-10-01T09:00:00Z'
};

const detail: TermListDetail = { ...program, terms: ['Wexley', 'Orrin Vale', 'Marlow'] };

describe('term list manager', () => {
	it('lists each stored list with counts and status, and no terms', () => {
		const { getByRole, getByText, queryByText } = render(TermListManager, {
			props: { lists: [program, retired] }
		});

		expect(getByText('2 term lists')).toBeTruthy();
		expect(getByRole('rowheader', { name: 'program' })).toBeTruthy();
		expect(getByRole('rowheader', { name: 'old-program' })).toBeTruthy();
		expect(getByText('Customer and host names')).toBeTruthy();
		expect(getByText('Active')).toBeTruthy();
		expect(getByText('Retired')).toBeTruthy();
		expect(queryByText('Wexley')).toBeNull();
		expect(getByRole('button', { name: 'New list' })).toBeTruthy();
	});

	it('opens a list, shows its terms, and saves the next version', async () => {
		const user = userEvent.setup();
		const saved: TermListDetail = {
			...detail,
			version: 3,
			terms: [...detail.terms, 'Quenby'],
			notes: 'Customer and host names'
		};
		const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
			const url = String(input);
			if (url === '/api/v1/scrub-terms/program' && init?.method === 'GET')
				return respond(200, detail);
			if (url === '/api/v1/scrub-terms/program' && init?.method === 'PUT')
				return respond(200, saved);
			if (url.startsWith('/api/v1/scrub-terms?'))
				return respond(200, { items: [{ ...program, version: 3, term_count: 4 }] });
			return respond(404, { detail: 'nope' });
		});
		vi.stubGlobal('fetch', fetchMock);
		const view = render(TermListManager, { props: { lists: [program] } });

		await user.click(view.getByRole('button', { name: 'Open program' }));
		const termsField = (await view.findByLabelText('Terms')) as HTMLTextAreaElement;
		expect(termsField.value).toBe('Wexley\nOrrin Vale\nMarlow');
		expect(view.getByRole('heading', { name: 'program · version 2' })).toBeTruthy();
		expect(view.getByText(/Saving a changed list creates version 3/)).toBeTruthy();

		await user.type(termsField, '\nQuenby');
		await user.click(view.getByRole('button', { name: 'Save new version' }));

		expect(await view.findByText('Saved version 3. Version 2 is unchanged.')).toBeTruthy();
		const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')!;
		expect(JSON.parse(String(put[1]?.body))).toEqual({
			terms: ['Wexley', 'Orrin Vale', 'Marlow', 'Quenby'],
			notes: 'Customer and host names'
		});
		expect(view.getByRole('heading', { name: 'program · version 3' })).toBeTruthy();
		// The table refreshed to the new version.
		expect(view.getByRole('table').textContent).toContain('4');
	});

	it('creates a new list and reports validation without echoing terms', async () => {
		const user = userEvent.setup();
		const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
			if (init?.method === 'PUT')
				return respond(422, {
					detail: 'Term list is invalid',
					message: '201 distinct terms exceed the limit of 200'
				});
			return respond(200, { items: [] });
		});
		vi.stubGlobal('fetch', fetchMock);
		const view = render(TermListManager, { props: { lists: [] } });

		expect(view.getByRole('heading', { name: 'No term lists yet' })).toBeTruthy();
		await user.click(view.getByRole('button', { name: 'New list' }));
		const save = view.getByRole('button', { name: 'Save list' });
		expect(save.hasAttribute('disabled')).toBe(true);

		await user.type(view.getByLabelText('Name'), 'bad name');
		await user.type(view.getByLabelText('Terms'), 'Tallis');
		expect(save.hasAttribute('disabled')).toBe(true);
		expect(view.getByLabelText('Name').getAttribute('aria-invalid')).toBe('true');

		await user.clear(view.getByLabelText('Name'));
		await user.type(view.getByLabelText('Name'), 'new-program');
		expect(save.hasAttribute('disabled')).toBe(false);
		await user.click(save);

		expect(await view.findByRole('alert')).toBeTruthy();
		expect(view.getByText('201 distinct terms exceed the limit of 200')).toBeTruthy();
		expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/scrub-terms/new-program');
	});

	it('retires an open list after confirmation and locks its editor', async () => {
		const user = userEvent.setup();
		vi.stubGlobal(
			'confirm',
			vi.fn(() => true)
		);
		const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
			const url = String(input);
			if (url.endsWith('/retire'))
				return respond(200, { ...program, retired_at: '2026-10-27T10:00:00Z' });
			if (url === '/api/v1/scrub-terms/program' && init?.method === 'GET')
				return respond(200, detail);
			return respond(200, { items: [{ ...program, retired_at: '2026-10-27T10:00:00Z' }] });
		});
		vi.stubGlobal('fetch', fetchMock);
		const view = render(TermListManager, { props: { lists: [program] } });

		await user.click(view.getByRole('button', { name: 'Open program' }));
		await user.click(await view.findByRole('button', { name: 'Retire list' }));

		expect(await view.findByText(/program is retired/)).toBeTruthy();
		expect(view.queryByRole('button', { name: 'Retire list' })).toBeNull();
		expect((view.getByLabelText('Terms') as HTMLTextAreaElement).disabled).toBe(true);
		expect(view.getByRole('button', { name: 'Save new version' }).hasAttribute('disabled')).toBe(
			true
		);
		expect(view.getByText('Retired')).toBeTruthy();
	});
});
