<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { folders as foldersStore, chats, pinnedChats, currentChatPage } from '$lib/stores';
	import { getFolders } from '$lib/apis/folders';
	import {
		getChatList,
		getPinnedChatList,
		getChatMetaById,
		updateChatFolderIdById
	} from '$lib/apis/chats';

	export let chatId: string;

	const dispatch = createEventDispatcher();

	let folderItems: Array<{ id: string; name: string }> = [];
	let selectedFolder: string | null = null;
	let loading = true;
	let saving = false;

	onMount(async () => {
		await ensureFolders();
		await fetchCurrentFolder();
		loading = false;
	});

	async function ensureFolders() {
		let current = get(foldersStore);
		if (!current || Object.keys(current).length === 0) {
			const fetched = await getFolders(localStorage.token);
			foldersStore.set(fetched ?? {});
			current = fetched ?? {};
		}

		folderItems = Object.values(current ?? {}).map((folder: any) => ({
			id: folder.id,
			name: folder.name
		}));
	}

	async function fetchCurrentFolder() {
		try {
			const meta = await getChatMetaById(localStorage.token, chatId);
			selectedFolder = meta?.folder_id ?? null;
		} catch (error) {
			console.error('Failed to fetch chat metadata', error);
			selectedFolder = null;
		}
	}

	async function refreshChats() {
		currentChatPage.set(1);
		const updatedChats = await getChatList(localStorage.token, get(currentChatPage));
		chats.set(updatedChats);
		pinnedChats.set(await getPinnedChatList(localStorage.token));
	}

	async function handleSubmit() {
		saving = true;
		try {
			await updateChatFolderIdById(localStorage.token, chatId, selectedFolder || null);
			await refreshChats();
			toast.success('Chat updated.');
			dispatch('close');
		} catch (error) {
			console.error(error);
			toast.error('Failed to move chat.');
		} finally {
			saving = false;
		}
	}
</script>

{#if loading}
	<div class="px-4 py-6 text-sm text-gray-500 dark:text-gray-400">Loading folders…</div>
{:else}
	<form class="px-4 py-6 space-y-4" on:submit|preventDefault={handleSubmit}>
		<div class="space-y-2">
			<label class="text-sm font-medium text-gray-700 dark:text-gray-300">
				Select destination folder
			</label>

			<div class="space-y-2 max-h-60 overflow-y-auto pr-2">
				<label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
					<input
						type="radio"
						name="folder"
						value=""
						checked={selectedFolder === null}
						on:change={() => (selectedFolder = null)}
					/>
					<span>No folder</span>
				</label>

				{#each folderItems as folder}
					<label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
						<input
							type="radio"
							name="folder"
							value={folder.id}
							checked={selectedFolder === folder.id}
							on:change={() => (selectedFolder = folder.id)}
						/>
						<span>{folder.name}</span>
					</label>
				{/each}
			</div>
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
				{saving ? 'Saving…' : 'Move'}
			</button>
		</div>
	</form>
{/if}

