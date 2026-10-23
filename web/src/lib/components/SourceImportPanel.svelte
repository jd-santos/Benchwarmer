<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import {
		ApiClientError,
		getImportConfig,
		getSourceImports,
		getSources,
		startImport
	} from '$lib/api/client';
	import type { ImportBatchSummary, ImportConfig, ImportRun, SourceStatus } from '$lib/api/types';
	import { formatTimestamp, plural } from '$lib/conversations/format';
	import { onMount } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';

	/**
	 * Import conversation files already on this host into a configured source.
	 * The panel loads its own data so a page refresh after an import keeps its state.
	 */
	let sources = $state<SourceStatus[]>([]);

	let config = $state<ImportConfig | null | 'unavailable'>(null);
	const paths = new SvelteMap<string, string>();
	const busy = new SvelteMap<string, boolean>();
	const results = new SvelteMap<string, { run: ImportRun | null; error: string | null }>();
	const history = new SvelteMap<string, ImportBatchSummary[]>();

	const importable = $derived.by(() => {
		const current = config;
		if (current === null || current === 'unavailable') return [];
		return sources.filter((source) => current.kinds.includes(source.kind));
	});

	async function loadHistory(sourceId: string): Promise<void> {
		try {
			history.set(sourceId, await getSourceImports(sourceId));
		} catch {
			history.delete(sourceId);
		}
	}

	onMount(async () => {
		try {
			const [loadedConfig, loadedSources] = await Promise.all([getImportConfig(), getSources()]);
			config = loadedConfig;
			sources = loadedSources.items;
		} catch {
			config = 'unavailable';
			return;
		}
		await Promise.all(
			sources
				.filter((source) => (config as ImportConfig).kinds.includes(source.kind))
				.map((source) => loadHistory(source.id))
		);
	});

	function describe(error: unknown): string {
		if (error instanceof ApiClientError && error.status === 422) {
			const body = error.body;
			if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string')
				return body.detail;
		}
		if (error instanceof ApiClientError && error.status === 404)
			return 'This source no longer exists.';
		return 'The import could not be started. Check that the API is running.';
	}

	async function submit(event: SubmitEvent, sourceId: string): Promise<void> {
		event.preventDefault();
		const path = (paths.get(sourceId) ?? '').trim();
		if (!path) return;
		busy.set(sourceId, true);
		results.delete(sourceId);
		try {
			const run = await startImport(sourceId, path);
			results.set(sourceId, { run, error: null });
			await loadHistory(sourceId);
			if (run.outcome === 'succeeded') await invalidateAll();
		} catch (error) {
			results.set(sourceId, { run: null, error: describe(error) });
		} finally {
			busy.set(sourceId, false);
		}
	}

	function summarize(run: ImportRun): string {
		switch (run.outcome) {
			case 'succeeded':
				return `Imported ${plural(run.conversations, 'conversation')} (${plural(run.revisions, 'new revision')}, ${plural(run.snapshots, 'new snapshot')}).`;
			case 'unchanged':
				return 'Nothing new: these exact files were imported before.';
			default:
				return run.error_summary ?? 'The import failed.';
		}
	}

	const outcomeLabel: Record<string, string> = {
		succeeded: 'Succeeded',
		partial: 'Partial',
		failed: 'Failed'
	};
</script>

<section class="import-panel" aria-labelledby="import-heading">
	<h2 id="import-heading">Import from this machine</h2>
	{#if config === null}
		<p class="muted" aria-live="polite">Checking import settings…</p>
	{:else if config === 'unavailable'}
		<p class="muted">Import settings could not be read from the API.</p>
	{:else if config.roots.length === 0}
		<p class="muted" data-import-off>
			Host-local import is off. Set <code>BENCHWARMER_IMPORT_ROOTS</code> on the server to the directories
			that hold conversation files, then restart it. Other machines send their conversations through collectors.
		</p>
	{:else if importable.length === 0}
		<p class="muted">
			No configured source accepts files from a path. Importable kinds: {config.kinds.join(', ')}.
		</p>
	{:else}
		<p class="muted import-panel__roots">
			Paths must sit under {config.roots.length === 1 ? 'the import root' : 'an import root'}:
			{#each config.roots as root, index (root)}{index > 0 ? ', ' : ''}<code>{root}</code>{/each}. A
			Pi path may be a session file or a directory of sessions; a ChatGPT path is the export file.
			Importing never starts model work.
		</p>
		<ul class="import-panel__sources">
			{#each importable as source (source.id)}
				{@const result = results.get(source.id)}
				{@const batches = history.get(source.id) ?? []}
				<li class="import-source">
					<h3 class="import-source__name">
						{source.display_name} <span class="muted">({source.kind})</span>
					</h3>
					<form class="import-form" onsubmit={(event) => submit(event, source.id)}>
						<label class="field import-form__path">
							<span class="field__label">Path on this machine</span>
							<input
								type="text"
								autocomplete="off"
								spellcheck="false"
								placeholder={`${config.roots[0]}/…`}
								value={paths.get(source.id) ?? ''}
								oninput={(event) => paths.set(source.id, event.currentTarget.value)}
								disabled={busy.get(source.id) ?? false}
							/>
						</label>
						<button
							type="submit"
							class="button"
							disabled={(busy.get(source.id) ?? false) || !(paths.get(source.id) ?? '').trim()}
						>
							{busy.get(source.id) ? 'Importing…' : 'Import'}
						</button>
					</form>
					{#if result?.error}
						<p class="field__error" role="alert">{result.error}</p>
					{:else if result?.run}
						<p
							class="notice import-result import-result--{result.run.outcome}"
							role="status"
							data-import-result
						>
							{summarize(result.run)}
						</p>
					{/if}
					{#if batches.length > 0}
						<details class="import-history">
							<summary>{plural(batches.length, 'earlier import')}</summary>
							<ul>
								{#each batches.slice(0, 10) as batch (batch.id)}
									<li>
										<time datetime={batch.started_at}>{formatTimestamp(batch.started_at)}</time>
										·
										<span class="import-outcome import-outcome--{batch.outcome}"
											>{outcomeLabel[batch.outcome] ?? batch.outcome}</span
										>
										{#if batch.error_summary}
											· <span class="muted">{batch.error_summary}</span>
										{/if}
									</li>
								{/each}
							</ul>
						</details>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>
