// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AppNavigation from './AppNavigation.svelte';

const originalMatchMedia = window.matchMedia;

function useNarrowScreen() {
	window.matchMedia = vi.fn().mockImplementation((query: string) => ({
		matches: true,
		media: query,
		onchange: null,
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		addListener: vi.fn(),
		removeListener: vi.fn(),
		dispatchEvent: vi.fn()
	}));
}

afterEach(() => {
	cleanup();
	window.matchMedia = originalMatchMedia;
});

describe('AppNavigation', () => {
	it('provides named banner and navigation landmarks with only implemented routes', () => {
		const { getByRole, getAllByRole } = render(AppNavigation, {
			props: { currentPath: '/' }
		});

		expect(getByRole('banner')).toBeTruthy();
		expect(getByRole('navigation', { name: 'Primary' })).toBeTruthy();
		expect(
			getAllByRole('link').map((link) => ({
				name: link.textContent?.trim(),
				href: link.getAttribute('href')
			}))
		).toEqual([
			{ name: 'Benchwarmer', href: '/' },
			{ name: 'Overview', href: '/' },
			{ name: 'Sources', href: '/sources' }
		]);
	});

	it('indicates the current page without marking other navigation links', () => {
		const { getByRole } = render(AppNavigation, {
			props: { currentPath: '/sources' }
		});

		expect(getByRole('link', { name: 'Sources' }).getAttribute('aria-current')).toBe('page');
		expect(getByRole('link', { name: 'Overview' }).hasAttribute('aria-current')).toBe(false);
	});

	it('opens and closes the narrow-screen navigation from the keyboard', async () => {
		useNarrowScreen();
		const user = userEvent.setup();
		const { getByRole } = render(AppNavigation, {
			props: { currentPath: '/' }
		});
		const menu = getByRole('button', { name: 'Navigation' });
		const links = document.querySelector('[data-navigation-links]');

		expect(menu.getAttribute('aria-expanded')).toBe('false');
		expect(links?.hasAttribute('hidden')).toBe(true);

		menu.focus();
		expect(document.activeElement).toBe(menu);
		await user.keyboard('{Enter}');
		expect(menu.getAttribute('aria-expanded')).toBe('true');
		expect(links?.hasAttribute('hidden')).toBe(false);
		await user.tab();
		expect(document.activeElement).toBe(getByRole('link', { name: 'Overview' }));
		menu.focus();
		await user.keyboard('{Enter}');
		expect(menu.getAttribute('aria-expanded')).toBe('false');
		expect(links?.hasAttribute('hidden')).toBe(true);
	});

	it('exposes a closed narrow-screen navigation state before interaction', () => {
		useNarrowScreen();
		const { getByRole } = render(AppNavigation, {
			props: { currentPath: '/' }
		});
		const menu = getByRole('button', { name: 'Navigation' });
		const links = document.querySelector('[data-navigation-links]');

		expect(menu.tagName).toBe('BUTTON');
		expect(menu.getAttribute('aria-controls')).toBe('primary-navigation');
		expect(menu.getAttribute('aria-expanded')).toBe('false');
		expect(links?.hasAttribute('hidden')).toBe(true);
	});
});
