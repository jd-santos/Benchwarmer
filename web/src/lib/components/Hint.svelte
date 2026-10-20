<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		explanation,
		tone = 'neutral',
		children
	}: {
		explanation: string;
		tone?: 'neutral' | 'warn';
		children: Snippet;
	} = $props();

	const id = $props.id();
	let pinned = $state(false);
</script>

<!-- A label whose explanation shows on hover and focus, or stays open after a tap. -->
<span class="hint" class:hint--pinned={pinned}>
	<button
		class="tag tag--{tone} hint__label"
		type="button"
		aria-describedby="{id}-tip"
		aria-expanded={pinned}
		onclick={() => (pinned = !pinned)}
		onblur={() => (pinned = false)}
	>
		{@render children()}
	</button>
	<span id="{id}-tip" role="tooltip" class="tooltip">{explanation}</span>
</span>
