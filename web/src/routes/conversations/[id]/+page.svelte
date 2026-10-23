<script lang="ts">
	import { resolve } from '$app/paths';
	import { ApiClientError } from '$lib/api/client';
	import ConversationReader from '$lib/components/ConversationReader.svelte';
	import { conversationLabel } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let title = $state('Conversation');

	$effect(() => {
		let current = true;
		title = 'Conversation';
		data.conversation.then(
			(detail) => {
				if (current) title = conversationLabel(detail.summary);
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

{#await data.conversation}
	<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
		<h2>Loading conversation</h2>
		<p>Reading the captured transcript…</p>
	</section>
{:then detail}
	{#key detail.summary.revision}
		{#await data.bundles}
			<ConversationReader {detail} query={data.query} />
		{:then bundles}
			<ConversationReader {detail} query={data.query} {bundles} />
		{/await}
	{/key}
{:catch error}
	<section class="status-panel status-panel--error" role="alert">
		{#if isMissing(error)}
			<h2>{data.revision ? 'Revision not found' : 'Conversation not found'}</h2>
			<p>
				It may have been removed from the library or the link may be wrong.
				<a href={resolve('/conversations')}>Browse conversations</a>
			</p>
		{:else}
			<h2>Conversation unavailable</h2>
			<p>
				The local API could not provide this conversation. Check that it is running and reload this
				page.
			</p>
		{/if}
	</section>
{/await}
