<script lang="ts">
	import { resolve } from '$app/paths';
	import { ApiClientError } from '$lib/api/client';
	import TaskEditor from '$lib/components/TaskEditor.svelte';
	import { taskLabel } from '$lib/tasks/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let title = $state('Task');

	$effect(() => {
		let active = true;
		title = 'Task';
		data.task.then(
			(detail) => {
				if (active) title = taskLabel(detail.document);
			},
			() => undefined
		);
		return () => {
			active = false;
		};
	});

	function isMissing(error: unknown): boolean {
		return error instanceof ApiClientError && error.status === 404;
	}
</script>

<svelte:head>
	<title>{title} · Benchwarmer</title>
</svelte:head>

<p class="run-page__back"><a href={resolve('/tasks')}>← Tasks</a></p>
{#await data.task}
	<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
		<h2>Loading task</h2>
		<p>Resolving its conversation…</p>
	</section>
{:then detail}
	{#key `${detail.id}:${detail.version}`}
		<TaskEditor {detail} />
	{/key}
{:catch error}
	<section class="status-panel status-panel--error" role="alert">
		{#if isMissing(error)}
			<h2>{data.version ? 'Version not found' : 'Task not found'}</h2>
			<p>The link may be wrong. <a href={resolve('/tasks')}>All tasks</a></p>
		{:else}
			<h2>Task unavailable</h2>
			<p>
				The local API could not provide this task. Check that it is running and reload this page.
			</p>
		{/if}
	</section>
{/await}
