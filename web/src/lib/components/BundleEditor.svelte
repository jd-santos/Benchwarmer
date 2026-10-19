<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import { ApiClientError, updateBundle } from '$lib/api/client';
	import type {
		BundleDetail,
		BundleDocument,
		BundleStatus,
		EvidenceRole,
		ResolvedBundleItem
	} from '$lib/api/types';
	import {
		bundleLabel,
		roleOptions,
		scopeLabel,
		statusLabel,
		statusOptions
	} from '$lib/bundles/format';
	import { SvelteSet } from 'svelte/reactivity';
	import { refKey } from '$lib/bundles/selection';
	import { formatTime, formatTimestamp, plural, roleLabel } from '$lib/conversations/format';

	let { detail }: { detail: BundleDetail } = $props();

	interface Entry {
		resolved: ResolvedBundleItem;
		role: EvidenceRole;
		note: string;
	}

	function entriesFrom(source: BundleDetail): Entry[] {
		return source.items.map((resolved) => ({
			resolved,
			role: resolved.item.role,
			note: resolved.item.note ?? ''
		}));
	}

	let saved = $state<BundleDetail | null>(null);
	const current = $derived(saved ?? detail);
	const readOnly = $derived(current.revision !== current.latest_revision);

	let objective = $derived(current.document.objective);
	let status = $derived<BundleStatus>(current.document.status);
	let rationale = $derived(current.document.rationale ?? '');
	let missing = $derived(current.document.missing_evidence.join('\n'));
	let entries = $derived(entriesFrom(current));

	let saving = $state(false);
	let messages = $state<string[]>([]);
	let itemIssues = $state<Record<number, string>>({});
	let conflict = $state<number | null>(null);
	let confirmation = $state('');

	const draft = $derived<BundleDocument>({
		objective: objective.trim(),
		status,
		rationale: rationale.trim() || null,
		missing_evidence: missing
			.split('\n')
			.map((line) => line.trim())
			.filter(Boolean),
		items: entries.map((entry) => ({
			ref: entry.resolved.item.ref,
			role: entry.role,
			note: entry.note.trim() || null
		}))
	});
	const dirty = $derived(JSON.stringify(draft) !== JSON.stringify(normalized(current.document)));
	const needsObjective = $derived(status !== 'draft' && draft.objective === '');
	const statusHint = $derived(statusOptions.find((option) => option.value === status)?.hint);
	const conversations = $derived([
		...new Map(current.items.map((item) => [item.item.ref.conversation_id, item])).values()
	]);
	const openNotes = new SvelteSet<string>();

	function normalized(document: BundleDocument): BundleDocument {
		return {
			objective: document.objective,
			status: document.status,
			rationale: document.rationale,
			missing_evidence: document.missing_evidence,
			items: document.items.map((item) => ({
				ref: item.ref,
				role: item.role,
				note: item.note ?? null
			}))
		};
	}

	// Writable deriveds are not deeply reactive, so edits replace the array.
	function edit(index: number, change: Partial<Entry>): void {
		entries = entries.map((entry, position) =>
			position === index ? { ...entry, ...change } : entry
		);
	}

	function move(index: number, step: number): void {
		const next = [...entries];
		const [entry] = next.splice(index, 1);
		next.splice(index + step, 0, entry);
		entries = next;
	}

	function remove(index: number): void {
		entries = entries.filter((_, position) => position !== index);
	}

	function sourceHref(item: ResolvedBundleItem): ResolvedPathname {
		const ref = item.item.ref;
		const base = resolve('/conversations/[id]', { id: ref.conversation_id });
		const search = item.conversation_is_latest
			? ''
			: `?${new URLSearchParams({ revision: ref.revision })}`;
		return `${base}${search}#${encodeURIComponent(ref.event_id)}` as ResolvedPathname;
	}

	function revisionHref(number: number | null): ResolvedPathname {
		const base = resolve('/bundles/[id]', { id: current.id });
		return (number === null ? base : `${base}?revision=${number}`) as ResolvedPathname;
	}

	async function save(): Promise<void> {
		if (saving || !dirty || needsObjective || entries.length === 0) return;
		saving = true;
		messages = [];
		itemIssues = {};
		conflict = null;
		confirmation = '';
		try {
			saved = await updateBundle(current.id, draft, current.revision);
			confirmation = `Saved revision ${saved.revision}.`;
		} catch (failure) {
			if (failure instanceof ApiClientError && failure.status === 409) {
				const body = failure.body as { latest_revision?: unknown } | undefined;
				conflict = typeof body?.latest_revision === 'number' ? body.latest_revision : 0;
			} else if (failure instanceof ApiClientError && failure.issues.length > 0) {
				for (const issue of failure.issues) {
					if (issue.item_index === null) messages = [...messages, issue.message];
					else itemIssues[issue.item_index] = issue.message;
				}
			} else {
				messages = ['The bundle could not be saved. Your edits are still here; try again.'];
			}
		} finally {
			saving = false;
		}
	}
