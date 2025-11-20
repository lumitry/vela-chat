<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import { getFolders } from '$lib/apis/folders';
	import { folders as foldersStore } from '$lib/stores';
	import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
	import Home from '$lib/components/icons/Home.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;

	let selectedFolderId: string | null = null;

	interface FolderOption {
		id: string | null;
		name: string;
		level: number;
		parent_id: string | null;
	}

	let folderOptions: FolderOption[] = [];

	const buildFolderOptions = (folders: Record<string, any>) => {
		// Convert folders object to array
		const folderList = Object.values(folders).filter((f: any) => f.id && f.name);

		// Build hierarchical folder options
		folderOptions = [
			{
				id: null,
				name: $i18n.t('Root'),
				level: 0,
				parent_id: null
			}
		];

		// Add folders in hierarchical order
		const addFolderWithChildren = (folderId: string | null, level: number) => {
			const children = folderList
				.filter((f: any) => f.parent_id === folderId)
				.sort((a: any, b: any) =>
					a.name.localeCompare(b.name, undefined, {
						numeric: true,
						sensitivity: 'base'
					})
				);

			for (const child of children) {
				folderOptions.push({
					id: child.id,
					name: child.name,
					level: level,
					parent_id: child.parent_id
				});
				addFolderWithChildren(child.id, level + 1);
			}
		};

		addFolderWithChildren(null, 1);
	};

	const loadFolders = async () => {
		// Check if folders are already in the store
		const cachedFolders = $foldersStore;
		if (Object.keys(cachedFolders).length > 0) {
			// Use cached folders
			buildFolderOptions(cachedFolders);
			return;
		}

		// If not cached, fetch from API
		loading = true;
		try {
			const folderList = await getFolders(localStorage.token);

			// Build a lookup table
			const folders: Record<string, any> = {};
			for (const folder of folderList) {
				folders[folder.id] = folder;
			}

			// Update store for future use
			foldersStore.set(folders);

			// Build options from fetched data
			buildFolderOptions(folders);
		} catch (error) {
			console.error('Error loading folders:', error);
		} finally {
			loading = false;
		}
	};

	const handleConfirm = () => {
		dispatch('confirm', { folderId: selectedFolderId });
		show = false;
	};

	const handleCancel = () => {
		show = false;
	};

	$: if (show) {
		loadFolders();
		selectedFolderId = null;
	}
</script>

<Modal bind:show size="sm">
	<div class="px-4 py-4">
		<div class="text-lg font-semibold dark:text-gray-100 mb-4">
			{$i18n.t('Move to Folder')}
		</div>

		<div class="space-y-1 max-h-[60vh] overflow-y-auto">
			{#each folderOptions as option}
				<button
					class="w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 transition {selectedFolderId ===
					option.id
						? 'bg-gray-200 dark:bg-gray-800'
						: 'hover:bg-gray-100 dark:hover:bg-gray-900'}"
					on:click={() => {
						selectedFolderId = option.id;
					}}
				>
					<div style="padding-left: {option.level * 20}px" class="flex items-center gap-2 flex-1">
						{#if option.id === null}
							<Home className="size-4 text-gray-700 dark:text-gray-300" strokeWidth="2" />
						{:else}
							<FolderOpen className="size-4 text-gray-700 dark:text-gray-300" strokeWidth="2" />
						{/if}
						<span class="text-sm text-gray-700 dark:text-gray-300">{option.name}</span>
					</div>
					{#if selectedFolderId === option.id}
						<div class="text-blue-500">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="w-5 h-5"
							>
								<path
									fill-rule="evenodd"
									d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					{/if}
				</button>
			{/each}
		</div>

		<div class="mt-5 flex justify-end gap-2">
			<button
				class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
				on:click={handleCancel}
			>
				{$i18n.t('Cancel')}
			</button>
			<button
				class="px-4 py-2 text-sm font-medium bg-gray-900 dark:bg-white text-white dark:text-black rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
				on:click={handleConfirm}
				disabled={selectedFolderId === undefined}
			>
				{$i18n.t('Move')}
			</button>
		</div>
	</div>
</Modal>
