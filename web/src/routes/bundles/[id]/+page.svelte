<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import { ApiClientError } from '$lib/api/client';
	import { bundleLabel } from '$lib/bundles/format';
	import BundleEditor from '$lib/components/BundleEditor.svelte';
	import { _views, type BundleView } from '../+page';
	import type { BundleNavigation } from './+page';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let title = $state('Bundle');

	function listHref(navigation: BundleNavigation): ResolvedPathname {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams();
		if (navigation.view !== 'all') params.set('view', navigation.view);
		if (navigation.run) params.set('run', navigation.run);
		const search = params.toString();
		return `${resolve('/bundles')}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	/** A sibling bundle, keeping the list context so the arrows keep working there. */
	function bundleHref(navigation: BundleNavigation, id: string): ResolvedPathname {
		const base = resolve('/bundles/[id]', { id });
		const search = listHref(navigation).split('?')[1];
		return `${base}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	function viewLabel(view: BundleView): string {
		return _views.find((option) => option.value === view)?.label ?? 'All bundles';
	}

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
	{#await data.navigation then navigation}
		{#if navigation}
			<nav class="bundle-nav" aria-label="Bundles in this view">
				<a href={listHref(navigation)}>← {viewLabel(navigation.view)}</a>
				<span class="bundle-nav__steps">
					{#if navigation.position !== null}
						<span>{navigation.position} of {navigation.total}</span>
					{/if}
					{#if navigation.previousId}
						<a href={bundleHref(navigation, navigation.previousId)} rel="prev">← Previous</a>
					{:else}
						<span aria-disabled="true">← Previous</span>
					{/if}
					{#if navigation.nextId}
						<a href={bundleHref(navigation, navigation.nextId)} rel="next">Next →</a>
					{:else}
						<span aria-disabled="true">Next →</span>
					{/if}
				</span>
			</nav>
		{/if}
	{/await}
	{#key `${detail.id}:${detail.revision}`}
		{#await data.navigation}
			<BundleEditor {detail} run={data.run} />
		{:then navigation}
			<BundleEditor
				{detail}
				run={data.run}
				nextHref={navigation?.nextId ? bundleHref(navigation, navigation.nextId) : null}
			/>
		{/await}
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
