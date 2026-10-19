// @vitest-environment jsdom

import { cleanup, render, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { detail } from '$lib/conversations/fixtures';
import ConversationReader from './ConversationReader.svelte';

beforeAll(() => {
	// jsdom does not implement scrolling.
	Element.prototype.scrollIntoView = vi.fn();
	window.scrollTo = vi.fn() as typeof window.scrollTo;
});

afterEach(() => {
	cleanup();
	sessionStorage.clear();
});

describe('conversation reader', () => {
	it('reads the latest path and marks gaps instead of inventing content', () => {
		const { getByRole, getByText, queryByText } = render(ConversationReader, {
			props: { detail }
		});

		expect(getByRole('heading', { name: 'Refund investigation', level: 1 })).toBeTruthy();
		expect(getByRole('button', { name: /^Path Alternate 1/ })).toBeTruthy();
		expect(getByText('I can offer a replacement instead.')).toBeTruthy();
		expect(queryByText('Text not captured')).toBeNull();
		expect(getByRole('navigation', { name: 'Paths from this message' })).toBeTruthy();
	});

	it('selects messages as evidence for a bundle', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn<typeof fetch>().mockResolvedValue(
				new Response(JSON.stringify({ items: [] }), {
					headers: { 'Content-Type': 'application/json' }
				})
			)
		);
		const user = userEvent.setup();
		const { getByRole, getAllByRole, getByText, queryByRole } = render(ConversationReader, {
			props: { detail }
		});
		expect(queryByRole('checkbox')).toBeNull();

		await user.click(getByRole('button', { name: 'Select evidence' }));
		expect(getByText('Pick messages or highlight text')).toBeTruthy();
		await user.click(getAllByRole('checkbox', { name: /^Select user/ })[0]!);

		expect(getByText('1 item selected')).toBeTruthy();
		expect(getByRole('button', { name: 'Create bundle' }).hasAttribute('disabled')).toBe(false);

		await user.click(getByRole('button', { name: 'Done selecting' }));
		expect(queryByRole('checkbox')).toBeNull();
		vi.unstubAllGlobals();
	});

	it('switches paths from the fork point', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText } = render(ConversationReader, { props: { detail } });

		await user.click(getByRole('button', { name: 'Original' }));

		expect(getByRole('button', { name: /^Path Original/ })).toBeTruthy();
		expect(getByText('Text not captured')).toBeTruthy();
	});

	it('describes how each path differs and switches from the picker', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText } = render(ConversationReader, { props: { detail } });
		const picker = getByRole('button', { name: /^Path Alternate 1/ });

		await user.click(picker);
		const menu = getByRole('list', { name: 'Paths' });
		expect(menu.textContent).toContain(
			'Diverges from Original at turn 1: the assistant replies differently'
		);
		expect(menu.textContent).toContain('model-b');
		expect(menu.textContent).toContain('Follows the earliest captured reply');

		await user.click(within(menu).getByRole('button', { name: /^Original/ }));

		expect(picker.getAttribute('aria-expanded')).toBe('false');
		expect(getByRole('button', { name: /^Path Original/ })).toBeTruthy();
		expect(getByText('Text not captured')).toBeTruthy();
	});

	it('opens the outline by default and remembers closing it', async () => {
		const user = userEvent.setup();
		const { getByRole, getAllByRole } = render(ConversationReader, { props: { detail } });
		const hide = getByRole('button', { name: 'Hide contents' });

		expect(hide.getAttribute('aria-expanded')).toBe('true');
		expect(getByRole('navigation', { name: 'Conversation contents' })).toBeTruthy();

		await user.click(hide);

		const show = getAllByRole('button', { name: 'Show contents' })[0]!;
		expect(show.getAttribute('aria-expanded')).toBe('false');
		expect(show.closest('.reader__rail')).not.toBeNull();
		expect(document.getElementById('conversation-outline')?.hidden).toBe(true);
		expect(sessionStorage.getItem('benchwarmer:outline-open')).toBe('false');
	});

	it('warns when an earlier revision is shown', () => {
		const { getByRole } = render(ConversationReader, {
			props: { detail: { ...detail, is_latest: false } }
		});

		expect(getByRole('status').textContent).toContain('Viewing an earlier capture');
		expect(getByRole('link', { name: 'View latest' }).getAttribute('href')).toBe(
			'/conversations/conversation-a'
		);
	});
});
