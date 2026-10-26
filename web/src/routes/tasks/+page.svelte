<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { TaskSummary } from '$lib/api/types';
	import { objectiveTypeLabel } from '$lib/bundles/format';
	import { formatDate, formatTimestamp } from '$lib/conversations/format';
	import { kindLabel, statusLabel, taskLabel } from '$lib/tasks/format';
	import { _views, type TaskView } from './+page';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function viewHref(view: TaskView, bundle: string | null = data.bundle): ResolvedPathname {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams();
		if (view !== 'all') params.set('view', view);
		if (bundle) params.set('bundle', bundle);
		const search = params.toString();
		return `${resolve('/tasks')}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	function taskHref(task: TaskSummary): ResolvedPathname {
		return resolve('/tasks/[id]', { id: task.id });
	}

	function bundleHref(task: TaskSummary): ResolvedPathname {
		return resolve('/bundles/[id]', { id: task.bundle_id });
	}

	const emptyHeading: Record<TaskView, string> = {
		all: 'No tasks yet',
		draft: 'No draft tasks',
		approved: 'No approved tasks',
		retired: 'No retired tasks'
	};
</script>

<svelte:head>
	<title>Tasks · Benchwarmer</title>
	<meta
		name="description"
		content="Reviewed bundles prepared as tests, with a cut point and criteria."
	/>
</svelte:head>

<div class="bundles-page">
	<h1 class="page-title">Tasks</h1>
	<p class="muted view-note">
		A task is a reviewed bundle prepared as a test: the turn the candidate's view ends at, criteria
		of acceptable behavior, and a leakage check. Open a reviewed bundle and choose "Prepare as task"
		to add one.
	</p>

	<nav class="view-links" aria-label="Task views">
		{#each _views as view (view.value)}
			<a
				href={viewHref(view.value)}
				aria-current={data.view === view.value ? 'page' : undefined}
				title={view.hint}>{view.label}</a
			>
		{/each}
	</nav>

	{#if data.bundle}
		<p class="muted view-note" data-bundle-note>
			Showing tasks prepared from one bundle.
			<a href={viewHref(data.view, null)}>Show every bundle</a>
		</p>
	{/if}

	{#await data.tasks}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading tasks</h2>
			<p>Reading saved tasks…</p>
		</section>
	{:then response}
		{#if response.items.length === 0}
			<section class="empty-state">
				<h2>{emptyHeading[data.view]}</h2>
				<p>Tasks appear here once a reviewed bundle is prepared as one.</p>
			</section>
		{:else}
			<div class="table-scroll">
				<table class="data-table bundle-table">
					<colgroup>
						<col class="bundle-table__col-summary" />
						<col class="bundle-table__col-type" />
						<col class="bundle-table__col-type" />
						<col />
						<col />
						<col />
					</colgroup>
					<thead>
						<tr>
							<th scope="col">Task</th>
							<th scope="col" class="wide-only">Kind</th>
							<th scope="col" class="wide-only">Type</th>
							<th scope="col" class="wide-only">Status</th>
							<th scope="col" class="numeric">Criteria</th>
							<th scope="col" class="wide-only">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each response.items as task (task.id)}
							<tr>
								<th scope="row">
									<a
										class:untitled={!task.summary.trim() && !task.objective.trim()}
										href={taskHref(task)}>{taskLabel(task)}</a
									>
									<span class="bundle-table__note">
										<a href={bundleHref(task)}>Bundle revision {task.bundle_revision}</a>
										· version {task.version}{task.partition ? ` · ${task.partition}` : ''}
									</span>
									<span class="bundle-table__note bundle-table__meta">
										<span class="task-status task-status--{task.status}"
											>{statusLabel(task.status)}</span
										>
										· {kindLabel(task.kind)} ·
										<time datetime={task.updated_at}>{formatTimestamp(task.updated_at)}</time>
									</span>
								</th>
								<td class="wide-only nowrap">{kindLabel(task.kind)}</td>
								<td class="wide-only nowrap" class:muted={task.objective_type === 'unknown'}>
									{objectiveTypeLabel(task.objective_type)}
								</td>
								<td class="wide-only nowrap">
									<span class="task-status task-status--{task.status}"
										>{statusLabel(task.status)}</span
									>
								</td>
								<td class="numeric">{task.criterion_count}</td>
								<td class="wide-only muted nowrap">
									<time datetime={task.updated_at} title={formatTimestamp(task.updated_at)}
										>{formatDate(task.updated_at)}</time
									>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Tasks unavailable</h2>
			<p>The local API could not list tasks. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
