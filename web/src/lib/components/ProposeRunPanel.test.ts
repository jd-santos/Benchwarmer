// @vitest-environment jsdom

import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConversationsResponse, ModelCatalog, ModelWorkPlan } from '$lib/api/types';

vi.mock('$lib/api/client', async (importOriginal) => {
	const original = await importOriginal<typeof import('$lib/api/client')>();
	return {
		...original,
		getModelWorkConfig: vi.fn(),
		getModelCatalog: vi.fn(),
		getConversations: vi.fn(),
		getPlans: vi.fn(),
		getPlan: vi.fn(),
		createPlan: vi.fn(),
		approvePlan: vi.fn(),
		cancelPlan: vi.fn()
	};
});

import {
	ApiClientError,
	approvePlan,
	createPlan,
	getConversations,
	getModelCatalog,
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

const catalog: ModelCatalog = {
	generated_at: '2026-10-23T09:59:00Z',
	fetched_at: '2026-10-23T09:59:01Z',
	providers: [
		{
			id: 'anthropic',
			name: 'Anthropic',
			key_variables: ['ANTHROPIC_API_KEY'],
			base_url_override: null,
			provider_list: 'listed',
			models_dev: 'listed',
			model_count: 3
		},
		{
			id: 'openrouter',
			name: 'OpenRouter',
			key_variables: ['OPENROUTER_API_KEY'],
			base_url_override: null,
			provider_list: 'listed',
			models_dev: 'listed',
			model_count: 1
		}
	],
	models: [
		{
			provider: 'anthropic',
			id: 'claude-sonnet-6',
			name: 'Claude Sonnet 6',
			reasoning: true,
			thinking_levels: ['low', 'high'],
			context_window: 2000000,
			max_output: 256000,
			release_date: '2027-01-15',
			cost: { input: 4, output: 20, cache_read: 0.4, cache_write: 5 },
			sources: ['models.dev', 'provider'],
			listed_by_provider: true,
			runnable: true
		},
		{
			provider: 'anthropic',
			id: 'claude-sonnet-5-5',
			name: 'Claude Sonnet 5.5',
			reasoning: true,
			thinking_levels: ['low', 'medium', 'high', 'xhigh', 'max'],
			context_window: 1000000,
			max_output: 128000,
			release_date: '2026-09-01',
			cost: { input: 3, output: 15, cache_read: 0.3, cache_write: 3.75 },
			sources: ['pi-ai', 'models.dev', 'provider'],
			listed_by_provider: true,
			runnable: true
		},
		{
			provider: 'anthropic',
			id: 'claude-haiku-4-5-20251001',
			name: 'Claude Haiku 4.5',
			reasoning: true,
			thinking_levels: ['low', 'medium', 'high'],
			context_window: 200000,
			max_output: 64000,
			release_date: '2025-10-01',
			cost: { input: 1, output: 5, cache_read: 0.1, cache_write: 1.25 },
			sources: ['pi-ai', 'models.dev'],
			listed_by_provider: false,
			runnable: true
		},
		{
			provider: 'openrouter',
			id: 'meta-llama/llama-4-maverick',
			name: 'Llama 4 Maverick',
			reasoning: false,
			thinking_levels: [],
			context_window: 1000000,
			max_output: null,
			release_date: '2025-04-05',
			cost: { input: 0.2, output: 0.6, cache_read: 0, cache_write: 0 },
			sources: ['pi-ai', 'models.dev', 'provider'],
			listed_by_provider: true,
			runnable: true
		}
	],
	notes: []
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
	it("offers the models the server has keys for, newest first, with that model's thinking levels", async () => {
		vi.mocked(getModelWorkConfig).mockResolvedValue({
			can_run: true,
			workflows: ['propose-bundles'],
			thinking_levels: ['off', 'low', 'medium', 'high', 'xhigh', 'max'],
			max_inputs: 200
		});
		vi.mocked(getModelCatalog).mockResolvedValue(catalog);
		vi.mocked(createPlan).mockResolvedValue(plan);
		vi.mocked(approvePlan).mockResolvedValue({
			...plan,
			status: 'running',
			run_id: 'propose-bundles-2026-10-23T10-00-01-000Z',
			started_at: '2026-10-23T10:00:01Z'
		});
		const user = userEvent.setup();
		const { findByRole, getByRole, getByText, container } = render(ProposeRunPanel);

		const modelSelect = (await findByRole('combobox', { name: 'Model' })) as HTMLSelectElement;
		expect(getByRole('combobox', { name: 'Provider' })).toBeTruthy();
		// The newest listed model is chosen first; a model the provider no longer lists sits in its own group.
		expect(modelSelect.value).toBe('claude-sonnet-6');
		const groups = [...modelSelect.querySelectorAll('optgroup')].map((group) => group.label);
		expect(groups).toEqual(['Listed by Anthropic', "In catalogs, not in Anthropic's list"]);
		expect(getByText(/\$4\.00 in, \$20\.00 out per M tokens/)).toBeTruthy();
		expect(getByText(/not in the pinned harness catalog/)).toBeTruthy();

		const thinkingSelect = getByRole('combobox', { name: 'Thinking' }) as HTMLSelectElement;
		expect([...thinkingSelect.options].map((option) => option.value)).toEqual(['', 'low', 'high']);
		await user.selectOptions(thinkingSelect, 'high');

		// Switching models keeps a level the new model offers and drops one it does not.
		await user.selectOptions(modelSelect, 'claude-sonnet-5-5');
		expect((getByRole('combobox', { name: 'Thinking' }) as HTMLSelectElement).value).toBe('high');
		await user.selectOptions(getByRole('combobox', { name: 'Thinking' }), 'max');
		await user.selectOptions(modelSelect, 'claude-sonnet-6');
		expect((getByRole('combobox', { name: 'Thinking' }) as HTMLSelectElement).value).toBe('');

		await user.selectOptions(getByRole('combobox', { name: 'Thinking' }), 'low');
		await user.click(await findByRole('checkbox', { name: /Refund investigation/ }));
		await user.click(getByRole('button', { name: 'Preview plan' }));

		await waitFor(() => expect(container.querySelector('[data-plan]')).toBeTruthy());
		expect(createPlan).toHaveBeenCalledWith({
			workflow: 'propose-bundles',
			conversation_ids: ['conversation-a'],
			model: { provider: 'anthropic', model_id: 'claude-sonnet-6', thinking_level: 'low' },
			instructions: null
		});
		expect(getByText('a'.repeat(64))).toBeTruthy();
		expect(getByText(/No estimate before the run/)).toBeTruthy();

		await user.click(getByRole('button', { name: 'Approve and run' }));
		expect(approvePlan).toHaveBeenCalledWith('plan-1', 'a'.repeat(64));
		await waitFor(() => expect(getByText('Running')).toBeTruthy());
		expect(getByRole('button', { name: 'Cancel' })).toBeTruthy();
	});

	it('shows no thinking selector for a model without reasoning and lets the operator type an id', async () => {
		vi.mocked(getModelWorkConfig).mockResolvedValue({
			can_run: true,
			workflows: ['propose-bundles'],
			thinking_levels: ['off', 'low', 'medium', 'high', 'xhigh', 'max'],
			max_inputs: 200
		});
		vi.mocked(getModelCatalog).mockResolvedValue(catalog);
		vi.mocked(createPlan).mockResolvedValue(plan);
		const user = userEvent.setup();
		const { findByRole, getByRole, getByText, queryByRole } = render(ProposeRunPanel);

		await findByRole('combobox', { name: 'Model' });
		await user.selectOptions(getByRole('combobox', { name: 'Provider' }), 'openrouter');
		expect((getByRole('combobox', { name: 'Model' }) as HTMLSelectElement).value).toBe(
			'meta-llama/llama-4-maverick'
		);
		expect(queryByRole('combobox', { name: 'Thinking' })).toBeNull();
		expect(getByText('Not offered by this model.')).toBeTruthy();

		await user.click(getByRole('button', { name: 'Type a model id' }));
		const typed = getByRole('textbox', { name: 'Model' });
		await user.clear(typed);
		await user.type(typed, 'anthropic/claude-sonnet-7');
		const thinking = getByRole('combobox', { name: 'Thinking' }) as HTMLSelectElement;
		expect([...thinking.options].map((option) => option.value)).toEqual([
			'',
			'off',
			'low',
			'medium',
			'high',
			'xhigh',
			'max'
		]);
		await user.click(await findByRole('checkbox', { name: /Refund investigation/ }));
		await user.click(getByRole('button', { name: 'Preview plan' }));
		await waitFor(() =>
			expect(createPlan).toHaveBeenCalledWith({
				workflow: 'propose-bundles',
				conversation_ids: ['conversation-a'],
				model: { provider: 'anthropic', model_id: 'claude-sonnet-7', thinking_level: null },
				instructions: null
			})
		);
	});

	it('falls back to a typed model id when the list is unavailable and says why', async () => {
		vi.mocked(getModelWorkConfig).mockResolvedValue({
			can_run: true,
			workflows: ['propose-bundles'],
			thinking_levels: ['off', 'low'],
			max_inputs: 200
		});
		vi.mocked(getModelCatalog).mockRejectedValue(
			new ApiClientError('unavailable', {
				kind: 'http',
				status: 503,
				body: { detail: 'the harness could not list models: models.dev is down' }
			})
		);
		const { findByRole, getByText, queryByRole } = render(ProposeRunPanel);
		expect(await findByRole('textbox', { name: 'Model' })).toBeTruthy();
		expect(getByText(/models.dev is down/)).toBeTruthy();
		expect(queryByRole('button', { name: 'Choose from the list instead' })).toBeNull();
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
		expect(getModelCatalog).not.toHaveBeenCalled();
		await user.click(await findByRole('checkbox', { name: /Refund investigation/ }));
		await user.type(getByRole('textbox', { name: 'Model' }), 'claude-sonnet-5-5');
		await user.click(getByRole('button', { name: 'Preview plan' }));
		const approve = await findByRole('button', { name: 'Approve and run' });
		expect(approve.hasAttribute('disabled')).toBe(true);
	});
});
