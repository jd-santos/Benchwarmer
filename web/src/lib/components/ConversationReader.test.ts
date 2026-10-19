// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
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
		expect(getByText('Path 2 of 2')).toBeTruthy();
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
		expect(getByText('Select messages or highlight text')).toBeTruthy();
		await user.click(getAllByRole('checkbox', { name: 'Select' })[0]!);

		expect(getByText('1 item selected')).toBeTruthy();
		expect(getByRole('button', { name: 'Create bundle' }).hasAttribute('disabled')).toBe(false);

		await user.click(getByRole('button', { name: 'Done selecting' }));
		expect(queryByRole('checkbox')).toBeNull();
		vi.unstubAllGlobals();
	});

	it('switches paths from the fork point', async () => {
		const user = userEvent.setup();
		const { getByRole, getByText } = render(ConversationReader, { props: { detail } });

		await user.click(getByRole('button', { name: 'Path 1' }));

		expect(getByText('Path 1 of 2')).toBeTruthy();
		expect(getByText('Text not captured')).toBeTruthy();
	});

	it('keeps the outline hidden until the drawer toggle opens it', async () => {
		const user = userEvent.setup();
		const { getByRole } = render(ConversationReader, { props: { detail } });
		const toggle = getByRole('button', { name: 'Show contents' });

		expect(toggle.getAttribute('aria-expanded')).toBe('false');
		expect(document.getElementById('conversation-outline')?.hidden).toBe(true);

		await user.click(toggle);

		expect(getByRole('button', { name: 'Hide contents' }).getAttribute('aria-expanded')).toBe(
			'true'
		);
		expect(getByRole('navigation', { name: 'Conversation contents' })).toBeTruthy();
	});

	it('warns when an earlier revision is shown', () => {
		const { getByRole } = render(ConversationReader, {
			props: { detail: { ...detail, is_latest: false } }
		});

		expect(getByRole('status').textContent).toContain('Viewing an earlier revision');
		expect(getByRole('link', { name: 'View latest' }).getAttribute('href')).toBe(
			'/conversations/conversation-a'
		);
	});
});
