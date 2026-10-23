<script lang="ts">
	import type { CoverageValue, SourceCoverage } from '$lib/api/types';
	import SourceImportPanel from '$lib/components/SourceImportPanel.svelte';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const coverageFields: ReadonlyArray<{ key: keyof SourceCoverage; label: string }> = [
		{ key: 'sessions', label: 'Sessions' },
		{ key: 'prompts', label: 'Prompts' },
		{ key: 'token_usage', label: 'Token usage' },
		{ key: 'request_ids', label: 'Request IDs' },
		{ key: 'actual_charges', label: 'Actual charges' },
		{ key: 'list_price_estimates', label: 'List-price estimates' },
		{ key: 'subscription_expense', label: 'Subscription expense' },
		{ key: 'quota', label: 'Quota' },
		{ key: 'credits', label: 'Credits' },
		{ key: 'classifications', label: 'Classifications' }
	];

	const coverageLabels: Record<CoverageValue, { symbol: string; label: string }> = {
		available: { symbol: '●', label: 'Available' },
		partial: { symbol: '◐', label: 'Partial' },
		unavailable: { symbol: '○', label: 'Unavailable' },
		unknown: { symbol: '?', label: 'Unknown' }
	};
</script>

<svelte:head>
	<title>Sources · Benchwarmer</title>
	<meta name="description" content="Import freshness and coverage by source." />
</svelte:head>

<div class="sources-page">
	<h1 class="page-title">Sources</h1>

	{#await data.sources}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading sources</h2>
			<p>Reading source and coverage status…</p>
		</section>
	{:then response}
		{#if response.items.length === 0}
			<section class="status-panel" aria-labelledby="no-sources-heading">
				<h2 id="no-sources-heading">No sources configured</h2>
				<p>Load a fixture or add an importer before reviewing source coverage.</p>
			</section>
		{:else}
			<p class="result-count">{plural(response.items.length, 'source')} configured</p>
			<div class="table-scroll">
				<table class="data-table coverage-table">
					<thead>
						<tr>
							<td></td>
							{#each response.items as source (source.id)}
								<th scope="col">
									{source.display_name}
									<span class="coverage-table__kind">{source.kind}</span>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						<tr>
							<th scope="row">Last import</th>
							{#each response.items as source (source.id)}
								<td class:muted={source.last_successful_import_at === null}>
									{source.last_successful_import_at === null
										? 'Never imported'
										: formatTimestamp(source.last_successful_import_at)}
								</td>
							{/each}
						</tr>
						{#each coverageFields as field (field.key)}
							<tr>
								<th scope="row">{field.label}</th>
								{#each response.items as source (source.id)}
									{@const state = coverageLabels[source.coverage[field.key]]}
									<td class="coverage coverage--{source.coverage[field.key]}">
										<span aria-hidden="true">{state.symbol}</span>
										{state.label}
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Sources unavailable</h2>
			<p>
				The local API could not provide source status. Check that it is running and reload this
				page.
			</p>
		</section>
	{/await}
	<SourceImportPanel />
</div>
