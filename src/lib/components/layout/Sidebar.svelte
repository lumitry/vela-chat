<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { goto } from '$app/navigation';
	import {
		user,
		chats,
		settings,
		showSettings,
		chatId,
		tags,
		showSidebar,
		mobile,
		showArchivedChats,
		pinnedChats,
		scrollPaginationEnabled,
		currentChatPage,
		temporaryChatEnabled,
		channels,
		socket,
		config,
		isApp,
		chatListSortBy,
		folders as foldersStore
	} from '$lib/stores';
	import { onMount, getContext, tick, onDestroy } from 'svelte';

	const i18n = getContext('i18n');

	import {
		deleteChatById,
		getChatList,
		getAllTags,
		getChatListBySearchText,
		createNewChat,
		getPinnedChatList,
		getPinnedChatListMetadata,
		toggleChatPinnedStatusById,
		getChatPinnedStatusById,
		getChatById,
		getChatMetaById,
		updateChatFolderIdById,
		importChat
	} from '$lib/apis/chats';
	import {
		createNewFolder,
		getFolders,
		updateFolderParentIdById,
		updateFolderIsExpandedById,
		batchUpdateFolderIsExpanded
	} from '$lib/apis/folders';
	import { setBatchUpdateFunction } from '$lib/utils/folderBatch';
	import { sidebarNavigationCommand, type SidebarNavigationCommand } from '$lib/stores/sidebar';
	import { getTimeRange } from '$lib/utils';

	import ArchivedChatsModal from './Sidebar/ArchivedChatsModal.svelte';
	import UserMenu from './Sidebar/UserMenu.svelte';
	import ChatItem from './Sidebar/ChatItem.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Loader from '../common/Loader.svelte';
	import AddFilesPlaceholder from '../AddFilesPlaceholder.svelte';
	import SearchInput from './Sidebar/SearchInput.svelte';
	import Folder from '../common/Folder.svelte';
	import Plus from '../icons/Plus.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Folders from './Sidebar/Folders.svelte';
	import { getChannels, createNewChannel } from '$lib/apis/channels';
	import ChannelModal from './Sidebar/ChannelModal.svelte';
	import ChannelItem from './Sidebar/ChannelItem.svelte';
	import PencilSquare from '../icons/PencilSquare.svelte';
	import Home from '../icons/Home.svelte';

	const BREAKPOINT = 768;

	let navElement;
	let search = '';

	let shiftKey = false;

	let selectedChatId = null;
	let showDropdown = false;

	$: userImageSrc = $user?.profile_image_url ?? '';
	let showPinnedChat = true;

	let showCreateChannel = false;

	// Pagination variables
	let chatListLoading = false;
	let allChatsLoaded = false;

	let folders = {};
	let newFolderId = null;

	// Reactively sync folders from store (for updates from command palette, etc.)
	// This allows the command palette to refresh folders by updating the store
	$: if ($foldersStore && Object.keys($foldersStore).length > 0) {
		// Deep clone to ensure reactivity triggers
		folders = JSON.parse(JSON.stringify($foldersStore));
	}

	// Sorted chats list
	let sortedChats: any[] = [];

	// Sort chats based on selected sort option
	$: {
		if ($chats && Array.isArray($chats)) {
			sortedChats = [...$chats]
				.map((chat) => {
					// Recalculate time_range based on sort field
					if ($chatListSortBy === 'created') {
						return {
							...chat,
							time_range: getTimeRange(chat.created_at)
						};
					}
					return chat;
				})
				.sort((a: any, b: any) => {
					switch ($chatListSortBy) {
						case 'created':
							// Sort by created_at (newest first)
							return b.created_at - a.created_at;
						case 'title':
							// Sort alphabetically by title (A-Z)
							return a.title.localeCompare(b.title, undefined, {
								numeric: true,
								sensitivity: 'base'
							});
						case 'updated':
						default:
							// Sort by updated_at (most recently modified first) - default
							return b.updated_at - a.updated_at;
					}
				});
		} else {
			sortedChats = [];
		}
	}

	// Save sort preference to localStorage when it changes
	$: if ($chatListSortBy) {
		localStorage.setItem('chatListSortBy', $chatListSortBy);
		// Re-sort folder chats when sort preference changes
		if (folders && Object.keys(folders).length > 0) {
			for (const folderId in folders) {
				if (folders[folderId]?.items?.chats && Array.isArray(folders[folderId].items.chats)) {
					folders[folderId].items.chats.sort((a: any, b: any) => {
						switch ($chatListSortBy) {
							case 'created':
								return (b.created_at ?? 0) - (a.created_at ?? 0);
							case 'title':
								return a.title.localeCompare(b.title, undefined, {
									numeric: true,
									sensitivity: 'base'
								});
							case 'updated':
							default:
								return (b.updated_at ?? 0) - (a.updated_at ?? 0);
						}
					});
				}
			}
			// Trigger reactivity
			folders = { ...folders };
		}
	}

	const initFolders = async () => {
		const folderList = await getFolders(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return [];
		});

		folders = {};

		// First pass: Initialize all folder entries
		for (const folder of folderList) {
			// Ensure folder is added to folders with its data first
			folders[folder.id] = { ...(folders[folder.id] || {}), ...folder };

			// Sort chats within each folder based on current sort preference
			if (folders[folder.id].items?.chats && Array.isArray(folders[folder.id].items.chats)) {
				folders[folder.id].items.chats = folders[folder.id].items.chats.sort((a: any, b: any) => {
					switch ($chatListSortBy) {
						case 'created':
							return (b.created_at ?? 0) - (a.created_at ?? 0);
						case 'title':
							return a.title.localeCompare(b.title, undefined, {
								numeric: true,
								sensitivity: 'base'
							});
						case 'updated':
						default:
							return (b.updated_at ?? 0) - (a.updated_at ?? 0);
					}
				});
			}

			if (newFolderId && folder.id === newFolderId) {
				folders[folder.id].new = true;
				newFolderId = null;
			}
		}

		// Second pass: Tie child folders to their parents
		for (const folder of folderList) {
			if (folder.parent_id) {
				// Ensure the parent folder is initialized if it doesn't exist
				if (!folders[folder.parent_id]) {
					folders[folder.parent_id] = {}; // Create a placeholder if not already present
				}

				// Initialize childrenIds array if it doesn't exist and add the current folder id
				folders[folder.parent_id].childrenIds = folders[folder.parent_id].childrenIds
					? [...folders[folder.parent_id].childrenIds, folder.id]
					: [folder.id];

				// Sort the children by updated_at field
				folders[folder.parent_id].childrenIds.sort((a, b) => {
					return folders[b].updated_at - folders[a].updated_at;
				});
			}
		}

		// Update the folders store so other components can use it
		foldersStore.set(folders);
	};

	const createFolder = async (name = 'Untitled') => {
		if (name === '') {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const rootFolders = Object.values(folders).filter((folder) => folder.parent_id === null);
		if (rootFolders.find((folder) => folder.name.toLowerCase() === name.toLowerCase())) {
			// If a folder with the same name already exists, append a number to the name
			let i = 1;
			while (
				rootFolders.find((folder) => folder.name.toLowerCase() === `${name} ${i}`.toLowerCase())
			) {
				i++;
			}

			name = `${name} ${i}`;
		}

		// Add a dummy folder to the list to show the user that the folder is being created
		const tempId = uuidv4();
		folders = {
			...folders,
			tempId: {
				id: tempId,
				name: name,
				created_at: Date.now(),
				updated_at: Date.now()
			}
		};

		const res = await createNewFolder(localStorage.token, name).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			newFolderId = res.id;
			await initFolders();
		}
	};

	const handleNavigationCommand = async (command: SidebarNavigationCommand | null) => {
		try {
			if (command?.type === 'navigateToChat') {
				await navigateToChat(command.target);
			} else if (command?.type === 'navigateToFolder') {
				await navigateToFolder(command.target);
			}
		} catch (error) {
			console.error('Error handling navigation command:', error);
		}
	};

	const navigateToChat = async (chatId: string) => {
		// First get the chat details to see if it's in a folder
		try {
			const chatDetails = await getChatById(localStorage.token, chatId);
			if (chatDetails?.folder_id) {
				// If chat is in a folder, expand the folder hierarchy first
				await expandFolderHierarchy(chatDetails.folder_id);

				// Wait for DOM updates after expansion
				await tick();
				await new Promise((resolve) => setTimeout(resolve, 100));

				// Then scroll to the specific chat within the expanded folder
				await scrollToChat(chatId);
			} else {
				// Chat is not in a folder, just scroll to it in the main list
				await scrollToChat(chatId);
			}
		} catch (error) {
			console.error('Failed to navigate to chat:', error);
			// Fallback: try to scroll to chat anyway
			await scrollToChat(chatId);
		}
	};

	const navigateToFolder = async (folderId: string) => {
		// Expand the entire folder hierarchy to make the target folder visible
		await expandFolderHierarchy(folderId);

		// Wait for all DOM updates to complete
		await tick();
		await new Promise((resolve) => setTimeout(resolve, 100));

		// Scroll to the folder
		await scrollToFolder(folderId);
	};

	const expandFolderHierarchy = async (folderId: string) => {
		// Build folder hierarchy from current folders data
		const folderMap = { ...folders };

		// Find all parent folders that need to be expanded
		const foldersToExpand = [];
		let currentFolder = folderMap[folderId];

		while (currentFolder) {
			foldersToExpand.unshift(currentFolder.id);
			currentFolder = currentFolder.parent_id ? folderMap[currentFolder.parent_id] : null;
		}

		// Collect folders that need backend updates (batch them)
		const foldersToUpdate = [];
		for (const folderIdToExpand of foldersToExpand) {
			const folder = folderMap[folderIdToExpand];
			if (folder && !folder.is_expanded) {
				foldersToUpdate.push({ id: folderIdToExpand, isExpanded: true });
			}

			// Always update local state to trigger UI expansion
			folders = {
				...folders,
				[folderIdToExpand]: {
					...folders[folderIdToExpand],
					is_expanded: true,
					expansionTimestamp: Date.now() // Force UI expansion regardless of previous state
				}
			};
		}

		// Batch update all folders that need backend updates
		if (foldersToUpdate.length > 0) {
			try {
				await batchUpdateFolderIsExpanded(localStorage.token, foldersToUpdate);
			} catch (error) {
				console.error('Failed to batch update folder expanded states:', error);
				// Fallback to individual updates if batch fails
				for (const update of foldersToUpdate) {
					try {
						await updateFolderIsExpandedById(localStorage.token, update.id, update.isExpanded);
					} catch (err) {
						console.error(`Failed to update folder ${update.id}:`, err);
					}
				}
			}
		}

		// Wait for DOM to update
		await tick();
		await new Promise((resolve) => setTimeout(resolve, 50));
	};

	const scrollToFolder = async (folderId: string) => {
		// Use a retry mechanism to find the element
		const maxAttempts = 10;
		const delay = 50;

		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			const folderElement = document.querySelector(`[data-folder-id="${folderId}"]`);
			if (folderElement) {
				folderElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
				return; // Success
			}

			// Wait before trying again
			await new Promise((resolve) => setTimeout(resolve, delay));
		}

		console.warn(
			`Folder element with ID ${folderId} not found for scrolling after ${maxAttempts} attempts`
		);
	};

	const scrollToChat = async (chatId: string) => {
		// Use a retry mechanism to find the element
		const maxAttempts = 10;
		const delay = 50;

		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			const chatElement =
				document.querySelector(`[data-chat-id="${chatId}"]`) ||
				document.querySelector(`[href="/c/${chatId}"]`);
			if (chatElement) {
				chatElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
				return; // Success
			}

			// Wait before trying again
			await new Promise((resolve) => setTimeout(resolve, delay));
		}

		console.warn(
			`Chat element with ID ${chatId} not found for scrolling after ${maxAttempts} attempts`
		);
	};

	const initChannels = async () => {
		await channels.set(await getChannels(localStorage.token));
	};

	const initChatList = async () => {
		// Reset pagination variables
		tags.set(await getAllTags(localStorage.token));

		// Always refresh pinned chats to reflect pin/unpin changes
		pinnedChats.set(await getPinnedChatListMetadata(localStorage.token));

		initFolders();

		currentChatPage.set(1);
		allChatsLoaded = false;

		if (search) {
			await chats.set(
				await getChatListBySearchText(localStorage.token, search, $currentChatPage, undefined)
			);
		} else {
			await chats.set(await getChatList(localStorage.token, $currentChatPage));
		}

		// Enable pagination
		scrollPaginationEnabled.set(true);
	};

	const loadMoreChats = async () => {
		chatListLoading = true;

		currentChatPage.set($currentChatPage + 1);

		let newChatList = [];

		if (search) {
			newChatList = await getChatListBySearchText(
				localStorage.token,
				search,
				$currentChatPage,
				undefined
			);
		} else {
			newChatList = await getChatList(localStorage.token, $currentChatPage);
		}

		// once the bottom of the list has been reached (no results) there is no need to continue querying
		allChatsLoaded = newChatList.length === 0;
		await chats.set([...($chats ? $chats : []), ...newChatList]);

		chatListLoading = false;
	};

	let searchDebounceTimeout;
	let searchAbortController: AbortController | null = null;

	const searchDebounceHandler = async () => {
		console.log('search', search);
		chats.set(null);

		// Cancel any in-flight search request
		if (searchAbortController) {
			searchAbortController.abort();
			searchAbortController = null;
		}

		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}

		if (search === '') {
			await initChatList();
			return;
		} else {
			// With request cancellation, we can use a shorter debounce (50ms)
			// Old requests get cancelled, so we only process the latest one
			// This gives near-instant feel while preventing wasted requests
			searchDebounceTimeout = setTimeout(async () => {
				// Create new AbortController for this request
				searchAbortController = new AbortController();
				const currentController = searchAbortController;

				allChatsLoaded = false;
				currentChatPage.set(1);

				try {
					const results = await getChatListBySearchText(
						localStorage.token,
						search,
						1,
						currentController.signal
					);

					// Only update if this request wasn't cancelled
					if (!currentController.signal.aborted) {
						await chats.set(results);

						if ($chats.length === 0) {
							tags.set(await getAllTags(localStorage.token));
						}
					}
				} catch (err) {
					// Ignore AbortError - it's expected when cancelling old requests
					if (err.name !== 'AbortError') {
						console.error('Search error:', err);
					}
				} finally {
					// Clear controller if this was the active one
					if (searchAbortController === currentController) {
						searchAbortController = null;
					}
				}
			}, 50); // Reduced to 50ms with cancellation support
		}
	};

	const importChatHandler = async (items, pinned = false, folderId = null) => {
		console.log('importChatHandler', items, pinned, folderId);
		for (const item of items) {
			console.log(item);
			if (item.chat) {
				await importChat(localStorage.token, item.chat, item?.meta ?? {}, pinned, folderId);
			}
		}

		initChatList();
	};

	const inputFilesHandler = async (files) => {
		console.log(files);

		for (const file of files) {
			const reader = new FileReader();
			reader.onload = async (e) => {
				const content = e.target.result;

				try {
					const chatItems = JSON.parse(content);
					importChatHandler(chatItems);
				} catch {
					toast.error($i18n.t(`Invalid file format.`));
				}
			};

			reader.readAsText(file);
		}
	};

	const tagEventHandler = async (type, tagName, chatId) => {
		console.log(type, tagName, chatId);
		if (type === 'delete') {
			initChatList();
		} else if (type === 'add') {
			initChatList();
		}
	};

	let draggedOver = false;

	const onDragOver = (e) => {
		e.preventDefault();

		// Check if a file is being draggedOver.
		if (e.dataTransfer?.types?.includes('Files')) {
			draggedOver = true;
		} else {
			draggedOver = false;
		}
	};

	const onDragLeave = () => {
		draggedOver = false;
	};

	const onDrop = async (e) => {
		e.preventDefault();
		console.log(e); // Log the drop event

		// Perform file drop check and handle it accordingly
		if (e.dataTransfer?.files) {
			const inputFiles = Array.from(e.dataTransfer?.files);

			if (inputFiles && inputFiles.length > 0) {
				console.log(inputFiles); // Log the dropped files
				inputFilesHandler(inputFiles); // Handle the dropped files
			}
		}

		draggedOver = false; // Reset draggedOver status after drop
	};

	let touchstart;
	let touchend;

	function checkDirection() {
		const screenWidth = window.innerWidth;
		const swipeDistance = Math.abs(touchend.screenX - touchstart.screenX);
		if (touchstart.clientX < 40 && swipeDistance >= screenWidth / 8) {
			if (touchend.screenX < touchstart.screenX) {
				showSidebar.set(false);
			}
			if (touchend.screenX > touchstart.screenX) {
				showSidebar.set(true);
			}
		}
	}

	const onTouchStart = (e) => {
		touchstart = e.changedTouches[0];
		console.log(touchstart.clientX);
	};

	const onTouchEnd = (e) => {
		touchend = e.changedTouches[0];
		checkDirection();
	};

	const onKeyDown = (e) => {
		if (e.key === 'Shift') {
			shiftKey = true;
		}
	};

	const onKeyUp = (e) => {
		if (e.key === 'Shift') {
			shiftKey = false;
		}
	};

	const onFocus = () => {};

	const onBlur = () => {
		shiftKey = false;
		selectedChatId = null;
	};

	onMount(async () => {
		// Initialize shared folder batching service
		setBatchUpdateFunction(async (updates) => {
			try {
				await batchUpdateFolderIsExpanded(localStorage.token, updates);
			} catch (error) {
				console.error('Failed to batch update folder expanded states:', error);
				// Fallback to individual updates if batch fails
				for (const update of updates) {
					try {
						await updateFolderIsExpandedById(localStorage.token, update.id, update.isExpanded);
					} catch (err) {
						console.error(`Failed to update folder ${update.id}:`, err);
					}
				}
			}
		});

		showPinnedChat = localStorage?.showPinnedChat ? localStorage.showPinnedChat === 'true' : true;

		mobile.subscribe((value) => {
			if ($showSidebar && value) {
				showSidebar.set(false);
			}

			if ($showSidebar && !value) {
				const navElement = document.getElementsByTagName('nav')[0];
				if (navElement) {
					navElement.style['-webkit-app-region'] = 'drag';
				}
			}

			if (!$showSidebar && !value) {
				showSidebar.set(true);
			}
		});

		showSidebar.set(!$mobile ? localStorage.sidebar === 'true' : false);
		showSidebar.subscribe((value) => {
			localStorage.sidebar = value;

			// nav element is not available on the first render
			const navElement = document.getElementsByTagName('nav')[0];

			if (navElement) {
				if ($mobile) {
					if (!value) {
						navElement.style['-webkit-app-region'] = 'drag';
					} else {
						navElement.style['-webkit-app-region'] = 'no-drag';
					}
				} else {
					navElement.style['-webkit-app-region'] = 'drag';
				}
			}
		});

		// await initChannels();
		await initChatList();

		// Listen for navigation commands from other components
		sidebarNavigationCommand.subscribe(async (command) => {
			if (command) {
				await handleNavigationCommand(command);
				// Clear the command after handling
				sidebarNavigationCommand.set(null);
			}
		});

		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);

		window.addEventListener('touchstart', onTouchStart);
		window.addEventListener('touchend', onTouchEnd);

		window.addEventListener('focus', onFocus);
		window.addEventListener('blur-sm', onBlur);

		const dropZone = document.getElementById('sidebar');

		dropZone?.addEventListener('dragover', onDragOver);
		dropZone?.addEventListener('drop', onDrop);
		dropZone?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', onKeyDown);
		window.removeEventListener('keyup', onKeyUp);

		window.removeEventListener('touchstart', onTouchStart);
		window.removeEventListener('touchend', onTouchEnd);

		window.removeEventListener('focus', onFocus);
		window.removeEventListener('blur-sm', onBlur);

		const dropZone = document.getElementById('sidebar');

		dropZone?.removeEventListener('dragover', onDragOver);
		dropZone?.removeEventListener('drop', onDrop);
		dropZone?.removeEventListener('dragleave', onDragLeave);
	});
