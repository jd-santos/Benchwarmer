<script lang="ts">
	import { resolve } from '$app/paths';
	import { ApiClientError } from '$lib/api/client';
	import TaskEditor from '$lib/components/TaskEditor.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function issueMessage(error: unknown): string | null {
		if (!(error instanceof ApiClientError)) return null;
		return error.taskIssues[0]?.message ?? null;
	}
</script>

<svelte:head>
	<title>New task · Benchwarmer</title>
</svelte:head>

<p class="run-page__back">
	<a href={resolve('/bundles/[id]', { id: data.bundle })}>← Back to the bundle</a>
</p>
{#await data.draft}
	<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
		<h2>Preparing a task</h2>
		<p>Proposing a cut point from the bundle's evidence…</p>
	</section>
{:then draft}
	<TaskEditor {draft} />
{:catch error}
	<section class="status-panel status-panel--error" role="alert">
		<h2>This bundle cannot seed a task</h2>
		<p>
			{issueMessage(error) ??
				'The local API could not prepare a task from this bundle. Check that it is running and reload.'}
		</p>
	</section>
{/await}
