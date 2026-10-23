<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { RunSummary } from '$lib/api/types';
	import { formatDuration, formatEstimate, shortModel, workflowLabel } from '$lib/bundles/format';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const listHref = resolve('/runs');

	function workflowHref(workflow: string | null): ResolvedPathname {
		return (
			workflow ? `${listHref}?${new URLSearchParams({ workflow })}` : listHref
		) as ResolvedPathname;
	}

	/** Where a run's output can be reviewed; only bundle proposals have a review view today. */
	function producedHref(run: RunSummary): ResolvedPathname | null {
		if (run.bundle_count === 0) return null;
		return `${resolve('/bundles')}?${new URLSearchParams({
			view: 'proposed',
			run: run.run_id
		})}` as ResolvedPathname;
	}

	function workflows(items: RunSummary[]): string[] {
		return [...new Set(items.map((run) => run.workflow))].sort();
	}

	function totals(items: RunSummary[]): { tokens: number; estimate: number } {
		return items.reduce(
			(sum, run) => ({
				tokens: sum.tokens + run.total_tokens,
				estimate: sum.estimate + run.estimated_cost
			}),
			{ tokens: 0, estimate: 0 }
		);
	}
</script>

<svelte:head>
	<title>Runs · Benchwarmer</title>
	<meta name="description" content="Every model-driven run, with token usage and estimated cost." />
</svelte:head>

<div class="runs-page">
	<h1 class="page-title">Runs</h1>
	<p class="muted view-note">
		Every workflow that invoked a model, most recent first, with its raw token usage. Costs are
		catalog estimates, not charges.
	</p>

	{#await data.runs}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading runs</h2>
			<p>Reading recorded runs…</p>
		</section>
	{:then response}
		{@const kinds = workflows(response.items)}
		{#if kinds.length > 1 || data.workflow}
			<nav class="view-links" aria-label="Workflows">
				<a href={workflowHref(null)} aria-current={data.workflow === null ? 'page' : undefined}
					>All workflows</a
				>
				{#each kinds as workflow (workflow)}
					<a
						href={workflowHref(workflow)}
						aria-current={data.workflow === workflow ? 'page' : undefined}
						>{workflowLabel(workflow)}</a
					>
				{/each}
			</nav>
		{/if}
		{#if response.items.length === 0}
			<section class="status-panel" aria-labelledby="no-runs-heading">
				<h2 id="no-runs-heading">No runs recorded</h2>
				<p>
					A run appears here after an operator runs a harness workflow by hand. Nothing in the
					library starts model work on its own.
				</p>
			</section>
		{:else}
			{@const sum = totals(response.items)}
			<p class="result-count" data-run-totals>
				{plural(response.items.length, 'run')} · {sum.tokens.toLocaleString()} tokens · about {formatEstimate(
					sum.estimate
				)}
			</p>
			<div class="table-scroll">
				<table class="data-table runs-table">
					<thead>
						<tr>
							<th scope="col">Run</th>
							<th scope="col" class="wide-only">Workflow</th>
							<th scope="col" class="wide-only">Model</th>
							<th scope="col" class="numeric wide-only">Inputs</th>
							<th scope="col" class="wide-only">Produced</th>
							<th scope="col" class="numeric wide-only">Tokens</th>
							<th scope="col" class="numeric wide-only">Est. cost</th>
						</tr>
					</thead>
					<tbody>
						{#each response.items as run (run.run_id)}
							{@const produced = producedHref(run)}
							<tr>
								<th scope="row">
									<a href={resolve('/runs/[id]', { id: run.run_id })}
										><time datetime={run.started_at}>{formatTimestamp(run.started_at)}</time></a
									>
									<span class="runs-table__note"
										>{formatDuration(run.started_at, run.finished_at)}</span
									>
									<span class="runs-table__note runs-table__meta">
										{workflowLabel(run.workflow)}
										{#if produced}
											· <a href={produced}>{plural(run.bundle_count, 'bundle')}</a>
										{/if}
										· {run.total_tokens.toLocaleString()} tokens · {formatEstimate(
											run.estimated_cost
										)}
									</span>
								</th>
								<td class="wide-only">{workflowLabel(run.workflow)}</td>
								<td class="wide-only" title="{run.provider}/{run.model}">
									{shortModel(run.model)}{run.thinking_level ? `, ${run.thinking_level}` : ''}
								</td>
								<td class="numeric wide-only">{run.input_count}</td>
								<td class="wide-only">
									{#if produced}
										<a href={produced}>{plural(run.bundle_count, 'bundle')}</a>
									{:else}
										<span class="muted">Nothing</span>
									{/if}
								</td>
								<td class="numeric wide-only">{run.total_tokens.toLocaleString()}</td>
								<td class="numeric wide-only" title={run.pricing_source}
									>{formatEstimate(run.estimated_cost)}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Runs unavailable</h2>
			<p>The local API could not list runs. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
