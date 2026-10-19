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
	import { bundleLabel, roleOptions, scopeLabel, statusOptions } from '$lib/bundles/format';
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
	<p class="reader__toolbar"><a class="reader__back" href={resolve('/bundles')}>Bundles</a></p>

	<header class="bundle-editor__header">
		<h1 class:untitled={!current.document.objective}>{bundleLabel(current.document.objective)}</h1>
		<p class="transcript__meta">
			<span>Revision {current.revision} of {current.latest_revision}</span>
			<span>{plural(current.items.length, 'item')}</span>
			<span>Updated {formatTimestamp(current.updated_at)}</span>
		</p>
		{#if readOnly}
			<p class="notice" role="status">
				Viewing an earlier revision. <a href={revisionHref(null)}>View latest</a>
			</p>
		{/if}
	</header>

	<form
		class="bundle-form"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<fieldset class="bundle-form__fields" disabled={readOnly}>
			<div class="field">
				<label for="bundle-objective">Objective</label>
				<input
					id="bundle-objective"
					type="text"
					maxlength="4000"
					bind:value={objective}
					aria-describedby={needsObjective ? 'bundle-objective-error' : undefined}
					aria-invalid={needsObjective}
				/>
				{#if needsObjective}
					<p id="bundle-objective-error" class="field__error">
						Add an objective before marking the bundle {status === 'reviewed'
							? 'reviewed'
							: 'analysis only'}.
					</p>
				{/if}
			</div>

			<fieldset class="field field--choices">
				<legend>Status</legend>
				{#each statusOptions as option (option.value)}
					<label class="choice">
						<input type="radio" name="status" value={option.value} bind:group={status} />
						<span>{option.label}</span>
						<span class="choice__hint">{option.hint}</span>
					</label>
				{/each}
			</fieldset>

			<section class="bundle-evidence" aria-labelledby="bundle-evidence-heading">
				<h2 id="bundle-evidence-heading">Evidence</h2>
				{#if entries.length === 0}
					<p class="field__error">A bundle needs at least one item. Undo by reloading the page.</p>
				{/if}
				<ol class="evidence-list">
					{#each entries as entry, index (refKey(entry.resolved.item.ref))}
						{@const item = entry.resolved}
						{#if item.omitted_before}
							<li class="evidence-gap">
								{plural(item.omitted_before, 'event')} not included
							</li>
						{/if}
						<li class="evidence-item" class:evidence-item--invalid={itemIssues[index]}>
							<div class="evidence-item__head">
								<label class="evidence-item__role">
									<span class="visually-hidden">Role of item {index + 1}</span>
									<select
										value={entry.role}
										onchange={(event) =>
											edit(index, { role: event.currentTarget.value as EvidenceRole })}
									>
										{#each roleOptions as option (option.value)}
											<option value={option.value}>{option.label}</option>
										{/each}
									</select>
								</label>
								<p class="evidence-item__source">
									<span>{roleLabel(item.event_role as never)}</span>
									{#if item.occurred_at}<span>{formatTime(item.occurred_at)}</span>{/if}
									<span>{scopeLabel(item)}</span>
									<a href={sourceHref(item)}>{item.conversation_title ?? 'Open in conversation'}</a>
								</p>
							</div>
							{#if item.excerpt === null}
								<p class="block-gap">Text not captured</p>
							{:else}
								<blockquote class="evidence-item__excerpt">{item.excerpt}</blockquote>
							{/if}
							{#if itemIssues[index]}
								<p class="field__error">{itemIssues[index]}</p>
							{/if}
							<div class="evidence-item__foot">
								<label class="evidence-item__note">
									<span>Note</span>
									<input
										type="text"
										aria-label="Note for item {index + 1}"
										maxlength="4000"
										value={entry.note}
										oninput={(event) => edit(index, { note: event.currentTarget.value })}
									/>
								</label>
								<button
									class="text-button"
									type="button"
									disabled={index === 0}
									aria-label="Move item {index + 1} up"
									onclick={() => move(index, -1)}>Up</button
								>
								<button
									class="text-button"
									type="button"
									disabled={index === entries.length - 1}
									aria-label="Move item {index + 1} down"
									onclick={() => move(index, 1)}>Down</button
								>
								<button
									class="text-button text-button--danger"
									type="button"
									aria-label="Remove item {index + 1}"
									onclick={() => remove(index)}>Remove</button
								>
							</div>
						</li>
					{/each}
				</ol>
			</section>

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
				<p id="bundle-missing-hint" class="field__hint">
					One gap per line, such as files or output that were not captured.
				</p>
			</div>
		</fieldset>

		{#if !readOnly}
			<div class="bundle-form__actions">
				<button
					class="button button--primary"
					type="submit"
					disabled={!dirty || saving || needsObjective || entries.length === 0}
				>
					{saving ? 'Saving…' : 'Save revision'}
				</button>
				<p class="bundle-form__status" aria-live="polite">
					{#if confirmation && !dirty}{confirmation}{:else if dirty}Unsaved changes{/if}
				</p>
			</div>
			{#if conflict !== null}
				<div class="notice" role="alert">
					This bundle was changed elsewhere{conflict ? ` (now revision ${conflict})` : ''}. Your
					edits are still here.
					<button class="text-button" type="button" onclick={() => void invalidateAll()}>
						Load the latest and discard my edits
					</button>
				</div>
			{/if}
			{#if messages.length > 0}
				<ul class="field__error" role="alert">
					{#each messages as message, index (index)}<li>{message}</li>{/each}
				</ul>
			{/if}
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
