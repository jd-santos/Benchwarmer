<script lang="ts">
	import {
		ApiClientError,
		getTermList,
		getTermLists,
		retireTermList,
		saveTermList
	} from '$lib/api/client';
	import type { TermListDetail, TermListSummary } from '$lib/api/types';
	import { formatTimestamp, plural } from '$lib/conversations/format';

	/**
	 * List, open, save, and retire stored scrub term lists. The table shows
	 * counts; terms appear only in the editor after a list is opened.
	 */
	let { lists: initial }: { lists: TermListSummary[] } = $props();

	// The page hands over the loaded rows once; refreshes come from the API.
	// svelte-ignore state_referenced_locally
	let lists = $state<TermListSummary[]>(initial);
	let listError = $state('');

	// The editor: a new list, or one version of an existing list.
	let open = $state<TermListDetail | null>(null);
	let creating = $state(false);
	let opening = $state<string | null>(null);
	let name = $state('');
	let termsText = $state('');
	let notes = $state('');
	let saving = $state(false);
	let retiring = $state(false);
	let message = $state('');
	let error = $state('');

	const editing = $derived(creating || open !== null);
	const terms = $derived(
		termsText
			.split('\n')
			.map((line) => line.trim())
			.filter(Boolean)
	);
	const namePattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
	const nameValid = $derived(namePattern.test(name.trim()));
	const canSave = $derived(nameValid && terms.length > 0 && !saving && open?.retired_at == null);

	async function refresh(): Promise<void> {
		try {
			lists = (await getTermLists(true)).items;
			listError = '';
		} catch {
			listError = 'The list of term lists could not be refreshed. Reload the page.';
		}
	}

	function startNew(): void {
		open = null;
		creating = true;
		name = '';
		termsText = '';
		notes = '';
		message = '';
		error = '';
	}

	async function openList(summary: TermListSummary): Promise<void> {
		opening = summary.name;
		message = '';
		error = '';
		try {
			const detail = await getTermList(summary.name);
			open = detail;
			creating = false;
			name = detail.name;
			termsText = detail.terms.join('\n');
			notes = detail.notes ?? '';
		} catch {
			error = 'The list could not be opened. Check that the API is running.';
		} finally {
			opening = null;
		}
	}

	function close(): void {
		open = null;
		creating = false;
		message = '';
		error = '';
	}

	function describe(failure: unknown): string {
		if (failure instanceof ApiClientError && failure.status === 409)
			return 'This list is retired; a retired list cannot be saved again.';
		if (failure instanceof ApiClientError && failure.status === 422) {
			const body = failure.body;
			if (body && typeof body === 'object' && 'message' in body && typeof body.message === 'string')
				return body.message;
			return 'The list cannot be saved as given. Check the name and the terms.';
		}
		return 'The list could not be saved. Your edits are still here; try again.';
	}

	async function save(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!canSave) return;
		saving = true;
		message = '';
		error = '';
		const before = open?.version ?? null;
		try {
			const detail = await saveTermList(name.trim(), terms, notes.trim() || null);
			open = detail;
			creating = false;
			termsText = detail.terms.join('\n');
			notes = detail.notes ?? '';
			message =
				before === null
					? `Saved ${detail.name} as version ${detail.version}.`
					: before === detail.version
						? `Nothing changed; version ${detail.version} stands.`
						: `Saved version ${detail.version}. Version ${before} is unchanged.`;
			await refresh();
		} catch (failure) {
			error = describe(failure);
		} finally {
			saving = false;
		}
	}

	async function retire(): Promise<void> {
		if (open === null || retiring) return;
		if (!window.confirm(`Retire ${open.name}? Exports that pin a version still resolve it.`))
			return;
		retiring = true;
		message = '';
		error = '';
		try {
			const summary = await retireTermList(open.name);
			open = { ...open, retired_at: summary.retired_at };
			message = `${summary.name} is retired. It no longer appears in the export picker.`;
			await refresh();
		} catch {
			error = 'The list could not be retired. Try again.';
		} finally {
			retiring = false;
		}
	}
</script>

