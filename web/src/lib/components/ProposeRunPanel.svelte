<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import {
		ApiClientError,
		approvePlan,
		cancelPlan,
		createPlan,
		getConversations,
		getModelCatalog,
		getModelWorkConfig,
		getPlan,
		getPlans
	} from '$lib/api/client';
	import type {
		CatalogModel,
		ConversationSummary,
		ModelCatalog,
		ModelWorkConfig,
		ModelWorkPlan
	} from '$lib/api/types';
	import { formatDate, formatTimestamp, plural } from '$lib/conversations/format';
	import { onDestroy, onMount } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';

	/**
	 * Propose bundles for chosen conversations with a model, from the app.
	 * Nothing runs until the operator approves the exact frozen plan.
	 *
	 * The model list comes from the harness: providers whose key the server
	 * holds, each with the models its own list, models.dev, and the pinned
	 * catalog know. Thinking levels are the chosen model's own. An operator can
	 * always type a model id instead.
	 */
	let config = $state<ModelWorkConfig | null | 'unavailable'>(null);
	let catalog = $state<ModelCatalog | null>(null);
	let catalogError = $state<string | null>(null);
	let listing = $state(false);
	let conversations = $state<ConversationSummary[]>([]);
	let total = $state(0);
	let query = $state('');
	let searching = $state(false);
	const chosen = new SvelteSet<string>();
	let providerId = $state('');
	let catalogModelId = $state('');
	let typed = $state(false);
	let typedModel = $state('anthropic/');
	let thinking = $state('');
	let instructions = $state('');
	let plan = $state<ModelWorkPlan | null>(null);
	let recent = $state<ModelWorkPlan[]>([]);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;

	const providers = $derived(catalog?.providers.filter((item) => item.model_count > 0) ?? []);
	const providerName = $derived(
		providers.find((item) => item.id === providerId)?.name ?? providerId
	);
	const providerModels = $derived(
		catalog?.models.filter((model) => model.provider === providerId && model.runnable) ?? []
	);
	const listedModels = $derived(
		providerModels.filter((model) => model.listed_by_provider !== false)
	);
	const unlistedModels = $derived(
		providerModels.filter((model) => model.listed_by_provider === false)
	);
	const selected = $derived<CatalogModel | undefined>(
		providerModels.find((model) => model.id === catalogModelId)
	);
	/** Picking from the list, as opposed to typing an id. */
	const fromList = $derived(!typed && catalog !== null && providers.length > 0);

	const [provider, modelId] = $derived.by(() => {
		if (fromList) return [providerId, catalogModelId];
		const index = typedModel.indexOf('/');
		return index === -1
			? [typedModel.trim(), '']
			: [typedModel.slice(0, index).trim(), typedModel.slice(index + 1).trim()];
	});
	/** Levels the chosen model offers; every configured level when the model is typed. */
	const thinkingLevels = $derived(
		fromList
			? (selected?.thinking_levels ?? [])
			: config && config !== 'unavailable'
				? config.thinking_levels
				: []
	);
	const canPreview = $derived(chosen.size > 0 && provider !== '' && modelId !== '' && !busy);
	const live = $derived(plan !== null && (plan.status === 'approved' || plan.status === 'running'));

	$effect(() => {
		// A level the current model does not offer falls back to its default.
		if (thinking && !thinkingLevels.includes(thinking)) thinking = '';
	});

	async function search(): Promise<void> {
		searching = true;
		try {
			const page = await getConversations({ q: query.trim() || undefined, limit: 50 });
			conversations = page.items;
			total = page.total;
		} catch {
			conversations = [];
			total = 0;
		} finally {
			searching = false;
		}
	}

	async function loadRecent(): Promise<void> {
		try {
			recent = (await getPlans()).slice(0, 5);
		} catch {
			recent = [];
		}
	}

	function pickDefaults(next: ModelCatalog): void {
		const available = next.providers.filter((item) => item.model_count > 0);
		if (!available.some((item) => item.id === providerId)) providerId = available[0]?.id ?? '';
		pickFirstModel(next);
	}

	function pickFirstModel(next: ModelCatalog): void {
		const models = next.models.filter((model) => model.provider === providerId && model.runnable);
		if (models.some((model) => model.id === catalogModelId)) return;
		catalogModelId =
			models.find((model) => model.listed_by_provider !== false)?.id ?? models[0]?.id ?? '';
	}

	async function listModels(refresh = false): Promise<void> {
		listing = true;
		catalogError = null;
		try {
			const next = await getModelCatalog({ refresh });
			catalog = next;
			pickDefaults(next);
		} catch (failure) {
			catalogError = describe(failure, 'The model list could not be read from the API.');
			if (catalog === null) typed = true;
		} finally {
			listing = false;
		}
	}

	function changeProvider(next: string): void {
		providerId = next;
		if (catalog) pickFirstModel(catalog);
	}

	onMount(async () => {
		try {
			config = await getModelWorkConfig();
		} catch {
			config = 'unavailable';
			return;
		}
		const tasks = [search(), loadRecent()];
		if (config.can_run) tasks.push(listModels());
		else typed = true;
		await Promise.all(tasks);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function describe(failure: unknown, fallback?: string): string {
		if (
			failure instanceof ApiClientError &&
			(failure.status === 422 || failure.status === 409 || failure.status === 503)
		) {
			const body = failure.body;
			if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string')
				return body.detail;
		}
		return (
			fallback ?? 'The request did not reach the API, or the API refused it. Check the server log.'
		);
	}

	async function preview(): Promise<void> {
		busy = true;
		error = null;
		try {
			plan = await createPlan({
				workflow: 'propose-bundles',
				conversation_ids: [...chosen],
				model: { provider, model_id: modelId, thinking_level: thinking || null },
				instructions: instructions.trim() || null
			});
		} catch (failure) {
			error = describe(failure);
		} finally {
			busy = false;
		}
	}

	function watch(id: string): void {
		if (timer) clearInterval(timer);
		timer = setInterval(async () => {
			try {
				const latest = await getPlan(id);
				plan = latest;
				if (latest.status !== 'running' && latest.status !== 'approved') {
					if (timer) clearInterval(timer);
					timer = null;
					await loadRecent();
				}
			} catch {
				// Keep polling; a transient failure should not stop the view.
			}
		}, 3000);
	}

	async function approve(): Promise<void> {
		if (!plan) return;
		busy = true;
		error = null;
		try {
			plan = await approvePlan(plan.id, plan.digest);
			await loadRecent();
			if (plan.status === 'running' || plan.status === 'approved') watch(plan.id);
		} catch (failure) {
			error = describe(failure);
		} finally {
			busy = false;
		}
	}

	async function cancel(): Promise<void> {
		if (!plan) return;
		busy = true;
		try {
			plan = await cancelPlan(plan.id);
			await loadRecent();
		} catch (failure) {
			error = describe(failure);
		} finally {
			busy = false;
		}
	}

	function discard(): void {
		plan = null;
		error = null;
	}

	function runBundlesHref(runId: string): ResolvedPathname {
		return `${resolve('/bundles')}?${new URLSearchParams({
			view: 'proposed',
			run: runId
		})}` as ResolvedPathname;
	}

	const money = new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
		maximumFractionDigits: 2
	});

	/** Short enough for a select: the name and when it came out; the id sits in the facts line. */
	function modelLabel(model: CatalogModel): string {
		return model.release_date ? `${model.name} · ${model.release_date}` : model.name;
	}

	function tokens(count: number): string {
		return count >= 1_000_000
			? `${Math.round(count / 100_000) / 10}M`
			: `${Math.round(count / 1000)}k`;
	}

	/** One quiet line under the model: its id, price, window, and whether the harness knows it. */
	function modelFacts(model: CatalogModel): string {
		const facts: string[] = [];
		if (model.name !== model.id) facts.push(model.id);
		if (model.cost)
			facts.push(
				`${money.format(model.cost.input)} in, ${money.format(model.cost.output)} out per M tokens`
			);
		else facts.push('no price in any catalog; the run records zero cost');
		if (model.context_window) facts.push(`${tokens(model.context_window)} context`);
		if (!model.sources.includes('pi-ai'))
			facts.push('not in the pinned harness catalog; runs with a sibling model’s settings');
		return facts.join(' · ');
	}

	const sourceLabel: Record<ModelCatalog['providers'][number]['provider_list'], string> = {
		listed: 'from its own model list',
		unavailable: 'its model list could not be read',
		not_offered: 'it publishes no model list',
		skipped: 'its model list was not checked'
	};

	const statusLabel: Record<ModelWorkPlan['status'], string> = {
		proposed: 'Awaiting approval',
		approved: 'Starting',
		running: 'Running',
		finished: 'Finished',
		failed: 'Failed',
		cancelled: 'Cancelled',
		interrupted: 'Interrupted'
	};
