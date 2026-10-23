<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { BundleSummary } from '$lib/api/types';
	import {
		bundleLabel,
		describeProducer,
		formatEstimate,
		originLabel,
		shortModel,
		statusLabel,
		usageTotals
	} from '$lib/bundles/format';
	import { formatDate, formatTimestamp, plural } from '$lib/conversations/format';
	import { _views, type BundleView } from './+page';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const listHref = resolve('/bundles');

	function viewHref(view: BundleView, run: string | null = data.run): ResolvedPathname {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams();
		if (view !== 'all') params.set('view', view);
		if (run) params.set('run', run);
		const search = params.toString();
		return `${listHref}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	/** The model for a proposal, or the workflow when no model was recorded. */
	function producerNote(bundle: BundleSummary): string | null {
		if (bundle.origin !== 'generated') return null;
		const { workflow, model } = describeProducer(bundle.producer);
		return model ? shortModel(model) : workflow;
	}

	const emptyHeading: Record<BundleView, string> = {
		all: 'No bundles yet',
		proposed: 'No proposed drafts to review',
		rejected: 'No rejected bundles'
	};
</script>

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

	{#if data.run}
		<p class="muted view-note" data-run-note>
			Showing bundles whose latest revision came from harness run
			<code>{data.run}</code>. <a href={viewHref(data.view, null)}>Show every run</a>
		</p>
		{#if data.runRecord}
			{#await data.runRecord then run}
				{#if run}
					{@const totals = usageTotals(run.usage_total)}
					<p class="muted view-note" data-run-usage>
						{run.model.provider}/{run.model.model_id}{run.model.thinking_level
							? `, thinking ${run.model.thinking_level}`
							: ''}
						· {plural(run.inputs.length, 'conversation')} · {totals.tokens.toLocaleString()} tokens ·
						about {formatEstimate(totals.estimate)} ({run.pricing_source})
						{#if run.model.base_url_override}
							· via {new URL(run.model.base_url_override).host}
						{/if}
					</p>
				{/if}
			{/await}
		{/if}
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
						In a <a href={resolve('/conversations')}>conversation</a>, choose
						<strong>Select evidence</strong>, pick messages or highlight text, then create a bundle.
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
					<col class="bundle-table__col-objective" />
					<col />
					<col />
					<col />
					<col />
				</colgroup>
				<thead>
					<tr>
						<th scope="col">Bundle</th>
						<th scope="col" class="wide-only">Objective</th>
						<th scope="col" class="wide-only nowrap">Status</th>
						<th scope="col" class="wide-only nowrap">Origin</th>
						<th scope="col" class="numeric">Items</th>
						<th scope="col" class="wide-only nowrap">Updated</th>
					</tr>
				</thead>
				<tbody>
					{#each response.items as bundle (bundle.id)}
						{@const note = producerNote(bundle)}
						<tr>
							<th scope="row">
								<a
									class:untitled={bundleLabel(bundle) === 'Untitled bundle'}
									href={resolve('/bundles/[id]', { id: bundle.id })}
								>
									{bundleLabel(bundle)}
								</a>
								{#if bundle.conversation_ids.length > 1}
									<span class="bundle-table__note">
										{plural(bundle.conversation_ids.length, 'conversation')}
									</span>
								{/if}
								{#if bundle.objective.trim()}
									<span class="bundle-table__note bundle-table__meta">{bundle.objective}</span>
								{/if}
								<span class="bundle-table__note bundle-table__meta" title={bundle.producer}>
									<span class="bundle-status bundle-status--{bundle.status}"
										>{statusLabel(bundle.status)}</span
									>
									· {originLabel(bundle.origin)}{note ? `, ${note}` : ''}
									· <time datetime={bundle.updated_at}>{formatTimestamp(bundle.updated_at)}</time>
								</span>
							</th>
							<td class="wide-only muted">
								{#if bundle.objective.trim()}{bundle.objective}{:else}Not set{/if}
							</td>
							<td class="wide-only nowrap"
								><span class="bundle-status bundle-status--{bundle.status}"
									>{statusLabel(bundle.status)}</span
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
					{/each}
				</tbody>
			</table>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Bundles unavailable</h2>
			<p>The local API could not list bundles. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
