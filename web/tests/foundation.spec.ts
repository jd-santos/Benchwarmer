import { access } from 'node:fs/promises';
import type { Page } from '@playwright/test';
import { expect, startFoundation, test } from './support/foundation';

const coverageLabels = [
	'Sessions',
	'Token usage',
	'Request IDs',
	'Actual charges',
	'List-price estimates',
	'Subscription expense',
	'Quota',
	'Credits',
	'Prompts',
	'Classifications'
] as const;

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
	const width = await page.evaluate(() => ({
		client: document.documentElement.clientWidth,
		scroll: document.documentElement.scrollWidth
	}));
	expect(width.scroll).toBeLessThanOrEqual(width.client);
}

async function expectFixtureSources(page: Page): Promise<void> {
	await expect(page.getByText('3 sources configured')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Synthetic Codex profile' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Synthetic Hermes profile' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Synthetic Pi profile' })).toBeVisible();

	const hermes = page.getByRole('article', { name: 'Synthetic Hermes profile' });
	await expect(hermes.getByText('Sep 16, 2026, 11:55 AM UTC')).toBeVisible();
	for (const label of coverageLabels) await expect(hermes.getByText(label)).toBeVisible();
	await expect(hermes.getByText('Available', { exact: true })).toBeVisible();
	await expect(hermes.getByText('Partial', { exact: true })).toHaveCount(2);
	await expect(hermes.getByText('Unavailable', { exact: true })).toHaveCount(2);
	await expect(hermes.getByText('Unknown', { exact: true })).toHaveCount(5);
}

test('completes the fixture-backed desktop flow', async ({ foundation, page }) => {
	await access(foundation.dataRoot);
	await page.setViewportSize({ width: 1280, height: 900 });

	const health = await page.request.get(`${foundation.apiUrl}/api/v1/health`);
	expect(health.ok()).toBe(true);
	expect(await health.json()).toMatchObject({ status: 'ok', alembic_revision: '0002' });

	await page.goto(foundation.webUrl);
	await expect(page.getByRole('heading', { name: 'System overview' })).toBeVisible();
	await expect(page.getByText('Operational')).toBeVisible();
	await expect(page.getByText('Revision 0002')).toBeVisible();
	await expect(page.getByText('3 configured', { exact: true })).toBeVisible();
	await expect(page.getByText('1 of 3 imported successfully')).toBeVisible();
	await expectNoHorizontalOverflow(page);

	await page.getByRole('link', { name: 'Review sources' }).click();
	await expect(page).toHaveURL(`${foundation.webUrl}/sources`);
	await expect(page.getByRole('heading', { name: 'Sources', exact: true })).toBeVisible();
	await expectFixtureSources(page);
	await expectNoHorizontalOverflow(page);
});

test('completes the fixture-backed flow at 375px using only the keyboard', async ({
	foundation,
	page
}) => {
	await page.setViewportSize({ width: 375, height: 812 });
	await page.goto(foundation.webUrl);
	await expect(page.getByRole('heading', { name: 'System overview' })).toBeVisible();
	await expect(page.getByText('3 configured', { exact: true })).toBeVisible();
	await expectNoHorizontalOverflow(page);

	await page.keyboard.press('Tab');
	await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
	await expect(page.getByRole('link', { name: 'Skip to content' })).toBeVisible();
	await page.keyboard.press('Tab');
	await expect(page.getByRole('link', { name: 'Benchwarmer' })).toBeFocused();
	await page.keyboard.press('Tab');
	const menu = page.getByRole('button', { name: 'Navigation' });
	await expect(menu).toBeFocused();
	await page.keyboard.press('Enter');
	await expect(menu).toHaveAttribute('aria-expanded', 'true');
	await page.keyboard.press('Tab');
	await expect(page.getByRole('link', { name: 'Overview' })).toBeFocused();
	await page.keyboard.press('Tab');
	await expect(page.getByRole('link', { name: 'Sources', exact: true })).toBeFocused();
	await page.keyboard.press('Enter');

	await expect(page).toHaveURL(`${foundation.webUrl}/sources`);
	await expect(page.getByRole('heading', { name: 'Sources', exact: true })).toBeVisible();
	await expectFixtureSources(page);
	await expectNoHorizontalOverflow(page);
});

test('shows an actionable state when API requests fail', async ({ foundation, page }) => {
	await page.route(`${foundation.webUrl}/api/**`, (route) => route.abort('connectionfailed'));

	await page.goto(foundation.webUrl);
	const alert = page.getByRole('alert');
	await expect(alert).toContainText('Status unavailable');
	await expect(alert).toContainText('Check that it is running and reload this page.');
	await expect(page.getByText('Operational')).toHaveCount(0);
});

test('removes its temporary data root during teardown', async () => {
	const foundation = await startFoundation();
	const dataRoot = foundation.dataRoot;
	await access(dataRoot);

	await foundation.stop();

	await expect(access(dataRoot)).rejects.toMatchObject({ code: 'ENOENT' });
});
