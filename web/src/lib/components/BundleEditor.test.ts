// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { bundle, proposedBundle } from '$lib/bundles/fixtures';
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
	it('shows each cited excerpt, who said it, its scope, and the gap before it', () => {
		const { getByText, getByRole, queryByText, container } = render(BundleEditor, {
			props: { detail: bundle }
		});

		expect(getByRole('heading', { name: 'Untitled bundle', level: 1 })).toBeTruthy();
		expect(getByText('I need a refund for the second item.')).toBeTruthy();
		// A glyph marks the speaker, with the role name as the readable label beside it.
		expect(container.querySelector('.role-glyph[data-role="user"]')).toBeTruthy();
		expect(getByText(/^\s*User\s*$/)).toBeTruthy();
		// Citing a whole turn needs no scope label; only a narrower scope is named.
		expect(queryByText(/Whole/)).toBeNull();
		expect(getByText('Selected text')).toBeTruthy();
		// Items keep conversation order; there is nothing to reorder.
		expect(container.querySelector('[aria-label^="Move item"]')).toBeNull();
		expect(getByText('2 events not included')).toBeTruthy();
		expect(getByRole('button', { name: 'Save revision' }).hasAttribute('disabled')).toBe(true);
	});

	it('shows tool calls and tool output as code, with call arguments indented', () => {
		const call = {
			...bundle.items[1],
			item: { ...bundle.items[1].item, ref: { ...bundle.items[1].item.ref, event_id: 'e5' } },
			block_kind: 'tool_call',
			excerpt: '{"command": "ls -la", "cwd": "/repo"}'
		};
		const output = {
			...bundle.items[1],
			item: { ...bundle.items[1].item, ref: { ...bundle.items[1].item.ref, event_id: 'e6' } },
			block_kind: 'tool_result',
			excerpt: 'total 0\ndrwxr-xr-x  2 dev  staff  64 Oct 23 10:00 .'
		};
		const { container } = render(BundleEditor, {
			props: { detail: { ...bundle, items: [...bundle.items, call, output] } }
		});

		const blocks = container.querySelectorAll('pre.evidence-card__code');
		expect(blocks.length).toBe(2);
		expect(blocks[0].textContent).toBe('{\n  "command": "ls -la",\n  "cwd": "/repo"\n}');
		expect(blocks[0].classList.contains('evidence-card__code--tool_call')).toBe(true);
		expect(blocks[1].textContent).toContain('drwxr-xr-x');
		expect(container.textContent).not.toContain('not captured');
	});

	it('lists the tool calls of a cited turn under its prose, expandable to the arguments', () => {
		const turn = {
			...bundle.items[0],
			excerpt: "I'll check the file.",
			tool_calls: [
				{ tool_call_id: 'call-7', arguments: '{"command": "grep -n health api.py"}' },
				{ tool_call_id: 'call-8', arguments: null }
			]
		};
		const { getByRole, getByText, container } = render(BundleEditor, {
			props: { detail: { ...bundle, items: [turn, bundle.items[1]] } }
		});

		expect(getByText("I'll check the file.")).toBeTruthy();
		const list = getByRole('list', { name: 'Tool calls in this turn' });
		expect(list.querySelectorAll('li').length).toBe(2);
		expect(getByText('command: grep -n health api.py')).toBeTruthy();
		expect(list.querySelector('details pre')?.textContent).toBe(
			'{\n  "command": "grep -n health api.py"\n}'
		);
		expect(getByText('arguments not captured')).toBeTruthy();
		expect(container.textContent).not.toContain('Text not captured');
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

		await user.type(getByLabelText('Summary'), 'A refund was requested and offered.');
		await user.type(getByLabelText('Goal'), 'Refund for the second item');
		await user.type(getByLabelText('Objective'), 'Refund handling');
		await user.selectOptions(getByLabelText('Role of item 2'), 'correction');
		await user.click(getByRole('button', { name: 'Save revision' }));

		expect(await findByText('Saved revision 2.')).toBeTruthy();
		const [url, init] = fetchMock.mock.calls[0]!;
		expect(url).toBe('/api/v1/bundles/bundle-1');
		const body = JSON.parse(String(init?.body));
		expect(body.base_revision).toBe(1);
		expect(body.document.summary).toBe('A refund was requested and offered.');
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

	it('titles a proposal by its summary and leaves its cost to the runs page', () => {
		const { getByRole, queryByText } = render(BundleEditor, { props: { detail: proposedBundle } });

		expect(
			getByRole('heading', { name: 'Refund request and the offered resolution', level: 1 })
		).toBeTruthy();
		expect(queryByText(/tokens/)).toBeNull();
	});

	it('marks items whose conversation changed in a later import, and counts them', () => {
		const stale = {
			...bundle,
			items: [bundle.items[0], { ...bundle.items[1], conversation_is_latest: false }]
		};
		const { getAllByText, container } = render(BundleEditor, { props: { detail: stale } });

		expect(container.querySelector('[data-stale-count]')?.textContent).toBe(
			'1 item cites an earlier import'
		);
		// One mark on the item itself; the header count is the other.
		expect(getAllByText(/[Ee]arlier import/).length).toBe(2);
	});

	it('shows no stale marks when every cited conversation is current', () => {
		const { queryByText, container } = render(BundleEditor, { props: { detail: bundle } });

		expect(container.querySelector('[data-stale-count]')).toBeNull();
		expect(queryByText(/[Ee]arlier import/)).toBeNull();
	});

	it('does not flag a human bundle as awaiting review', () => {
		const { queryByRole, getByText } = render(BundleEditor, { props: { detail: bundle } });

		expect(getByText('Human, in the web app')).toBeTruthy();
		expect(queryByRole('status')).toBeNull();
	});
});
