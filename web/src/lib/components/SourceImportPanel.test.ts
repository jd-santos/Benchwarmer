// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SourceStatus } from '$lib/api/types';
import { ApiClientError } from '$lib/api/client';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn() }));
vi.mock('$lib/api/client', async (importOriginal) => {
	const original = await importOriginal<typeof import('$lib/api/client')>();
	return {
		...original,
		getImportConfig: vi.fn(),
		getSourceImports: vi.fn(),
		getSources: vi.fn(),
		startImport: vi.fn()
	};
});

import { getImportConfig, getSourceImports, getSources, startImport } from '$lib/api/client';
import SourceImportPanel from './SourceImportPanel.svelte';

const coverage = {
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
} as const;

const sources: SourceStatus[] = [
	{
		id: 'pi-a',
		kind: 'pi',
		display_name: 'Pi on this Mac',
		last_successful_import_at: null,
		coverage
	},
	{
		id: 'hermes-a',
		kind: 'hermes',
		display_name: 'Hermes',
		last_successful_import_at: null,
		coverage
	}
];

beforeEach(() => {
	vi.mocked(getSources).mockResolvedValue({ items: sources });
});

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
});

describe('source import panel', () => {
	it('says how to turn host import on when no roots are configured', async () => {
		vi.mocked(getImportConfig).mockResolvedValue({
			roots: [],
			kinds: ['pi', 'chatgpt', 'conversation_file']
		});
		const { findByText, queryByRole } = render(SourceImportPanel);

		expect(await findByText(/Host-local import is off/)).toBeTruthy();
		expect(queryByRole('button', { name: 'Import' })).toBeNull();
	});

	it('offers a form only for importable sources and reports what an import did', async () => {
		vi.mocked(getImportConfig).mockResolvedValue({
			roots: ['/srv/inbox'],
			kinds: ['pi', 'chatgpt', 'conversation_file']
		});
		vi.mocked(getSourceImports).mockResolvedValue([
			{
				id: 'pi-ui-1',
				outcome: 'failed',
				started_at: '2026-10-20T10:00:00Z',
				completed_at: '2026-10-20T10:00:01Z',
				error_summary: 'Pi session directory contains no sessions'
			}
		]);
		vi.mocked(startImport).mockResolvedValue({
			batch_id: 'pi-ui-2',
			outcome: 'succeeded',
			conversations: 3,
			revisions: 3,
			snapshots: 3,
			error_summary: null
		});
		const user = userEvent.setup();
		const { findByRole, getByRole, getByText, queryByText, container } = render(SourceImportPanel);

		const path = await findByRole('textbox', { name: 'Path on this machine' });
		expect(getByText(/Pi on this Mac/)).toBeTruthy();
		expect(queryByText(/^Hermes/)).toBeNull();
		expect(getByText('/srv/inbox')).toBeTruthy();
		expect(getByText('1 earlier import')).toBeTruthy();
		const button = getByRole('button', { name: 'Import' });
		expect(button.hasAttribute('disabled')).toBe(true);

		await user.type(path, '/srv/inbox/pi-sessions');
		await user.click(button);

		await waitFor(() =>
			expect(container.querySelector('[data-import-result]')?.textContent).toContain(
				'Imported 3 conversations'
			)
		);
		expect(startImport).toHaveBeenCalledWith('pi-a', '/srv/inbox/pi-sessions');
	});

	it('shows the server reason when a path is refused', async () => {
		vi.mocked(getImportConfig).mockResolvedValue({ roots: ['/srv/inbox'], kinds: ['pi'] });
		vi.mocked(getSourceImports).mockResolvedValue([]);
		vi.mocked(startImport).mockRejectedValue(
			new ApiClientError('The API returned HTTP 422.', {
				kind: 'http',
				status: 422,
				body: { detail: 'path is outside the configured import roots' }
			})
		);
		const user = userEvent.setup();
		const { findByRole, getByRole } = render(SourceImportPanel);

		await user.type(await findByRole('textbox'), '/elsewhere');
		await user.click(getByRole('button', { name: 'Import' }));

		expect((await findByRole('alert')).textContent).toContain(
			'outside the configured import roots'
		);
	});
});