</script>

<details class="propose-run" data-propose-run>
	<summary>Propose bundles with a model</summary>
	{#if config === null}
		<p class="muted" aria-live="polite">Checking whether this application can start runs…</p>
	{:else if config === 'unavailable'}
		<p class="muted">The model-work settings could not be read from the API.</p>
	{:else}
		{#if !config.can_run}
			<p class="notice" role="status" data-cannot-run>
				This application can preview plans but cannot start them. Set
				<code>BENCHWARMER_HARNESS_DIR</code> to the checkout's <code>harness</code> directory on the server
				and restart it, or run the harness by hand with the command a plan shows.
			</p>
		{/if}
		{#if plan === null}
			<div class="propose-run__form">
				<section class="propose-run__pick" aria-labelledby="plan-pick-heading">
					<h3 id="plan-pick-heading">Conversations</h3>
					<form
						class="propose-run__search"
						onsubmit={(event) => (event.preventDefault(), search())}
					>
						<label for="plan-search" class="visually-hidden">Find conversations</label>
						<input
							id="plan-search"
							type="search"
							bind:value={query}
							placeholder="Keyword in title or text"
						/>
						<button type="submit" class="button" disabled={searching}>Search</button>
					</form>
					{#if conversations.length === 0}
						<p class="muted">{searching ? 'Searching…' : 'No conversations match.'}</p>
					{:else}
						<p class="muted propose-run__count" aria-live="polite">
							{plural(chosen.size, 'conversation')} chosen · showing {conversations.length} of {total}
						</p>
						<ul class="propose-run__list">
							{#each conversations as conversation (conversation.id)}
								<li>
									<label class="propose-run__row">
										<input
											type="checkbox"
											checked={chosen.has(conversation.id)}
											onchange={(event) =>
												event.currentTarget.checked
													? chosen.add(conversation.id)
													: chosen.delete(conversation.id)}
										/>
										<span class="propose-run__title"
											>{conversation.title ?? conversation.native_id}</span
										>
										<span class="muted propose-run__meta">
											{conversation.source.kind} · {plural(conversation.message_count, 'message')}
											{#if conversation.started_at}
												· {formatDate(conversation.started_at)}
											{/if}
										</span>
									</label>
								</li>
							{/each}
						</ul>
					{/if}
				</section>

				<section class="propose-run__setup" aria-labelledby="plan-run-heading">
					<h3 id="plan-run-heading">Run</h3>
					{#if listing && catalog === null}
						<p class="muted" aria-live="polite">Listing the models this server has keys for…</p>
					{:else if fromList}
						<div class="field">
							<label for="plan-provider">Provider</label>
							<select
								id="plan-provider"
								value={providerId}
								onchange={(event) => changeProvider(event.currentTarget.value)}
							>
								{#each providers as item (item.id)}
									<option value={item.id}>{item.name}</option>
								{/each}
							</select>
						</div>
						<div class="field">
							<label for="plan-model">Model</label>
							<select
								id="plan-model"
								bind:value={catalogModelId}
								aria-describedby="plan-model-facts"
							>
								{#if unlistedModels.length > 0}
									<optgroup label="Listed by {providerName}">
										{#each listedModels as model (model.id)}
											<option value={model.id}>{modelLabel(model)}</option>
										{/each}
									</optgroup>
									<optgroup label="In catalogs, not in {providerName}'s list">
										{#each unlistedModels as model (model.id)}
											<option value={model.id}>{modelLabel(model)}</option>
										{/each}
									</optgroup>
								{:else}
									{#each listedModels as model (model.id)}
										<option value={model.id}>{modelLabel(model)}</option>
									{/each}
								{/if}
							</select>
							<p id="plan-model-facts" class="field__hint">
								{#if selected}{modelFacts(selected)}{:else}Choose a model.{/if}
							</p>
						</div>
						<div class="field">
							<label for="plan-thinking">Thinking</label>
							{#if selected && selected.reasoning === false}
								<p id="plan-thinking" class="field__static muted">Not offered by this model.</p>
							{:else}
								<select id="plan-thinking" bind:value={thinking}>
									<option value="">Model default</option>
									{#each thinkingLevels as level (level)}
										<option value={level}>{level}</option>
									{/each}
								</select>
								{#if selected && selected.reasoning === null}
									<p class="field__hint">No catalog says whether this model offers thinking.</p>
								{/if}
							{/if}
						</div>
						<p class="muted propose-run__source">
							{#each providers.filter((item) => item.id === providerId) as item (item.id)}
								{item.name}: {sourceLabel[item.provider_list]}{item.models_dev === 'listed'
									? ' and models.dev'
									: ''}.
							{/each}
							<button
								type="button"
								class="text-button"
								disabled={listing}
								onclick={() => listModels(true)}
							>
								{listing ? 'Refreshing…' : 'Refresh'}
							</button>
							·
							<button type="button" class="text-button" onclick={() => (typed = true)}>
								Type a model id
							</button>
						</p>
						{#if catalogError}
							<p class="field__error" role="alert">{catalogError}</p>
						{/if}
					{:else}
						<div class="field">
							<label for="plan-model">Model</label>
							<input
								id="plan-model"
								type="text"
								bind:value={typedModel}
								autocomplete="off"
								spellcheck="false"
								placeholder="provider/model-id"
								aria-describedby="plan-model-hint"
							/>
							<p id="plan-model-hint" class="field__hint">
								As the harness names it, such as <code>anthropic/claude-sonnet-5-5</code>. The
								server needs that provider's key in its environment.
							</p>
						</div>
						<div class="field">
							<label for="plan-thinking">Thinking</label>
							<select id="plan-thinking" bind:value={thinking}>
								<option value="">Model default</option>
								{#each thinkingLevels as level (level)}
									<option value={level}>{level}</option>
								{/each}
							</select>
						</div>
						{#if catalog !== null && providers.length > 0}
							<p class="muted propose-run__source">
								<button type="button" class="text-button" onclick={() => (typed = false)}>
									Choose from the list instead
								</button>
							</p>
						{:else if catalogError}
							<p class="muted propose-run__source" role="status">
								No model list: {catalogError}
							</p>
						{:else if catalog !== null}
							<p class="muted propose-run__source" role="status">
								{catalog.notes[0] ??
									'No provider key is set on the server, so there is no list to choose from.'}
							</p>
						{/if}
					{/if}
					<div class="field propose-run__instructions">
						<label for="plan-notes">Operator notes (optional)</label>
						<textarea id="plan-notes" rows="3" maxlength="4000" bind:value={instructions}
						></textarea>
					</div>
					<div class="propose-run__submit">
						<button type="button" class="button" disabled={!canPreview} onclick={preview}>
							Preview plan
						</button>
						<span class="muted">
							{#if chosen.size === 0}
								Choose at least one conversation.
							{:else if !provider || !modelId}
								Choose a model.
							{:else}
								{plural(chosen.size, 'conversation')} · {provider}/{modelId}{thinking
									? ` · thinking ${thinking}`
									: ''}
							{/if}
						</span>
					</div>
					{#if error}
						<p class="field__error" role="alert">{error}</p>
					{/if}
				</section>
			</div>
		{:else}
			<section class="plan" aria-labelledby="plan-heading" data-plan>
				<h3 id="plan-heading">
					Plan · <span class="plan__status plan__status--{plan.status}"
						>{statusLabel[plan.status]}</span
					>
				</h3>
				<dl class="plan__facts">
					<dt>Workflow</dt>
					<dd>{plan.workflow}</dd>
					<dt>Model</dt>
					<dd>
						{plan.model.provider}/{plan.model.model_id}{plan.model.thinking_level
							? `, thinking ${plan.model.thinking_level}`
							: ''}
					</dd>
					<dt>Inputs</dt>
					<dd>
						{plural(plan.inputs.length, 'conversation')}, each pinned to its current import
						<ul class="plan__inputs">
							{#each plan.inputs as input (input.conversation_id)}
								<li>
									<a href={resolve('/conversations/[id]', { id: input.conversation_id })}
										>{input.title ?? input.conversation_id}</a
									>
								</li>
							{/each}
						</ul>
					</dd>
					{#if plan.instructions}
						<dt>Notes</dt>
						<dd>{plan.instructions}</dd>
					{/if}
					<dt>Cost</dt>
					<dd>
						No estimate before the run. Usage and a catalog estimate are recorded on the Runs page
						when it finishes. Private conversation text is sent to this provider.
					</dd>
					<dt>Digest</dt>
					<dd><code class="plan__digest">{plan.digest}</code></dd>
				</dl>
				{#if error}
					<p class="field__error" role="alert">{error}</p>
				{/if}
				{#if plan.error_summary && plan.status !== 'proposed'}
					<p class="muted" role="status">{plan.error_summary}</p>
				{/if}
				<div class="plan__actions">
					{#if plan.status === 'proposed'}
						<button
							type="button"
							class="button button--primary"
							disabled={busy || !config.can_run}
							onclick={approve}
						>
							Approve and run
						</button>
						<button type="button" class="text-button" disabled={busy} onclick={discard}>
							Discard
						</button>
					{:else if live}
						<button type="button" class="button" disabled={busy} onclick={cancel}>Cancel</button>
						<span class="muted" aria-live="polite"
							>Started {plan.started_at ? formatTimestamp(plan.started_at) : 'just now'}.</span
						>
					{:else}
						{#if plan.run_id}
							<a href={resolve('/runs/[id]', { id: plan.run_id })}>Run details</a>
							<a href={runBundlesHref(plan.run_id)}>Review its drafts</a>
						{/if}
						<button type="button" class="text-button" onclick={discard}>New plan</button>
					{/if}
				</div>
			</section>
		{/if}
		{#if recent.length > 0}
			<section class="plan-history" aria-labelledby="plan-history-heading">
				<h3 id="plan-history-heading">Recent plans</h3>
				<ul>
					{#each recent as item (item.id)}
						<li>
							<time datetime={item.created_at}>{formatTimestamp(item.created_at)}</time>
							· {plural(item.inputs.length, 'conversation')}
							· {item.model.provider}/{item.model.model_id}
							·
							<span class="plan__status plan__status--{item.status}"
								>{statusLabel[item.status]}</span
							>
							{#if item.run_id && (item.status === 'finished' || item.status === 'failed' || item.status === 'cancelled')}
								· <a href={resolve('/runs/[id]', { id: item.run_id })}>run</a>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}
</details>
