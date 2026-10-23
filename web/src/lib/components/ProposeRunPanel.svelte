<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import {
		ApiClientError,
		approvePlan,
		cancelPlan,
		createPlan,
		getConversations,
		getModelWorkConfig,
		getPlan,
		getPlans
	} from '$lib/api/client';
	import type { ConversationSummary, ModelWorkConfig, ModelWorkPlan } from '$lib/api/types';
	import { formatDate, formatTimestamp, plural } from '$lib/conversations/format';
	import { onDestroy, onMount } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';

	/**
	 * Propose bundles for chosen conversations with a model, from the app.
	 * Nothing runs until the operator approves the exact frozen plan.
	 */
	let config = $state<ModelWorkConfig | null | 'unavailable'>(null);
	let conversations = $state<ConversationSummary[]>([]);
	let total = $state(0);
	let query = $state('');
	let searching = $state(false);
	const chosen = new SvelteSet<string>();
	let model = $state('anthropic/');
	let thinking = $state('');
	let instructions = $state('');
	let plan = $state<ModelWorkPlan | null>(null);
	let recent = $state<ModelWorkPlan[]>([]);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;

	const [provider, modelId] = $derived.by(() => {
		const index = model.indexOf('/');
		return index === -1
			? [model.trim(), '']
			: [model.slice(0, index).trim(), model.slice(index + 1).trim()];
	});
	const canPreview = $derived(chosen.size > 0 && provider !== '' && modelId !== '' && !busy);
	const live = $derived(plan !== null && (plan.status === 'approved' || plan.status === 'running'));

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

	onMount(async () => {
		try {
			config = await getModelWorkConfig();
		} catch {
			config = 'unavailable';
			return;
		}
		await Promise.all([search(), loadRecent()]);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function describe(failure: unknown): string {
		if (failure instanceof ApiClientError && (failure.status === 422 || failure.status === 409)) {
			const body = failure.body;
			if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string')
				return body.detail;
		}
		return 'The request did not reach the API, or the API refused it. Check the server log.';
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
			<div class="propose-run__pick">
				<form class="propose-run__search" onsubmit={(event) => (event.preventDefault(), search())}>
					<div class="field">
						<label for="plan-search">Find conversations</label>
						<input
							id="plan-search"
							type="search"
							bind:value={query}
							placeholder="Keyword in title or text"
						/>
					</div>
					<button type="submit" class="button" disabled={searching}>Search</button>
				</form>
				{#if conversations.length === 0}
					<p class="muted">{searching ? 'Searching…' : 'No conversations match.'}</p>
				{:else}
					<p class="muted propose-run__count">
						Showing {conversations.length} of {plural(total, 'conversation')}. {plural(
							chosen.size,
							'conversation'
						)} chosen.
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
			</div>
			<div class="propose-run__model">
				<div class="field">
					<label for="plan-model">Model</label>
					<input
						id="plan-model"
						type="text"
						bind:value={model}
						autocomplete="off"
						spellcheck="false"
						placeholder="provider/model-id"
						aria-describedby="plan-model-hint"
					/>
					<p id="plan-model-hint" class="field__hint">
						As the harness names it, such as <code>anthropic/claude-sonnet-5-5</code>. The server
						needs that provider's key in its environment.
					</p>
				</div>
				<div class="field">
					<label for="plan-thinking">Thinking</label>
					<select id="plan-thinking" bind:value={thinking}>
						<option value="">Model default</option>
						{#each config.thinking_levels as level (level)}
							<option value={level}>{level}</option>
						{/each}
					</select>
				</div>
				<div class="field propose-run__instructions">
					<label for="plan-notes">Operator notes (optional)</label>
					<textarea id="plan-notes" rows="2" maxlength="4000" bind:value={instructions}></textarea>
				</div>
				<button type="button" class="button" disabled={!canPreview} onclick={preview}>
					Preview plan
				</button>
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
