import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'tests',
	testMatch: '**/*.spec.ts',
	fullyParallel: false,
	workers: 1,
	timeout: 45_000,
	use: {
		browserName: 'chromium',
		trace: 'retain-on-failure'
	}
});
