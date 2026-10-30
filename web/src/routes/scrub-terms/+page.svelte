<script lang="ts">
	import TermListManager from '$lib/components/TermListManager.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Scrub terms · Benchwarmer</title>
	<meta
		name="description"
		content="Named, versioned lists of terms the case export scrubs besides the built-in kinds."
	/>
</svelte:head>

<div class="term-lists-page">
	<h1 class="page-title">Scrub terms</h1>
	<p class="muted view-note">
		The export scrubs emails, URLs, paths, addresses, secrets, and hostnames on its own. Everything
		else it should hide, such as people, customers, hosts without a known suffix, and project
		codenames, comes from a term list. Lists are versioned: a changed save makes the next version
		and a record names the version it used.
	</p>

	{#await data.lists}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading term lists</h2>
			<p>Reading stored lists…</p>
		</section>
	{:then response}
		<TermListManager lists={response.items} />
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Term lists unavailable</h2>
			<p>The local API could not list term lists. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
