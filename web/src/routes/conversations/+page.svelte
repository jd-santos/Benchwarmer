<script lang="ts">
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import type { ConversationSummary, SearchHit } from '$lib/api/types';
	import {
		captureGaps,
		conversationLabel,
		formatTimestamp,
		hasMessageGap,
		highlightParts,
		plural
	} from '$lib/conversations/format';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const listHref = resolve('/conversations');

	function conversationHref(
		summary: ConversationSummary,
		hit: SearchHit | null = null
	): ResolvedPathname {
		const base = resolve('/conversations/[id]', { id: summary.id });
		const query = data.filters.q ? `?${new URLSearchParams({ q: data.filters.q })}` : '';
		const anchor = hit?.event_id ? `#${encodeURIComponent(hit.event_id)}` : '';
		return `${base}${query}${anchor}` as ResolvedPathname;
	}

	function pageHref(offset: number): ResolvedPathname {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- built per call, never stored
		const params = new URLSearchParams();
		if (data.filters.q) params.set('q', data.filters.q);
		if (data.filters.sourceId) params.set('source', data.filters.sourceId);
		if (offset > 0) params.set('offset', String(offset));
		const search = params.toString();
		return `${listHref}${search ? `?${search}` : ''}` as ResolvedPathname;
	}

	function activity(summary: ConversationSummary): string {
		return summary.last_activity_at === null
			? 'Activity time not captured'
			: formatTimestamp(summary.last_activity_at);
	}

	function hitLabel(hit: SearchHit): string {
		const labels: Record<string, string> = {
			title: 'Title',
			text: 'Message',
			reasoning: 'Reasoning',
			tool_call: 'Tool call',
			tool_result: 'Tool output'
		};
		return labels[hit.field] ?? hit.field;
	}
</script>

<svelte:head>
	<title>Conversations · Benchwarmer</title>
	<meta name="description" content="Browse and search imported conversations." />
</svelte:head>

<div class="conversations-page">
	<header class="conversations-page__header">
		<h1>Conversations</h1>
	</header>

	<form class="conversation-search" method="GET" action={listHref} role="search">
		<div class="conversation-search__field">
			<label for="conversation-query">Search text</label>
			<input
				id="conversation-query"
				name="q"
				type="search"
				value={data.filters.q}
				autocomplete="off"
				maxlength="500"
			/>
		</div>
		{#await data.sources then sources}
			{#if sources !== null && sources.items.length > 1}
				<div class="conversation-search__field">
					<label for="conversation-source">Source</label>
					<select id="conversation-source" name="source" value={data.filters.sourceId}>
						<option value="">All sources</option>
						{#each sources.items as source (source.id)}
							<option value={source.id}>{source.display_name}</option>
						{/each}
					</select>
				</div>
			{/if}
		{/await}
		<button class="button button--primary" type="submit">Search</button>
		{#if data.filters.q || data.filters.sourceId}
			<a class="text-link" href={listHref}>Clear</a>
		{/if}
	</form>

	{#await data.conversations}
		<section class="status-panel status-panel--loading" aria-live="polite" aria-busy="true">
			<h2>Loading conversations</h2>
			<p>Reading the library…</p>
		</section>
	{:then page}
		{@const filtered = data.filters.q !== '' || data.filters.sourceId !== ''}
		{#if page.total === 0}
			<section class="status-panel" aria-labelledby="no-conversations-heading">
				{#if filtered}
					<h2 id="no-conversations-heading">No matching conversations</h2>
					<p>
						{#if data.filters.q}Nothing in the library contains “{data.filters.q}”.{:else}This
							source has no imported conversations.{/if}
					</p>
				{:else}
					<h2 id="no-conversations-heading">No conversations imported</h2>
					<p>Import a source to start browsing.</p>
				{/if}
			</section>
		{:else}
			<p class="result-count" aria-live="polite">
				{#if data.filters.q}
					{plural(page.total, 'conversation')}
					{page.total === 1 ? 'matches' : 'match'} “{data.filters.q}”
				{:else}
					{plural(page.total, 'conversation')}
				{/if}
			</p>

			<ol class="conversation-list">
				{#each page.items as summary (summary.id)}
					{@const gaps = captureGaps(summary.coverage)}
					<li class="conversation-row">
						<a class="conversation-row__title" href={conversationHref(summary)}>
							{conversationLabel(summary)}
						</a>
						<p class="conversation-row__meta">
							<span>{summary.source.display_name}</span>
							<span>{activity(summary)}</span>
							<span>{plural(summary.message_count, 'message')}</span>
							{#if summary.branch_count > 1}
								<span>{plural(summary.branch_count, 'branch', 'branches')}</span>
							{/if}
							{#if summary.relationship_counts.continuation}
								<span>Continues another session</span>
							{/if}
							{#if hasMessageGap(summary.coverage)}
								<span class="capture-flag">
									Messages {summary.coverage.messages}
								</span>
							{/if}
						</p>
						{#if gaps.length > 0 && !hasMessageGap(summary.coverage)}
							<p class="conversation-row__capture">
								Capture: {gaps.map((gap) => `${gap.label} ${gap.state}`).join(', ')}
							</p>
						{/if}
						{#if summary.matches.length > 0}
							<ul class="search-hits" aria-label="Matches in {conversationLabel(summary)}">
								{#each summary.matches as hit, index (index)}
									<li>
										<span class="search-hits__field">{hitLabel(hit)}</span>
										<a href={conversationHref(summary, hit)}>
											{#each highlightParts(hit.snippet, data.filters.q) as part, partIndex (partIndex)}
												{#if part.match}<mark>{part.text}</mark>{:else}{part.text}{/if}
											{/each}
										</a>
									</li>
								{/each}
							</ul>
							{#if summary.match_count > summary.matches.length}
								<p class="search-hits__more">
									{plural(
										summary.match_count - summary.matches.length,
										'more match',
										'more matches'
									)}
									in this conversation
								</p>
							{/if}
						{/if}
					</li>
				{/each}
			</ol>

			{#if page.total > page.limit}
				<nav class="pagination" aria-label="Conversation pages">
					{#if page.offset > 0}
						<a href={pageHref(Math.max(0, page.offset - page.limit))}>Previous</a>
					{/if}
					<span>
						{page.offset + 1}–{Math.min(page.offset + page.items.length, page.total)} of {page.total}
					</span>
					{#if page.offset + page.limit < page.total}
						<a href={pageHref(page.offset + page.limit)}>Next</a>
					{/if}
				</nav>
			{/if}
		{/if}
	{:catch}
		<section class="status-panel status-panel--error" role="alert">
			<h2>Conversations unavailable</h2>
			<p>
				The local API could not provide the library. Check that it is running and reload this page.
			</p>
		</section>
	{/await}
</div>
