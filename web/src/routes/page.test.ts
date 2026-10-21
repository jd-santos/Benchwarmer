// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getBundles, getConversations, getHealth, getSources } from '$lib/api/client';
import type { BundleSummary, HealthResponse, SourcesResponse } from '$lib/api/types';
import Page from './+page.svelte';
import { _loadFoundationOverview } from './+page';

vi.mock('$lib/api/client', () => ({
	getHealth: vi.fn(),
	getSources: vi.fn(),
	getConversations: vi.fn(),
	getBundles: vi.fn()
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

const bundles: BundleSummary[] = [
	{
		id: 'bundle-1',
		revision: 2,
		objective: 'Refund handling',
		status: 'reviewed',
		origin: 'human',
		producer: 'web',
		item_count: 3,
		conversation_ids: ['conversation-a'],
		updated_at: '2026-10-19T10:00:00Z'
	},
	{
		id: 'bundle-2',
		revision: 1,
		objective: '',
		status: 'draft',
		origin: 'generated',
		producer: 'benchwarmer-harness/propose-bundles@0.0.1 anthropic/test',
		item_count: 1,
		conversation_ids: ['conversation-a'],
		updated_at: '2026-10-19T11:00:00Z'
	}
];

const library = { conversations: 5, bundles };

describe('overview page', () => {
	it('announces a stable loading state while status is pending', () => {
		const overview = deferred<never>();
		const { getByRole, getByText } = render(Page, {
			props: { data: { overview: overview.promise }, params: {} }
		});

		expect(getByRole('heading', { name: 'Overview', level: 1 })).toBeTruthy();
		expect(getByRole('heading', { name: 'Loading overview' })).toBeTruthy();
		expect(getByText('Reading the library and source status…')).toBeTruthy();
	});

	it('shows the workflow with counts, sources, and a quiet system line', async () => {
		const { findByRole, getByRole, getByText } = render(Page, {
			props: {
				data: { overview: Promise.resolve({ health: migratedHealth, sources, library }) },
				params: {}
			}
		});

		const workflow = await findByRole('list', { name: 'Evaluation workflow' });
		expect(workflow.textContent).toContain('5');
		expect(getByText('1 reviewed · 1 draft')).toBeTruthy();
		expect(getByRole('link', { name: /^1 · Conversations/ }).getAttribute('href')).toBe(
			'/conversations'
		);
		expect(getByRole('link', { name: /^2 · Evidence bundles/ }).getAttribute('href')).toBe(
			'/bundles'
		);
		expect(getByRole('rowheader', { name: 'Hermes profile' })).toBeTruthy();
		expect(getByText('Never imported')).toBeTruthy();
		expect(getByRole('link', { name: 'Coverage details' }).getAttribute('href')).toBe('/sources');
		expect(getByText('Database revision 0002')).toBeTruthy();
	});

	it('says what to run when the database is not migrated', async () => {
		const health: HealthResponse = { ...migratedHealth, alembic_revision: null };
		const { findByText, getByText, queryByRole } = render(Page, {
			props: {
				data: { overview: Promise.resolve({ health, sources: null, library: null }) },
				params: {}
			}
		});

		expect(await findByText('Database setup required')).toBeTruthy();
		expect(getByText('uv run alembic upgrade head')).toBeTruthy();
		expect(getByText('Database not migrated')).toBeTruthy();
		expect(queryByRole('list', { name: 'Evaluation workflow' })).toBeNull();
	});

	it('marks counts unknown rather than zero when the library cannot be read', async () => {
		const { findByText, getByRole } = render(Page, {
			props: {
				data: { overview: Promise.resolve({ health: migratedHealth, sources, library: null }) },
				params: {}
			}
		});

		expect(await findByText('Library counts could not be loaded.')).toBeTruthy();
		expect(getByRole('list', { name: 'Evaluation workflow' }).textContent).toContain('—');
	});

	it('shows a clear unavailable state when the API request fails', async () => {
		const request = Promise.reject(new Error('offline'));
		request.catch(() => undefined);
		const { findByRole, getByText } = render(Page, {
			props: { data: { overview: request }, params: {} }
		});

		expect(await findByRole('alert')).toBeTruthy();
		expect(getByText('API unavailable')).toBeTruthy();
		expect(getByText(/Check that it is running/)).toBeTruthy();
	});
});

describe('overview data loading', () => {
	it('loads sources and library counts after confirming the database is migrated', async () => {
		vi.mocked(getHealth).mockResolvedValue(migratedHealth);
		vi.mocked(getSources).mockResolvedValue(sources);
		vi.mocked(getConversations).mockResolvedValue({ items: [], total: 5, limit: 1, offset: 0 });
		vi.mocked(getBundles).mockResolvedValue({ items: bundles });

		await expect(_loadFoundationOverview()).resolves.toEqual({
			health: migratedHealth,
			sources,
			library
		});
	});

	it('keeps status when library counts fail', async () => {
		vi.mocked(getHealth).mockResolvedValue(migratedHealth);
		vi.mocked(getSources).mockResolvedValue(sources);
		vi.mocked(getConversations).mockRejectedValue(new Error('offline'));
		vi.mocked(getBundles).mockResolvedValue({ items: bundles });

		await expect(_loadFoundationOverview()).resolves.toEqual({
			health: migratedHealth,
			sources,
			library: null
		});
	});

	it('does not request records from an unmigrated database', async () => {
		const health: HealthResponse = { ...migratedHealth, alembic_revision: null };
		vi.mocked(getHealth).mockResolvedValue(health);

		await expect(_loadFoundationOverview()).resolves.toEqual({
			health,
			sources: null,
			library: null
		});
		expect(getSources).not.toHaveBeenCalled();
		expect(getConversations).not.toHaveBeenCalled();
	});
});