</script>

<div class="bundle-editor">
	<a class="back-link" href={resolve('/bundles')}>Bundles</a>

	<header class="bundle-editor__header">
		<h1 class:untitled={!current.document.objective}>{bundleLabel(current.document.objective)}</h1>
		<p class="meta-line">
			<span>{statusLabel(current.document.status)}</span>
			<span>{plural(current.items.length, 'item')}</span>
			{#if conversations.length === 1}
				<span>
					From <a href={sourceHref(conversations[0])}
						>{conversations[0].conversation_title ?? 'an untitled conversation'}</a
					>
				</span>
			{:else}
				<span>From {plural(conversations.length, 'conversation')}</span>
			{/if}
			{#if current.latest_revision > 1}
				<span>Revision {current.revision}</span>
			{/if}
		</p>
		{#if readOnly}
			<p class="notice" role="status">
				Viewing an earlier revision. <a href={revisionHref(null)}>View latest</a>
			</p>
		{/if}
	</header>

	<form
		class="bundle-layout"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<fieldset class="bundle-summary" disabled={readOnly}>
			<legend class="visually-hidden">Summary</legend>
			<div class="field">
				<label for="bundle-objective">Objective</label>
				<textarea
					id="bundle-objective"
					rows="2"
					maxlength="4000"
					bind:value={objective}
					aria-describedby="bundle-objective-hint"
					aria-invalid={needsObjective}></textarea>
				<p id="bundle-objective-hint" class={needsObjective ? 'field__error' : 'field__hint'}>
					{needsObjective
						? 'Add an objective before changing the status.'
						: 'What this evidence shows, in a sentence.'}
				</p>
			</div>

			<fieldset class="field">
				<legend>Status</legend>
				<div class="segmented">
					{#each statusOptions as option (option.value)}
						<label>
							<input type="radio" name="status" value={option.value} bind:group={status} />
							<span>{option.label}</span>
						</label>
					{/each}
				</div>
				<p class="field__hint">{statusHint}</p>
			</fieldset>
		</fieldset>

		<section class="bundle-evidence" aria-labelledby="bundle-evidence-heading">
			<h2 id="bundle-evidence-heading">Evidence</h2>
			{#if entries.length === 0}
				<p class="field__error">A bundle needs at least one item. Reload to undo.</p>
			{/if}
			<ol class="evidence-list">
				{#each entries as entry, index (refKey(entry.resolved.item.ref))}
					{@const item = entry.resolved}
					{@const key = refKey(item.item.ref)}
					{#if item.omitted_before}
						<li class="evidence-gap">{plural(item.omitted_before, 'event')} not included</li>
					{/if}
					<li class="evidence-card" class:evidence-card--invalid={itemIssues[index]}>
						<div class="evidence-card__bar">
							<label class="evidence-card__role">
								<span class="visually-hidden">Role of item {index + 1}</span>
								<select
									value={entry.role}
									disabled={readOnly}
									onchange={(event) =>
										edit(index, { role: event.currentTarget.value as EvidenceRole })}
								>
									{#each roleOptions as option (option.value)}
										<option value={option.value}>{option.label}</option>
									{/each}
								</select>
							</label>
							{#if !readOnly}
								<div class="evidence-card__tools">
									<button
										class="tool-button"
										type="button"
										disabled={index === 0}
										aria-label="Move item {index + 1} up"
										title="Move up"
										onclick={() => move(index, -1)}>↑</button
									>
									<button
										class="tool-button"
										type="button"
										disabled={index === entries.length - 1}
										aria-label="Move item {index + 1} down"
										title="Move down"
										onclick={() => move(index, 1)}>↓</button
									>
									<button
										class="tool-button tool-button--danger"
										type="button"
										aria-label="Remove item {index + 1}"
										title="Remove"
										onclick={() => remove(index)}>×</button
									>
								</div>
							{/if}
						</div>

						{#if item.excerpt === null}
							<p class="block-gap">Text not captured</p>
						{:else}
							<blockquote class="evidence-card__excerpt">{item.excerpt}</blockquote>
						{/if}

						<p class="meta-line evidence-card__source">
							<span>{roleLabel(item.event_role as never)}</span>
							{#if item.occurred_at}<span>{formatTime(item.occurred_at)}</span>{/if}
							<span>{scopeLabel(item)}</span>
							<span>
								<a href={sourceHref(item)}
									>{conversations.length > 1
										? (item.conversation_title ?? 'Open in conversation')
										: 'View in conversation'}</a
								>
							</span>
						</p>

						{#if itemIssues[index]}
							<p class="field__error">{itemIssues[index]}</p>
						{/if}

						{#if entry.note || openNotes.has(key)}
							<label class="evidence-card__note">
								<span>Note</span>
								<input
									type="text"
									maxlength="4000"
									value={entry.note}
									disabled={readOnly}
									oninput={(event) => edit(index, { note: event.currentTarget.value })}
								/>
							</label>
						{:else if !readOnly}
							<button
								class="text-button evidence-card__add-note"
								type="button"
								onclick={() => openNotes.add(key)}
							>
								Add note
							</button>
						{/if}
					</li>
				{/each}
			</ol>
		</section>

		<fieldset class="bundle-notes" disabled={readOnly}>
			<legend class="visually-hidden">Review notes</legend>
			<div class="field">
				<label for="bundle-rationale">Why these items</label>
				<textarea id="bundle-rationale" rows="3" maxlength="4000" bind:value={rationale}></textarea>
			</div>
			<div class="field">
				<label for="bundle-missing">Missing evidence</label>
				<textarea
					id="bundle-missing"
					rows="3"
					aria-describedby="bundle-missing-hint"
					bind:value={missing}></textarea>
				<p id="bundle-missing-hint" class="field__hint">One gap per line.</p>
			</div>
		</fieldset>

		{#if !readOnly}
			<div class="save-bar" class:save-bar--dirty={dirty}>
				<p class="save-bar__status" aria-live="polite">
					{#if dirty}Unsaved changes{:else if confirmation}{confirmation}{:else}No changes{/if}
				</p>
				<button
					class="button button--primary"
					type="submit"
					disabled={!dirty || saving || needsObjective || entries.length === 0}
				>
					{saving ? 'Saving…' : 'Save revision'}
				</button>
				{#if conflict !== null}
					<div class="notice save-bar__message" role="alert">
						This bundle was changed elsewhere{conflict ? ` (now revision ${conflict})` : ''}. Your
						edits are still here.
						<button class="text-button" type="button" onclick={() => void invalidateAll()}>
							Load the latest and discard my edits
						</button>
					</div>
				{/if}
				{#if messages.length > 0}
					<ul class="field__error save-bar__message" role="alert">
						{#each messages as message, index (index)}<li>{message}</li>{/each}
					</ul>
				{/if}
			</div>
		{/if}
	</form>

	{#if current.revisions.length > 1}
		<details class="revisions">
			<summary>{plural(current.revisions.length, 'revision')}</summary>
			<ol>
				{#each current.revisions as revision (revision.number)}
					<li>
						{#if revision.number === current.revision}
							<span aria-current="true">Revision {revision.number} (shown)</span>
						{:else}
							<a
								href={revisionHref(
									revision.number === current.latest_revision ? null : revision.number
								)}
							>
								Revision {revision.number}
							</a>
						{/if}
						· {formatTimestamp(revision.created_at)}
					</li>
				{/each}
			</ol>
		</details>
	{/if}
</div>
