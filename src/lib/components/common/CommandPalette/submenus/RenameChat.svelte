<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { updateChatById, getChatList, getPinnedChatList } from '$lib/apis/chats';
	import {
		chats,
		pinnedChats,
		chatTitle as chatTitleStore,
		chatId as activeChatIdStore,
		currentChatPage,
		chatCache
	} from '$lib/stores';

	export let chatId: string;
	export let currentTitle: string = '';

	const dispatch = createEventDispatcher();

	let title = currentTitle ?? '';
	let saving = false;

	const isActiveChat = () => get(activeChatIdStore) === chatId;

	async function refreshChatLists() {
		currentChatPage.set(1);
		const updatedChats = await getChatList(localStorage.token, get(currentChatPage));
		chats.set(updatedChats);
		pinnedChats.set(await getPinnedChatList(localStorage.token));
	}

	async function handleSubmit() {
		const trimmed = title.trim();
		if (!trimmed) {
			toast.error('Title cannot be empty.');
			return;
		}

		saving = true;

		try {
			await updateChatById(localStorage.token, chatId, { title: trimmed });
			chatCache.update((cache) => {
				cache.delete(chatId);
				return cache;
			});

			if (isActiveChat()) {
				chatTitleStore.set(trimmed);
			}

			await refreshChatLists();
			toast.success('Chat renamed.');
			dispatch('close');
		} catch (error) {
			console.error(error);
			toast.error('Failed to rename chat.');
		} finally {
			saving = false;
		}
	}
</script>

<form class="px-4 py-6 space-y-4" on:submit|preventDefault={handleSubmit}>
	<div class="space-y-2">
		<label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
			New title
		</label>
		<input
			class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-850 px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600"
			bind:value={title}
			placeholder="Enter chat title"
		/>
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
			{saving ? 'Saving…' : 'Rename'}
		</button>
	</div>
</form>

