<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { Pathname } from '$app/types';
	import { onMount } from 'svelte';

	let { currentPath }: { currentPath: string } = $props();

	const narrowNavigationQuery = '(max-width: 47.999rem)';
	// UI-002 intentionally links this accepted destination before its page file exists.
	const sourcesHref = resolve('/sources' as Pathname);

	function navigationQuery(): MediaQueryList | undefined {
		if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
		return window.matchMedia(narrowNavigationQuery);
	}

	let isNarrow = $state(navigationQuery()?.matches ?? false);
	let navigationOpen = $state(false);

	afterNavigate(() => {
		navigationOpen = false;
	});

	function isCurrent(href: string) {
		return currentPath === href || (href !== '/' && currentPath.startsWith(`${href}/`));
	}

	onMount(() => {
		const query = navigationQuery();
		if (!query) return;

		const updateNavigationMode = (event: MediaQueryListEvent) => {
			isNarrow = event.matches;
			if (!event.matches) navigationOpen = false;
		};

		isNarrow = query.matches;
		query.addEventListener('change', updateNavigationMode);

		return () => query.removeEventListener('change', updateNavigationMode);
	});
</script>

<header class="app-header">
	<div class="app-header__inner">
		<a class="app-brand" href={resolve('/')}>Benchwarmer</a>

		<nav class="app-navigation" aria-label="Primary">
			<button
				class="app-navigation__toggle"
				type="button"
				aria-label="Navigation"
				aria-controls="primary-navigation"
				aria-expanded={navigationOpen}
				hidden={!isNarrow}
				onclick={() => (navigationOpen = !navigationOpen)}
			>
				Menu
			</button>

			<ul
				id="primary-navigation"
				class="app-navigation__links"
				data-navigation-links
				hidden={isNarrow && !navigationOpen}
			>
				<li>
					<a href={resolve('/')} aria-current={isCurrent('/') ? 'page' : undefined}>Overview</a>
				</li>
				<li>
					<a href={sourcesHref} aria-current={isCurrent('/sources') ? 'page' : undefined}>Sources</a
					>
				</li>
			</ul>
		</nav>
	</div>
</header>
