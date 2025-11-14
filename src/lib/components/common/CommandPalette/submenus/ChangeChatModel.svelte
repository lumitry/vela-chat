<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { models as modelsStore, chats, pinnedChats, currentChatPage, chatCache } from '$lib/stores';
	import { getChatById, getChatList, getPinnedChatList, updateChatById } from '$lib/apis/chats';

	export let chatId: string;

	const dispatch = createEventDispatcher();

	let availableModels: Array<{ id: string; name: string }> = [];
	let selectedModelId: string = '';
	let loading = true;
	let saving = false;

	onMount(async () => {
		await loadModels();
		await loadCurrentModel();
		loading = false;
	});

	async function loadModels() {
		const current = get(modelsStore) ?? [];
		availableModels = current.map((model: any) => ({
			id: model.id,
			name: model.name ?? model.id
		}));
	}

	async function loadCurrentModel() {
		try {
			const chat = await getChatById(localStorage.token, chatId);
			selectedModelId = chat?.chat?.models?.[0] ?? availableModels[0]?.id ?? '';
		} catch (error) {
			console.error(error);
			selectedModelId = availableModels[0]?.id ?? '';
		}
	}

	async function refreshChats() {
		currentChatPage.set(1);
		const updatedChats = await getChatList(localStorage.token, get(currentChatPage));
		chats.set(updatedChats);
		pinnedChats.set(await getPinnedChatList(localStorage.token));
	}

	async function handleSubmit() {
		if (!selectedModelId) {
			toast.error('Select a model first.');
			return;
		}

		saving = true;

		try {
			await updateChatById(localStorage.token, chatId, { models: [selectedModelId] });
			chatCache.update((cache) => {
				cache.delete(chatId);
				return cache;
			});
			await refreshChats();
			toast.success('Model updated.');
			dispatch('close');
		} catch (error) {
			console.error(error);
			toast.error('Failed to update model.');
		} finally {
			saving = false;
		}
	}
</script>

{#if loading}
	<div class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">Loading models…</div>
{:else}
	<form class="px-4 py-6 space-y-4" on:submit|preventDefault={handleSubmit}>
		<div class="space-y-2">
			<label class="text-sm font-medium text-gray-700 dark:text-gray-300">Select model</label>
			<select
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-850 px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600"
				bind:value={selectedModelId}
			>
				{#each availableModels as model}
					<option value={model.id}>{model.name}</option>
				{/each}
			</select>
		</div>

		<div class="flex justify-end gap-2">
			<button
				type="button"
				class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
				on:click={() => dispatch('close')}
			>
				Cancel
			</button>
			<button
				type="submit"
				class="px-3 py-1.5 text-sm font-medium rounded-lg bg-black text-white dark:bg-white dark:text-black hover:bg-gray-900 dark:hover:bg-gray-100 disabled:opacity-50"
				disabled={saving}
			>
				{saving ? 'Saving…' : 'Change'}
			</button>
		</div>
	</form>
{/if}

