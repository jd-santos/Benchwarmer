<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import {
		ApiClientError,
		createBundle,
		getBundle,
		getBundles,
		updateBundle
	} from '$lib/api/client';
	import type { BundleItem, BundleSummary } from '$lib/api/types';
	import { mergeItems } from '$lib/bundles/selection';
	import { bundleLabel } from '$lib/bundles/format';
	import { plural } from '$lib/conversations/format';
	import { onMount } from 'svelte';

	let {
		conversationId,
		items,
		canAddText,
		onaddtext,
		onclear
	}: {
		conversationId: string;
		items: BundleItem[];
		canAddText: boolean;
		onaddtext: () => void;
		onclear: () => void;
	} = $props();

	let bundles = $state<BundleSummary[]>([]);
	let target = $state('');
	let pending = $state(false);
	let error = $state<string[]>([]);

	onMount(() => {
		getBundles(conversationId).then(
			(response) => (bundles = response.items),
			() => (bundles = [])
		);
	});

	function messages(failure: unknown): string[] {
		if (failure instanceof ApiClientError) {
			if (failure.issues.length > 0) return failure.issues.map((issue) => issue.message);
			if (failure.status === 409) return ['That bundle changed while saving. Try again.'];
		}
		return ['The bundle could not be saved. Check that the local API is running.'];
	}

	async function save(): Promise<void> {
		if (pending || items.length === 0) return;
		pending = true;
		error = [];
		try {
			let id: string;
			if (target) {
				const current = await getBundle(target);
				const document = {
					...current.document,
					items: mergeItems(current.document.items, items)
				};
				id = (await updateBundle(target, document, current.revision)).id;
			} else {
				id = (
					await createBundle({
						objective: '',
						status: 'draft',
						items,
						rationale: null,
						missing_evidence: []
					})
				).id;
			}
			onclear();
			await goto(resolve('/bundles/[id]', { id }));
		} catch (failure) {
			error = messages(failure);
		} finally {
			pending = false;
		}
	}
</script>

<section class="evidence-tray" aria-label="Selected evidence">
	<p class="evidence-tray__count" aria-live="polite">
		{items.length === 0
			? 'Select messages or highlight text'
			: `${plural(items.length, 'item')} selected`}
	</p>
	<div class="evidence-tray__actions">
		<button
			class="text-button"
			type="button"
			disabled={!canAddText}
			onpointerdown={(event) => event.preventDefault()}
			onclick={onaddtext}
		>
			Add highlighted text
		</button>
		{#if items.length > 0}
			<button class="text-button" type="button" onclick={onclear}>Clear</button>
		{/if}
		<label class="evidence-tray__target">
			<span class="visually-hidden">Bundle</span>
			<select bind:value={target} disabled={pending}>
				<option value="">New bundle</option>
				{#each bundles as bundle (bundle.id)}
					<option value={bundle.id}>Add to: {bundleLabel(bundle.objective)}</option>
				{/each}
			</select>
		</label>
		<button
			class="button button--primary"
			type="button"
			disabled={items.length === 0 || pending}
			onclick={() => void save()}
		>
			{pending ? 'Saving…' : target ? 'Add to bundle' : 'Create bundle'}
		</button>
	</div>
	{#if error.length > 0}
		<ul class="evidence-tray__error" role="alert">
			{#each error as message, index (index)}
				<li>{message}</li>
			{/each}
		</ul>
	{/if}
</section>