<div class="term-lists">
	{#if listError}<p class="field__error" role="alert">{listError}</p>{/if}
	{#if lists.length === 0}
		<section class="empty-state">
			<h2>No term lists yet</h2>
			<p>
				A list names the people, customers, hosts, and project words the built-in detectors cannot
				know. Save one here, then pick it when exporting a case record.
			</p>
		</section>
	{:else}
		<p class="result-count">{plural(lists.length, 'term list')}</p>
		<div class="table-scroll">
			<table class="data-table term-lists__table">
				<thead>
					<tr>
						<th scope="col">Name</th>
						<th scope="col" class="numeric">Version</th>
						<th scope="col" class="numeric">Terms</th>
						<th scope="col" class="wide-only">Notes</th>
						<th scope="col" class="wide-only">Saved</th>
						<th scope="col">Status</th>
						<td></td>
					</tr>
				</thead>
				<tbody>
					{#each lists as item (item.name)}
						<tr class:muted={item.retired_at !== null}>
							<th scope="row">{item.name}</th>
							<td class="numeric">{item.version}</td>
							<td class="numeric">{item.term_count}</td>
							<td class="wide-only term-lists__notes">{item.notes ?? ''}</td>
							<td class="wide-only nowrap">
								<time datetime={item.created_at}>{formatTimestamp(item.created_at)}</time>
							</td>
							<td class="nowrap">{item.retired_at === null ? 'Active' : 'Retired'}</td>
							<td class="nowrap">
								<button
									class="text-button"
									type="button"
									disabled={opening !== null}
									aria-label="Open {item.name}"
									onclick={() => void openList(item)}
								>
									{opening === item.name ? 'Opening…' : 'Open'}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<div class="term-lists__actions">
		{#if !creating}
			<button class="button" type="button" onclick={startNew}>New list</button>
		{/if}
		{#if error && !editing}<span class="field__error" role="alert">{error}</span>{/if}
	</div>

	{#if editing}
		<form class="term-list-editor" aria-labelledby="term-list-editor-heading" onsubmit={save}>
			<h2 id="term-list-editor-heading">
				{#if open === null}
					New term list
				{:else}
					{open.name} · version {open.version}{open.retired_at !== null ? ' · retired' : ''}
				{/if}
			</h2>
			{#if open === null}
				<div class="field">
					<label for="term-list-name">Name</label>
					<input
						id="term-list-name"
						type="text"
						autocomplete="off"
						spellcheck="false"
						bind:value={name}
						aria-describedby="term-list-name-hint"
						aria-invalid={name.trim() !== '' && !nameValid ? 'true' : undefined}
					/>
					<p id="term-list-name-hint" class="field__hint">
						Letters, digits, dots, dashes, underscores; up to 64. The name is permanent.
					</p>
				</div>
			{:else}
				<p class="field__hint">
					Saving a changed list creates version {open.version + 1}; version {open.version} stays as it
					is. Exports that pinned an older version still resolve it.
				</p>
			{/if}
			<div class="field">
				<label for="term-list-terms">Terms</label>
				<textarea
					id="term-list-terms"
					rows="8"
					spellcheck="false"
					placeholder="One per line"
					bind:value={termsText}
					disabled={open?.retired_at != null}
					aria-describedby="term-list-terms-hint"></textarea>
				<p id="term-list-terms-hint" class="field__hint">
					{plural(terms.length, 'term')}, up to 200. Matched as whole words, case-insensitively.
					Terms stay on this host; exports carry counts and the list's name and version.
				</p>
			</div>
			<div class="field">
				<label for="term-list-notes">Notes</label>
				<input
					id="term-list-notes"
					type="text"
					bind:value={notes}
					disabled={open?.retired_at != null}
					placeholder="What this list covers; shown in the table"
				/>
			</div>
			<div class="term-lists__actions">
				<button class="button button--primary" type="submit" disabled={!canSave}>
					{saving ? 'Saving…' : open === null ? 'Save list' : 'Save new version'}
				</button>
				{#if open !== null && open.retired_at === null}
					<button
						class="text-button text-button--danger"
						type="button"
						disabled={retiring}
						onclick={() => void retire()}
					>
						{retiring ? 'Retiring…' : 'Retire list'}
					</button>
				{/if}
				<button class="text-button" type="button" onclick={close}>Close</button>
				{#if message}<span class="field__hint" role="status">{message}</span>{/if}
				{#if error}<span class="field__error" role="alert">{error}</span>{/if}
			</div>
		</form>
	{/if}
</div>
