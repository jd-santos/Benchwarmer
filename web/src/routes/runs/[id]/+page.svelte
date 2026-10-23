<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { RunInput, RunModelUsage, RunUsageTotal } from '$lib/api/types';
	import {
		formatDuration,
		formatEstimate,
		shortId,
		shortRunId,
		usageTotals,
		workflowLabel
	} from '$lib/bundles/format';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const inputStatus: Record<RunInput['status'], string> = {
		done: 'Done',
		unanswered: 'Nothing produced',
		error: 'Error'
	};

	/** Usage rows by model, then by tool, each named as the record keys them. */
	function usageRows(usage: RunUsageTotal): { name: string; kind: string; usage: RunModelUsage }[] {
		return [
			...Object.entries(usage.models).map(([name, entry]) => ({
				name,
				kind: 'model',
				usage: entry
			})),
			...Object.entries(usage.tools).map(([name, entry]) => ({ name, kind: 'tool', usage: entry }))
		];
	}

	function bundlesHref(runId: string): ResolvedPathname {
		return `${resolve('/bundles')}?${new URLSearchParams({
			view: 'proposed',
			run: runId
		})}` as ResolvedPathname;
	}

	function inputHref(input: RunInput): ResolvedPathname | null {
		return input.kind === 'conversation' ? resolve('/conversations/[id]', { id: input.id }) : null;
	}
</script>

<svelte:head>
	<title>Run · Benchwarmer</title>
	<meta name="description" content="One model-driven run: its inputs, usage, and estimated cost." />
</svelte:head>

<div class="run-page">
	<p class="run-page__back"><a href={resolve('/runs')}>← Runs</a></p>
	{#await data.run}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading run</h2>
			<p>Reading the run record…</p>
		</section>
	{:then run}
		{@const bundleCount = run.inputs.reduce((sum, input) => sum + input.bundle_ids.length, 0)}
		{@const total = usageTotals(run.usage_total)}
		<header class="run-page__header">
			<h1 class="page-title">{workflowLabel(run.workflow)} · {shortRunId(run.run_id)}</h1>
			<p class="meta-line">
				<span><time datetime={run.started_at}>{formatTimestamp(run.started_at)}</time></span>
				<span>{formatDuration(run.started_at, run.finished_at)}</span>
				<span
					>{run.model.provider}/{run.model.model_id}{run.model.thinking_level
						? `, thinking ${run.model.thinking_level}`
						: ''}</span
				>
				{#if run.model.base_url_override}
					<span>via {new URL(run.model.base_url_override).host}</span>
				{/if}
				<span>Harness {run.harness_version}</span>
			</p>
			<p class="meta-line">
				<span>{plural(run.inputs.length, 'input')}</span>
				<span>{total.tokens.toLocaleString()} tokens</span>
				<span>about {formatEstimate(total.estimate)} ({run.pricing_source})</span>
				{#if bundleCount > 0}
					<span><a href={bundlesHref(run.run_id)}>{plural(bundleCount, 'bundle')} proposed</a></span
					>
				{/if}
			</p>
			{#if run.report_path}
				<p class="muted run-page__report">Report: <code>{run.report_path}</code></p>
			{/if}
		</header>

		<section aria-labelledby="run-usage-heading">
			<h2 id="run-usage-heading" class="section-title">Usage</h2>
			<div class="table-scroll">
				<table class="data-table usage-table">
					<thead>
						<tr>
							<th scope="col">Model or tool</th>
							<th scope="col" class="numeric">Input</th>
							<th scope="col" class="numeric">Output</th>
							<th scope="col" class="numeric wide-only">Cache read</th>
							<th scope="col" class="numeric wide-only">Cache write</th>
							<th scope="col" class="numeric">Total</th>
							<th scope="col" class="numeric">Est. cost</th>
						</tr>
					</thead>
					<tbody>
						{#each usageRows(run.usage_total) as row (row.kind + row.name)}
							<tr>
								<th scope="row">{row.name}{row.kind === 'tool' ? ' (tool)' : ''}</th>
								<td class="numeric">{row.usage.input.toLocaleString()}</td>
								<td class="numeric">{row.usage.output.toLocaleString()}</td>
								<td class="numeric wide-only">{row.usage.cache_read.toLocaleString()}</td>
								<td class="numeric wide-only">{row.usage.cache_write.toLocaleString()}</td>
								<td class="numeric">{row.usage.total_tokens.toLocaleString()}</td>
								<td class="numeric">{formatEstimate(row.usage.cost.total)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<section aria-labelledby="run-inputs-heading">
			<h2 id="run-inputs-heading" class="section-title">Inputs</h2>
			<p class="muted view-note">
				Usage is recorded per input. When one input produced several bundles, the figure covers all
				of them.
			</p>
			<div class="table-scroll">
				<table class="data-table inputs-table">
					<thead>
						<tr>
							<th scope="col">Input</th>
							<th scope="col" class="wide-only">Outcome</th>
							<th scope="col">Produced</th>
							<th scope="col" class="numeric wide-only">Tokens</th>
							<th scope="col" class="numeric wide-only">Est. cost</th>
						</tr>
					</thead>
					<tbody>
						{#each run.inputs as input (input.id)}
							{@const usage = usageTotals(input.usage)}
							{@const href = inputHref(input)}
							<tr>
								<th scope="row">
									<span title={input.id}>
										{#if href}<a {href}>{shortId(input.id)}</a>{:else}{shortId(input.id)}{/if}
									</span>
									<span class="runs-table__note">{input.kind}</span>
									<span class="runs-table__note runs-table__meta">
										<span class="run-outcome run-outcome--{input.status}"
											>{inputStatus[input.status]}</span
										>
										{#if input.reason}({input.reason}){/if}
										· {usage.tokens.toLocaleString()} tokens · {formatEstimate(usage.estimate)}
									</span>
								</th>
								<td class="wide-only">
									<span class="run-outcome run-outcome--{input.status}"
										>{inputStatus[input.status]}</span
									>
									{#if input.reason}<span class="runs-table__note">{input.reason}</span>{/if}
								</td>
								<td>
									{#if input.bundle_ids.length === 0}
										<span class="muted">Nothing</span>
									{:else}
										<ul class="run-bundles">
											{#each input.bundle_ids as id (id)}
												<li>
													<a href={resolve('/bundles/[id]', { id })} title={id}>{shortId(id)}</a>
												</li>
											{/each}
										</ul>
									{/if}
								</td>
								<td class="numeric wide-only">{usage.tokens.toLocaleString()}</td>
								<td class="numeric wide-only">{formatEstimate(usage.estimate)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Run unavailable</h2>
			<p>
				The local API could not provide this run. Check that it is running and reload this page.
			</p>
		</section>
	{/await}
</div>
