import { access } from 'node:fs/promises';
import { expect, startFoundation, test } from './support/foundation';

test('starts a migrated and seeded disposable application', async ({ foundation, page }) => {
	await access(foundation.dataRoot);

	const health = await page.request.get(`${foundation.apiUrl}/api/v1/health`);
	expect(health.ok()).toBe(true);
	expect(await health.json()).toMatchObject({ status: 'ok', alembic_revision: '0002' });

	await page.goto(`${foundation.webUrl}/sources`);
	await expect(page.getByRole('heading', { name: 'Sources', exact: true })).toBeVisible();
	await expect(page.getByText('3 sources configured')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Synthetic Hermes profile' })).toBeVisible();
});

test('removes its temporary data root during teardown', async () => {
	const foundation = await startFoundation();
	const dataRoot = foundation.dataRoot;
	await access(dataRoot);

	await foundation.stop();

	await expect(access(dataRoot)).rejects.toMatchObject({ code: 'ENOENT' });
});
