<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';
	import { get, type Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';

	import {
		WEBUI_NAME,
		banners,
		chatId,
		config,
		mobile,
		settings,
		showArchivedChats,
		showControls,
		showSidebar,
		temporaryChatEnabled,
		user,
		chats,
		models
	} from '$lib/stores';

	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import ChatInfoModal from '../chat/ChatInfoModal.svelte';
	import ModelSelector from '../chat/ModelSelector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import MenuLines from '../icons/MenuLines.svelte';
	import AdjustmentsHorizontal from '../icons/AdjustmentsHorizontal.svelte';

	import PencilSquare from '../icons/PencilSquare.svelte';
	import Info from '../icons/Info.svelte';
	import Banner from '../common/Banner.svelte';
	import { getChatMetaById } from '$lib/apis/chats';
	import { getFolders } from '$lib/apis/folders';
	import { navigateToChat, navigateToFolder } from '$lib/stores/sidebar';
	import { createMessagesList } from '$lib/utils';
	import { testId } from '$lib/utils/testId';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let initNewChat: Function;
	export let title: string = $WEBUI_NAME;
	export let shareEnabled: boolean = false;

	export let chat;
	export let history;
	export let selectedModels;
	export let showModelSelector = true;

	let showShareChatModal = false;
	let showDownloadChatModal = false;
	let showChatInfoModal = false;

	$: userImageSrc = $user?.profile_image_url ?? '';

	// State for current chat info
	let currentChatDetails = null;
	let currentFolderName = null;
	let folders = {};

	type ChatInfoSnapshot = {
		totalMessages: number;
		currentBranchMessages: number;
		branchCount: number;
		attachmentCount: number;
		totalCost: number;
		totalInputTokens: number;
		totalOutputTokens: number;
		totalReasoningTokens: number;
		uniqueModels: {
			id: string;
			label: string;
			icon?: string | null;
			messageCount: number;
		}[];
		createdAt: number | null;
		updatedAt: number | null;
	};

	let chatInfoSnapshot: ChatInfoSnapshot | null = null;

	// Lightweight collision detection
	let chatTitleButton = null;
	let modelSelectorElement = null;

	const adjustTitlePosition = () => {
		// Early returns for efficiency
		if (!chatTitleButton || !modelSelectorElement) return;
		if (window.innerWidth < 768) return; // Only run on desktop/tablet
		if (!currentChatDetails) {
			// Reset any positioning styles when no chat details
			chatTitleButton.style.left = '';
			chatTitleButton.style.transform = '';
			return;
		}

		// Get the positioning container (the flex-1 container with relative positioning)
		const positioningContainer = chatTitleButton.parentElement.parentElement;
		if (!positioningContainer) return;

		const containerRect = positioningContainer.getBoundingClientRect();
		const modelRect = modelSelectorElement.getBoundingClientRect();
		const buttonRect = chatTitleButton.getBoundingClientRect();

		// Calculate where the title would be if centered in the container
		const containerCenter = containerRect.width / 2;
		const buttonHalfWidth = buttonRect.width / 2;
		const centeredLeftPosition = containerCenter - buttonHalfWidth;

		// Calculate model selector right edge relative to positioning container
		const modelRightEdge = modelRect.right - containerRect.left;

		// Check if centering would cause overlap (with 16px margin for better spacing)
		const wouldOverlap = centeredLeftPosition < modelRightEdge + 16;

		if (wouldOverlap) {
			// Position to the right of model selector with margin
			const offset = modelRightEdge + 16;
			chatTitleButton.style.left = `${offset}px`;
			chatTitleButton.style.transform = 'none';
		} else {
			// Use centered position
			chatTitleButton.style.left = '50%';
			chatTitleButton.style.transform = 'translateX(-50%)';
		}
	};

	// Load folders on mount
	onMount(() => {
		// Load folders
		const loadFolders = async () => {
			try {
				const folderList = await getFolders(localStorage.token);
				folders = {};
				for (const folder of folderList) {
					folders[folder.id] = folder;
				}
			} catch (error) {
				console.error('Failed to load folders:', error);
			}
		};

		loadFolders();

		// Debounced resize listener to avoid excessive calls
		let resizeTimeout;
		const handleResize = () => {
			clearTimeout(resizeTimeout);
			resizeTimeout = setTimeout(() => {
				requestAnimationFrame(adjustTitlePosition);
			}, 100); // 100ms debounce
		};

		window.addEventListener('resize', handleResize);

		return () => {
			window.removeEventListener('resize', handleResize);
			clearTimeout(resizeTimeout);
		};
	});

	// Reactive statement to load current chat details when chatId changes
	$: if ($chatId && localStorage.token) {
		loadCurrentChatDetails();
	}

	// Reactive statement to update folder name when folders or chat details change
	$: if (currentChatDetails?.folder_id && folders[currentChatDetails.folder_id]) {
		currentFolderName = folders[currentChatDetails.folder_id].name;
	} else {
		currentFolderName = null;
	}

	// Reactive statement to refresh chat details when chats list changes (indicating title or folder changes)
	$: if ($chats && $chatId && currentChatDetails) {
		refreshChatDetails();
	}

	// Only trigger position adjustment when elements are first available or when content that affects layout changes
	$: if (chatTitleButton && modelSelectorElement && currentChatDetails) {
		// Use tick to ensure DOM is updated, then position
		tick().then(() => {
			requestAnimationFrame(adjustTitlePosition);
		});
	}

	const refreshChatDetails = async () => {
		// Re-fetch the chat details to get updated title and folder_id
		try {
			const updatedChatDetails = await getChatMetaById(localStorage.token, $chatId);
			if (updatedChatDetails && currentChatDetails) {
				// Update both title and folder_id if they changed
				if (updatedChatDetails.title !== currentChatDetails.title) {
					currentChatDetails.title = updatedChatDetails.title;
				}
				if (updatedChatDetails.folder_id !== currentChatDetails.folder_id) {
					currentChatDetails.folder_id = updatedChatDetails.folder_id;
				}
			}
		} catch (error) {
			console.error('Failed to refresh chat details:', error);
		}
	};

	const loadCurrentChatDetails = async () => {
		try {
			currentChatDetails = await getChatMetaById(localStorage.token, $chatId);
			// Position adjustment will be triggered by reactive statement
		} catch (error) {
			console.error('Failed to load chat details:', error);
			currentChatDetails = null;
		}
	};

	const handleChatTitleClick = async () => {
		// 1. Open the sidebar if it's closed
		if (!$showSidebar) {
			showSidebar.set(true);
			await tick(); // Wait for sidebar to open
		}

		// 2. Use the sidebar navigation store to handle the navigation
		if (currentChatDetails?.folder_id) {
			// Navigate to the folder containing the chat
			navigateToFolder(currentChatDetails.folder_id);
		} else {
			// Navigate directly to the chat (not in a folder)
			navigateToChat($chatId);
		}
	};

	const buildChatInfoSnapshot = (): ChatInfoSnapshot => {
		const snapshot: ChatInfoSnapshot = {
			totalMessages: 0,
			currentBranchMessages: 0,
			branchCount: 0,
			attachmentCount: 0,
			totalCost: 0,
			totalInputTokens: 0,
			totalOutputTokens: 0,
			totalReasoningTokens: 0,
			uniqueModels: [],
			createdAt: currentChatDetails?.created_at ? currentChatDetails.created_at * 1000 : null,
			updatedAt: currentChatDetails?.updated_at ? currentChatDetails.updated_at * 1000 : null
		};

		if (!history || !history.messages) {
			return snapshot;
		}

		const messagesMap: Record<string, any> = history.messages ?? {};
		const messageList = Object.values(messagesMap).filter((message) => !!message) as any[];

		snapshot.totalMessages = messageList.length;

		if (history.currentId) {
			snapshot.currentBranchMessages = createMessagesList(history, history.currentId).length;
		}

		const availableModels = get(models) ?? [];
		const modelLookup = new Map<string, (typeof availableModels)[number]>();
		for (const model of availableModels) {
			if (!model) continue;
			modelLookup.set(model.id, model);
			if (model.name) {
				modelLookup.set(model.name, model);
			}
		}

		const modelsUsed = new Map<
			string,
			{
				id: string;
				label: string;
				icon?: string | null;
				messageCount: number;
			}
		>();

		const registerModel = (identifier?: string | null, labelOverride?: string | null) => {
			if (!identifier) return null;
			const normalizedId = String(identifier).trim();
			if (!normalizedId) return null;

			const matchedModel = modelLookup.get(normalizedId);
			const resolvedLabel = labelOverride?.trim() || matchedModel?.name?.trim() || normalizedId;
			const resolvedIcon = matchedModel?.info?.meta?.profile_image_url ?? null;

			if (modelsUsed.has(normalizedId)) {
				const existing = modelsUsed.get(normalizedId);
				if (existing) {
					if (existing.label === existing.id && resolvedLabel && resolvedLabel !== existing.label) {
						existing.label = resolvedLabel;
					}
					if (!existing.icon && resolvedIcon) {
						existing.icon = resolvedIcon;
					}
				}
				return normalizedId;
			}

			modelsUsed.set(normalizedId, {
				id: normalizedId,
				label: resolvedLabel || normalizedId,
				icon: resolvedIcon,
				messageCount: 0
			});

			return normalizedId;
		};

		const incrementModelUsage = (identifier?: string | null, labelOverride?: string | null) => {
			const registeredId = registerModel(identifier, labelOverride);
			if (registeredId && modelsUsed.has(registeredId)) {
				const entry = modelsUsed.get(registeredId);
				if (entry) {
					entry.messageCount += 1;
				}
				return registeredId;
			}
			return null;
		};

		const extractUsageNumber = (value: unknown): number => {
			if (typeof value === 'number' && Number.isFinite(value)) {
				return value;
			}
			return 0;
		};

		for (const message of messageList) {
			if (!message) continue;

			// Skip user messages - they don't have models
			if (message.role === 'user') {
				// Still count attachments and branches for user messages
				if (Array.isArray(message.files)) {
					snapshot.attachmentCount += message.files.length;
				}
				const children = Array.isArray(message.childrenIds)
					? message.childrenIds.filter((childId) => childId && messagesMap[childId])
					: [];
				if (children.length === 0) {
					snapshot.branchCount += 1;
				}
				continue;
			}

			// Check model field (history uses 'model', cached data may use 'model_id')
			const modelId =
				message.model ?? message.model_id ?? message.selectedModelId ?? message.selected_model_id;
			incrementModelUsage(modelId) ??
				incrementModelUsage('unknown-model', $i18n.t('Unknown Model'));

			if (Array.isArray(message.files)) {
				snapshot.attachmentCount += message.files.length;
			}

			const usage = message.usage || message?.meta?.usage || null;
			if (usage) {
				const totalCost =
					extractUsageNumber(usage.cost) || extractUsageNumber(usage.estimates?.total_cost) || 0;
				const inputTokens =
					extractUsageNumber(usage.prompt_tokens) ||
					extractUsageNumber(usage.prompt_eval_count) ||
					extractUsageNumber(usage.token_usage?.prompt_tokens) ||
					extractUsageNumber(usage.token_usage?.input_tokens);
				const outputTokens =
					extractUsageNumber(usage.completion_tokens) ||
					extractUsageNumber(usage.eval_count) ||
					extractUsageNumber(usage.token_usage?.completion_tokens) ||
					extractUsageNumber(usage.token_usage?.output_tokens);
				const reasoningTokens =
					extractUsageNumber(usage.completion_tokens_details?.reasoning_tokens) ||
					extractUsageNumber(usage.reasoning_tokens) ||
					extractUsageNumber(usage.token_usage?.reasoning_tokens);

				snapshot.totalCost += totalCost;
				snapshot.totalInputTokens += inputTokens;
				snapshot.totalOutputTokens += outputTokens;
				snapshot.totalReasoningTokens += reasoningTokens;
			}

			const children = Array.isArray(message.childrenIds)
				? message.childrenIds.filter((childId) => childId && messagesMap[childId])
				: [];

			if (children.length === 0) {
				snapshot.branchCount += 1;
			}
		}

		snapshot.uniqueModels = Array.from(modelsUsed.values()).sort((a, b) =>
			a.label.localeCompare(b.label, undefined, { sensitivity: 'base' })
		);

		return snapshot;
	};

	const openChatInfo = () => {
		chatInfoSnapshot = buildChatInfoSnapshot();
		showChatInfoModal = true;
	};
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />
<ChatInfoModal
	bind:show={showChatInfoModal}
	stats={chatInfoSnapshot}
	chatTitle={currentChatDetails?.title || $i18n.t('Untitled Chat')}
/>

<nav class="sticky top-0 z-30 w-full py-1.5 -mb-8 flex flex-col items-center drag-region">
	<div class="flex items-center w-full px-1.5">
		<div
			class=" bg-linear-to-b via-50% from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pointer-events-none absolute inset-0 -bottom-7 z-[-1]"
		></div>

		<div class=" flex max-w-full w-full mx-auto px-1 pt-0.5 bg-transparent">
			<div class="flex items-center w-full max-w-full">
				<div
					class="{$showSidebar
						? 'md:hidden'
						: ''} mr-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
				>
					<button
						id="sidebar-toggle-button"
						class="cursor-pointer px-2 py-2 flex rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
						on:click={() => {
							showSidebar.set(!$showSidebar);
						}}
						aria-label="Toggle Sidebar"
					>
						<div class=" m-auto self-center">
							<MenuLines />
						</div>
					</button>
				</div>

				<div
					class="flex-1 max-w-full py-0.5 relative
            {$showSidebar ? 'ml-1' : ''}
            "
				>
					<div class="flex flex-col gap-1">
						<div class="relative flex items-center overflow-visible">
							{#if showModelSelector}
								<div class="flex-shrink-0 z-10" bind:this={modelSelectorElement}>
									<ModelSelector bind:selectedModels showSetDefault={!shareEnabled} />
								</div>
							{/if}

							{#if $chatId && currentChatDetails}
								<button
									bind:this={chatTitleButton}
									class="hidden md:flex flex-col items-center justify-center text-center px-2 pointer-events-auto cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850 rounded-lg transition-colors absolute"
									on:click={handleChatTitleClick}
									aria-label="Navigate to chat location in sidebar"
									data-testid={testId('Chat', 'Navbar', 'ChatTitle', 'Button')}
								>
									{#if currentFolderName}
										<div
											class="text-xs text-gray-500 dark:text-gray-400 truncate whitespace-nowrap"
											data-testid={testId('Chat', 'Navbar', 'ChatTitle', 'FolderName')}
										>
											{currentFolderName}
										</div>
									{/if}
									<div
										class="text-sm font-medium text-gray-700 dark:text-gray-200 truncate whitespace-nowrap"
										data-testid={testId('Chat', 'Navbar', 'ChatTitle', 'Title')}
									>
										{currentChatDetails.title || $i18n.t('Untitled Chat')}
									</div>
								</button>
							{/if}
						</div>
					</div>
				</div>

				<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
					<!-- <div class="md:hidden flex self-center w-[1px] h-5 mx-2 bg-gray-300 dark:bg-stone-700" /> -->
					{#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
						<Menu
							{chat}
							{shareEnabled}
							shareHandler={() => {
								showShareChatModal = !showShareChatModal;
							}}
							downloadHandler={() => {
								showDownloadChatModal = !showDownloadChatModal;
							}}
						>
							<button
								class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								id="chat-context-menu-button"
								data-testid={testId('Chat', 'Navbar', 'ChatContextMenuButton')}
							>
								<div class=" m-auto self-center">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										class="size-5"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M6.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM12.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM18.75 12a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"
										/>
									</svg>
								</div>
							</button>
						</Menu>
					{/if}

					{#if $chatId && currentChatDetails}
						<Tooltip content={$i18n.t('Chat Info')}>
							<button
								class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={openChatInfo}
								aria-label="Chat Info"
								data-testid={testId('Chat', 'Navbar', 'ChatInfoButton')}
							>
								<div class=" m-auto self-center">
									<Info className=" size-5" strokeWidth="1.5" />
								</div>
							</button>
						</Tooltip>
					{/if}

					<Tooltip content={$i18n.t('Controls')}>
						<button
							class=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							on:click={async () => {
								await showControls.set(!$showControls);
							}}
							aria-label="Controls"
							data-testid={testId('Chat', 'Navbar', 'ControlsButton')}
						>
							<div class=" m-auto self-center">
								<AdjustmentsHorizontal className=" size-5" strokeWidth="0.5" />
							</div>
						</button>
					</Tooltip>

					<Tooltip content={$i18n.t('New Chat')}>
						<button
							id="new-chat-button"
							class=" flex {$showSidebar
								? 'md:hidden'
								: ''} cursor-pointer px-2 py-2 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							on:click={() => {
								initNewChat();
							}}
							aria-label="New Chat"
						>
							<div class=" m-auto self-center">
								<PencilSquare className=" size-5" strokeWidth="2" />
							</div>
						</button>
					</Tooltip>

					{#if $user !== undefined && $user !== null}
						<UserMenu
							className="max-w-[200px]"
							role={$user?.role}
							on:show={(e) => {
								if (e.detail === 'archived-chat') {
									showArchivedChats.set(true);
								}
							}}
						>
							<button
								class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								aria-label="User Menu"
								data-testid={testId('Navbar', 'UserMenu', 'Button')}
							>
								<div class=" self-center">
									<img
										src={userImageSrc}
										class="size-6 object-cover rounded-full"
										alt="User profile"
										draggable="false"
									/>
								</div>
							</button>
						</UserMenu>
					{/if}
				</div>
			</div>
		</div>
	</div>

	{#if !history.currentId && !$chatId && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial' || (($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats))}
		<div class=" w-full z-30 mt-5">
			<div class=" flex flex-col gap-1 w-full">
				{#if ($config?.license_metadata?.type ?? null) === 'trial'}
					<Banner
						banner={{
							type: 'info',
							title: 'Trial License',
							content: $i18n.t(
								'You are currently using a trial license. Please contact support to upgrade your license.'
							)
						}}
					/>
				{/if}

				{#if ($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats}
					<Banner
						banner={{
							type: 'error',
							title: 'License Error',
							content: $i18n.t(
								'Exceeded the number of seats in your license. Please contact support to increase the number of seats.'
							)
						}}
					/>
				{/if}

				{#each $banners.filter( (b) => (b.dismissible ? !JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]').includes(b.id) : true) ) as banner}
					<Banner
						{banner}
						on:dismiss={(e) => {
							const bannerId = e.detail;

							localStorage.setItem(
								'dismissedBannerIds',
								JSON.stringify(
									[
										bannerId,
										...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]')
									].filter((id) => $banners.find((b) => b.id === id))
								)
							);
						}}
					/>
				{/each}
			</div>
		</div>
	{/if}
</nav>
