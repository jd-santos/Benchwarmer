<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Pathname } from '$app/types';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const sourcesHref = resolve('/sources' as Pathname);

	function sourceSummary(successful: number, total: number): string {
		if (total === 0) return 'No sources configured';
		if (successful === 0) return 'No successful imports yet';
		return `${successful} of ${total} imported successfully`;
	}
</script>

<svelte:head>
	<title>Overview · Benchwarmer</title>
	<meta
		name="description"
		content="Check Benchwarmer service, database, source, and coverage status."
	/>
</svelte:head>

<div class="overview">
	<header class="overview__header">
		<h1>System overview</h1>
		<p>Check whether Benchwarmer is ready to browse imported conversations.</p>
	</header>

	{#await data.overview}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Checking system status</h2>
			<p>Reading service, database, and source state…</p>
		</section>
	{:then overview}
		{@const sources = overview.sources}
		{@const sourceCount = sources?.items.length ?? 0}
		{@const successfulSources =
			sources?.items.filter((source) => source.last_successful_import_at !== null).length ?? 0}
		{@const coverage = sources?.items.flatMap((source) => Object.values(source.coverage)) ?? []}
		{@const partialCoverage = coverage.filter((state) => state === 'partial').length}
		{@const unavailableCoverage = coverage.filter((state) => state === 'unavailable').length}
		{@const unknownCoverage = coverage.filter((state) => state === 'unknown').length}

		<section class="system-status" aria-labelledby="system-status-heading">
			<div class="section-heading">
				<div>
					<h2 id="system-status-heading">Current status</h2>
					<p>Live state reported by the local API.</p>
				</div>
				<span
					class="status-label {overview.health.alembic_revision === null
						? 'status-label--warning'
						: 'status-label--success'}"
				>
					{overview.health.alembic_revision === null ? 'Setup required' : 'Operational'}
				</span>
			</div>

			<dl class="status-grid">
				<div>
					<dt>Service</dt>
					<dd>Online</dd>
					<p>The API is responding.</p>
				</div>
				<div>
					<dt>Database</dt>
					{#if overview.health.alembic_revision === null}
						<dd>Migration required</dd>
						<p>No database revision is installed.</p>
					{:else}
						<dd>Revision {overview.health.alembic_revision}</dd>
						<p>The database is migrated.</p>
					{/if}
				</div>
				<div>
					<dt>Sources</dt>
					{#if sources === null}
						<dd>Unavailable</dd>
						<p>Migrate the database to read sources.</p>
					{:else}
						<dd>{sourceCount} configured</dd>
						<p>{sourceSummary(successfulSources, sourceCount)}</p>
					{/if}
				</div>
			</dl>
		</section>

		{#if sources !== null}
			<section class="coverage-summary" aria-labelledby="coverage-heading">
				<div class="section-heading">
					<div>
						<h2 id="coverage-heading">Source coverage</h2>
						<p>Coverage states are reported explicitly; unknown values are not treated as zero.</p>
					</div>
					<a class="text-link" href={sourcesHref}>Review sources</a>
				</div>

				{#if sourceCount === 0}
					<p class="empty-state">No sources are configured.</p>
				{:else}
					<dl class="coverage-grid">
						<div>
							<dt>Partial</dt>
							<dd>{partialCoverage}</dd>
						</div>
						<div>
							<dt>Unavailable</dt>
							<dd>{unavailableCoverage}</dd>
						</div>
						<div>
							<dt>Unknown</dt>
							<dd>{unknownCoverage}</dd>
						</div>
					</dl>
					<p class="coverage-note">
						Counts represent source fields across {sourceCount} configured sources.
					</p>
				{/if}
			</section>
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Status unavailable</h2>
			<p>
				The local API could not provide system status. Check that it is running and reload this
				page.
			</p>
		</section>
	{/await}
</div>
