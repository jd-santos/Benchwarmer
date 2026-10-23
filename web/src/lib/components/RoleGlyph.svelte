<script lang="ts">
	import type { EventRole } from '$lib/api/types';

	/** A small glyph that marks who spoke; the text label beside it stays the accessible name. */
	let { role }: { role: EventRole } = $props();
</script>

<svg
	class="role-glyph role-glyph--{role}"
	viewBox="0 0 16 16"
	width="14"
	height="14"
	aria-hidden="true"
	focusable="false"
	data-role={role}
>
	{#if role === 'user'}
		<circle cx="8" cy="5" r="3" />
		<path d="M2.5 14.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
	{:else if role === 'assistant'}
		<path d="M8 1.5 9.7 6.3 14.5 8 9.7 9.7 8 14.5 6.3 9.7 1.5 8 6.3 6.3Z" />
	{:else if role === 'tool'}
		<rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
		<path d="M4.5 6l2.5 2-2.5 2M8.5 10.5h3" />
	{:else}
		<path d="M8 1.5 13.6 4.75v6.5L8 14.5 2.4 11.25v-6.5Z" />
	{/if}
</svg>
