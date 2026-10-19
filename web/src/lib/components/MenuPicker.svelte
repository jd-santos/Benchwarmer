<script lang="ts">
	import type { ResolvedPathname } from '$app/types';

	export interface MenuOption {
		id: string;
		title: string;
		details: string[];
		/** Navigate instead of calling onselect. */
		href?: ResolvedPathname;
	}

	let {
		label,
		note,
		options,
		currentId,
		compact = false,
		onselect
	}: {
		/** Accessible name prefix, such as "Path"; never shown. */
		label: string;
		/** One line at the top of the menu saying what the options are. */
		note: string;
		options: MenuOption[];
		currentId: string | undefined;
		compact?: boolean;
		onselect?: (id: string) => void;
	} = $props();

	let open = $state(false);
	let root = $state<HTMLElement | null>(null);
	let button = $state<HTMLButtonElement | null>(null);
	const menuId = $derived(`menu-${label.toLowerCase().replaceAll(/\W+/g, '-')}`);
	const current = $derived(options.find((option) => option.id === currentId) ?? options[0]);

	function choose(id: string): void {
		open = false;
		button?.focus();
		onselect?.(id);
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

<div class="menu-picker" class:menu-picker--compact={compact} bind:this={root}>
	<button
		bind:this={button}
		class="menu-picker__button"
		type="button"
		aria-expanded={open}
		aria-controls={menuId}
		onclick={() => (open = !open)}
	>
		<span class="visually-hidden">{label}</span>
		<span class="menu-picker__current">{current.title}</span>
		<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
			<path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.75" />
		</svg>
	</button>
	<div id={menuId} class="menu-picker__menu" hidden={!open}>
		<p class="menu-picker__note">{note}</p>
		<ul aria-label={label === 'Path' ? 'Paths' : `${label}s`}>
			{#each options as option (option.id)}
				{@const selected = option.id === current.id}
				<li>
					{#if option.href && !selected}
						<a class="menu-option" href={option.href} onclick={() => (open = false)}>
							<span class="menu-option__title">{option.title}</span>
							{#each option.details as detail, index (index)}
								<span class="menu-option__detail">{detail}</span>
							{/each}
						</a>
					{:else}
						<button
							class="menu-option"
							type="button"
							aria-current={selected ? 'true' : undefined}
							onclick={() => choose(option.id)}
						>
							<span class="menu-option__title">
								{option.title}
								{#if selected}<span class="menu-option__viewing">Viewing</span>{/if}
							</span>
							{#each option.details as detail, index (index)}
								<span class="menu-option__detail">{detail}</span>
							{/each}
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	</div>
</div>
