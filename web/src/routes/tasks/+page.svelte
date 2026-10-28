<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import { ApiClientError, assignPartitions } from '$lib/api/client';
	import type { Partition, PartitionAssignment, TaskSummary } from '$lib/api/types';
	import { objectiveTypeLabel } from '$lib/bundles/format';
	import { formatDate, formatTimestamp, plural } from '$lib/conversations/format';
	import {
		defaultSplit,
		kindLabel,
		partitionLabel,
		partitionOptions,
		statusLabel,
		taskLabel
	} from '$lib/tasks/format';
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

	// Assign partitions by family: the seed and split are the only inputs, and
	// the recorded run is what the page shows afterwards.
	let seed = $state('');
	let split = $state<Record<Partition, number>>({ ...defaultSplit });
	let includeRetired = $state(false);
	let assigning = $state(false);
	let assigned = $state<PartitionAssignment | null>(null);
	let assignError = $state('');
	const splitTotal = $derived(
		Math.round((split.development + split.calibration + split.holdout) * 1000) / 1000
	);
	const splitValid = $derived(
		Math.abs(splitTotal - 1) < 0.0005 && Object.values(split).every((value) => value >= 0)
	);

	function setFraction(partition: Partition, raw: string): void {
		const value = Number(raw);
		split = { ...split, [partition]: Number.isFinite(value) ? value : 0 };
	}

	async function runAssignment(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (assigning || !seed.trim() || !splitValid) return;
		assigning = true;
		assignError = '';
		try {
			assigned = await assignPartitions({
				seed: seed.trim(),
				split: { ...split },
				scope: {
					statuses: includeRetired ? ['draft', 'approved', 'retired'] : ['draft', 'approved']
				}
			});
			await invalidateAll();
		} catch (failure) {
			const body = failure instanceof ApiClientError ? failure.body : undefined;
			assignError =
				body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
					? body.detail
					: 'Partitions could not be assigned. Check that the API is running and try again.';
		} finally {
			assigning = false;
		}
	}

	function describe(run: PartitionAssignment): string {
		const counts = partitionOptions
			.map(
				(option) =>
					`${run.family_counts[option.value]} ${option.label.toLowerCase()} (${plural(run.task_counts[option.value], 'task')})`
			)
			.join(', ');
		return `${plural(run.family_count, 'family', 'families')} across ${plural(run.task_count, 'task')}: ${counts}.`;
	}
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
						<col class="bundle-table__col-type" />
						<col />
						<col />
					</colgroup>
					<thead>
						<tr>
							<th scope="col">Task</th>
							<th scope="col" class="wide-only">Kind</th>
							<th scope="col" class="wide-only">Type</th>
							<th scope="col" class="wide-only">Status</th>
							<th scope="col" class="wide-only">Partition</th>
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
										· version {task.version}
									</span>
									<span class="bundle-table__note bundle-table__meta">
										<span class="task-status task-status--{task.status}"
											>{statusLabel(task.status)}</span
										>
										{#if task.analysis_only}· <span class="task-analysis-only">Analysis only</span
											>{/if}
										· {kindLabel(task.kind)}
										{#if task.partition}· {partitionLabel(task.partition)}{/if}
										·
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
									{#if task.analysis_only}
										<span
											class="task-analysis-only bundle-table__note"
											title="Its criteria need more than the reconstruction level provides; it cannot be approved as a runnable test"
											>Analysis only</span
										>
									{/if}
								</td>
								<td class="wide-only nowrap" class:muted={!task.partition}>
									{task.partition ? partitionLabel(task.partition) : 'Not assigned'}
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

	<section class="partitions" aria-labelledby="partitions-heading">
		<h2 id="partitions-heading">Partitions</h2>
		<p class="muted view-note">
			Development, calibration, and holdout are assigned by family: every task from the same
			conversation, its branches, and its continuations lands on one side. The side is a hash of the
			family and the seed, so the same seed never moves a family; only a new seed reshuffles.
		</p>
		{#await data.partitions then latest}
			{@const run = assigned ?? latest}
			{#if run}
				<p class="partitions__latest" data-latest-assignment>
					Last assigned <time datetime={run.created_at}>{formatTimestamp(run.created_at)}</time>
					with seed <code>{run.seed}</code>{#if run.scope.statuses.includes('retired')}, including
						retired tasks{/if}. {describe(run)}
					{#if assigned && assigned.moved_families > 0}
						{plural(assigned.moved_families, 'family', 'families')} changed side.
					{/if}
				</p>
			{:else}
				<p class="muted" data-no-assignment>No partitions assigned yet.</p>
			{/if}
		{/await}
		<form class="partitions__form" onsubmit={(event) => void runAssignment(event)}>
			<div class="field partitions__seed">
				<label for="partition-seed">Seed</label>
				<input
					id="partition-seed"
					type="text"
					maxlength="255"
					required
					placeholder="A word or date to reproduce this split"
					bind:value={seed}
				/>
			</div>
			<fieldset class="field partitions__split">
				<legend>Share of families</legend>
				<div class="partitions__fractions">
					{#each partitionOptions as option (option.value)}
						<label class="partitions__fraction">
							<span>{option.label}</span>
							<input
								type="number"
								min="0"
								max="1"
								step="0.05"
								value={split[option.value]}
								oninput={(event) => setFraction(option.value, event.currentTarget.value)}
								aria-invalid={!splitValid}
							/>
						</label>
					{/each}
				</div>
				{#if !splitValid}
					<p class="field__error" id="partition-split-error">
						The three shares must add up to 1; they add up to {splitTotal}.
					</p>
				{:else}
					<p class="field__hint">Default 0.6 / 0.2 / 0.2. Shares apply to families, not tasks.</p>
				{/if}
			</fieldset>
			<label class="partitions__retired">
				<input type="checkbox" bind:checked={includeRetired} />
				Include retired tasks
			</label>
			<div class="partitions__actions">
				<button class="button" type="submit" disabled={assigning || !seed.trim() || !splitValid}>
					{assigning ? 'Assigning…' : 'Assign partitions by family'}
				</button>
				{#if assignError}<span class="field__error" role="alert">{assignError}</span>{/if}
			</div>
		</form>
	</section>
</div>
