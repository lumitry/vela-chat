<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import { knowledge as knowledgeStore } from '$lib/stores';
	import { getKnowledgeBases } from '$lib/apis/knowledge';

	export let query: string = '';

	const dispatch = createEventDispatcher();

	let knowledgeBases: Array<{ id: string; name: string; description?: string }> = [];
	let filter = '';
	let loading = true;

	onMount(async () => {
		let current = get(knowledgeStore);
		if (!current || current.length === 0) {
			try {
				const fetched = await getKnowledgeBases(localStorage.token);
				knowledgeStore.set(fetched ?? []);
				current = fetched ?? [];
			} catch (error) {
				console.error(error);
				toast.error('Failed to load knowledge bases.');
				current = [];
			}
		}

		knowledgeBases = (current ?? []).map((kb: any) => ({
			id: kb.id,
			name: kb.name,
			description: kb.description
		}));
		loading = false;
	});

	$: filteredList = knowledgeBases.filter((kb) => {
		if (!filter.trim()) return true;
		const text = `${kb.name} ${kb.description ?? ''}`.toLowerCase();
		return text.includes(filter.trim().toLowerCase());
	});

	async function startChatWithKnowledgeBase(kb: { id: string; name: string }) {
		const params = new URLSearchParams();
		if (query) params.set('q', query);
		params.set('knowledge-base', kb.id);

		sessionStorage.setItem(
			'commandPaletteKnowledgeBase',
			JSON.stringify({ id: kb.id, name: kb.name })
		);

		await goto(`/?${params.toString()}`);
		toast.success(`New chat started with "${kb.name}" knowledge base.`);
		dispatch('close');
	}
</script>

{#if loading}
	<div class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">Loading knowledge bases…</div>
{:else}
	<div class="px-4 py-6 space-y-4">
		<div class="space-y-2">
			<label class="text-sm font-medium text-gray-700 dark:text-gray-300">
				Select a knowledge base
			</label>
			<input
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-850 px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600"
				placeholder="Search knowledge bases..."
				bind:value={filter}
			/>
		</div>

		{#if filteredList.length === 0}
			<div class="text-sm text-gray-500 dark:text-gray-400">
				No knowledge bases found. You can create one from the workspace.
			</div>
		{:else}
			<div class="space-y-2 max-h-60 overflow-y-auto pr-2">
				{#each filteredList as kb}
					<button
						type="button"
						class="w-full text-left px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-850"
						on:click={() => startChatWithKnowledgeBase(kb)}
					>
						<div class="text-sm font-medium text-gray-800 dark:text-gray-100">{kb.name}</div>
						{#if kb.description}
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">{kb.description}</div>
						{/if}
					</button>
				{/each}
			</div>
		{/if}

		<div class="flex justify-end">
			<button
				type="button"
				class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
				on:click={() => dispatch('close')}
			>
				Close
			</button>
		</div>
	</div>
{/if}
