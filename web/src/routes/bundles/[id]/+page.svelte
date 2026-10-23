<script lang="ts">
	import { resolve } from '$app/paths';
	import { ApiClientError } from '$lib/api/client';
	import { bundleLabel } from '$lib/bundles/format';
	import BundleEditor from '$lib/components/BundleEditor.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let title = $state('Bundle');

	$effect(() => {
		let current = true;
		title = 'Bundle';
		data.bundle.then(
			(detail) => {
				if (current) title = bundleLabel(detail.document);
			},
			() => undefined
		);
		return () => {
			current = false;
		};
	});

	function isMissing(error: unknown): boolean {
		return error instanceof ApiClientError && error.status === 404;
	}
</script>

<svelte:head>
	<title>{title} · Benchwarmer</title>
</svelte:head>

{#await data.bundle}
	<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
		<h2>Loading bundle</h2>
		<p>Resolving its evidence…</p>
	</section>
{:then detail}
	{#key `${detail.id}:${detail.revision}`}
		<BundleEditor {detail} run={data.run} />
	{/key}
{:catch error}
	<section class="status-panel status-panel--error" role="alert">
		{#if isMissing(error)}
			<h2>{data.revision ? 'Revision not found' : 'Bundle not found'}</h2>
			<p>The link may be wrong. <a href={resolve('/bundles')}>All bundles</a></p>
		{:else}
			<h2>Bundle unavailable</h2>
			<p>
				The local API could not provide this bundle. Check that it is running and reload this page.
			</p>
		{/if}
	</section>
{/await}
