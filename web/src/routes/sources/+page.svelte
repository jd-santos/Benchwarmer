<script lang="ts">
	import type { CoverageValue, SourceCoverage } from '$lib/api/types';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const coverageFields: ReadonlyArray<{ key: keyof SourceCoverage; label: string }> = [
		{ key: 'sessions', label: 'Sessions' },
		{ key: 'token_usage', label: 'Token usage' },
		{ key: 'request_ids', label: 'Request IDs' },
		{ key: 'actual_charges', label: 'Actual charges' },
		{ key: 'list_price_estimates', label: 'List-price estimates' },
		{ key: 'subscription_expense', label: 'Subscription expense' },
		{ key: 'quota', label: 'Quota' },
		{ key: 'credits', label: 'Credits' },
		{ key: 'prompts', label: 'Prompts' },
		{ key: 'classifications', label: 'Classifications' }
	];

	function formatCoverage(value: CoverageValue): string {
		return value.charAt(0).toUpperCase() + value.slice(1);
	}

	function formatImportedAt(value: string | null): string {
		if (value === null) return 'Never imported';
		return `${new Intl.DateTimeFormat('en-US', {
			dateStyle: 'medium',
			timeStyle: 'short',
			timeZone: 'UTC'
		}).format(new Date(value))} UTC`;
	}
</script>

<svelte:head>
	<title>Sources · Benchwarmer</title>
	<meta
		name="description"
		content="Review import freshness and conversation, usage, and cost coverage by source."
	/>
</svelte:head>

<div class="sources-page">
	<header class="sources-page__header">
		<h1>Sources</h1>
		<p>Review import freshness and the evidence each source can provide.</p>
	</header>

	{#await data.sources}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading sources</h2>
			<p>Reading source and coverage status…</p>
		</section>
	{:then response}
		{#if response.items.length === 0}
			<section class="source-empty" aria-labelledby="no-sources-heading">
				<h2 id="no-sources-heading">No sources configured</h2>
				<p>Load a fixture or add an importer before reviewing source coverage.</p>
			</section>
		{:else}
			<p class="source-count">
				{response.items.length}
				{response.items.length === 1 ? 'source' : 'sources'} configured
			</p>
			<div class="source-list">
				{#each response.items as source (source.id)}
					<article class="source-card" aria-labelledby={`source-${source.id}`}>
						<header class="source-card__header">
							<div>
								<h2 id={`source-${source.id}`}>{source.display_name}</h2>
								<p>{source.kind}</p>
							</div>
							<span
								class:source-freshness--current={source.last_successful_import_at !== null}
								class:source-freshness--missing={source.last_successful_import_at === null}
								class="source-freshness"
							>
								{source.last_successful_import_at === null ? 'No successful import' : 'Imported'}
							</span>
						</header>

						<div class="source-card__freshness">
							<span>Last successful import</span>
							<strong>{formatImportedAt(source.last_successful_import_at)}</strong>
						</div>

						<section class="source-coverage" aria-labelledby={`coverage-${source.id}`}>
							<h3 id={`coverage-${source.id}`}>Coverage</h3>
							<dl>
								{#each coverageFields as field (field.key)}
									<div>
										<dt>{field.label}</dt>
										<dd>
											<span class={`coverage-state coverage-state--${source.coverage[field.key]}`}>
												{formatCoverage(source.coverage[field.key])}
											</span>
										</dd>
									</div>
								{/each}
							</dl>
						</section>
					</article>
				{/each}
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
</div>
