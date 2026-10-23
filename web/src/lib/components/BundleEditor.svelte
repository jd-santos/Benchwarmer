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
		HarnessRunRecord,
		ResolvedBundleItem
	} from '$lib/api/types';
	import {
		bundleLabel,
		formatEstimate,
		producerLabel,
		roleOptions,
		runInputFor,
		scopeLabel,
		statusLabel,
		statusOptions,
		usageTotals
	} from '$lib/bundles/format';
	import { SvelteSet } from 'svelte/reactivity';
	import { refKey } from '$lib/bundles/selection';
	import { formatTime, formatTimestamp, plural, roleLabel } from '$lib/conversations/format';

	let {
		detail,
		run = Promise.resolve(null)
	}: { detail: BundleDetail; run?: Promise<HarnessRunRecord | null> } = $props();

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

	let summary = $derived(current.document.summary);
	let objective = $derived(current.document.objective);
	let goal = $derived(current.document.goal);
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
		summary: summary.trim(),
		objective: objective.trim(),
		goal: goal.trim(),
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
	const needsObjective = $derived(
		status !== 'draft' && status !== 'rejected' && draft.objective === ''
	);
	const needsReason = $derived(status === 'rejected' && draft.rationale === null);
	const blocked = $derived(needsObjective || needsReason || entries.length === 0);
	// A proposal awaits review until a person saves any revision over it.
	const awaitingReview = $derived(
		!readOnly && current.origin === 'generated' && current.document.status === 'draft'
	);
	const statusHint = $derived(statusOptions.find((option) => option.value === status)?.hint);
	const conversations = $derived([
		...new Map(current.items.map((item) => [item.item.ref.conversation_id, item])).values()
	]);
	const openNotes = new SvelteSet<string>();

	function normalized(document: BundleDocument): BundleDocument {
		return {
			summary: document.summary,
			objective: document.objective,
			goal: document.goal,
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

	function runHref(runId: string): ResolvedPathname {
		return `${resolve('/bundles')}?${new URLSearchParams({ run: runId })}` as ResolvedPathname;
	}

	/** The timestamp part of a run id, which is what distinguishes runs of one workflow. */
	function shortRunId(runId: string): string {
		return runId.replace(/^[a-z-]+-(?=\d{4})/, '');
	}

	function revisionHref(number: number | null): ResolvedPathname {
		const base = resolve('/bundles/[id]', { id: current.id });
		return (number === null ? base : `${base}?revision=${number}`) as ResolvedPathname;
	}

	async function save(): Promise<void> {
		if (saving || !dirty || blocked) return;
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
	<header class="bundle-editor__header">
		<h1 class:untitled={bundleLabel(current.document) === 'Untitled bundle'}>
			{bundleLabel(current.document)}
		</h1>
		<p class="meta-line">
			<span>{statusLabel(current.document.status)}</span>
			<span title={current.producer}>{producerLabel(current.origin, current.producer)}</span>
			{#if current.provenance}
				<span title={current.provenance.report_path ?? current.provenance.run_id}>
					<a href={runHref(current.provenance.run_id)}
						>Run {shortRunId(current.provenance.run_id)}</a
					>
				</span>
			{/if}
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
		{#if current.provenance}
			{#await run then record}
				{@const input = record ? runInputFor(record, current.id) : null}
				{#if record && input}
					{@const totals = usageTotals(input.usage)}
					<p class="meta-line" data-run-usage>
						<span>
							The pass that proposed this bundle{input.bundle_ids.length > 1
								? ` and ${input.bundle_ids.length - 1} other${input.bundle_ids.length > 2 ? 's' : ''}`
								: ''}
							used {totals.tokens.toLocaleString()} tokens, about {formatEstimate(totals.estimate)}
							({record.pricing_source})
						</span>
					</p>
				{/if}
			{/await}
		{/if}
		{#if readOnly}
			<p class="notice" role="status">
				Viewing an earlier revision. <a href={revisionHref(null)}>View latest</a>
			</p>
		{:else if awaitingReview}
			<p class="notice" role="status">
				A model proposed this bundle and no one has reviewed it. Check each item against its source,
				then set the status to Reviewed to accept it, or to Rejected with a reason.
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
				<label for="bundle-summary">Summary</label>
				<textarea
					id="bundle-summary"
					rows="2"
					maxlength="4000"
					placeholder="What this bundle shows, in a sentence or two for a reader"
					bind:value={summary}></textarea>
			</div>

			<div class="field">
				<label for="bundle-goal">Goal</label>
				<textarea
					id="bundle-goal"
					rows="2"
					maxlength="4000"
					placeholder="What this piece of work was trying to achieve, with its specifics"
					bind:value={goal}></textarea>
			</div>

			<div class="field">
				<label for="bundle-objective">Objective</label>
				<textarea
					id="bundle-objective"
					rows="2"
					maxlength="4000"
					placeholder="The kind of work in general terms, e.g. verify a fix by replaying historical inputs"
					bind:value={objective}
					aria-describedby={needsObjective ? 'bundle-objective-error' : 'bundle-objective-hint'}
					aria-invalid={needsObjective}></textarea>
				{#if needsObjective}
					<p id="bundle-objective-error" class="field__error">
						Add an objective before changing the status.
					</p>
				{:else}
					<p id="bundle-objective-hint" class="field__hint">
						Bundles are grouped by objective, so describe the type of work without project names,
						dates, or figures.
					</p>
				{/if}
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
				<label for="bundle-rationale"
					>{status === 'rejected' ? 'Why it was rejected' : 'Why these items'}</label
				>
				<textarea
					id="bundle-rationale"
					rows="3"
					maxlength="4000"
					placeholder={status === 'rejected'
						? 'What made this evidence unusable, so proposals can improve'
						: 'How these items connect to the objective'}
					bind:value={rationale}
					aria-describedby={needsReason ? 'bundle-rationale-error' : undefined}
					aria-invalid={needsReason}></textarea>
				{#if needsReason}
					<p id="bundle-rationale-error" class="field__error">
						Say why before rejecting; the reason stays with the bundle.
					</p>
				{/if}
			</div>
			<div class="field">
				<label for="bundle-missing">Missing evidence</label>
				<textarea
					id="bundle-missing"
					rows="3"
					placeholder="One gap per line, such as files or output that weren't captured"
					bind:value={missing}></textarea>
			</div>
		</fieldset>

		{#if !readOnly}
			<div class="save-bar" class:save-bar--dirty={dirty}>
				<p class="save-bar__status" aria-live="polite">
					{#if dirty}Unsaved changes{:else if confirmation}{confirmation}{:else}No changes{/if}
				</p>
				<button class="button button--primary" type="submit" disabled={!dirty || saving || blocked}>
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
						·
						<span title={revision.producer}
							>{producerLabel(revision.origin, revision.producer)}</span
						>
						· {formatTimestamp(revision.created_at)}
					</li>
				{/each}
			</ol>
		</details>
	{/if}
</div>