</script>

<ArchivedChatsModal
	bind:show={$showArchivedChats}
	on:change={async () => {
		await initChatList();
	}}
/>

<ChannelModal
	bind:show={showCreateChannel}
	onSubmit={async ({ name, access_control }) => {
		const res = await createNewChannel(localStorage.token, {
			name: name,
			access_control: access_control
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			$socket.emit('join-channels', { auth: { token: $user?.token } });
			await initChannels();
			showCreateChannel = false;
		}
	}}
/>

<!-- svelte-ignore a11y-no-static-element-interactions -->

{#if $showSidebar}
	<div
		class=" {$isApp
			? ' ml-[4.5rem] md:ml-0'
			: ''} fixed md:hidden z-40 top-0 right-0 left-0 bottom-0 bg-black/60 w-full min-h-screen h-screen flex justify-center overflow-hidden overscroll-contain"
		on:mousedown={() => {
			showSidebar.set(!$showSidebar);
		}}
	/>
{/if}

<div
	bind:this={navElement}
	id="sidebar"
	class="h-screen max-h-[100dvh] min-h-screen select-none {$showSidebar
		? 'md:relative w-[260px] max-w-[260px]'
		: '-translate-x-[260px] w-[0px]'} {$isApp
		? `ml-[4.5rem] md:ml-0 `
		: 'transition-width duration-200 ease-in-out'}  shrink-0 bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-200 text-sm fixed z-50 top-0 left-0 overflow-x-hidden
        "
	data-state={$showSidebar}
