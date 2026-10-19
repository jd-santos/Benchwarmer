<script lang="ts">
	import { page } from '$app/state';
	import AppNavigation from '$lib/components/AppNavigation.svelte';
	import '$lib/styles/app.css';

	let { children } = $props();
</script>

<a class="skip-link" href="#main-content">Skip to content</a>

<div class="app-shell">
	<AppNavigation currentPath={page.url.pathname} />

	<main id="main-content" class="app-main" tabindex="-1">
		{@render children()}
	</main>
</div>
