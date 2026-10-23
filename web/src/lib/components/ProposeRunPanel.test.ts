// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConversationsResponse, ModelWorkPlan } from '$lib/api/types';

vi.mock('$lib/api/client', async (importOriginal) => {
	const original = await importOriginal<typeof import('$lib/api/client')>();
	return {
		...original,
		getModelWorkConfig: vi.fn(),
		getConversations: vi.fn(),
		getPlans: vi.fn(),
		getPlan: vi.fn(),
		createPlan: vi.fn(),
		approvePlan: vi.fn(),
		cancelPlan: vi.fn()
	};
});

import {
	approvePlan,
	createPlan,
	getConversations,
	getModelWorkConfig,
	getPlans
} from '$lib/api/client';
import ProposeRunPanel from './ProposeRunPanel.svelte';

const conversations: ConversationsResponse = {
	items: [
		{
			id: 'conversation-a',
			source: { id: 'pi-a', kind: 'pi', display_name: 'Pi on this Mac' },
			native_id: 'n-a',
			revision: 'r1',
			captured_at: '2026-10-19T10:00:00Z',
			title: 'Refund investigation',
			preview: null,
			started_at: '2026-10-18T09:00:00Z',
			last_activity_at: null,
			event_count: 10,
			message_count: 6,
			branch_count: 1,
			relationship_counts: {},
			coverage: {},
			match_count: 0,
			matches: []
		}
	],
	total: 1,
	limit: 50,
	offset: 0
};

const plan: ModelWorkPlan = {
	id: 'plan-1',
	workflow: 'propose-bundles',
	status: 'proposed',
	digest: 'a'.repeat(64),
	inputs: [{ conversation_id: 'conversation-a', revision: 'r1', title: 'Refund investigation' }],
	model: { provider: 'anthropic', model_id: 'claude-sonnet-5-5', thinking_level: null },
	max_inputs: 1,
	instructions: null,
	estimated_cost: null,
	run_id: null,
	exit_code: null,
	error_summary: null,
	created_at: '2026-10-23T10:00:00Z',
	approved_at: null,
	started_at: null,
	finished_at: null
};

beforeEach(() => {
	vi.mocked(getConversations).mockResolvedValue(conversations);
	vi.mocked(getPlans).mockResolvedValue([]);
});

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
});

describe('propose run panel', () => {
	it('previews a frozen plan and approves it only by its digest', async () => {
		vi.mocked(getModelWorkConfig).mockResolvedValue({
			can_run: true,
			workflows: ['propose-bundles'],
			thinking_levels: ['off', 'low'],
			max_inputs: 200
		});
		vi.mocked(createPlan).mockResolvedValue(plan);
		vi.mocked(approvePlan).mockResolvedValue({
			...plan,
			status: 'running',
			run_id: 'propose-bundles-2026-10-23T10-00-01-000Z',
			started_at: '2026-10-23T10:00:01Z'
		});
		const user = userEvent.setup();
		const { findByRole, getByRole, getByText, container } = render(ProposeRunPanel);

		await user.click(await findByRole('checkbox', { name: /Refund investigation/ }));
		const preview = getByRole('button', { name: 'Preview plan' });
		expect(preview.hasAttribute('disabled')).toBe(true);
		await user.type(getByRole('textbox', { name: 'Model' }), 'claude-sonnet-5-5');
		await user.click(preview);

		await waitFor(() => expect(container.querySelector('[data-plan]')).toBeTruthy());
		expect(createPlan).toHaveBeenCalledWith({
			workflow: 'propose-bundles',
			conversation_ids: ['conversation-a'],
			model: { provider: 'anthropic', model_id: 'claude-sonnet-5-5', thinking_level: null },
			instructions: null
		});
		expect(getByText('a'.repeat(64))).toBeTruthy();
		expect(getByText(/No estimate before the run/)).toBeTruthy();

		await user.click(getByRole('button', { name: 'Approve and run' }));
		expect(approvePlan).toHaveBeenCalledWith('plan-1', 'a'.repeat(64));
		await waitFor(() => expect(getByText('Running')).toBeTruthy());
		expect(getByRole('button', { name: 'Cancel' })).toBeTruthy();
	});

	it('explains when the application cannot start runs and keeps approval disabled', async () => {
		vi.mocked(getModelWorkConfig).mockResolvedValue({
			can_run: false,
			workflows: ['propose-bundles'],
			thinking_levels: [],
			max_inputs: 200
		});
		vi.mocked(createPlan).mockResolvedValue(plan);
		const user = userEvent.setup();
		const { findByText, findByRole, getByRole } = render(ProposeRunPanel);

		expect(await findByText(/cannot start them/)).toBeTruthy();
		await user.click(await findByRole('checkbox', { name: /Refund investigation/ }));
		await user.type(getByRole('textbox', { name: 'Model' }), 'claude-sonnet-5-5');
		await user.click(getByRole('button', { name: 'Preview plan' }));
		const approve = await findByRole('button', { name: 'Approve and run' });
		expect(approve.hasAttribute('disabled')).toBe(true);
	});
});