>
	<div
		class="py-2 my-auto flex flex-col justify-between h-screen max-h-[100dvh] w-[260px] overflow-x-hidden z-50 {$showSidebar
			? ''
			: 'invisible'}"
	>
		<div class="px-1.5 flex justify-between space-x-1 text-gray-600 dark:text-gray-400">
			<button
				class=" cursor-pointer p-[7px] flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 transition"
				on:click={() => {
					showSidebar.set(!$showSidebar);
				}}
			>
				<div class=" m-auto self-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="size-5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12"
						/>
					</svg>
				</div>
			</button>

			<a
				id="sidebar-new-chat-button"
				class="flex justify-between items-center flex-1 rounded-lg px-2 py-1 h-full text-right hover:bg-gray-100 dark:hover:bg-gray-900 transition no-drag-region"
				href="/"
				draggable="false"
				on:click={async (e) => {
					if (e.metaKey || e.ctrlKey) {
						// Open in a new tab
						e.preventDefault();
						window.open('/', '_blank');
					} else {
						// Default behavior
						selectedChatId = null;
						await goto('/');
						const newChatButton = document.getElementById('new-chat-button');
						setTimeout(() => {
							newChatButton?.click();
							if ($mobile) {
								showSidebar.set(false);
							}
						}, 0);
					}
				}}
			>
				<div class="flex items-center">
					<div class="self-center mx-1.5">
						<img
							src="/static/favicon.png"
							class=" size-5 -translate-x-1.5 rounded-full"
							alt="logo"
						/>
					</div>
					<div class=" self-center font-medium text-sm text-gray-850 dark:text-white font-primary">
						{$i18n.t('New Chat')}
					</div>
				</div>

				<div>
					<PencilSquare className=" size-5" strokeWidth="2" />
				</div>
			</a>
		</div>

		<!-- {#if $user?.role === 'admin'}
			<div class="px-1.5 flex justify-center text-gray-800 dark:text-gray-200">
				<a
					class="grow flex items-center space-x-3 rounded-lg px-2 py-[7px] hover:bg-gray-100 dark:hover:bg-gray-900 transition"
					href="/home"
					on:click={() => {
						selectedChatId = null;
						chatId.set('');

						if ($mobile) {
							showSidebar.set(false);
						}
					}}
					draggable="false"
				>
					<div class="self-center">
						<Home strokeWidth="2" className="size-[1.1rem]" />
					</div>

					<div class="flex self-center translate-y-[0.5px]">
						<div class=" self-center font-medium text-sm font-primary">{$i18n.t('Home')}</div>
					</div>
				</a>
			</div>
		{/if} -->

		{#if $user?.role === 'admin' || $user?.permissions?.workspace?.models || $user?.permissions?.workspace?.knowledge || $user?.permissions?.workspace?.prompts || $user?.permissions?.workspace?.tools}
			<div class="px-1.5 flex justify-center text-gray-800 dark:text-gray-200">
				<a
					class="grow flex items-center space-x-3 rounded-lg px-2 py-[7px] hover:bg-gray-100 dark:hover:bg-gray-900 transition"
					href="/workspace"
					on:click={() => {
						selectedChatId = null;
						chatId.set('');

						if ($mobile) {
							showSidebar.set(false);
						}
					}}
					draggable="false"
				>
					<div class="self-center">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
							class="size-[1.1rem]"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 0 0 2.25-2.25V6a2.25 2.25 0 0 0-2.25-2.25H6A2.25 2.25 0 0 0 3.75 6v2.25A2.25 2.25 0 0 0 6 10.5Zm0 9.75h2.25A2.25 2.25 0 0 0 10.5 18v-2.25a2.25 2.25 0 0 0-2.25-2.25H6a2.25 2.25 0 0 0-2.25 2.25V18A2.25 2.25 0 0 0 6 20.25Zm9.75-9.75H18a2.25 2.25 0 0 0 2.25-2.25V6A2.25 2.25 0 0 0 18 3.75h-2.25A2.25 2.25 0 0 0 13.5 6v2.25a2.25 2.25 0 0 0 2.25 2.25Z"
							/>
						</svg>
					</div>

					<div class="flex self-center translate-y-[0.5px]">
						<div class=" self-center font-medium text-sm font-primary">{$i18n.t('Workspace')}</div>
					</div>
				</a>
			</div>
		{/if}

		<div class="relative {$temporaryChatEnabled ? 'opacity-20' : ''}">
			{#if $temporaryChatEnabled}
				<div class="absolute z-40 w-full h-full flex justify-center"></div>
			{/if}

			<SearchInput
				bind:value={search}
				on:input={searchDebounceHandler}
				placeholder={$i18n.t('Search')}
				showClearButton={true}
			/>
		</div>

		<!-- Chat Sort Selector -->
		<div class="px-2 py-1 {$temporaryChatEnabled ? 'opacity-20' : ''}">
			<div class="flex items-center gap-2 text-xs ml-2">
				<span class="text-gray-500 dark:text-gray-400">{$i18n.t('Sort by')}:</span>
				<!-- We have to override browser/default styling here because otherwise it tries to center the dropdown text which looks unbalanced due to the chevron. here's the non-override version for reference: -->
				<!-- <select
					bind:value={$chatListSortBy}
					class="bg-transparent text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded px-5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-gray-400 dark:focus:ring-gray-600"
				> -->
				<select
					bind:value={$chatListSortBy}
					class="appearance-none bg-transparent text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded pl-2 pr-6 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-gray-400 dark:focus:ring-gray-600 bg-[length:12px] bg-[right_0.3rem_center] bg-no-repeat"
					style="background-image: url('data:image/svg+xml;charset=UTF-8,%3csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 20 20%27 fill=%27none%27%3e%3cpath d=%27M7 8l3 3 3-3%27 stroke=%27%239ca3af%27 stroke-width=%271.5%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27/%3e%3c/svg%3e');"
				>
					<option value="updated">{$i18n.t('Last Modified')}</option>
					<option value="created">{$i18n.t('Date Created')}</option>
					<option value="title">{$i18n.t('Title (A-Z)')}</option>
				</select>
			</div>
		</div>

		<div
			class="relative flex flex-col flex-1 overflow-y-auto overflow-x-hidden {$temporaryChatEnabled
				? 'opacity-20'
				: ''}"
		>
			{#if $config?.features?.enable_channels && ($user?.role === 'admin' || $channels.length > 0) && !search}
				<Folder
					className="px-2 mt-0.5"
					name={$i18n.t('Channels')}
					dragAndDrop={false}
					onAdd={async () => {
						if ($user?.role === 'admin') {
							await tick();

							setTimeout(() => {
								showCreateChannel = true;
							}, 0);
						}
					}}
					onAddLabel={$i18n.t('Create Channel')}
				>
					{#each $channels as channel}
						<ChannelItem
							{channel}
							onUpdate={async () => {
								await initChannels();
							}}
						/>
					{/each}
				</Folder>
			{/if}

			<Folder
				collapsible={!search}
				className="px-2 mt-0.5"
				name={$i18n.t('Chats')}
				onAdd={() => {
					createFolder();
				}}
				onAddLabel={$i18n.t('New Folder')}
				on:import={(e) => {
					importChatHandler(e.detail);
				}}
				on:drop={async (e) => {
					const { type, id, meta, item } = e.detail;

					if (type === 'chat') {
						// Fetch meta (fast, ~100ms) instead of full chat for drag-and-drop
						let chat = meta;
						if (!chat) {
							chat = await getChatMetaById(localStorage.token, id).catch((error) => {
								// Fallback to full chat if meta fails
								return getChatById(localStorage.token, id).catch((error) => {
									return null;
								});
							});
						}
						// Fallback for importing external chats
						if (!chat && item) {
							chat = await importChat(localStorage.token, item.chat, item?.meta ?? {});
						}

						if (chat) {
							console.log(chat);
							if (chat.folder_id) {
								const res = await updateChatFolderIdById(localStorage.token, chat.id, null).catch(
									(error) => {
										toast.error(`${error}`);
										return null;
									}
								);
							}

							if (chat.pinned) {
								const res = await toggleChatPinnedStatusById(localStorage.token, chat.id);
							}

							initChatList();
						}
					} else if (type === 'folder') {
						if (folders[id].parent_id === null) {
							return;
						}

						const res = await updateFolderParentIdById(localStorage.token, id, null).catch(
							(error) => {
								toast.error(`${error}`);
								return null;
							}
						);

						if (res) {
							await initFolders();
						}
					}
				}}
			>
				{#if $temporaryChatEnabled}
					<div class="absolute z-40 w-full h-full flex justify-center"></div>
				{/if}

				{#if !search && $pinnedChats.length > 0}
					<div class="flex flex-col space-y-1 rounded-xl">
						<Folder
							className=""
							bind:open={showPinnedChat}
							on:change={(e) => {
								localStorage.setItem('showPinnedChat', e.detail);
								console.log(e.detail);
							}}
							on:import={(e) => {
								importChatHandler(e.detail, true);
							}}
							on:drop={async (e) => {
								const { type, id, item } = e.detail;

								if (type === 'chat') {
									let chat = await getChatById(localStorage.token, id).catch((error) => {
										return null;
									});
									if (!chat && item) {
										chat = await importChat(localStorage.token, item.chat, item?.meta ?? {});
									}

									if (chat) {
										console.log(chat);
										if (chat.folder_id) {
											const res = await updateChatFolderIdById(
												localStorage.token,
												chat.id,
												null
											).catch((error) => {
												toast.error(`${error}`);
												return null;
											});
										}

										if (!chat.pinned) {
											const res = await toggleChatPinnedStatusById(localStorage.token, chat.id);
										}

										initChatList();
									}
								}
							}}
							name={$i18n.t('Pinned')}
						>
							<div
								class="ml-3 pl-1 mt-[1px] flex flex-col overflow-y-auto scrollbar-hidden border-s border-gray-100 dark:border-gray-900"
							>
								{#each $pinnedChats as chat, idx}
									<ChatItem
										className=""
										id={chat.id}
										title={chat.title}
										{shiftKey}
										selected={selectedChatId === chat.id}
										on:select={() => {
											selectedChatId = chat.id;
										}}
										on:unselect={() => {
											selectedChatId = null;
										}}
										on:change={async () => {
											initChatList();
										}}
										on:tag={(e) => {
											const { type, name } = e.detail;
											tagEventHandler(type, name, chat.id);
										}}
									/>
								{/each}
							</div>
						</Folder>
					</div>
				{/if}

				{#if !search && folders}
					<Folders
						{folders}
						on:import={(e) => {
							const { folderId, items } = e.detail;
							importChatHandler(items, false, folderId);
						}}
						on:update={async (e) => {
							initChatList();
						}}
						on:change={async () => {
							initChatList();
						}}
					/>
				{/if}

				<div class=" flex-1 flex flex-col overflow-y-auto scrollbar-hidden">
					<div class="pt-1.5">
						{#if sortedChats && sortedChats.length > 0}
							{#each sortedChats as chat, idx}
								{#if $chatListSortBy !== 'title' && (idx === 0 || (idx > 0 && chat.time_range !== sortedChats[idx - 1].time_range))}
									<div
										class="w-full pl-2.5 text-xs text-gray-500 dark:text-gray-500 font-medium {idx ===
										0
											? ''
											: 'pt-5'} pb-1.5"
									>
										{$i18n.t(chat.time_range)}
										<!-- localisation keys for time_range to be recognized from the i18next parser (so they don't get automatically removed):
							{$i18n.t('Today')}
							{$i18n.t('Yesterday')}
							{$i18n.t('Previous 7 days')}
							{$i18n.t('Previous 30 days')}
							{$i18n.t('January')}
							{$i18n.t('February')}
							{$i18n.t('March')}
							{$i18n.t('April')}
							{$i18n.t('May')}
							{$i18n.t('June')}
							{$i18n.t('July')}
							{$i18n.t('August')}
							{$i18n.t('September')}
							{$i18n.t('October')}
							{$i18n.t('November')}
							{$i18n.t('December')}
							-->
									</div>
								{/if}

								<ChatItem
									className=""
									id={chat.id}
									title={chat.title}
									{shiftKey}
									selected={selectedChatId === chat.id}
									on:select={() => {
										selectedChatId = chat.id;
									}}
									on:unselect={() => {
										selectedChatId = null;
									}}
									on:change={async () => {
										initChatList();
									}}
									on:tag={(e) => {
										const { type, name } = e.detail;
										tagEventHandler(type, name, chat.id);
									}}
								/>
							{/each}

							{#if $scrollPaginationEnabled && !allChatsLoaded}
								<Loader
									on:visible={(e) => {
										if (!chatListLoading) {
											loadMoreChats();
										}
									}}
								>
									<div
										class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2"
									>
										<Spinner className=" size-4" />
										<div class=" ">Loading...</div>
									</div>
								</Loader>
							{/if}
						{:else}
							<div class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2">
								<Spinner className=" size-4" />
								<div class=" ">Loading...</div>
							</div>
						{/if}
					</div>
				</div>
			</Folder>
		</div>

		<div class="px-2">
			<div class="flex flex-col font-primary">
				{#if $user !== undefined && $user !== null}
					<UserMenu
						role={$user?.role}
						on:show={(e) => {
							if (e.detail === 'archived-chat') {
								showArchivedChats.set(true);
							}
						}}
					>
						<button
							class=" flex items-center rounded-xl py-2.5 px-2.5 w-full hover:bg-gray-100 dark:hover:bg-gray-900 transition"
							on:click={() => {
								showDropdown = !showDropdown;
							}}
						>
							<div class=" self-center mr-3">
								<img
									src={userImageSrc}
									class=" max-w-[30px] object-cover rounded-full"
									alt="User profile"
								/>
							</div>
							<div class=" self-center font-medium">{$user?.name}</div>
						</button>
					</UserMenu>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.scrollbar-hidden:active::-webkit-scrollbar-thumb,
	.scrollbar-hidden:focus::-webkit-scrollbar-thumb,
	.scrollbar-hidden:hover::-webkit-scrollbar-thumb {
		visibility: visible;
	}
	.scrollbar-hidden::-webkit-scrollbar-thumb {
		visibility: hidden;
	}
</style>
