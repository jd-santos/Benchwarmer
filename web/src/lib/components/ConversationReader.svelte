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
	import Hint from '$lib/components/Hint.svelte';
	import MenuPicker from '$lib/components/MenuPicker.svelte';
	import { describePaths, pathOptions } from '$lib/conversations/paths';
	import {
		outlineEntries as buildOutline,
		segmentText,
		turnOf,
		type Heading
	} from '$lib/conversations/structure';
	import {
		captureGaps,
		formatDate,
		gapLabel,
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
	const paths = $derived(describePaths(detail.branches, eventsById));
	const currentPath = $derived(paths.find((path) => path.branch.id === branch?.id));
	const versionOptions = $derived(
		detail.revisions.map((item, index) => ({
			id: item.revision,
			title: `Imported ${formatTimestamp(item.captured_at)}`,
			details: index === 0 ? ['Latest version'] : [],
			href: revisionHref(index === 0 ? null : item.revision)
		}))
	);
	const showTray = $derived(selectedItems.length > 0 || highlighted !== null);
	// The user turn the reader is in: the current event's own turn on this path.
	const currentTurnId = $derived.by(() => {
		if (currentEventId === null) return null;
		let turn: string | null = null;
		for (const event of visibleEvents) {
			if (event.kind === 'message' && event.role === 'user') turn = event.id;
			if (event.id === currentEventId) return turn;
		}
		return null;
	});
	// Contents: user turns (with the headings of their replies) and captured
	// markers, in conversation order.
	const outlineEntries = $derived(buildOutline(visibleEvents));
	const turnByEvent = $derived(turnOf(visibleEvents));
	let currentHeading = $state<{ id: string; eventId: string } | null>(null);
	let targetHeading = $state<{ id: string; eventId: string } | null>(null);
	const currentHeadingId = $derived(
		currentHeading && turnByEvent.get(currentHeading.eventId) === currentTurnId
			? currentHeading.id
			: null
	);
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

	function clearSelection(): void {
		selection.clear();
		highlighted = null;
		window.getSelection()?.removeAllRanges();
	}

	$effect(() => {
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

	function pathLabel(item: Branch): string {
		return paths.find((path) => path.branch.id === item.id)?.name ?? 'Path';
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

	/** Switch paths. The scroll position only moves when an anchor is given. */
	async function selectBranch(id: string, anchor: string | null = null): Promise<void> {
		if (id === branch?.id) {
			if (anchor) await scrollToEvent(anchor);
			return;
		}
		branchId = id;
		rememberBranch(id);
		if (anchor) await scrollToEvent(anchor);
	}

	function closeOutlineOnNarrow(): void {
		if (isNarrow()) outlineOpen = false;
	}

	function jumpToHeading(heading: Heading): void {
		closeOutlineOnNarrow();
		targetEventId = heading.eventId;
		currentEventId = heading.eventId;
		currentHeading = { id: heading.id, eventId: heading.eventId };
		targetHeading = currentHeading;
	}

	function jumpTo(eventId: string): void {
		closeOutlineOnNarrow();
		targetEventId = eventId;
		currentEventId = eventId;
		currentHeading = null;
		targetHeading = null;
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
	// The current event is the last one whose top has passed the reading line,
	// so a jump that scrolls a message to the top makes that message current.
	$effect(() => {
		const ids = visibleEvents.map((event) => event.id);
		const activeBranch = branch?.id;
		if (activeBranch === undefined) return;
		let frame = 0;
		const update = () => {
			frame = 0;
			// Just below where a jumped-to event lands (scroll-margin 5rem), so the
			// event you jumped to is current rather than the one after it.
			const line = 112;
			let current: string | null = null;
			for (const id of ids) {
				const element = document.getElementById(id);
				if (!element) continue;
				if (element.getBoundingClientRect().top > line) break;
				current = id;
			}
			// The last messages can never reach the reading line; at the end of the
			// page, prefer a visible jump target, then the last visible event.
			const atEnd =
				window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
			if (atEnd) {
				const visible = ids.filter((id) => {
					const top = document.getElementById(id)?.getBoundingClientRect().top;
					return top !== undefined && top < window.innerHeight;
				});
				current =
					targetEventId !== null && visible.includes(targetEventId)
						? targetEventId
						: (visible.at(-1) ?? current);
			}
			current ??= ids[0] ?? null;
			let heading: { id: string; eventId: string } | null = null;
			for (const element of document.querySelectorAll<HTMLElement>('.block-heading[id]')) {
				if (element.getBoundingClientRect().top > line) break;
				const owner = element.closest<HTMLElement>('[data-event]')?.id;
				if (owner) heading = { id: element.id, eventId: owner };
			}
			// At the end of the page the last headings never reach the line either.
			if (atEnd && targetHeading) {
				const top = document.getElementById(targetHeading.id)?.getBoundingClientRect().top;
				if (top !== undefined && top < window.innerHeight) heading = targetHeading;
			}
			if (heading?.id !== currentHeading?.id) currentHeading = heading;
			if (current === null || current === currentEventId) return;
			currentEventId = current;
			positions.set(activeBranch, current);
			writeStorage(positionsKey, JSON.stringify(Object.fromEntries(positions)));
		};
		const schedule = () => {
			if (frame === 0) frame = requestAnimationFrame(update);
		};
		schedule();
		window.addEventListener('scroll', schedule, { passive: true });
		window.addEventListener('resize', schedule);
		return () => {
			if (frame !== 0) cancelAnimationFrame(frame);
			window.removeEventListener('scroll', schedule);
			window.removeEventListener('resize', schedule);
		};
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

	/** A short name for a non-message event, specific when the source said what changed. */
	function markerLabel(event: ConversationEvent): string {
		const native = event.extensions?.pi_entry_type;
		const specific: Record<string, string> = {
			model_change: 'model changed',
			thinking_level_change: 'thinking level changed',
			session_info: 'session info',
			label: 'label',
			branch_summary: 'branch summary'
		};
		if (typeof native === 'string' && specific[native]) return specific[native];
		if (event.kind === 'compaction') return 'compaction';
		if (event.kind === 'configuration') return 'configuration changed';
		return 'unrecognized event';
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

{#snippet markerIcon(event: ConversationEvent)}
	<svg
		class="marker-icon"
		viewBox="0 0 16 16"
		width="14"
		height="14"
		aria-hidden="true"
		focusable="false"
	>
		{#if event.kind === 'compaction'}
			<path
				d="M8 1.5v4m0 0L6 3.5m2 2 2-2M8 14.5v-4m0 0-2 2m2-2 2 2M2.5 8h11"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		{:else if event.kind === 'configuration'}
			<path
				d="M2 4.5h12M2 8h12M2 11.5h12"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
			/>
			<circle cx="5.5" cy="4.5" r="1.6" fill="currentColor" />
			<circle cx="10.5" cy="8" r="1.6" fill="currentColor" />
			<circle cx="7" cy="11.5" r="1.6" fill="currentColor" />
		{:else}
			<circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5" />
			<path
				d="M6.2 6.3a1.8 1.8 0 1 1 2.6 1.6c-.6.3-.8.6-.8 1.3"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
			/>
			<circle cx="8" cy="11.6" r=".9" fill="currentColor" />
		{/if}
	</svg>
{/snippet}

{#snippet contentsToggle()}
	<button
		class="icon-button contents-toggle"
		type="button"
		aria-label={outlineOpen ? 'Hide contents' : 'Show contents'}
		aria-expanded={outlineOpen}
		aria-controls="conversation-outline"
		title={outlineOpen ? 'Hide contents' : 'Show contents'}
		onclick={() => setOutline(!outlineOpen)}
	>
		<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
			<circle cx="4" cy="5" r="1.4" fill="currentColor" />
			<circle cx="4" cy="10" r="1.4" fill="currentColor" />
			<circle cx="4" cy="15" r="1.4" fill="currentColor" />
			<path
				d="M8 5h9M8 10h9M8 15h9"
				fill="none"
				stroke="currentColor"
				stroke-width="1.75"
				stroke-linecap="round"
			/>
		</svg>
	</button>
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
			<div class="block-text" data-block-id={item.id}>
				{#each segmentText(item.text, item.id) as segment, index (index)}
					{#if segment.kind === 'heading'}
						<svelte:element
							this={segment.level <= 2 ? 'h3' : 'h4'}
							id={segment.id}
							class="block-heading block-heading--{Math.min(segment.level, 3)}"
							><span class="md-mark">{segment.marks}</span>{@render text(
								segment.text
							)}{segment.tail}</svelte:element
						>
					{:else}
						<span class="block-run">{@render text(segment.text)}</span>
					{/if}
				{/each}
			</div>
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
	<header class="reader__header">
		<div class="reader__main">
			<h1 id="conversation-title">{conversationLabel(summary)}</h1>
			<p class="byline">
				<span class="byline__source">{summary.source.display_name}</span>
				{#if summary.started_at}
					<time datetime={summary.started_at}>{formatTimestamp(summary.started_at)}</time>
				{:else}
					<span>Start time not captured</span>
				{/if}
				<span>· {plural(currentPath?.messageCount ?? summary.message_count, 'message')}</span>
			</p>
			{#if (currentPath && currentPath.models.length > 0) || gaps.length > 0}
				<ul class="tags" aria-label="Models and capture notes">
					{#each currentPath?.models ?? [] as model (model)}
						<li class="tag tag--code">{model}</li>
					{/each}
					{#each gaps as gap (gap.label)}
						{@const hint = gapLabel(gap)}
						<li>
							<Hint explanation={hint.explanation} tone="warn">{hint.text}</Hint>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
		<div class="reader__aside">
			{#if paths.length > 1}
				<MenuPicker
					label="Path"
					note="Branches within this conversation. Each path is one way it continued."
					options={pathOptions(paths)}
					currentId={branch?.id}
					onselect={(id) => void selectBranch(id)}
				/>
			{/if}
			{#if versionOptions.length > 1}
				<MenuPicker
					label="Version"
					note="Benchwarmer stores a new version of a conversation only when it changed since the previous import. Bundles link to one specific version."
					options={versionOptions}
					currentId={summary.revision}
					buttonLabel="Imported {formatDate(summary.captured_at)} · {plural(
						versionOptions.length,
						'version'
					)}"
					compact
				/>
			{:else}
				<span class="reader__imported">Imported {formatDate(summary.captured_at)}</span>
			{/if}
		</div>
		{#if !detail.is_latest}
			<p class="notice" role="status">
				Viewing the version imported {formatTimestamp(summary.captured_at)}; the conversation
				changed in a later import.
				<a href={revisionHref(null)}>View latest</a>
			</p>
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

	<div class="reader__rail">
		{#if !outlineOpen}
			{@render contentsToggle()}
		{/if}
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
			{@render contentsToggle()}
		</div>

		<section aria-labelledby="outline-turns">
			<h3 id="outline-turns" class="visually-hidden">Turns and captured events</h3>
			{#if outlineEntries.length === 0}
				<p class="outline__empty">No user messages on this path.</p>
			{:else}
				<ol class="outline__list">
					{#each outlineEntries as entry (entry.event.id)}
						<li>
							{#if entry.kind === 'turn'}
								<a
									class="outline__item"
									href={`#${encodeURIComponent(entry.event.id)}`}
									aria-current={entry.event.id === currentTurnId ? 'location' : undefined}
									onclick={() => jumpTo(entry.event.id)}
								>
									{outlineText(entry.event)}
								</a>
								{#if entry.headings.length > 0}
									<ol class="outline__children">
										{#each entry.headings as heading (heading.id)}
											<li>
												<a
													class="outline__item outline__item--child"
													class:outline__item--deep={heading.level >= 3}
													href={`#${encodeURIComponent(heading.id)}`}
													aria-current={heading.id === currentHeadingId ? 'location' : undefined}
													onclick={() => jumpToHeading(heading)}
												>
													{heading.label}
												</a>
											</li>
										{/each}
									</ol>
								{/if}
							{:else}
								<a
									class="outline__item outline__item--marker"
									href={`#${encodeURIComponent(entry.event.id)}`}
									onclick={() => jumpTo(entry.event.id)}
								>
									{@render markerIcon(entry.event)}
									{markerLabel(entry.event)}
								</a>
							{/if}
						</li>
					{/each}
				</ol>
			{/if}
		</section>

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
		{#if currentPath && paths.length > 1}
			<p class="transcript__path">
				{#if currentPath.divergence}
					<strong>{currentPath.name}</strong>
					<span>{currentPath.divergence}</span>
				{:else}
					<strong>Original conversation</strong>
					<span>Follows the earliest captured reply at every branch point</span>
				{/if}
			</p>
		{/if}
		{#if visibleEvents.length === 0}
			<p class="status-panel">This conversation has no captured events.</p>
		{:else}
			<ol class="events">
				{#each visibleEvents as event (event.id)}
					<li
						class="turn turn--{turnKind(event)}"
						class:turn--selected={selectedEvents.has(event.id)}
					>
						{@render selectToggle(event)}
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
									{#if currentPath?.divergence && event.id === currentPath.branch.divergent_event_id}
										<span class="event__tag">Path diverges here</span>
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
									{@render markerIcon(event)}
									<span>{markerLabel(event)}</span>
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
	{#if showTray}
		<EvidenceTray
			conversationId={summary.id}
			items={selectedItems}
			canAddText={highlighted !== null}
			onaddtext={addHighlightedText}
			onclear={clearSelection}
		/>
	{/if}
</div>
