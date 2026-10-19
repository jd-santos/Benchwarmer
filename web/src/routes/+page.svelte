<script lang="ts">
	import { resolve } from '$app/paths';
	import type { BundleSummary } from '$lib/api/types';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function bundleBreakdown(bundles: BundleSummary[]): string {
		const reviewed = bundles.filter((bundle) => bundle.status === 'reviewed').length;
		const drafts = bundles.filter((bundle) => bundle.status === 'draft').length;
		const parts = [];
		if (reviewed) parts.push(`${reviewed} reviewed`);
		if (drafts) parts.push(plural(drafts, 'draft'));
		return parts.join(' · ');
	}
</script>

<svelte:head>
	<title>Overview · Benchwarmer</title>
	<meta name="description" content="Benchwarmer library, evidence, and source status." />
</svelte:head>

<div class="overview">
	<h1 class="page-title">Overview</h1>

	{#await data.overview}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading overview</h2>
			<p>Reading the library and source status…</p>
		</section>
	{:then overview}
		{#if overview.health.alembic_revision === null}
			<section class="status-panel status-panel--warning" role="status">
				<h2>Database setup required</h2>
				<p>
					No database revision is installed. Run <code>uv run alembic upgrade head</code>, then
					reload.
				</p>
			</section>
		{:else}
			{@const library = overview.library}
			<ol class="workflow" aria-label="Evaluation workflow">
				<li>
					<a class="workflow__step" href={resolve('/conversations')}>
						<span class="workflow__label">1 · Conversations</span>
						<span class="workflow__count">{library ? library.conversations : '—'}</span>
						<span class="workflow__detail">Imported sessions to read and search</span>
					</a>
				</li>
				<li>
					<a class="workflow__step" href={resolve('/bundles')}>
						<span class="workflow__label">2 · Evidence bundles</span>
						<span class="workflow__count">{library ? library.bundles.length : '—'}</span>
						<span class="workflow__detail">
							{library && library.bundles.length > 0
								? bundleBreakdown(library.bundles)
								: 'Excerpts selected from conversations'}
						</span>
					</a>
				</li>
				<li>
					<div class="workflow__step workflow__step--planned">
						<span class="workflow__label">3 · Tasks</span>
						<span class="workflow__count">Not built yet</span>
						<span class="workflow__detail">Prepared from reviewed bundles</span>
					</div>
				</li>
				<li>
					<div class="workflow__step workflow__step--planned">
						<span class="workflow__label">4 · Evaluations</span>
						<span class="workflow__count">Not built yet</span>
						<span class="workflow__detail">Tasks run and judged per configuration</span>
					</div>
				</li>
			</ol>
			{#if library === null}
				<p class="field__hint">Library counts could not be loaded.</p>
			{/if}

			{#if overview.sources !== null}
				<section class="overview-sources" aria-labelledby="overview-sources-heading">
					<div class="section-row">
						<h2 id="overview-sources-heading">Sources</h2>
						<a href={resolve('/sources')}>Coverage details</a>
					</div>
					{#if overview.sources.items.length === 0}
						<p class="empty-state">No sources are configured.</p>
					{:else}
						<table class="data-table">
							<thead>
								<tr><th scope="col">Source</th><th scope="col">Last import</th></tr>
							</thead>
							<tbody>
								{#each overview.sources.items as source (source.id)}
									<tr>
										<th scope="row">{source.display_name}</th>
										<td class:muted={source.last_successful_import_at === null}>
											{source.last_successful_import_at === null
												? 'Never imported'
												: formatTimestamp(source.last_successful_import_at)}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</section>
			{/if}
		{/if}

		<p class="system-line">
			<span class="system-line__ok">API online</span>
			<span>
				{overview.health.alembic_revision === null
					? 'Database not migrated'
					: `Database revision ${overview.health.alembic_revision}`}
			</span>
		</p>
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>API unavailable</h2>
			<p>The local API is not responding. Check that it is running and reload this page.</p>
		</section>
	{/await}
</div>
