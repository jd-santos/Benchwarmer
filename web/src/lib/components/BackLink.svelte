<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { cameFrom } from '$lib/navigation';

	let { href, label }: { href: ResolvedPathname; label: string } = $props();

	// Behave like the browser's back button when it would return to the same
	// list, so its filters and scroll position come back; otherwise navigate.
	function goBack(event: MouseEvent): void {
		if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
		if (!cameFrom(href)) return;
		event.preventDefault();
		history.back();
	}
</script>

<a class="back-link" {href} onclick={goBack}>
	<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
		<path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.75" />
	</svg>
	{label}
</a>
