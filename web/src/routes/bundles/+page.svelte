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

<div class="conversations-page">
	<header class="conversations-page__header">
		<h1>Evidence bundles</h1>
	</header>

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
					Open a <a href={resolve('/conversations')}>conversation</a>, choose Select evidence, and
					create a bundle from the messages or text you pick.
				</p>
			</section>
		{:else}
			<p class="result-count">{plural(response.items.length, 'bundle')}</p>
			<ol class="conversation-list">
				{#each response.items as bundle (bundle.id)}
					<li class="conversation-row">
						<a
							class="conversation-row__title"
							class:conversation-row__title--untitled={!bundle.objective.trim()}
							href={resolve('/bundles/[id]', { id: bundle.id })}
						>
							{bundleLabel(bundle.objective)}
						</a>
						<p class="conversation-row__meta">
							<span>{statusLabel(bundle.status)}</span>
							<span>{plural(bundle.item_count, 'item')}</span>
							{#if bundle.conversation_ids.length > 1}
								<span>{plural(bundle.conversation_ids.length, 'conversation')}</span>
							{/if}
							<span>Updated {formatTimestamp(bundle.updated_at)}</span>
						</p>
					</li>
				{/each}
			</ol>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Bundles unavailable</h2>
			<p>The local API could not list bundles. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
