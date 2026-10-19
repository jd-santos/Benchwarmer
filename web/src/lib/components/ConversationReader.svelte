<script lang="ts">
	import { afterNavigate, replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type {
		Branch,
		BundleItem,
		ContentBlock,
		ConversationDetail,
		ConversationEvent,
		EvidenceRef
	} from '$lib/api/types';
	import {
		blockRangeFromSelection,
		defaultRole,
		refKey,
		type BlockRange
	} from '$lib/bundles/selection';
	import EvidenceTray from '$lib/components/EvidenceTray.svelte';
	import {
		captureGaps,
		conversationLabel,
		formatTime,
		formatTimestamp,
		highlightParts,
		lineCount,
		plural,
		roleLabel
	} from '$lib/conversations/format';
	import { onMount, tick } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';

	let { detail, query = null }: { detail: ConversationDetail; query?: string | null } = $props();

	const COLLAPSE_LINES = 6;
	const narrowQuery = '(max-width: 63.999rem)';
	const outlineKey = 'benchwarmer:outline-open';

	const summary = $derived(detail.summary);
	const eventsById = $derived(new Map(detail.events.map((event) => [event.id, event])));
	const branchIndex = $derived(new Map(detail.branches.map((branch, index) => [branch.id, index])));
	const childCounts = $derived(
		detail.events.reduce((counts, event) => {
			if (event.parent_id !== null)
				counts.set(event.parent_id, (counts.get(event.parent_id) ?? 0) + 1);
			return counts;
		}, new Map<string, number>())
	);
	const positionsKey = $derived(`benchwarmer:positions:${summary.id}`);

	// Open unless the reader closed it; narrow screens start closed in onMount.
	let outlineOpen = $state(readStorage(outlineKey) !== 'false');
	let branchId = $state('');
	let currentEventId = $state<string | null>(null);
	let targetEventId = $state<string | null>(null);
	const positions = new SvelteMap<string, string>();
	let selecting = $state(false);
	let highlighted = $state<BlockRange | null>(null);
	const selection = new SvelteMap<string, BundleItem>();
	const selectedItems = $derived(
		[...selection.values()].sort(
			(a, b) =>
				(eventsById.get(a.ref.event_id)?.ordinal ?? 0) -
					(eventsById.get(b.ref.event_id)?.ordinal ?? 0) ||
				(a.ref.text_start ?? -1) - (b.ref.text_start ?? -1)
		)
	);
	const selectedEvents = $derived(new Set(selectedItems.map((item) => item.ref.event_id)));

	const branch = $derived(
		detail.branches.find((item) => item.id === branchId) ?? detail.branches.at(-1)
	);
	const visibleEvents = $derived(
		(branch?.event_ids ?? [])
			.map((id) => eventsById.get(id))
			.filter((event): event is ConversationEvent => event !== undefined)
	);
	const turns = $derived(
		visibleEvents.filter((event) => event.kind === 'message' && event.role === 'user')
	);
	const capturedEvents = $derived(visibleEvents.filter((event) => event.kind !== 'message'));
	const gaps = $derived(captureGaps(summary.coverage));
	const continues = $derived(detail.relationships.filter((item) => item.kind === 'continuation'));
	const continuedIn = $derived(detail.referenced_by.filter((item) => item.kind === 'continuation'));

	function evidenceRef(eventId: string, range: BlockRange | null = null): EvidenceRef {
		return {
			conversation_id: summary.id,
			revision: summary.revision,
			event_id: eventId,
			block_id: range?.blockId ?? null,
			text_start: range?.start ?? null,
			text_end: range?.end ?? null
		};
	}

	function toggleEvent(event: ConversationEvent, checked: boolean): void {
		const ref = evidenceRef(event.id);
		if (checked) selection.set(refKey(ref), { ref, role: defaultRole(event.role) });
		else selection.delete(refKey(ref));
	}

	function addHighlightedText(): void {
		const range = highlighted;
		const event = range ? eventsById.get(range.eventId) : undefined;
		if (!range || !event) return;
		const ref = evidenceRef(event.id, range);
		const kind = event.content.find((item) => item.id === range.blockId)?.kind ?? null;
		selection.set(refKey(ref), { ref, role: defaultRole(event.role, kind) });
		window.getSelection()?.removeAllRanges();
	}

	function setSelecting(next: boolean): void {
		selecting = next;
		if (!next) {
			selection.clear();
			highlighted = null;
		}
	}

	$effect(() => {
		if (!selecting) return;
		const update = () => (highlighted = blockRangeFromSelection(window.getSelection()));
		document.addEventListener('selectionchange', update);
		return () => document.removeEventListener('selectionchange', update);
	});

	function readStorage(key: string): string | null {
		try {
			return sessionStorage.getItem(key);
		} catch {
			return null;
		}
	}

	function writeStorage(key: string, value: string): void {
		try {
			sessionStorage.setItem(key, value);
		} catch {
			// Reading position is a convenience; storage may be unavailable.
		}
	}

	function branchesThrough(eventId: string): Branch[] {
		return detail.branches.filter((item) => item.event_ids.includes(eventId));
	}

	function messageCount(item: Branch): number {
		return item.event_ids.filter((id) => eventsById.get(id)?.kind === 'message').length;
	}

	function pathLabel(item: Branch): string {
		return `Path ${(branchIndex.get(item.id) ?? 0) + 1}`;
	}

	function blockText(event: ConversationEvent): string | null {
		for (const block of event.content) {
			if (block.kind === 'text' && block.text) return block.text.split(/\s+/).join(' ');
		}
		return null;
	}

	function outlineText(event: ConversationEvent): string {
		const text = blockText(event);
		if (text === null) {
			const kinds = event.content.map((item) => blockLabel(item).split(' · ')[0]);
			return kinds.find((kind) => kind !== '') ?? `${roleLabel(event.role)} message, no text`;
		}
		return text.length > 90 ? `${text.slice(0, 90)}…` : text;
	}

	function conversationHref(id: string): ResolvedPathname {
		return resolve('/conversations/[id]', { id });
	}

	function revisionHref(revision: string | null): ResolvedPathname {
		const base = conversationHref(summary.id);
		return revision === null
			? base
			: (`${base}?${new URLSearchParams({ revision })}` as ResolvedPathname);
	}

	function isNarrow(): boolean {
		return typeof window.matchMedia === 'function' && window.matchMedia(narrowQuery).matches;
	}

	function setOutline(open: boolean): void {
		outlineOpen = open;
		if (!isNarrow()) writeStorage(outlineKey, String(open));
	}

	async function scrollToEvent(eventId: string, focus = true): Promise<void> {
		await tick();
		const element = document.getElementById(eventId);
		if (element === null) return;
		element.scrollIntoView({ block: 'start' });
		if (focus) element.focus({ preventScroll: true });
		targetEventId = eventId;
	}

	function rememberBranch(id: string): void {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams(window.location.search);
		params.set('branch', id);
		const href = `${conversationHref(summary.id)}?${params}${window.location.hash}`;
		try {
			replaceState(href as ResolvedPathname, {});
		} catch {
			// Shallow routing is unavailable before the router starts.
		}
	}

	/** Switch paths; keep the reader at the given anchor or this path's last position. */
	async function selectBranch(id: string, anchor: string | null = null): Promise<void> {
		if (id === branch?.id) {
			if (anchor) await scrollToEvent(anchor);
			return;
		}
		branchId = id;
		rememberBranch(id);
		const target = anchor ?? positions.get(id) ?? null;
		if (target) await scrollToEvent(target);
		else window.scrollTo({ top: 0 });
	}

	function closeOutlineOnNarrow(): void {
		if (isNarrow()) outlineOpen = false;
	}

	function jumpTo(eventId: string): void {
		closeOutlineOnNarrow();
		targetEventId = eventId;
	}

	function followHash(): void {
		const hash = decodeURIComponent(window.location.hash.slice(1));
		if (!hash || !eventsById.has(hash)) return;
		if (!branch?.event_ids.includes(hash)) {
			const containing = branchesThrough(hash).at(-1);
			if (containing) branchId = containing.id;
		}
		void scrollToEvent(hash);
	}

	function moveFocus(step: number): void {
		const ids = visibleEvents.map((event) => event.id);
		const active = document.activeElement?.closest('[data-event]')?.id ?? currentEventId;
		const index = active ? ids.indexOf(active) : -1;
		const next = ids[Math.min(ids.length - 1, Math.max(0, index + step))];
		if (next) void scrollToEvent(next);
	}

	function onKeydown(event: KeyboardEvent): void {
		if (event.metaKey || event.ctrlKey || event.altKey) return;
		const target = event.target as HTMLElement | null;
		if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
		if (event.key === 'j') moveFocus(1);
		else if (event.key === 'k') moveFocus(-1);
		else if (event.key === 'Escape' && outlineOpen && isNarrow()) setOutline(false);
	}

	function initialBranch(hash: string | null): string {
		const requested = new URL(window.location.href).searchParams.get('branch');
		const requestedBranch = detail.branches.find((item) => item.id === requested);
		if (requestedBranch && (hash === null || requestedBranch.event_ids.includes(hash))) {
			return requestedBranch.id;
		}
		if (hash !== null) {
			const containing = branchesThrough(hash).at(-1);
			if (containing) return containing.id;
		}
		return detail.branches.at(-1)?.id ?? '';
	}

	function isReload(): boolean {
		const entry = performance.getEntriesByType?.('navigation')[0] as
			PerformanceNavigationTiming | undefined;
		return entry?.type === 'reload';
	}

	onMount(() => {
		try {
			const saved = JSON.parse(readStorage(positionsKey) ?? '{}') as Record<string, unknown>;
			for (const [key, value] of Object.entries(saved)) {
				if (branchIndex.has(key) && typeof value === 'string' && eventsById.has(value)) {
					positions.set(key, value);
				}
			}
		} catch {
			// Ignore unreadable saved positions.
		}
		if (isNarrow()) outlineOpen = false;
		const rawHash = decodeURIComponent(window.location.hash.slice(1));
		const hash = rawHash && eventsById.has(rawHash) ? rawHash : null;
		branchId = initialBranch(hash);

		// A reload returns to where the reader was, not to a stale anchor.
		const saved = positions.get(branchId);
		if (hash !== null && !(isReload() && saved)) void scrollToEvent(hash);
		else if (saved) void scrollToEvent(saved, false);
	});

	afterNavigate(({ type }) => {
		if (type !== 'enter') followHash();
	});

	// Track the top-most visible event as this path's reading position.
	$effect(() => {
		const ids = visibleEvents.map((event) => event.id);
		const activeBranch = branch?.id;
		if (activeBranch === undefined || typeof IntersectionObserver === 'undefined') return;
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- observer bookkeeping, not state
		const visible = new Set<string>();
		const observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) visible.add(entry.target.id);
					else visible.delete(entry.target.id);
				}
				const first = ids.find((id) => visible.has(id));
				if (first) {
					currentEventId = first;
					positions.set(activeBranch, first);
					writeStorage(positionsKey, JSON.stringify(Object.fromEntries(positions)));
				}
			},
			{ rootMargin: '-15% 0px -60% 0px' }
		);
		for (const id of ids) {
			const element = document.getElementById(id);
			if (element) observer.observe(element);
		}
		return () => observer.disconnect();
	});

	function kindLabel(kind: ContentBlock['kind']): string {
		const labels: Record<string, string> = {
			reasoning: 'Reasoning',
			tool_call: 'Tool call',
			tool_result: 'Output',
			attachment: 'Attachment'
		};
		return labels[kind] ?? 'Unrecognized content';
	}

	function turnKind(event: ConversationEvent): 'user' | 'reply' | 'marker' {
		if (event.kind !== 'message') return 'marker';
		return event.role === 'user' ? 'user' : 'reply';
	}

	function collapsible(block: ContentBlock): boolean {
		return block.text !== null && lineCount(block.text) > COLLAPSE_LINES;
	}

	function blockLabel(block: ContentBlock): string {
		switch (block.kind) {
			case 'reasoning':
				return 'Reasoning';
			case 'tool_call':
				return `Tool call${block.tool_call_id ? ` · ${block.tool_call_id}` : ''}`;
			case 'tool_result':
				return `Tool output${block.tool_call_id ? ` · ${block.tool_call_id}` : ''}`;
			case 'attachment':
				return `Attachment${block.artifact_id ? ` · ${block.artifact_id}` : ''}`;
			case 'unknown':
				return 'Unrecognized content';
			default:
				return '';
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#snippet text(value: string)}
	{#each highlightParts(value, query) as part, index (index)}
		{#if part.match}<mark>{part.text}</mark>{:else}{part.text}{/if}
	{/each}
{/snippet}

{#snippet selectToggle(event: ConversationEvent)}
	<label class="turn__select">
		<input
			type="checkbox"
			checked={selection.has(refKey(evidenceRef(event.id)))}
			onchange={(change) => toggleEvent(event, change.currentTarget.checked)}
		/>
		<span class="visually-hidden">
			Select {event.kind === 'message'
				? roleLabel(event.role).toLowerCase()
				: 'event'}{event.occurred_at ? ` at ${formatTime(event.occurred_at)}` : ''}
		</span>
	</label>
{/snippet}

{#snippet blockHead(item: ContentBlock, meta: string | null)}
	<span class="block__kind">{kindLabel(item.kind)}</span>
	{#if item.tool_call_id}<span class="block__meta block__meta--code">{item.tool_call_id}</span>{/if}
	{#if meta}<span class="block__meta">{meta}</span>{/if}
{/snippet}

{#snippet block(item: ContentBlock)}
	{#if item.kind === 'text'}
		{#if item.text === null || item.text === ''}
			<p class="block-gap">Text not captured</p>
		{:else}
			<div class="block-text" data-block-id={item.id}>{@render text(item.text)}</div>
		{/if}
	{:else if item.text === null}
		<p class="block block--{item.kind} block--missing">
			{@render blockHead(item, 'content not captured')}
		</p>
	{:else if item.kind === 'reasoning'}
		<details class="block block--reasoning">
			<summary>{@render blockHead(item, plural(lineCount(item.text), 'line'))}</summary>
			<div class="block__body" data-block-id={item.id}>{@render text(item.text)}</div>
		</details>
	{:else if collapsible(item)}
		<details class="block block--{item.kind}">
			<summary>{@render blockHead(item, plural(lineCount(item.text), 'line'))}</summary>
			<pre data-block-id={item.id}>{@render text(item.text)}</pre>
		</details>
	{:else}
		<div class="block block--{item.kind}">
			<p class="block__head">{@render blockHead(item, null)}</p>
			<pre data-block-id={item.id}>{@render text(item.text)}</pre>
		</div>
	{/if}
{/snippet}

<div class="reader" class:reader--outline-open={outlineOpen}>
	<div class="reader__toolbar">
		<button
			class="button reader__contents"
			type="button"
			aria-expanded={outlineOpen}
			aria-controls="conversation-outline"
			title={outlineOpen ? 'Hide contents' : 'Show contents'}
			onclick={() => setOutline(!outlineOpen)}
		>
			<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
				<rect x="2.5" y="3.5" width="15" height="13" rx="1.5" fill="none" stroke="currentColor" />
				<line x1="7.5" y1="3.5" x2="7.5" y2="16.5" stroke="currentColor" />
				{#if outlineOpen}
					<rect x="3" y="4" width="4.5" height="12" fill="currentColor" opacity="0.35" />
				{/if}
			</svg>
			Contents
		</button>
		<a class="reader__back" href={resolve('/conversations')}>Conversations</a>
		<button
			class="button reader__select"
			type="button"
			aria-pressed={selecting}
			onclick={() => setSelecting(!selecting)}
		>
			{selecting ? 'Done selecting' : 'Select evidence'}
		</button>
	</div>

	<nav
		id="conversation-outline"
		class="outline"
		aria-label="Conversation contents"
		hidden={!outlineOpen}
	>
		<div class="outline__header">
			<h2>Contents</h2>
			<button class="text-button outline__close" type="button" onclick={() => setOutline(false)}>
				Close
			</button>
		</div>

		{#if detail.branches.length > 1}
			<section aria-labelledby="outline-paths">
				<h3 id="outline-paths">Paths</h3>
				<ul class="outline__list">
					{#each detail.branches as item (item.id)}
						<li>
							<button
								class="outline__item"
								type="button"
								aria-current={item.id === branch?.id ? 'true' : undefined}
								onclick={() => {
									closeOutlineOnNarrow();
									void selectBranch(item.id);
								}}
							>
								<span>{pathLabel(item)} · {plural(messageCount(item), 'message')}</span>
								<span class="outline__secondary">
									Ends: {outlineText(eventsById.get(item.leaf_event_id)!)}
								</span>
							</button>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<section aria-labelledby="outline-turns">
			<h3 id="outline-turns">User turns</h3>
			{#if turns.length === 0}
				<p class="outline__empty">No user messages on this path.</p>
			{:else}
				<ol class="outline__list">
					{#each turns as event (event.id)}
						<li>
							<a
								class="outline__item"
								href={`#${encodeURIComponent(event.id)}`}
								aria-current={event.id === currentEventId ? 'location' : undefined}
								onclick={() => jumpTo(event.id)}
							>
								{outlineText(event)}
							</a>
						</li>
					{/each}
				</ol>
			{/if}
		</section>

		{#if capturedEvents.length > 0}
			<section aria-labelledby="outline-captured">
				<h3 id="outline-captured">Captured events</h3>
				<ul class="outline__list">
					{#each capturedEvents as event (event.id)}
						<li>
							<a
								class="outline__item"
								href={`#${encodeURIComponent(event.id)}`}
								onclick={() => jumpTo(event.id)}
							>
								{event.kind === 'compaction'
									? 'Compaction'
									: event.kind === 'configuration'
										? 'Configuration change'
										: 'Unrecognized event'}
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if continues.length > 0 || continuedIn.length > 0}
			<section aria-labelledby="outline-related">
				<h3 id="outline-related">Related sessions</h3>
				<ul class="outline__list">
					{#each continues as item, index (index)}
						<li>
							{#if item.target_conversation_id}
								<a class="outline__item" href={conversationHref(item.target_conversation_id)}>
									Continues an earlier session
								</a>
							{:else}
								<span class="outline__note">Continues a session not in the library</span>
							{/if}
						</li>
					{/each}
					{#each continuedIn as item (item.conversation_id)}
						<li>
							<a class="outline__item" href={conversationHref(item.conversation_id)}>
								Continued in a later session
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	</nav>

	<article class="transcript" aria-labelledby="conversation-title">
		<header class="transcript__header">
			<h1 id="conversation-title">{conversationLabel(summary)}</h1>
			<p class="transcript__meta">
				<span>{summary.source.display_name}</span>
				{#if summary.started_at}
					<span>Started {formatTimestamp(summary.started_at)}</span>
				{:else}
					<span>Start time not captured</span>
				{/if}
				<span>{plural(summary.message_count, 'message')}</span>
				{#if detail.branches.length > 1 && branch}
					<span>{pathLabel(branch)} of {detail.branches.length}</span>
				{/if}
			</p>
			{#if gaps.length > 0}
				<p class="transcript__capture">
					Capture: {gaps.map((gap) => `${gap.label} ${gap.state}`).join(', ')}
				</p>
			{/if}
			{#if !detail.is_latest}
				<p class="notice" role="status">
					Viewing an earlier revision captured {formatTimestamp(summary.captured_at)}.
					<a href={revisionHref(null)}>View latest</a>
				</p>
			{/if}
			{#if detail.revisions.length > 1}
				<details class="revisions">
					<summary>{plural(detail.revisions.length, 'revision')}</summary>
					<ol>
						{#each detail.revisions as item, index (item.revision)}
							<li>
								{#if item.revision === summary.revision}
									<span aria-current="true">{formatTimestamp(item.captured_at)} (shown)</span>
								{:else}
									<a href={revisionHref(index === 0 ? null : item.revision)}>
										{formatTimestamp(item.captured_at)}
									</a>
								{/if}
							</li>
						{/each}
					</ol>
				</details>
			{/if}
			{#each continues as item, index (index)}
				<p class="relation">
					{#if item.target_conversation_id}
						Continues <a href={conversationHref(item.target_conversation_id)}>an earlier session</a>
					{:else}
						Continues a session that is not in the library ({item.target_native_id})
					{/if}
				</p>
			{/each}
		</header>

		{#if visibleEvents.length === 0}
			<p class="status-panel">This conversation has no captured events.</p>
		{:else}
			<ol class="events" class:events--selecting={selecting}>
				{#each visibleEvents as event (event.id)}
					<li class="turn turn--{turnKind(event)}">
						{#if selecting}
							{@render selectToggle(event)}
						{/if}
						{#if event.kind === 'message'}
							<section
								id={event.id}
								class="event event--{event.role}"
								class:event--target={event.id === targetEventId}
								class:event--selected={selectedEvents.has(event.id)}
								data-event
								tabindex="-1"
								aria-label="{roleLabel(event.role)}{event.occurred_at
									? ` at ${formatTime(event.occurred_at)}`
									: ''}"
							>
								<header class="event__header">
									<span class="event__role">{roleLabel(event.role)}</span>
									{#if event.occurred_at}
										<time datetime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
									{/if}
								</header>
								{#if event.content.length === 0}
									<p class="block-gap">No content captured</p>
								{:else}
									{#each event.content as item (item.id)}
										{@render block(item)}
									{/each}
								{/if}
							</section>
						{:else}
							<section
								id={event.id}
								class="event event--marker"
								class:event--target={event.id === targetEventId}
								class:event--selected={selectedEvents.has(event.id)}
								data-event
								tabindex="-1"
								aria-label={event.kind === 'compaction' ? 'Compaction' : 'Captured event'}
							>
								<p class="event__marker">
									{event.kind === 'compaction'
										? 'Context compacted'
										: event.kind === 'configuration'
											? 'Configuration changed'
											: 'Unrecognized event'}
								</p>
								{#each event.content as item (item.id)}
									{@render block(item)}
								{/each}
							</section>
						{/if}
						{#if (childCounts.get(event.id) ?? 0) > 1}
							<nav class="fork" aria-label="Paths from this message">
								<span>Paths continue from here:</span>
								{#each branchesThrough(event.id) as item (item.id)}
									<button
										class="text-button"
										type="button"
										aria-pressed={item.id === branch?.id}
										onclick={() => void selectBranch(item.id, event.id)}
									>
										{pathLabel(item)}
									</button>
								{/each}
							</nav>
						{/if}
					</li>
				{/each}
			</ol>
		{/if}

		{#if continuedIn.length > 0}
			<footer class="transcript__footer">
				{#each continuedIn as item (item.conversation_id)}
					<p class="relation">
						Continued in <a href={conversationHref(item.conversation_id)}>a later session</a>
					</p>
				{/each}
			</footer>
		{/if}
	</article>
	{#if selecting}
		<EvidenceTray
			conversationId={summary.id}
			items={selectedItems}
			canAddText={highlighted !== null}
			onaddtext={addHighlightedText}
			onclear={() => selection.clear()}
		/>
	{/if}
</div>
