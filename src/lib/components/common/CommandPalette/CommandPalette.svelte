<script lang="ts">
	import type { ComponentType } from 'svelte';
	import { SvelteComponent, onDestroy, onMount, tick } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import CommandItem from './CommandItem.svelte';
	import {
		commandPaletteQuery,
		commandPaletteSubmenu,
		isCommandPaletteOpen,
		type CommandPaletteSubmenuState
	} from '$lib/stores/commandPalette';
	import { executeCommand, searchCommands } from '$lib/utils/commandPalette/registry';
	import { commandContextStore } from '$lib/utils/commandPalette/context';
	import {
		type Command,
		type CommandComponentSource,
		type CommandContext,
		type CommandIconSource,
		type CommandSearchResult,
		type SubmenuCommand,
		type SubmenuItem
	} from '$lib/utils/commandPalette/types';
	import { getChatListBySearchText } from '$lib/apis/chats';
	import { preloadIcons } from '$lib/utils/commandPalette/iconCache';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import { toast } from 'svelte-sonner';
	import { updateChatById, getChatList, getPinnedChatList } from '$lib/apis/chats';
	import {
		chatCache,
		chatTitle as chatTitleStore,
		chatId as activeChatIdStore,
		currentChatPage,
		chats,
		pinnedChats
	} from '$lib/stores';
	import {
		recentChats,
		addRecentChat,
		type RecentChat
	} from '$lib/utils/commandPalette/recentChats';

	type ChatSearchResultItem = {
		id: string;
		title: string;
		time_range?: string;
	};

	type ChatSearchFallbackAction = {
		id: string;
		label: string;
		description?: string;
		execute: () => Promise<void> | void;
	};

	type ChatSearchListItem =
		| { kind: 'chat'; data: ChatSearchResultItem }
		| { kind: 'action'; data: ChatSearchFallbackAction };

	let show = false;
	let query = '';
	let results: CommandSearchResult[] = [];
	let selectionIndex = 0;
	let submenuStack: CommandPaletteSubmenuState[] = [];
	let searchInput: HTMLInputElement;
	let activeSubmenu: CommandPaletteSubmenuState | undefined;
	let mounted = false;
	let submenuItems: SubmenuItem[] = [];
	let submenuItemsLoading = false;
	let renameMode = false;
	let renameChatId: string | null = null;
	let renameCurrentTitle = '';
	// Store the query text when opening knowledge base submenu
	let pendingKnowledgeBaseQuery = '';

	const MAX_RESULTS = 12;

	let chatSearchMode = false;
	let newChatMode = false; // $ prefix mode
	let chatSearchQuery = '';
	let newChatQuery = '';
	let chatSearchResults: ChatSearchResultItem[] = [];
	let chatSearchItems: ChatSearchListItem[] = [];
	let chatSearchLoading = false;
	let chatSearchError: string | null = null;
	let chatSearchAbort: AbortController | null = null;
	let chatSearchDebounce: ReturnType<typeof setTimeout> | null = null;
	let recentChatItems: RecentChat[] = [];
	const recentChatsUnsubscribe = recentChats.subscribe((items) => {
		recentChatItems = items;
	});

	function isSvelteComponentConstructor(value: unknown): value is ComponentType {
		// Check if it's a function - Svelte components are functions
		if (typeof value !== 'function') return false;

		// For dynamically imported components, the prototype check might fail
		// So we check if it's a function and has the expected structure
		// Svelte components are constructors, so they should be callable with 'new'
		try {
			// Check if it has a prototype (constructor functions do)
			// or if it's a valid component (some wrapped components might not have prototype)
			return true;
		} catch {
			return false;
		}
	}

	function extractSubmenuComponent(value: unknown): ComponentType | null {
		if (!value) return null;

		// If it's directly a function, try to use it
		if (typeof value === 'function') {
			return value as ComponentType;
		}

		// If it's an object, check for default export
		if (typeof value === 'object' && value !== null) {
			const obj = value as Record<string, unknown>;

			// Try multiple ways to access the default export
			// 1. Direct property access
			if (obj.default && typeof obj.default === 'function') {
				return obj.default as ComponentType;
			}

			// 2. Check if it's in the prototype chain
			if ('default' in obj && typeof obj.default === 'function') {
				return obj.default as ComponentType;
			}

			// 3. Try Object.hasOwnProperty if available
			if (
				Object.prototype.hasOwnProperty.call(obj, 'default') &&
				typeof obj.default === 'function'
			) {
				return obj.default as ComponentType;
			}
		}

		return null;
	}

	function isPromiseLike(value: unknown): value is Promise<unknown> {
		return (
			typeof value === 'object' &&
			value !== null &&
			typeof (value as Record<string, unknown>).then === 'function'
		);
	}

	async function resolveSubmenuComponent(
		source: CommandComponentSource | Promise<unknown>
	): Promise<ComponentType> {
		if (isPromiseLike(source)) {
			try {
				const mod = await source;
				const component = extractSubmenuComponent(mod);
				if (!component) {
					console.error('Failed to extract component from module:', mod);
					console.error('Module keys:', Object.keys(mod as object));
					console.error('Module default type:', typeof (mod as Record<string, unknown>)?.default);
					throw new Error('Submenu loader did not return a Svelte component');
				}
				return component;
			} catch (error) {
				if (error instanceof Error && error.message.includes('Submenu loader')) {
					throw error;
				}
				console.error('Error resolving submenu component from Promise:', error);
				throw new Error(
					`Failed to load submenu component: ${error instanceof Error ? error.message : String(error)}`
				);
			}
		}

		if (isSvelteComponentConstructor(source)) {
			return source;
		}

		if (typeof source === 'function') {
			try {
				const mod = await (source as () => unknown)();
				const component = extractSubmenuComponent(mod);
				if (!component) {
					console.error('Failed to extract component from loader result:', mod);
					console.error('Loader result keys:', Object.keys(mod as object));
					throw new Error('Submenu loader did not return a Svelte component');
				}
				return component;
			} catch (error) {
				if (error instanceof Error && error.message.includes('Submenu loader')) {
					throw error;
				}
				console.error('Error resolving submenu component from loader:', error);
				throw new Error(
					`Failed to load submenu component: ${error instanceof Error ? error.message : String(error)}`
				);
			}
		}

		const component = extractSubmenuComponent(source);
		if (!component) {
			console.error('Failed to extract component from source:', source);
			throw new Error('Invalid submenu component');
		}

		return component;
	}

	const storesUnsubscribe = [
		isCommandPaletteOpen.subscribe(async ($open) => {
			show = $open;
			if ($open) {
				mounted = true;
			}
			if (show) {
				query = get(commandPaletteQuery);
				submenuStack = get(commandPaletteSubmenu);
				const trimmed = query.trimStart();
				chatSearchMode = trimmed.startsWith('>');
				newChatMode = trimmed.startsWith('$');
				if (chatSearchMode) {
					chatSearchQuery = trimmed.slice(1).trim();
					triggerChatSearch();
				} else if (newChatMode) {
					newChatQuery = trimmed.slice(1).trim();
					updateNewChatItems();
				} else {
					updateResults();
				}
				await tick();
				searchInput?.focus();
			} else {
				query = '';
				results = [];
				selectionIndex = 0;
				submenuStack = [];
				resetChatSearchState();
			}
		}),
		commandPaletteQuery.subscribe(($query) => {
			if (show && $query !== query) {
				query = $query;
				handleQueryChange(query);
			}
		}),
		commandPaletteSubmenu.subscribe(($submenuStack) => {
			if (show) {
				submenuStack = $submenuStack;
			}
		}),
		commandContextStore.subscribe((context) => {
			if (!show) return;
			if (chatSearchMode) {
				chatSearchItems = buildChatSearchItems(context);
				setSelectionFromChatSearch();
			} else if (newChatMode) {
				chatSearchItems = buildNewChatItems(newChatQuery, context);
				setSelectionFromChatSearch();
			} else {
				updateResults();
			}
		})
	];

	// Global keyboard handler to capture all events when palette is open
	function handleGlobalKeyDown(event: KeyboardEvent) {
		if (!show) return;

		// If input is not focused, focus it and handle the key
		if (document.activeElement !== searchInput && searchInput) {
			// For navigation keys, focus input and handle
			if (['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) {
				event.preventDefault();
				event.stopPropagation();
				searchInput.focus();
				handleKeyDown(event);
			}
			// For typing keys, focus input and insert the character
			else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
				event.preventDefault();
				event.stopPropagation();
				searchInput.focus();
				// Insert the character at cursor position
				const start = searchInput.selectionStart ?? query.length;
				const end = searchInput.selectionEnd ?? query.length;
				const newValue = query.slice(0, start) + event.key + query.slice(end);
				query = newValue;
				commandPaletteQuery.set(newValue);
				searchInput.setSelectionRange(start + 1, start + 1);
				handleQueryChange(newValue);
			}
		}
	}

	onMount(() => {
		document.addEventListener('keydown', handleGlobalKeyDown, true);
	});

	onDestroy(() => {
		document.removeEventListener('keydown', handleGlobalKeyDown, true);
		for (const unsubscribe of storesUnsubscribe) {
			unsubscribe();
		}
		if (chatSearchAbort) {
			chatSearchAbort.abort();
		}
		if (chatSearchDebounce) {
			clearTimeout(chatSearchDebounce);
		}
		recentChatsUnsubscribe();
	});

	function resetChatSearchState() {
		chatSearchMode = false;
		newChatMode = false;
		chatSearchQuery = '';
		newChatQuery = '';
		chatSearchResults = [];
		chatSearchItems = [];
		chatSearchLoading = false;
		chatSearchError = null;
		pendingKnowledgeBaseQuery = '';
		if (chatSearchAbort) {
			chatSearchAbort.abort();
			chatSearchAbort = null;
		}
		if (chatSearchDebounce) {
			clearTimeout(chatSearchDebounce);
			chatSearchDebounce = null;
		}
	}

	function updateNewChatItems() {
		const context = get(commandContextStore);
		chatSearchItems = buildNewChatItems(newChatQuery, context);
		setSelectionFromChatSearch();
	}

	function buildNewChatItems(rawQuery: string, context: CommandContext): ChatSearchListItem[] {
		const trimmed = rawQuery.trim();
		const actions = buildChatFallbackActions(trimmed, context);
		return actions.map((action) => ({
			kind: 'action',
			data: action
		}));
	}

	function closePalette() {
		isCommandPaletteOpen.set(false);
		commandPaletteQuery.set('');
		commandPaletteSubmenu.set([]);
		show = false;
		resetChatSearchState();
		renameMode = false;
		renameChatId = null;
		renameCurrentTitle = '';
	}

	async function enterRenameMode(chatId: string, currentTitle: string) {
		renameMode = true;
		renameChatId = chatId;
		renameCurrentTitle = currentTitle;
		query = currentTitle;
		commandPaletteQuery.set(currentTitle);
		await tick();
		searchInput?.focus();
		searchInput?.select();
	}

	function cancelRename() {
		renameMode = false;
		renameChatId = null;
		renameCurrentTitle = '';
		query = '';
		commandPaletteQuery.set('');
		updateResults();
	}

	async function saveRename() {
		if (!renameChatId) return;

		const trimmed = query.trim();
		if (!trimmed) {
			toast.error('Title cannot be empty.');
			return;
		}

		if (trimmed === renameCurrentTitle) {
			// No change, just close
			cancelRename();
			closePalette();
			return;
		}

		try {
			if (!renameChatId) return;
			const chatIdToUpdate = renameChatId;
			await updateChatById(localStorage.token, chatIdToUpdate, { title: trimmed });
			chatCache.update((cache) => {
				cache.delete(chatIdToUpdate);
				return cache;
			});

			if (get(activeChatIdStore) === chatIdToUpdate) {
				chatTitleStore.set(trimmed);
			}

			// Refresh chat lists
			currentChatPage.set(1);
			const updatedChats = await getChatList(localStorage.token, get(currentChatPage));
			chats.set(updatedChats);
			pinnedChats.set(await getPinnedChatList(localStorage.token));

			toast.success('Chat renamed.');
			cancelRename();
			closePalette();
		} catch (error) {
			console.error(error);
			toast.error('Failed to rename chat.');
		}
	}

	function updateResults() {
		if (chatSearchMode) return;

		const context = get(commandContextStore);
		const commandResults = searchCommands(query, {
			context,
			limit: MAX_RESULTS
		});

		let combinedResults = commandResults;

		if (!query.trim() && recentChatItems.length > 0) {
			const recentResults = recentChatItems.map((chat) => ({
				command: {
					id: `recent-chat:${chat.id}`,
					type: 'action',
					label: chat.title,
					description: 'Recent chat',
					keywords: ['recent', 'chat'],
					priority: 120,
					icon: ChatBubble,
					execute: async () => {
						addRecentChat({ id: chat.id, title: chat.title });
						await goto(`/c/${chat.id}`);
					}
				} as Command,
				score: null
			}));

			combinedResults = [...recentResults, ...commandResults];
		}

		results = combinedResults;

		if (results.length === 0) {
			selectionIndex = -1;
		} else {
			selectionIndex = 0;
		}

		const iconSources = results
			.slice(0, 6)
			.map((result) => result.command.icon)
			.filter((icon): icon is CommandIconSource => Boolean(icon));
		preloadIcons(iconSources);
	}

	async function handleQueryChange(value: string) {
		const activeSubmenuCommand = submenuStack[submenuStack.length - 1]?.command;

		// If in submenu with items, filter them
		if (activeSubmenuCommand?.getSubmenuItems) {
			const context = get(commandContextStore);
			try {
				const allItems = await Promise.resolve(activeSubmenuCommand.getSubmenuItems('', context));
				const lowerQuery = value.toLowerCase();
				submenuItems = allItems.filter(
					(item) =>
						item.label.toLowerCase().includes(lowerQuery) ||
						item.description?.toLowerCase().includes(lowerQuery)
				);
				if (submenuItems.length > 0 && selectionIndex >= submenuItems.length) {
					selectionIndex = 0;
				}
			} catch (error) {
				console.error('Failed to filter submenu items:', error);
			}
			return;
		}

		const trimmed = value.trimStart();
		const shouldChatSearch = trimmed.startsWith('>');
		const shouldNewChat = trimmed.startsWith('$');

		if (shouldChatSearch !== chatSearchMode || shouldNewChat !== newChatMode) {
			chatSearchMode = shouldChatSearch;
			newChatMode = shouldNewChat;
			chatSearchQuery = '';
			newChatQuery = '';
			chatSearchResults = [];
			chatSearchItems = [];
			chatSearchError = null;
			selectionIndex = 0;
		}

		if (chatSearchMode) {
			chatSearchQuery = trimmed.slice(1).trim();
			triggerChatSearch();
		} else if (newChatMode) {
			newChatQuery = trimmed.slice(1).trim();
			updateNewChatItems();
		} else {
			updateResults();
		}
	}

	function handleInput(event: Event) {
		const value = (event.target as HTMLInputElement).value;
		query = value;
		commandPaletteQuery.set(value);
		handleQueryChange(value);
	}

	async function handleKeyDown(event: KeyboardEvent) {
		// Always prevent default for navigation keys to avoid conflicts
		if (['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) {
			event.preventDefault();
			event.stopPropagation();
		}

		const activeSubmenuCommand = submenuStack[submenuStack.length - 1]?.command;
		const hasSubmenuItems = activeSubmenuCommand?.getSubmenuItems;
		const hasSubmenuComponent =
			activeSubmenuCommand?.getSubmenuComponent && submenuStack[submenuStack.length - 1]?.component;

		// Handle submenu items (new item-based submenus)
		if (hasSubmenuItems) {
			if (event.key === 'ArrowDown') {
				if (submenuItems.length > 0) {
					selectionIndex = (selectionIndex + 1) % submenuItems.length;
				}
			} else if (event.key === 'ArrowUp') {
				if (submenuItems.length > 0) {
					selectionIndex = (selectionIndex - 1 + submenuItems.length) % submenuItems.length;
				}
			} else if (event.key === 'Enter') {
				if (selectionIndex >= 0 && selectionIndex < submenuItems.length) {
					const item = submenuItems[selectionIndex];
					const context = get(commandContextStore);
					Promise.resolve(item.execute(context))
						.then(() => {
							popSubmenu();
						})
						.catch((error) => {
							console.error('Submenu item execution failed:', error);
						});
				}
			} else if (event.key === 'Escape') {
				popSubmenu();
			}
			return;
		}

		// Handle rename mode
		if (renameMode) {
			if (event.key === 'Enter') {
				event.preventDefault();
				event.stopPropagation();
				await saveRename();
			} else if (event.key === 'Escape') {
				event.preventDefault();
				event.stopPropagation();
				cancelRename();
			}
			// Let typing work normally in rename mode
			return;
		}

		// Handle legacy component-based submenus
		if (hasSubmenuComponent) {
			if (event.key === 'Escape') {
				popSubmenu();
			}
			return;
		}

		// Handle chat search mode
		if (chatSearchMode) {
			handleChatSearchKeyDown(event);
			return;
		}

		// Handle new chat mode ($ prefix)
		if (newChatMode) {
			handleChatSearchKeyDown(event);
			return;
		}

		// Handle main command list
		if (event.key === 'ArrowDown') {
			if (results.length > 0) {
				selectionIndex = (selectionIndex + 1) % results.length;
			}
		} else if (event.key === 'ArrowUp') {
			if (results.length > 0) {
				selectionIndex = (selectionIndex - 1 + results.length) % results.length;
			}
		} else if (event.key === 'Enter') {
			if (selectionIndex >= 0 && selectionIndex < results.length) {
				triggerCommand(results[selectionIndex].command);
			}
		} else if (event.key === 'Escape') {
			closePalette();
		}
	}

	function handleChatSearchKeyDown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			if (chatSearchItems.length > 0) {
				selectionIndex = (selectionIndex + 1) % chatSearchItems.length;
			}
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			if (chatSearchItems.length > 0) {
				selectionIndex = (selectionIndex - 1 + chatSearchItems.length) % chatSearchItems.length;
			}
		} else if (event.key === 'Enter') {
			event.preventDefault();
			const item = chatSearchItems[selectionIndex];
			if (item) {
				activateChatSearchItem(item);
			}
		} else if (event.key === 'Escape') {
			event.preventDefault();
			if (query) {
				query = '';
				commandPaletteQuery.set('');
				handleQueryChange('');
			} else {
				closePalette();
			}
		}
	}

	async function triggerCommand(command: Command) {
		try {
			// Special handling for rename command
			if (command.id === 'chat:rename') {
				const context = get(commandContextStore);
				const currentChatId = context?.currentChatId || get(activeChatIdStore);
				if (!currentChatId || currentChatId === 'local') {
					toast.error('Open a saved chat to rename it.');
					return;
				}
				const currentTitle = get(chatTitleStore) || '';
				await enterRenameMode(currentChatId, currentTitle);
				return;
			}

			// Special handling for search chats command - keep palette open
			if (command.id === 'core:search-chats') {
				await executeCommand(command);
				// Focus the input so user can immediately start typing
				await tick();
				searchInput?.focus();
				// Set cursor to end of input (after the >)
				if (searchInput) {
					const length = searchInput.value.length;
					searchInput.setSelectionRange(length, length);
				}
				return;
			}

			if (command.type === 'submenu') {
				await pushSubmenu(command);
				return;
			}

			await executeCommand(command);
			closePalette();
		} catch (error) {
			console.error('Failed to execute command:', error);
			// Don't close palette on error, let user try again
		}
	}

	async function activateChatSearchItem(item: ChatSearchListItem) {
		try {
			if (item.kind === 'chat') {
				addRecentChat({ id: item.data.id, title: item.data.title });
				await goto(`/c/${item.data.id}`);
				closePalette();
			} else {
				await Promise.resolve(item.data.execute());
				// Don't close palette if a submenu was opened (submenuStack changed)
				// This happens when opening knowledge base picker
				await tick(); // Wait for submenu to be pushed
				if (submenuStack.length === 0) {
					// No submenu was opened, safe to close
					closePalette();
				}
				// Otherwise, the submenu is now active and we should stay open
			}
		} catch (error) {
			console.error('Failed to activate chat search item:', error);
			// Don't close palette on error, let user try again
		}
	}

	async function pushSubmenu(command: SubmenuCommand) {
		const context = get(commandContextStore);

		// If submenu provides items, use that instead of component
		if (command.getSubmenuItems) {
			submenuItemsLoading = true;
			// Always start with empty query for submenus
			query = '';
			commandPaletteQuery.set('');
			try {
				// Always load all items first, filtering happens in handleQueryChange
				const items = await Promise.resolve(command.getSubmenuItems('', context));
				submenuItems = items;
				selectionIndex = 0;
			} catch (error) {
				console.error('Failed to load submenu items:', error);
				submenuItems = [];
			} finally {
				submenuItemsLoading = false;
			}

			const nextStack = [
				...submenuStack,
				{
					id: command.id,
					title: command.label,
					command,
					component: undefined,
					props: {}
				}
			];

			submenuStack = nextStack;
			commandPaletteSubmenu.set(nextStack);
			await tick();
			searchInput?.focus();
			return;
		}

		// Legacy component-based submenu
		if (command.getSubmenuComponent) {
			const component = await resolveSubmenuComponent(command.getSubmenuComponent());
			const props = command.getSubmenuProps ? command.getSubmenuProps(context) : {};

			const nextStack = [
				...submenuStack,
				{
					id: command.id,
					title: command.label,
					command,
					component,
					props
				}
			];

			submenuStack = nextStack;
			commandPaletteSubmenu.set(nextStack);
			await tick();
			searchInput?.focus();
		}
	}

	function popSubmenu() {
		if (submenuStack.length === 0) return;
		const nextStack = submenuStack.slice(0, -1);
		submenuStack = nextStack;
		commandPaletteSubmenu.set(nextStack);
		submenuItems = [];
		query = '';
		commandPaletteQuery.set('');
		selectionIndex = 0;
		// Clear pending knowledge base query if we're leaving that submenu
		if (
			nextStack.length === 0 ||
			nextStack[nextStack.length - 1]?.id !== 'chat-search:knowledge-base'
		) {
			pendingKnowledgeBaseQuery = '';
		}
		updateResults();
		searchInput?.focus();
	}

	function handleBackdropMouseDown(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			closePalette();
		}
	}

	function triggerChatSearch() {
		if (chatSearchDebounce) {
			clearTimeout(chatSearchDebounce);
		}

		chatSearchDebounce = setTimeout(async () => {
			if (!chatSearchMode) return;

			const controller = new AbortController();

			if (chatSearchAbort) {
				chatSearchAbort.abort();
			}

			const searchTerm = chatSearchQuery.trim();
			const context = get(commandContextStore);

			if (searchTerm === '') {
				chatSearchResults = [];
				chatSearchError = null;
				chatSearchLoading = false;
				chatSearchItems = buildChatSearchItems(context);
				setSelectionFromChatSearch();
				return;
			}

			chatSearchLoading = true;
			chatSearchError = null;
			chatSearchAbort = controller;

			try {
				const results =
					(await getChatListBySearchText(localStorage.token, searchTerm, 1, controller.signal)) ??
					[];
				chatSearchResults = results;
				chatSearchLoading = false;
				chatSearchItems = buildChatSearchItems(context);
				setSelectionFromChatSearch();
			} catch (error) {
				if ((error as Error)?.name === 'AbortError') {
					return;
				}
				console.error('Chat search failed', error);
				chatSearchLoading = false;
				chatSearchError = 'Unable to search chats right now.';
				chatSearchResults = [];
				chatSearchItems = buildChatSearchItems(context);
				setSelectionFromChatSearch();
			}
		}, 150);
	}

	function buildChatSearchItems(context: CommandContext): ChatSearchListItem[] {
		const items: ChatSearchListItem[] = chatSearchResults.map((result) => ({
			kind: 'chat',
			data: result
		}));

		const fallbacks = buildChatFallbackActions(chatSearchQuery, context);
		for (const action of fallbacks) {
			items.push({ kind: 'action', data: action });
		}

		return items;
	}

	function setSelectionFromChatSearch() {
		if (chatSearchItems.length === 0) {
			selectionIndex = -1;
		} else {
			selectionIndex = Math.min(selectionIndex, chatSearchItems.length - 1);
			if (selectionIndex < 0) {
				selectionIndex = 0;
			}
		}
	}

	function buildChatFallbackActions(
		rawQuery: string,
		context: CommandContext
	): ChatSearchFallbackAction[] {
		const actions: ChatSearchFallbackAction[] = [];
		const trimmed = rawQuery.trim();

		if (!trimmed) {
			return actions;
		}

		actions.push({
			id: 'chat-search:new-chat',
			label: `Send "${trimmed}" in new chat`,
			execute: async () => {
				await startNewChat({ query: trimmed });
			}
		});

		if (context.config?.features?.enable_web_search) {
			actions.push({
				id: 'chat-search:new-chat-web',
				label: 'Send in new chat with web search enabled',
				execute: async () => {
					await startNewChat({ query: trimmed, webSearch: true });
				}
			});
		}

		actions.push({
			id: 'chat-search:new-chat-knowledge',
			label: 'Send in new chat with knowledge base…',
			execute: async () => {
				await openKnowledgeBaseSubmenu(trimmed);
			}
		});

		if (context.config?.features?.enable_image_generation) {
			actions.push({
				id: 'chat-search:new-chat-image',
				label: 'Generate image in new chat',
				execute: async () => {
					await startNewChat({ query: trimmed, image: true });
				}
			});
		}

		return actions;
	}

	async function startNewChat(options: {
		query?: string;
		webSearch?: boolean;
		image?: boolean;
		knowledgeBaseId?: string;
		knowledgeBaseName?: string;
	}) {
		const params = new URLSearchParams();
		if (options.query) params.set('q', options.query);
		if (options.webSearch) params.set('web-search', 'true');
		if (options.image) params.set('image-generation', 'true');
		if (options.knowledgeBaseId) {
			params.set('knowledge-base', options.knowledgeBaseId);
			sessionStorage.setItem(
				'commandPaletteKnowledgeBase',
				JSON.stringify({
					id: options.knowledgeBaseId,
					name: options.knowledgeBaseName || 'Knowledge Base'
				})
			);
		}

		const url = params.toString() ? `/?${params.toString()}` : '/';
		await goto(url);
		closePalette();
	}

	async function openKnowledgeBaseSubmenu(searchText: string) {
		// Store the query text for later use
		pendingKnowledgeBaseQuery = searchText;

		const submenu: SubmenuCommand = {
			id: 'chat-search:knowledge-base',
			type: 'submenu',
			label: 'Attach Knowledge Base',
			keywords: ['knowledge', 'base'],
			getSubmenuItems: async (query: string, context?: CommandContext): Promise<SubmenuItem[]> => {
				const { get } = await import('svelte/store');
				const stores = await import('$lib/stores');
				const knowledgeStore = stores.knowledge;
				const { getKnowledgeBases } = await import('$lib/apis/knowledge');

				// Fetch knowledge bases
				let knowledgeBases: Array<{ id: string; name: string; description?: string }> = [];
				try {
					let current = get(knowledgeStore);
					if (!current || current.length === 0) {
						const fetched = await getKnowledgeBases(localStorage.token);
						knowledgeStore.set(fetched ?? []);
						current = fetched ?? [];
					}

					knowledgeBases = (current ?? []).map((kb: any) => ({
						id: kb.id,
						name: kb.name,
						description: kb.description
					}));
				} catch (error) {
					console.error('Failed to load knowledge bases:', error);
					return [];
				}

				// Filter by query
				const lowerQuery = query.toLowerCase();
				const filtered = knowledgeBases.filter((kb) => {
					if (!query) return true;
					const text = `${kb.name} ${kb.description ?? ''}`.toLowerCase();
					return text.includes(lowerQuery);
				});

				// Convert to SubmenuItems
				return filtered.map((kb) => ({
					id: `kb:${kb.id}`,
					label: kb.name,
					description: kb.description,
					execute: async () => {
						// Use the stored query text
						const queryText = pendingKnowledgeBaseQuery;
						await startNewChat({
							query: queryText,
							knowledgeBaseId: kb.id,
							knowledgeBaseName: kb.name
						});
					}
				}));
			}
		};

		await pushSubmenu(submenu);
	}

	function handleChatSearchItemClick(item: ChatSearchListItem) {
		activateChatSearchItem(item);
	}

	function submenuItemToCommand(item: SubmenuItem): Command {
		return {
			id: item.id,
			type: 'action',
			label: item.label,
			description: item.description,
			icon: item.icon,
			execute: item.execute
		} as Command;
	}

	$: activeSubmenu = submenuStack[submenuStack.length - 1];

	$: placeholderText = (() => {
		if (renameMode) {
			return 'Enter new chat title (Press Enter to save, Escape to cancel)';
		}
		if (activeSubmenu?.command) {
			const commandId = activeSubmenu.command.id;
			if (commandId === 'chat:move-to-folder') {
				return 'Search folders...';
			}
			if (commandId === 'chat:change-model') {
				return 'Search models...';
			}
			if (commandId === 'chat:export') {
				return 'Search export types...';
			}
			if (commandId === 'chat-search:knowledge-base') {
				return 'Search knowledge bases...';
			}
		}
		if (chatSearchMode) {
			return 'Search chats...';
		}
		if (newChatMode) {
			return 'Type your message...';
		}
		return 'Search commands...';
	})();
