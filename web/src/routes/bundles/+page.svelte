<script lang="ts">
	import { resolve } from '$app/paths';
	import { bundleLabel, statusLabel } from '$lib/bundles/format';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Evidence bundles · Benchwarmer</title>
	<meta name="description" content="Review evidence bundles assembled from conversations." />
</svelte:head>

<div class="bundles-page">
	<h1 class="page-title">Evidence bundles</h1>

	{#await data.bundles}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading bundles</h2>
			<p>Reading saved bundles…</p>
		</section>
	{:then response}
		{#if response.items.length === 0}
			<section class="status-panel" aria-labelledby="no-bundles-heading">
				<h2 id="no-bundles-heading">No bundles yet</h2>
				<p>
					In a <a href={resolve('/conversations')}>conversation</a>, choose
					<strong>Select evidence</strong>, pick messages or highlight text, then create a bundle.
				</p>
			</section>
		{:else}
			<table class="data-table bundle-table">
				<thead>
					<tr>
						<th scope="col">Objective</th>
						<th scope="col">Status</th>
						<th scope="col" class="numeric">Items</th>
						<th scope="col">Updated</th>
					</tr>
				</thead>
				<tbody>
					{#each response.items as bundle (bundle.id)}
						<tr>
							<th scope="row">
								<a
									class:untitled={!bundle.objective.trim()}
									href={resolve('/bundles/[id]', { id: bundle.id })}
								>
									{bundleLabel(bundle.objective)}
								</a>
								{#if bundle.conversation_ids.length > 1}
									<span class="bundle-table__note">
										{plural(bundle.conversation_ids.length, 'conversation')}
									</span>
								{/if}
							</th>
							<td
								><span class="bundle-status bundle-status--{bundle.status}"
									>{statusLabel(bundle.status)}</span
								></td
							>
							<td class="numeric">{bundle.item_count}</td>
							<td class="muted">{formatTimestamp(bundle.updated_at)}</td>
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
