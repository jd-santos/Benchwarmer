<script lang="ts">
	import { pathSummary, type PathDescription } from '$lib/conversations/paths';

	let {
		paths,
		currentId,
		onselect
	}: {
		paths: PathDescription[];
		currentId: string | undefined;
		onselect: (id: string) => void;
	} = $props();

	let open = $state(false);
	let root = $state<HTMLElement | null>(null);
	let button = $state<HTMLButtonElement | null>(null);
	const current = $derived(paths.find((path) => path.branch.id === currentId) ?? paths[0]);

	function choose(id: string): void {
		open = false;
		button?.focus();
		onselect(id);
	}

	$effect(() => {
		if (!open) return;
		const close = (event: Event) => {
			if (event instanceof KeyboardEvent) {
				if (event.key !== 'Escape') return;
				open = false;
				button?.focus();
			} else if (root && !root.contains(event.target as Node)) {
				open = false;
			}
		};
		document.addEventListener('pointerdown', close);
		document.addEventListener('keydown', close);
		return () => {
			document.removeEventListener('pointerdown', close);
			document.removeEventListener('keydown', close);
		};
	});
</script>

<div class="path-picker" bind:this={root}>
	<button
		bind:this={button}
		class="path-picker__button"
		type="button"
		aria-expanded={open}
		aria-controls="path-picker-menu"
		onclick={() => (open = !open)}
	>
		<span class="visually-hidden">Path</span>
		<span class="path-picker__name">{current.name}</span>
		<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
			<path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.75" />
		</svg>
	</button>
	<ul id="path-picker-menu" class="path-picker__menu" aria-label="Paths" hidden={!open}>
		{#each paths as path (path.branch.id)}
			{@const selected = path.branch.id === current.branch.id}
			<li>
				<button
					class="path-option"
					type="button"
					aria-current={selected ? 'true' : undefined}
					onclick={() => choose(path.branch.id)}
				>
					<span class="path-option__name">
						{path.name}
						{#if selected}<span class="path-option__viewing">Viewing</span>{/if}
					</span>
					<span class="path-option__detail">
						{path.divergence ?? 'Follows the earliest captured reply at every branch point'}
					</span>
					<span class="path-option__detail">{pathSummary(path)}</span>
				</button>
			</li>
		{/each}
	</ul>
</div>