</script>

{#if show || mounted}
	<div
		class={`fixed inset-0 z-[6000] flex items-start justify-center px-4 py-24 transition-opacity duration-75 ${show ? 'bg-black/50 backdrop-blur-sm opacity-100' : 'bg-transparent opacity-0 pointer-events-none'}`}
		role="presentation"
		aria-hidden={!show}
		on:mousedown={show ? handleBackdropMouseDown : undefined}
	>
		<div
			class={`w-full max-w-2xl bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 rounded-2xl shadow-3xl overflow-hidden transition-transform duration-75 ${show ? 'scale-100' : 'scale-95'}`}
			role="presentation"
			on:mousedown|stopPropagation
			on:click={() => searchInput?.focus()}
		>
			<div class="border-b border-gray-200 dark:border-gray-800 px-4 py-3">
				<input
					bind:this={searchInput}
					class="w-full bg-transparent text-base focus:outline-hidden placeholder:text-gray-400 dark:text-white"
					placeholder={placeholderText}
					value={query}
					on:input={handleInput}
					on:keydown={handleKeyDown}
					autofocus
					tabindex="0"
				/>
				{#if !renameMode && !activeSubmenu && !chatSearchMode && !newChatMode}
					<div class="mt-2 flex gap-4 text-xs text-gray-400 dark:text-gray-500">
						<span
							>Press <kbd
								class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
								>></kbd
							> to search chats</span
						>
						<span
							>Press <kbd
								class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
								>$</kbd
							> to start new chat</span
						>
					</div>
				{/if}
			</div>

			{#if renameMode}
				<div class="max-h-96 overflow-y-auto px-2 py-3">
					<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">
						Type the new title and press Enter to save, or Escape to cancel.
					</div>
				</div>
			{:else if activeSubmenu}
				{#if activeSubmenu.command?.getSubmenuItems}
					<div class="max-h-96 overflow-y-auto px-2 py-3">
						{#if submenuItemsLoading}
							<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">Loading…</div>
						{:else if submenuItems.length > 0}
							<ul class="flex flex-col gap-1">
								{#each submenuItems as item, index (item.id)}
									<button
										type="button"
										class="text-left w-full"
										on:click={() => {
											const context = get(commandContextStore);
											Promise.resolve(item.execute(context))
												.then(() => {
													popSubmenu();
												})
												.catch((error) => {
													console.error('Submenu item execution failed:', error);
												});
										}}
									>
										<CommandItem
											command={submenuItemToCommand(item)}
											selected={index === selectionIndex}
										/>
									</button>
								{/each}
							</ul>
						{:else}
							<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">No items found.</div>
						{/if}
					</div>
				{:else if activeSubmenu.component}
					{#key activeSubmenu.id}
						<svelte:component
							this={activeSubmenu.component}
							on:close={popSubmenu}
							{...activeSubmenu.props ?? {}}
						/>
					{/key}
				{/if}
			{:else if chatSearchMode || newChatMode}
				<div class="max-h-96 overflow-y-auto px-2 py-3">
					{#if chatSearchMode && chatSearchLoading}
						<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">Searching chats…</div>
					{:else if chatSearchItems.length > 0}
						<ul class="flex flex-col gap-1">
							{#each chatSearchItems as item, index (item.kind === 'chat' ? item.data.id : item.data.id)}
								<button
									type="button"
									class="text-left w-full"
									on:click={() => handleChatSearchItemClick(item)}
								>
									<div
										class={`px-3 py-2 rounded-lg transition-colors flex items-center gap-3 ${
											index === selectionIndex
												? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white'
												: 'hover:bg-gray-100 dark:hover:bg-gray-850'
										}`}
									>
										{#if item.kind === 'chat'}
											<ChatBubble className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
											<div class="flex flex-col flex-1">
												<div class="font-medium leading-tight">{item.data.title}</div>
												{#if item.data.time_range}
													<div class="text-xs text-gray-500 dark:text-gray-400">
														{item.data.time_range}
													</div>
												{/if}
											</div>
										{:else}
											<div class="flex flex-col flex-1">
												<div class="font-medium leading-tight">{item.data.label}</div>
												{#if item.data.description}
													<div class="text-xs text-gray-500 dark:text-gray-400">
														{item.data.description}
													</div>
												{/if}
											</div>
										{/if}
									</div>
								</button>
							{/each}
						</ul>
					{:else if chatSearchError}
						<div class="px-3 py-6 text-sm text-red-500 dark:text-red-400">
							{chatSearchError}
						</div>
					{:else}
						<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">
							{#if chatSearchQuery.trim()}
								No chats found. Try another query or create a new chat.
							{:else}
								Start typing after ">" to search your chats.
							{/if}
						</div>
					{/if}
				</div>
			{:else}
				<div class="max-h-96 overflow-y-auto px-2 py-3">
					{#if results.length > 0}
						<ul class="flex flex-col gap-1">
							{#each results as result, index (result.command.id)}
								<button
									type="button"
									class="text-left"
									on:click={() => triggerCommand(result.command)}
								>
									<CommandItem command={result.command} selected={index === selectionIndex} />
								</button>
							{/each}
						</ul>
					{:else}
						<div class="px-3 py-6 text-sm text-gray-500 dark:text-gray-400">
							No commands available.
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}
