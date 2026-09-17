// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getHealth, getSources } from '$lib/api/client';
import type { HealthResponse, SourcesResponse } from '$lib/api/types';
import Page from './+page.svelte';
import { _loadFoundationOverview } from './+page';

vi.mock('$lib/api/client', () => ({
	getHealth: vi.fn(),
	getSources: vi.fn()
}));

const migratedHealth: HealthResponse = {
	status: 'ok',
	alembic_revision: '0002',
	data_root_writable: true
};

const sources: SourcesResponse = {
	items: [
		{
			id: 'source-a',
			kind: 'hermes',
			display_name: 'Hermes profile',
			last_successful_import_at: '2026-09-16T11:55:02Z',
			coverage: {
				sessions: 'available',
				token_usage: 'partial',
				request_ids: 'unavailable',
				actual_charges: 'unknown',
				list_price_estimates: 'unavailable',
				subscription_expense: 'unknown',
				quota: 'unknown',
				credits: 'unknown',
				prompts: 'partial',
				classifications: 'available'
			}
		},
		{
			id: 'source-b',
			kind: 'codex',
			display_name: 'Codex profile',
			last_successful_import_at: null,
			coverage: {
				sessions: 'unknown',
				token_usage: 'unknown',
				request_ids: 'unknown',
				actual_charges: 'unknown',
				list_price_estimates: 'unknown',
				subscription_expense: 'unknown',
				quota: 'unknown',
				credits: 'unknown',
				prompts: 'unknown',
				classifications: 'unknown'
			}
		}
	]
};

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason?: unknown) => void;
	const promise = new Promise<T>((resolvePromise, rejectPromise) => {
		resolve = resolvePromise;
		reject = rejectPromise;
	});
	return { promise, resolve, reject };
}

afterEach(() => {
	cleanup();
	vi.resetAllMocks();
});

describe('overview page', () => {
	it('announces a stable loading state while status is pending', () => {
		const overview = deferred<{ health: HealthResponse; sources: SourcesResponse | null }>();
		const { getByRole, getByText } = render(Page, {
			props: { data: { overview: overview.promise }, params: {} }
		});

		expect(getByRole('heading', { name: 'System overview' })).toBeTruthy();
		expect(getByRole('heading', { name: 'Checking system status' })).toBeTruthy();
		expect(getByText('Reading service, database, and source state…')).toBeTruthy();
	});

	it('shows healthy service, migration, source, and explicit coverage state', async () => {
		const { findByText, getByRole, getAllByText, getByText } = render(Page, {
			props: {
				data: { overview: Promise.resolve({ health: migratedHealth, sources }) },
				params: {}
			}
		});

		expect(await findByText('Revision 0002')).toBeTruthy();
		expect(getByText('2 configured')).toBeTruthy();
		expect(getByText('1 of 2 imported successfully')).toBeTruthy();
		expect(getAllByText('Partial').length).toBe(1);
		expect(getAllByText('Unavailable').length).toBe(1);
		expect(getAllByText('Unknown').length).toBe(1);
		expect(getByRole('link', { name: 'Review sources' }).getAttribute('href')).toBe('/sources');
	});

	it('labels an unmigrated database without fabricating source status', async () => {
		const health: HealthResponse = { ...migratedHealth, alembic_revision: null };
		const { findByText, getByText, queryByRole } = render(Page, {
			props: { data: { overview: Promise.resolve({ health, sources: null }) }, params: {} }
		});

		expect(await findByText('Migration required')).toBeTruthy();
		expect(getByText('Setup required')).toBeTruthy();
		expect(getByText('No database revision is installed.')).toBeTruthy();
		expect(getByText('Migrate the database to read sources.')).toBeTruthy();
		expect(queryByRole('heading', { name: 'Source coverage' })).toBeNull();
	});

	it('shows a clear unavailable state when the API request fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = render(Page, {
			props: { data: { overview: request }, params: {} }
		});

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('Status unavailable')).toBeTruthy();
		expect(getByText(/Check that it is running/)).toBeTruthy();
	});
});

describe('overview data loading', () => {
	it('loads sources after confirming that the database is migrated', async () => {
		vi.mocked(getHealth).mockResolvedValue(migratedHealth);
		vi.mocked(getSources).mockResolvedValue(sources);

		await expect(_loadFoundationOverview()).resolves.toEqual({
			health: migratedHealth,
			sources
		});
		expect(getHealth).toHaveBeenCalledOnce();
		expect(getSources).toHaveBeenCalledOnce();
	});

	it('does not request source records from an unmigrated database', async () => {
		const health: HealthResponse = { ...migratedHealth, alembic_revision: null };
		vi.mocked(getHealth).mockResolvedValue(health);

		await expect(_loadFoundationOverview()).resolves.toEqual({ health, sources: null });
		expect(getSources).not.toHaveBeenCalled();
	});
});
