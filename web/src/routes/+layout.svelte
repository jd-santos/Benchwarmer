<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import AppNavigation from '$lib/components/AppNavigation.svelte';
	import { recordNavigation } from '$lib/navigation';
	import '$lib/styles/app.css';

	let { children } = $props();

	afterNavigate(({ from, to }) => {
		// Hash and query changes within one page keep the page's origin.
		const previous = from?.url ?? null;
		if (previous && previous.pathname === to?.url?.pathname) return;
		recordNavigation(previous);
	});
</script>

<a class="skip-link" href="#main-content">Skip to content</a>

<div class="app-shell">
	<AppNavigation currentPath={page.url.pathname} />

	<main id="main-content" class="app-main" tabindex="-1">
		{@render children()}
	</main>
</div>
