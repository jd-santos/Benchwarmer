<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { BundleSummary, ObjectiveType } from '$lib/api/types';
	import {
		bundleLabel,
		describeProducer,
		objectiveTypeLabel,
		objectiveTypeOptions,
		originLabel,
		shortModel,
		shortRunId,
		statusLabel
	} from '$lib/bundles/format';
	import { formatDate, formatTimestamp, plural } from '$lib/conversations/format';
	import { goto } from '$app/navigation';
	import { _views, type BundleView } from './+page';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const listHref = resolve('/bundles');

	function viewHref(
		view: BundleView,
		run: string | null = data.run,
		type: ObjectiveType | null = data.type
	): ResolvedPathname {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams();
		if (view !== 'all') params.set('view', view);
		if (run) params.set('run', run);
		if (type) params.set('type', type);
		const search = params.toString();
		return `${listHref}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	/** A bundle's page, carrying the view so its arrows step through this same list. */
	function bundleHref(id: string): ResolvedPathname {
		const search = viewHref(data.view).split('?')[1];
		const base = resolve('/bundles/[id]', { id });
		return `${base}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	/** The model for a proposal, or the workflow when no model was recorded. */
	function producerNote(bundle: BundleSummary): string | null {
		if (bundle.origin !== 'generated') return null;
		const { workflow, model } = describeProducer(bundle.producer);
		return model ? shortModel(model) : workflow;
	}

	/** Drafts by the run that proposed them, in list order (newest run first). */
	function byRun(items: BundleSummary[]): { runId: string | null; items: BundleSummary[] }[] {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const groups = new Map<string | null, BundleSummary[]>();
		for (const bundle of items) {
			const group = groups.get(bundle.run_id) ?? [];
			group.push(bundle);
			groups.set(bundle.run_id, group);
		}
		return [...groups.entries()].map(([runId, group]) => ({ runId, items: group }));
	}

	const grouped = $derived(data.view === 'proposed' && data.run === null && data.runs !== null);

	const emptyHeading: Record<BundleView, string> = {
		all: 'No bundles yet',
		proposed: 'No proposed drafts to review',
		rejected: 'No rejected bundles'
	};
</script>

{#snippet row(bundle: BundleSummary)}
	{@const note = producerNote(bundle)}
	<tr>
		<th scope="row">
			<a
				class:untitled={!bundle.summary.trim() && !bundle.objective.trim()}
				href={bundleHref(bundle.id)}
			>
				{bundleLabel(bundle)}
			</a>
			{#if bundle.conversation_ids.length > 1}
				<span class="bundle-table__note">
					{plural(bundle.conversation_ids.length, 'conversation')}
				</span>
			{/if}
			{#if bundle.objective.trim() || bundle.objective_type !== 'unknown'}
				<span class="bundle-table__note bundle-table__meta">
					{#if bundle.objective_type !== 'unknown'}{objectiveTypeLabel(bundle.objective_type)}{/if}
					{#if bundle.objective_type !== 'unknown' && bundle.objective.trim()}·{/if}
					{bundle.objective}
				</span>
			{/if}
			<span class="bundle-table__note bundle-table__meta" title={bundle.producer}>
				<span class="bundle-status bundle-status--{bundle.status}"
					>{statusLabel(bundle.status)}</span
				>
				· {originLabel(bundle.origin)}{note ? `, ${note}` : ''}
				· <time datetime={bundle.updated_at}>{formatTimestamp(bundle.updated_at)}</time>
			</span>
		</th>
		<td class="wide-only nowrap" class:muted={bundle.objective_type === 'unknown'}>
			{objectiveTypeLabel(bundle.objective_type)}
		</td>
		<td class="wide-only muted">
			{#if bundle.objective.trim()}{bundle.objective}{:else}Not set{/if}
		</td>
		<td class="wide-only nowrap"
			><span class="bundle-status bundle-status--{bundle.status}">{statusLabel(bundle.status)}</span
			></td
		>
		<td class="wide-only nowrap" title={bundle.producer}>
			{originLabel(bundle.origin)}
			{#if note}<span class="bundle-table__note">{note}</span>{/if}
		</td>
		<td class="numeric">{bundle.item_count}</td>
		<td class="wide-only muted nowrap">
			<time datetime={bundle.updated_at} title={formatTimestamp(bundle.updated_at)}
				>{formatDate(bundle.updated_at)}</time
			>
		</td>
	</tr>
{/snippet}

<svelte:head>
	<title>Evidence bundles · Benchwarmer</title>
	<meta name="description" content="Review evidence bundles assembled from conversations." />
</svelte:head>

<div class="bundles-page">
	<h1 class="page-title">Evidence bundles</h1>

	<nav class="view-links" aria-label="Bundle views">
		{#each _views as view (view.value)}
			<a
				href={viewHref(view.value)}
				aria-current={data.view === view.value ? 'page' : undefined}
				title={view.hint}
			>
				{view.label}
				{#if view.value === 'proposed' && data.proposedCount !== null}
					{#await data.proposedCount then count}
						{#if count !== null && count > 0}
							<span class="view-links__count">{count}</span>
						{/if}
					{/await}
				{/if}
			</a>
		{/each}
	</nav>

	<form class="list-filter" onsubmit={(event) => event.preventDefault()}>
		<label class="list-filter__field">
			<span>Type of work</span>
			<select
				value={data.type ?? ''}
				onchange={(event) =>
					goto(
						viewHref(
							data.view,
							data.run,
							(event.currentTarget.value || null) as ObjectiveType | null
						),
						{ keepFocus: true }
					)}
			>
				<option value="">All types</option>
				{#each objectiveTypeOptions as option (option.value)}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</label>
	</form>

	{#if data.run}
		<p class="muted view-note" data-run-note>
			Showing bundles whose latest revision came from harness run
			<code>{data.run}</code>. <a href={viewHref(data.view, null)}>Show every run</a>
		</p>
	{/if}

	{#if data.view === 'proposed'}
		<p class="muted view-note">
			A model proposed these drafts in a hand-run harness pass. Open one to check each cited item,
			then mark it Reviewed to accept it or Rejected with a reason. Nothing here is approved until a
			person saves it.
		</p>
	{/if}

	{#await data.bundles}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading bundles</h2>
			<p>Reading saved bundles…</p>
		</section>
	{:then response}
		{#if response.items.length === 0}
			<section class="status-panel" aria-labelledby="no-bundles-heading">
				<h2 id="no-bundles-heading">{emptyHeading[data.view]}</h2>
				{#if data.view === 'all'}
					<p>
						In a <a href={resolve('/conversations')}>conversation</a>, tick the checkbox beside a
						turn or highlight text, then create a bundle from the evidence tray.
					</p>
				{:else if data.view === 'proposed'}
					<p>
						Proposed drafts appear after an operator runs the analysis harness by hand.
						<a href={viewHref('all')}>All bundles</a>
					</p>
				{:else}
					<p>
						Rejecting a bundle keeps it here with its reason.
						<a href={viewHref('all')}>All bundles</a>
					</p>
				{/if}
			</section>
		{:else}
			<table class="data-table bundle-table">
				<colgroup>
					<col class="bundle-table__col-summary" />
					<col class="bundle-table__col-type" />
					<col class="bundle-table__col-objective" />
					<col />
					<col />
					<col />
					<col />
				</colgroup>
				<thead>
					<tr>
						<th scope="col">Bundle</th>
						<th scope="col" class="wide-only nowrap">Type</th>
						<th scope="col" class="wide-only">Objective</th>
						<th scope="col" class="wide-only nowrap">Status</th>
						<th scope="col" class="wide-only nowrap">Origin</th>
						<th scope="col" class="numeric">Items</th>
						<th scope="col" class="wide-only nowrap">Updated</th>
					</tr>
				</thead>
				{#if grouped && data.runs}
					{#await data.runs then runs}
						{#each byRun(response.items) as group (group.runId ?? 'none')}
							{@const record = runs.find((run) => run.run_id === group.runId) ?? null}
							<tbody class="bundle-table__group">
								<tr>
									<th scope="colgroup" colspan="7" class="bundle-table__group-heading">
										{#if group.runId}
											<a href={resolve('/runs/[id]', { id: group.runId })}
												>Run {shortRunId(group.runId)}</a
											>
											{#if record}
												· <span title="{record.provider}/{record.model}"
													>{shortModel(record.model)}</span
												>
												·
												<time datetime={record.started_at}
													>{formatTimestamp(record.started_at)}</time
												>
											{/if}
											· {plural(group.items.length, 'draft')}
											· <a href={viewHref('proposed', group.runId)}>Only this run</a>
										{:else}
											Not from a recorded run · {plural(group.items.length, 'draft')}
										{/if}
									</th>
								</tr>
								{#each group.items as bundle (bundle.id)}
									{@render row(bundle)}
								{/each}
							</tbody>
						{/each}
					{/await}
				{:else}
					<tbody>
						{#each response.items as bundle (bundle.id)}
							{@render row(bundle)}
						{/each}
					</tbody>
				{/if}
			</table>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Bundles unavailable</h2>
			<p>The local API could not list bundles. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
