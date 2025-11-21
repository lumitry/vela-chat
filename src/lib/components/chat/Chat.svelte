<script lang="ts">
	import { run } from 'svelte/legacy';

	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';
	import mermaid from 'mermaid';
	import { PaneGroup, Pane, PaneResizer } from 'paneforge';

	import { getContext, onDestroy, onMount, tick } from 'svelte';
	const i18n: Writable<i18nType> = getContext('i18n');

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { get, type Unsubscriber, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import {
		chatId,
		chats,
		config,
		type Model,
		models,
		tags as allTags,
		settings,
		showSidebar,
		WEBUI_NAME,
		banners,
		user,
		socket,
		showControls,
		showCallOverlay,
		currentChatPage,
		temporaryChatEnabled,
		mobile,
		showOverview,
		chatTitle,
		showArtifacts,
		tools,
		toolServers,
		chatCache
	} from '$lib/stores';
	import {
		convertMessagesToHistory,
		copyToClipboard,
		getMessageContentParts,
		createMessagesList,
		extractSentencesForAudio,
		promptTemplate,
		splitStream,
		sleep,
		removeDetails,
		getPromptVariables,
		processDetails
	} from '$lib/utils';

	import { generateChatCompletion } from '$lib/apis/ollama';
	import {
		addTagById,
		createNewChat,
		deleteTagById,
		deleteTagsById,
		getAllTags,
		getChatList,
		getTagsById,
		updateChatById,
		getChatMetaById,
		getChatById,
		getChatSync,
		getMessagesBatch
	} from '$lib/apis/chats';
	import {
		initMessageDB,
		getMessagesByChatId,
		getMessagesByIds,
		bulkPutMessages,
		deleteMessagesByChatId,
		isIndexedDBAvailable
	} from '$lib/utils/indexeddb';
	import xxhashWasm from 'xxhash-wasm';
	import { generateOpenAIChatCompletion } from '$lib/apis/openai';

	// Initialize XXHash (async, but we'll await it when needed)
	let xxhash64: ((data: string) => bigint) | null = null;
	const getXXHash = async () => {
		if (!xxhash64) {
			const { h64 } = await xxhashWasm();
			xxhash64 = (data: string) => h64(data);
		}
		return xxhash64;
	};
	import { processWeb, processWebSearch, processYoutubeVideo } from '$lib/apis/retrieval';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import { queryMemory } from '$lib/apis/memories';
	import { getAndUpdateUserLocation, getUserSettings } from '$lib/apis/users';
	import {
		chatCompleted,
		generateQueries,
		chatAction,
		generateMoACompletion,
		stopTask,
		getTaskIdsByChatId
	} from '$lib/apis';
	import { getTools } from '$lib/apis/tools';

	import Banner from '../common/Banner.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import ChatControls from './ChatControls.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import NotificationToast from '../NotificationToast.svelte';
	import Spinner from '../common/Spinner.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Switch from '$lib/components/common/Switch.svelte';

	interface Props {
		chatIdProp?: string;
	}

	let { chatIdProp = '' }: Props = $props();

	// Helper function to strip files array and data.file_ids from collection objects
	const stripCollectionFiles = (file) => {
		if (file?.type === 'collection') {
			const { files, data, ...rest } = file;
			const stripped = { ...rest };
			// Keep data but remove file_ids if present
			if (data && typeof data === 'object') {
				const { file_ids, ...dataRest } = data;
				if (Object.keys(dataRest).length > 0) {
					stripped.data = dataRest;
				}
			}
			return stripped;
		}
		return file;
	};

	let loading = $state(false);

	const eventTarget = new EventTarget();

	// Helper function to cache a message in IndexedDB
	const cacheMessage = async (message: any, chatId: string) => {
		if (!isIndexedDBAvailable() || !message?.id) {
			return;
		}

		try {
			// Compute cache key (same as backend - uses content length for performance)
			// Use Array.from() to count Unicode code points (like Python len()), not UTF-16 code units
			// Use XXHash for fast non-cryptographic hashing (much faster than SHA-256)
			const content = message.content || '';
			const content_length = Array.from(content).length; // Count code points, not UTF-16 units
			const updated_at = String(message.timestamp || message.updated_at || Date.now());
			const role = message.role || '';
			const model_id = message.model || message.model_id || '';
			const combined = `${content_length}${updated_at}${role}${model_id}`;
			const hasher = await getXXHash();
			const cache_key = hasher(combined).toString(16).padStart(16, '0');

			// Build meta object, including merged property if present
			// Backend stores merged in meta.merged, so we do the same for consistency
			const meta = message.meta ? { ...message.meta } : {};
			if (message.merged) {
				meta.merged = message.merged;
			}

			const cachedMessage = {
				id: message.id,
				chat_id: chatId,
				parent_id: message.parentId || null,
				role: message.role,
				model_id: message.model || message.model_id || null,
				position: message.position || null,
				content: message.content || '',
				content_json: message.content_json || null,
				status: message.status || null,
				usage: message.usage || null,
				meta: Object.keys(meta).length > 0 ? meta : null,
				annotation: message.annotation || null,
				feedback_id: message.feedbackId || message.feedback_id || null,
				selected_model_id: message.selectedModelId || message.selected_model_id || null,
				files: message.files || null,
				sources: message.sources || null,
				created_at: message.timestamp || message.created_at || Math.floor(Date.now() / 1000),
				updated_at: message.timestamp || message.updated_at || Math.floor(Date.now() / 1000),
				cache_key: cache_key,
				cached_at: Date.now(),
				modelIdx: message.modelIdx ?? null, // Root-level property, not in meta
				modelName: message.modelName ?? null, // Root-level property, not in meta
				models: message.models ?? null, // Root-level property for side-by-side chats
				children_ids: message.childrenIds || [] // CRITICAL: Store children IDs for message tree structure
			};

			await bulkPutMessages([cachedMessage]);
		} catch (error) {
			console.warn('Failed to cache message in IndexedDB:', error);
			// Don't throw - caching failure shouldn't break the app
		}
	};
	let controlPane = $state();
	let controlPaneComponent = $state();

	let autoScroll = $state(true);
	let processing = '';
	let messagesContainerElement: HTMLDivElement = $state();

	let navbarElement = $state();

	let showEventConfirmation = $state(false);
	let eventConfirmationTitle = $state('');
	let eventConfirmationMessage = $state('');
	let eventConfirmationInput = $state(false);
	let eventConfirmationInputPlaceholder = $state('');
	let eventConfirmationInputValue = $state('');
	let eventCallback = $state(null);

	let chatIdUnsubscriber: Unsubscriber | undefined;

	let selectedModels = $state(['']);
	let atSelectedModel: Model | undefined = $state();
	let selectedModelIds = $state([]);

	let selectedToolIds = $state([]);
	let imageGenerationEnabled = $state(false);
	let webSearchEnabled = $state(false);
	let codeInterpreterEnabled = $state(false);

	let chat = null;
	let tags = [];

	let history = $state({
		messages: {},
		currentId: null
	});

	let taskIds = $state(null);

	// Chat Input
	let prompt = $state('');
	let chatFiles = $state([]);
	let files = $state([]);
	let params = $state({});
	let lastChatId = $state('');

	// Module-level timer for token speed calculation
	let tokenTimerStart = 0;
	let firstTokenReceived = false;
	let isStreamingResponse = false;
	let streamRequestStart = 0; // Timer for when streaming request was initiated

	// Load chat and handle message linking, triggered when chatIdProp changes
	async function loadAndLink() {
		loading = true;

		prompt = '';
		files = [];
		selectedToolIds = [];
		webSearchEnabled = false;
		imageGenerationEnabled = false;

		if (chatIdProp && (await loadChat())) {
			await tick();
			loading = false;

			const saved = localStorage.getItem(`chat-input-${chatIdProp}`);
			if (saved) {
				try {
					const input = JSON.parse(saved);
					prompt = input.prompt;
					files = input.files;
					selectedToolIds = input.selectedToolIds;
					webSearchEnabled = input.webSearchEnabled;
					imageGenerationEnabled = input.imageGenerationEnabled;
				} catch {}
			}

			document.getElementById('chat-input')?.focus();
			// Scroll: if linking to a message, scroll to it; else scroll to bottom
			const targetMessageId = $page.url.searchParams.get('message');
			if (targetMessageId && history.messages[targetMessageId]) {
				await showMessage({ id: targetMessageId });
			} else {
				setTimeout(() => scrollToBottom(), 0);
			}
		} else {
			await goto('/');
		}
	}


	// Watch for URL changes when on home page (no chatId) to trigger initNewChat
	let lastUrlQuery = $state('');


	const saveSessionSelectedModels = () => {
		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			return;
		}
		sessionStorage.selectedModels = JSON.stringify(selectedModels);
		console.log('saveSessionSelectedModels', selectedModels, sessionStorage.selectedModels);
	};

	// When models load and we're on a new chat page, set the selected model
	// Guard against race conditions with initNewChat
	let modelSelectionInProgress = $state(false);


	const setToolIds = async () => {
		if (!$tools) {
			tools.set(await getTools(localStorage.token));
		}

		if (selectedModels.length !== 1 && !atSelectedModel) {
			return;
		}

		const model = atSelectedModel ?? $models.find((m) => m.id === selectedModels[0]);
		if (model) {
			selectedToolIds = (model?.info?.meta?.toolIds ?? []).filter((id) =>
				$tools.find((t) => t.id === id)
			);
		}
	};

	const showMessage = async (
		message,
		options: { skipSave?: boolean; scrollToHighlight?: boolean; occurrenceIndex?: number } = {}
	) => {
		const { skipSave = false, scrollToHighlight = false, occurrenceIndex = 0 } = options;
		const _chatId = JSON.parse(JSON.stringify($chatId));
		let _messageId = JSON.parse(JSON.stringify(message.id));

		let messageChildrenIds = [];
		if (_messageId === null) {
			messageChildrenIds = Object.keys(history.messages).filter(
				(id) => history.messages[id].parentId === null
			);
		} else {
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		while (messageChildrenIds.length !== 0) {
			_messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		history.currentId = _messageId;

		await tick();
		await tick();
		await tick();

		const messageElement = document.getElementById(`message-${message.id}`);
		if (messageElement) {
			if (scrollToHighlight) {
				// Wait a bit more for highlighting to be applied
				await tick();
				await new Promise((resolve) => setTimeout(resolve, 50));

				// Find all highlighted text (mark elements) within this message
				const highlightedElements = messageElement.querySelectorAll('mark');
				if (highlightedElements.length > 0) {
					// Navigate to the specific occurrence (or first if index is out of bounds)
					const targetIndex = Math.min(occurrenceIndex, highlightedElements.length - 1);
					const highlightedElement = highlightedElements[targetIndex];
					if (highlightedElement) {
						// Scroll to center the highlighted text
						highlightedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
					} else {
						// Fallback to scrolling the message if no highlight found
						messageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
					}
				} else {
					// Fallback to scrolling the message if no highlight found
					messageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
				}
			} else {
				messageElement.scrollIntoView({ behavior: 'smooth' });
			}
		}

		await tick();
		if (!skipSave) {
			saveChatHandler(_chatId, history);
		}
	};

	const chatEventHandler = async (event, cb) => {
		console.log(event);

		if (event.chat_id === $chatId) {
			await tick();
			let message = history.messages[event.message_id];

			if (message) {
				const type = event?.data?.type ?? null;
				const data = event?.data?.data ?? null;

				if (type === 'status') {
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, message, event.chat_id);
				} else if (type === 'chat:message:delta' || type === 'message') {
					message.content += data.content;
				} else if (type === 'chat:message' || type === 'replace') {
					message.content = data.content;
				} else if (type === 'chat:message:files' || type === 'files') {
					message.files = data.files;
				} else if (type === 'chat:title') {
					chatTitle.set(data);
					currentChatPage.set(1);
					await chats.set(await getChatList(localStorage.token, $currentChatPage));
				} else if (type === 'chat:tags') {
					chat = await getChatById(localStorage.token, $chatId);
					allTags.set(await getAllTags(localStorage.token));
				} else if (type === 'source' || type === 'citation') {
					if (data?.type === 'code_execution') {
						// Code execution; update existing code execution by ID, or add new one.
						if (!message?.code_executions) {
							message.code_executions = [];
						}

						const existingCodeExecutionIndex = message.code_executions.findIndex(
							(execution) => execution.id === data.id
						);

						if (existingCodeExecutionIndex !== -1) {
							message.code_executions[existingCodeExecutionIndex] = data;
						} else {
							message.code_executions.push(data);
						}

						message.code_executions = message.code_executions;
					} else {
						// Regular source.
						if (message?.sources) {
							message.sources.push(data);
						} else {
							message.sources = [data];
						}
					}
				} else if (type === 'notification') {
					const toastType = data?.type ?? 'info';
					const toastContent = data?.content ?? '';

					if (toastType === 'success') {
						toast.success(toastContent);
					} else if (toastType === 'error') {
						toast.error(toastContent);
					} else if (toastType === 'warning') {
						toast.warning(toastContent);
					} else {
						toast.info(toastContent);
					}
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
				} else if (type === 'execute') {
					eventCallback = cb;

					try {
						// Use Function constructor to evaluate code in a safer way
						const asyncFunction = new Function(`return (async () => { ${data.code} })()`);
						const result = await asyncFunction(); // Await the result of the async function

						if (cb) {
							cb(result);
						}
					} catch (error) {
						console.error('Error executing code:', error);
					}
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
				} else {
					console.log('Unknown message type', data);
				}

				history.messages[event.message_id] = message;
			}
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		if (event.origin !== window.origin) {
			return;
		}

		// Replace with your iframe's origin
		if (event.data.type === 'input:prompt') {
			console.debug(event.data.text);

			const inputElement = document.getElementById('chat-input');

			if (inputElement) {
				prompt = event.data.text;
				inputElement.focus();
			}
		}

		if (event.data.type === 'action:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitPrompt(prompt);
			}
		}

		if (event.data.type === 'input:prompt:submit') {
			console.debug(event.data.text);

			if (event.data.text !== '') {
				await tick();
				submitPrompt(event.data.text);
			}
		}
	};

	// Handle model updates from command palette
	function handleModelUpdate(event: CustomEvent) {
		const { chatId: updatedChatId, models: newModels } = event.detail;
		if (updatedChatId === chatIdProp && newModels && newModels.length > 0) {
			selectedModels = newModels;
			// Also update the cache entry if it exists
			chatCache.update((cache) => {
				const cached = cache.get(updatedChatId);
				if (cached && cached.chat) {
					cached.chat.models = newModels;
					cache.set(updatedChatId, cached);
				}
				return cache;
			});
		}
	}

	onMount(async () => {
		window.addEventListener('chat-model-updated', handleModelUpdate as EventListener);
		console.log('mounted');
		window.addEventListener('message', onMessageHandler);
		$socket?.on('chat-events', chatEventHandler);

		if (!$chatId) {
			// Initialize new chat on mount if we're on home page
			if ($page.url.pathname === '/') {
				await tick();
				await initNewChat();
			}

			chatIdUnsubscriber = chatId.subscribe(async (value) => {
				if (!value) {
					await tick(); // Wait for DOM updates
					await initNewChat();
				}
			});
		} else {
			if ($temporaryChatEnabled) {
				await goto('/');
			}
		}

		if (localStorage.getItem(`chat-input-${chatIdProp}`)) {
			try {
				const input = JSON.parse(localStorage.getItem(`chat-input-${chatIdProp}`));
				prompt = input.prompt;
				files = input.files;
				selectedToolIds = input.selectedToolIds;
				webSearchEnabled = input.webSearchEnabled;
				imageGenerationEnabled = input.imageGenerationEnabled;
			} catch (e) {
				prompt = '';
				files = [];
				selectedToolIds = [];
				webSearchEnabled = false;
				imageGenerationEnabled = false;
			}
		}

		showControls.subscribe(async (value) => {
			if (controlPane && !$mobile) {
				try {
					if (value) {
						controlPaneComponent.openPane();
					} else {
						controlPane.collapse();
					}
				} catch (e) {
					// ignore
				}
			}

			if (!value) {
				showCallOverlay.set(false);
				showOverview.set(false);
				showArtifacts.set(false);
			}
		});

		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		chats.subscribe(() => {});
	});

	onDestroy(() => {
		window.removeEventListener('chat-model-updated', handleModelUpdate as EventListener);
		chatIdUnsubscriber?.();
		window.removeEventListener('message', onMessageHandler);
		$socket?.off('chat-events', chatEventHandler);
	});

	// File upload functions

	const uploadGoogleDriveFile = async (fileData) => {
		console.log('Starting uploadGoogleDriveFile with:', {
			id: fileData.id,
			name: fileData.name,
			url: fileData.url,
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		// Validate input
		if (!fileData?.id || !fileData?.name || !fileData?.url || !fileData?.headers?.Authorization) {
			throw new Error('Invalid file data provided');
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: fileData.url,
			name: fileData.name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: 0
		};

		try {
			files = [...files, fileItem];
			console.log('Processing web file with URL:', fileData.url);

			// Configure fetch options with proper headers
			const fetchOptions = {
				headers: {
					Authorization: fileData.headers.Authorization,
					Accept: '*/*'
				},
				method: 'GET'
			};

			// Attempt to fetch the file
			console.log('Fetching file content from Google Drive...');
			const fileResponse = await fetch(fileData.url, fetchOptions);

			if (!fileResponse.ok) {
				const errorText = await fileResponse.text();
				throw new Error(`Failed to fetch file (${fileResponse.status}): ${errorText}`);
			}

			// Get content type from response
			const contentType = fileResponse.headers.get('content-type') || 'application/octet-stream';
			console.log('Response received with content-type:', contentType);

			// Convert response to blob
			console.log('Converting response to blob...');
			const fileBlob = await fileResponse.blob();

			if (fileBlob.size === 0) {
				throw new Error('Retrieved file is empty');
			}

			console.log('Blob created:', {
				size: fileBlob.size,
				type: fileBlob.type || contentType
			});

			// Create File object with proper MIME type
			const file = new File([fileBlob], fileData.name, {
				type: fileBlob.type || contentType
			});

			console.log('File object created:', {
				name: file.name,
				size: file.size,
				type: file.type
			});

			if (file.size === 0) {
				throw new Error('Created file is empty');
			}

			// Upload file to server
			console.log('Uploading file to server...');
			const uploadedFile = await uploadFile(localStorage.token, file);

			if (!uploadedFile) {
				throw new Error('Server returned null response for file upload');
			}

			console.log('File uploaded successfully:', uploadedFile);

			// Update file item with upload results
			fileItem.status = 'uploaded';
			fileItem.file = uploadedFile;
			fileItem.id = uploadedFile.id;
			fileItem.size = file.size;
			fileItem.collection_name = uploadedFile?.meta?.collection_name;
			fileItem.url = `${WEBUI_API_BASE_URL}/files/${uploadedFile.id}`;

			files = files;
			toast.success($i18n.t('File uploaded successfully'));
		} catch (e) {
			console.error('Error uploading file:', e);
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error(
				$i18n.t('Error uploading file: {{error}}', {
					error: e.message || 'Unknown error'
				})
			);
		}
	};

	const uploadWeb = async (url) => {
		console.log(url);

		const fileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processWeb(localStorage.token, '', url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};

				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(JSON.stringify(e));
		}
	};

	const uploadYoutubeTranscription = async (url) => {
		console.log(url);

		const fileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			context: 'full',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processYoutubeVideo(localStorage.token, url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};
				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(`${e}`);
		}
	};

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		// Wait for models to be loaded before proceeding
		if ($models.length === 0) {
			// Wait up to 5 seconds for models to load
			let attempts = 0;
			while ($models.length === 0 && attempts < 50) {
				await tick();
				await new Promise((resolve) => setTimeout(resolve, 100));
				attempts++;
			}
		}

		if ($page.url.searchParams.get('models')) {
			selectedModels = $page.url.searchParams.get('models')?.split(',');
		} else if ($page.url.searchParams.get('model')) {
			const urlModels = $page.url.searchParams.get('model')?.split(',');

			if (urlModels.length === 1) {
				const m = $models.find((m) => m.id === urlModels[0]);
				if (!m) {
					const modelSelectorButton = document.getElementById('model-selector-0-button');
					if (modelSelectorButton) {
						modelSelectorButton.click();
						await tick();

						const modelSelectorInput = document.getElementById('model-search-input');
						if (modelSelectorInput) {
							modelSelectorInput.focus();
							modelSelectorInput.value = urlModels[0];
							modelSelectorInput.dispatchEvent(new Event('input'));
						}
					}
				} else {
					selectedModels = urlModels;
				}
			} else {
				selectedModels = urlModels;
			}
		} else {
			if (sessionStorage.selectedModels) {
				selectedModels = JSON.parse(sessionStorage.selectedModels);
				sessionStorage.removeItem('selectedModels');
			} else {
				if ($settings?.models) {
					selectedModels = $settings?.models;
				} else if ($config?.default_models) {
					console.log($config?.default_models.split(',') ?? '');
					selectedModels = $config?.default_models.split(',');
				}
			}
		}

		selectedModels = selectedModels.filter((modelId) => $models.map((m) => m.id).includes(modelId));
		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			if ($models.length > 0) {
				selectedModels = [$models[0].id];
			} else {
				// If still no models, wait a bit more and try again
				await new Promise((resolve) => setTimeout(resolve, 200));
				if ($models.length > 0) {
					selectedModels = [$models[0].id];
				} else {
					selectedModels = [''];
				}
			}
		}

		await showControls.set(false);
		await showCallOverlay.set(false);
		await showOverview.set(false);
		await showArtifacts.set(false);

		if ($page.url.pathname.includes('/c/')) {
			window.history.replaceState(history.state, '', `/`);
		}

		autoScroll = true;

		await chatId.set('');
		await chatTitle.set('');

		history = {
			messages: {},
			currentId: null
		};

		// Handle knowledge base from URL or sessionStorage AFTER clearing chatFiles
		const knowledgeBaseId = $page.url.searchParams.get('knowledge-base');
		if (knowledgeBaseId) {
			try {
				const kbData = sessionStorage.getItem('commandPaletteKnowledgeBase');
				if (kbData) {
					const kb = JSON.parse(kbData);
					console.log('kb', kb);
					// Add knowledge base as a file attachment
					// Knowledge bases use type: 'collection' (not 'knowledge')
					// The structure should match what Knowledge.svelte creates
					chatFiles = [
						{
							type: 'collection',
							id: knowledgeBaseId,
							name: kb.name || 'Knowledge Base',
							description: kb.description,
							collection_name: knowledgeBaseId,
							status: 'processed'
						}
					];
					sessionStorage.removeItem('commandPaletteKnowledgeBase');
				}
			} catch (error) {
				console.error('Failed to attach knowledge base:', error);
			}
		} else {
			chatFiles = [];
		}
		params = {};

		if ($page.url.searchParams.get('youtube')) {
			uploadYoutubeTranscription(
				`https://www.youtube.com/watch?v=${$page.url.searchParams.get('youtube')}`
			);
		}
		if ($page.url.searchParams.get('web-search') === 'true') {
			webSearchEnabled = true;
		}

		if ($page.url.searchParams.get('image-generation') === 'true') {
			imageGenerationEnabled = true;
		}

		if ($page.url.searchParams.get('tools')) {
			selectedToolIds = $page.url.searchParams
				.get('tools')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		} else if ($page.url.searchParams.get('tool-ids')) {
			selectedToolIds = $page.url.searchParams
				.get('tool-ids')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		}

		if ($page.url.searchParams.get('call') === 'true') {
			showCallOverlay.set(true);
			showControls.set(true);
		}

		if ($page.url.searchParams.get('q')) {
			const queryPrompt = $page.url.searchParams.get('q') ?? '';
			prompt = queryPrompt;

			console.log('queryPrompt', queryPrompt);

			if (queryPrompt) {
				// Wait for component to be fully ready before submitting
				// Use a more robust waiting mechanism
				const waitForReady = async (maxAttempts = 20) => {
					for (let i = 0; i < maxAttempts; i++) {
						await tick();
						console.log('not yet ready, waiting for 100ms');
						await new Promise((resolve) => setTimeout(resolve, 100));

						// Check if models are ready and valid
						const validModels = selectedModels.filter(
							(modelId) => modelId && modelId !== '' && $models.map((m) => m.id).includes(modelId)
						);

						if (validModels.length > 0 && $models.length > 0 && !loading) {
							selectedModels = validModels;
							await tick();
							return true;
						}
					}
					return false;
				};

				const isReady = await waitForReady();
				if (isReady) {
					submitPrompt(queryPrompt);
				} else {
					// Fallback: set prompt and let user submit manually
					prompt = queryPrompt;
					console.warn('Component not ready for auto-submit, prompt set for manual submission');
				}
			}
		}

		selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);

		// Settings are already loaded in app layout, no need to fetch again
		// Just focus the chat input
		const chatInput = document.getElementById('chat-input');
		setTimeout(() => chatInput?.focus(), 0);
	};

	const loadChat = async () => {
		chatId.set(chatIdProp);

		// Check cache first for prefetched data
		const cache = $chatCache;
		let cachedFullChat = cache.get($chatId);

		let chatMeta;
		let fullChat;

		if (cachedFullChat) {
			// Use cached data - extract metadata from cached full chat
			fullChat = cachedFullChat;
			// Extract metadata from the cached chat structure
			// getChatById returns { id, title, chat: { title, models, params, files, history } }
			const chatData = cachedFullChat.chat || {};
			chatMeta = {
				title: chatData.title || cachedFullChat.title,
				models: chatData.models,
				params: chatData.params,
				files: chatData.files
			};
			// Skip API call for metadata since we have the full chat
		} else {
			// Not in cache, fetch from API
			chatMeta = await getChatMetaById(localStorage.token, $chatId).catch(async (error) => {
				await goto('/');
				return null;
			});
		}

		if (chatMeta) {
			tags = await getTagsById(localStorage.token, $chatId).catch(async (error) => {
				return [];
			});

			const chatContent = {
				title: chatMeta.title,
				models: chatMeta.models,
				params: chatMeta.params,
				files: chatMeta.files
			};

			if (chatContent) {
				console.log(chatContent);

				selectedModels =
					(chatContent?.models ?? undefined) !== undefined
						? chatContent.models
						: [chatContent.models ?? ''];

				// Differential sync: Use IndexedDB cache if available, otherwise fall back to full fetch
				try {
					let useDifferentialSync = isIndexedDBAvailable();
					let syncData = null;
					let cachedMessages: any[] = [];
					let messagesToFetch: string[] = [];

					if (useDifferentialSync) {
						try {
							// Try differential sync
							syncData = await getChatSync(localStorage.token, $chatId);

							if (syncData && syncData.history && syncData.history.messages) {
								// Get cached messages from IndexedDB
								cachedMessages = await getMessagesByChatId($chatId);

								// Build map of cached messages by ID
								const cachedMap = new Map(cachedMessages.map((m) => [m.id, m]));

								// Compare cache_keys to find missing/outdated messages
								const serverMessages = syncData.history.messages;
								const serverMessageIds = Object.keys(serverMessages);

								// Check if server has fewer messages than cache (trust server)
								if (serverMessageIds.length < cachedMessages.length) {
									console.warn(
										`Server has fewer messages (${serverMessageIds.length}) than cache (${cachedMessages.length}), clearing cache for chat ${$chatId}`
									);
									await deleteMessagesByChatId($chatId);
									cachedMessages = [];
									cachedMap.clear();
								}

								// Find messages that need to be fetched
								for (const msgId of serverMessageIds) {
									const serverMsg = serverMessages[msgId];
									const cachedMsg = cachedMap.get(msgId);

									if (!cachedMsg || cachedMsg.cache_key !== serverMsg.cache_key) {
										messagesToFetch.push(msgId);
									}
								}

								// Fetch missing messages in batches
								if (messagesToFetch.length > 0) {
									console.log(
										`Fetching ${messagesToFetch.length} missing/outdated messages for chat ${$chatId}`
									);
									const batchResponse = await getMessagesBatch(
										localStorage.token,
										$chatId,
										messagesToFetch
									);

									if (batchResponse && batchResponse.messages) {
										// Convert batch messages to cached format
										const messagesToCache = batchResponse.messages.map((msg: any) => {
											// Extract modelIdx, modelName, and models from meta if present (backend stores them in meta)
											// but frontend expects them at root level
											let modelIdx = msg.modelIdx ?? null;
											let modelName = msg.modelName ?? null;
											let models = msg.models ?? null;
											if (msg.meta && typeof msg.meta === 'object') {
												if (modelIdx === null && 'modelIdx' in msg.meta) {
													modelIdx = msg.meta.modelIdx;
												}
												if (modelName === null && 'modelName' in msg.meta) {
													modelName = msg.meta.modelName;
												}
												if (models === null && 'models' in msg.meta) {
													models = msg.meta.models;
												}
											}

											// Extract statusHistory from status.statusHistory if present
											// We store status as-is (with statusHistory inside it), but also need to handle
											// the case where statusHistory might already be at root level from backend
											let status = msg.status || null;
											if (status && typeof status === 'object' && status.statusHistory) {
												// status already has statusHistory inside it, which is what we want to store
												// The extraction to root level happens when restoring from cache
											}

											return {
												id: msg.id,
												chat_id: $chatId,
												parent_id: msg.parent_id,
												role: msg.role,
												model_id: msg.model_id,
												position: msg.position ?? null,
												content: msg.content_text || msg.content || '',
												content_json: msg.content_json || null,
												status: status, // Store status as-is (may contain statusHistory inside it)
												usage: msg.usage || null,
												meta: msg.meta || null,
												annotation: msg.annotation || null,
												feedback_id: msg.feedback_id || null,
												selected_model_id: msg.selected_model_id || null,
												files: msg.files || null,
												sources: msg.sources || null,
												created_at: msg.created_at || 0,
												updated_at: msg.updated_at || 0,
												cache_key: msg.cache_key,
												cached_at: Date.now(),
												modelIdx: modelIdx, // Root-level property
												modelName: modelName, // Root-level property
												models: models, // Root-level property for side-by-side chats
												children_ids: syncData?.history?.messages?.[msg.id]?.children_ids || [] // Get children_ids from sync data
											};
										});

										// Bulk insert/update in IndexedDB
										await bulkPutMessages(messagesToCache);

										// Update cached messages map
										for (const msg of messagesToCache) {
											cachedMap.set(msg.id, msg);
										}
									}
								}

								// Load all messages from IndexedDB (now up to date)
								cachedMessages = await getMessagesByChatId($chatId);
							} else {
								// Sync endpoint returned legacy format or no messages, fall back
								useDifferentialSync = false;
							}
						} catch (syncError) {
							console.warn('Differential sync failed, falling back to full fetch:', syncError);
							// If quota exceeded, clear cache and retry once
							if (syncError instanceof DOMException && syncError.name === 'QuotaExceededError') {
								console.warn('IndexedDB quota exceeded, clearing cache...');
								try {
									const { clearAllMessages } = await import('$lib/utils/indexeddb');
									await clearAllMessages();
								} catch (clearError) {
									console.error('Failed to clear cache:', clearError);
								}
							}
							useDifferentialSync = false;
						}
					}

					// If differential sync didn't work, fall back to full fetch
					if (!useDifferentialSync || cachedMessages.length === 0) {
						if (!fullChat) {
							fullChat = await getChatById(localStorage.token, $chatId);
							// Cache the fetched data (LRU will evict oldest if at max size)
							if (fullChat) {
								chatCache.update((cache) => {
									cache.set($chatId, fullChat);
									return cache;
								});
							}
						}

						if (fullChat?.chat?.history?.messages) {
							// Convert legacy format to frontend history structure
							const messagesMap = fullChat.chat.history.messages;
							let currentId = fullChat.chat.history.currentId || null;

							// JOIN operation: Populate content, sources, and files in messages array from history.messages
							if (fullChat.chat.messages && Array.isArray(fullChat.chat.messages)) {
								for (const message of fullChat.chat.messages) {
									if (message && message.id) {
										const messageId = String(message.id);
										if (messageId in messagesMap) {
											const historyMsg = messagesMap[messageId];
											if (!message.content && historyMsg.content) {
												message.content = historyMsg.content;
											}
											if (!message.sources && historyMsg.sources) {
												message.sources = historyMsg.sources;
											}
											if (!message.files && historyMsg.files) {
												message.files = historyMsg.files;
											}
											for (const key in historyMsg) {
												if (key !== 'id' && (message[key] === undefined || message[key] === null)) {
													message[key] = historyMsg[key];
												}
											}
										}
									}
								}
							}

							// Sort childrenIds for all messages (by position, then created_at - same as backend)
							// This ensures sibling messages are displayed in the correct order
							for (const msgId in messagesMap) {
								const msg = messagesMap[msgId];
								if (msg.childrenIds && msg.childrenIds.length > 0) {
									msg.childrenIds = [...msg.childrenIds].sort((id1, id2) => {
										const child1 = messagesMap[id1];
										const child2 = messagesMap[id2];
										if (!child1 || !child2) return 0;

										// Sort by position first (ASC), then by created_at (ASC)
										// Backend: order_by(ChatMessage.position.asc(), ChatMessage.created_at.asc())
										// For legacy messages with null positions, treat null as coming before numeric positions
										// This ensures older messages (with null) come before newer messages (with 0)
										const pos1 = child1.position;
										const pos2 = child2.position;

										// Handle null positions: null comes before all numeric positions (for legacy compatibility)
										if (pos1 === null && pos2 === null) {
											// Both null - sort by created_at
											const created1 = child1.timestamp || child1.created_at || 0;
											const created2 = child2.timestamp || child2.created_at || 0;
											return created1 - created2;
										} else if (pos1 === null) {
											return -1; // pos1 is null, comes before pos2 (legacy message)
										} else if (pos2 === null) {
											return 1; // pos2 is null, comes before pos1 (legacy message)
										} else {
											// Both are numeric
											if (pos1 !== pos2) {
												return pos1 - pos2;
											}
											// If positions are equal, sort by created_at
											const created1 = child1.timestamp || child1.created_at || 0;
											const created2 = child2.timestamp || child2.created_at || 0;
											return created1 - created2;
										}
									});
								}
							}

							// Validate currentId
							if (currentId && !messagesMap[currentId]) {
								console.warn(
									`currentId ${currentId} not found in messages, finding valid leaf message`
								);
								const leafMessages = Object.values(messagesMap).filter((msg: any) => {
									if (!msg.childrenIds || msg.childrenIds.length === 0) return true;
									return !msg.childrenIds.some((childId: string) => messagesMap[childId]);
								});
								if (leafMessages.length > 0) {
									leafMessages.sort((a: any, b: any) => (b.timestamp || 0) - (a.timestamp || 0));
									currentId = leafMessages[0].id;
								} else {
									const allMessages = Object.values(messagesMap) as any[];
									if (allMessages.length > 0) {
										allMessages.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
										currentId = allMessages[0].id;
									} else {
										currentId = null;
									}
								}
							}

							history = {
								messages: messagesMap,
								currentId: currentId
							};

							// Cache messages in IndexedDB if available (for next time)
							if (isIndexedDBAvailable() && messagesMap) {
								try {
									const hasher = await getXXHash();
									const messagesToCache = await Promise.all(
										Object.values(messagesMap).map(async (msg: any) => {
											// Compute cache key (same as backend - uses content length for performance)
											// Use Array.from() to count Unicode code points (like Python len()), not UTF-16 code units
											// Use XXHash for fast non-cryptographic hashing (much faster than SHA-256)
											const content = msg.content || '';
											const content_length = Array.from(content).length; // Count code points, not UTF-16 units
											const updated_at = String(msg.timestamp || msg.updated_at || 0);
											const role = msg.role || '';
											const model_id = msg.model || msg.model_id || '';
											const combined = `${content_length}${updated_at}${role}${model_id}`;
											const cache_key = hasher(combined).toString(16).padStart(16, '0');

											// Build meta object, including merged property if present
											// Backend stores merged in meta.merged, so we do the same for consistency
											const meta = msg.meta ? { ...msg.meta } : {};
											if (msg.merged) {
												meta.merged = msg.merged;
											}

											return {
												id: msg.id,
												chat_id: $chatId,
												parent_id: msg.parentId || null,
												role: msg.role,
												model_id: msg.model || msg.model_id || null,
												position: msg.position || null,
												content: msg.content || '',
												content_json: msg.content_json || null,
												status: msg.status || null,
												usage: msg.usage || null,
												meta: Object.keys(meta).length > 0 ? meta : null,
												annotation: msg.annotation || null,
												feedback_id: msg.feedbackId || msg.feedback_id || null,
												selected_model_id: msg.selectedModelId || msg.selected_model_id || null,
												files: msg.files || null,
												sources: msg.sources || null,
												created_at: msg.timestamp || msg.created_at || 0,
												updated_at: msg.timestamp || msg.updated_at || 0,
												cache_key: cache_key,
												cached_at: Date.now(),
												modelIdx: msg.modelIdx ?? null, // Root-level property
												modelName: msg.modelName ?? null, // Root-level property
												models: msg.models ?? null, // Root-level property for side-by-side chats
												children_ids: msg.childrenIds || [] // CRITICAL: Store children IDs for message tree structure
											};
										})
									);

									await bulkPutMessages(messagesToCache);
								} catch (cacheError) {
									console.warn('Failed to cache messages in IndexedDB:', cacheError);
								}
							}
						} else {
							history = convertMessagesToHistory([]);
						}
					} else {
						// Build history from IndexedDB cached messages
						const messagesMap: Record<string, any> = {};

						for (const cachedMsg of cachedMessages) {
							// Extract statusHistory from status.statusHistory and put at root level
							// Frontend expects both status and statusHistory at root level
							let statusHistory = null;
							let status = null;

							if (cachedMsg.status && typeof cachedMsg.status === 'object') {
								// Extract statusHistory if present
								if (cachedMsg.status.statusHistory !== undefined) {
									statusHistory = cachedMsg.status.statusHistory;
								}

								// Only set status if it has meaningful content
								// If status only has statusHistory: null, treat it as null
								const statusKeys = Object.keys(cachedMsg.status);
								const hasMeaningfulContent = statusKeys.some((key) => {
									const value = cachedMsg.status[key];
									// Check if value is not null/undefined and not an empty array
									if (value === null || value === undefined) return false;
									if (Array.isArray(value) && value.length === 0) return false;
									// statusHistory can be null, but if it's the only key, status should be null
									if (key === 'statusHistory' && value === null && statusKeys.length === 1)
										return false;
									return true;
								});

								if (hasMeaningfulContent) {
									status = cachedMsg.status;
								}
							}

							// Convert cached message to frontend format
							// Use cached children_ids if available, fall back to sync data
							let childrenIds =
								cachedMsg.children_ids && cachedMsg.children_ids.length > 0
									? cachedMsg.children_ids
									: syncData?.history?.messages?.[cachedMsg.id]?.children_ids || [];

							// Sort childrenIds by position and created_at (same as backend)
							// This ensures sibling messages are displayed in the correct order
							// Backend orders by: position ASC, then created_at ASC
							if (childrenIds.length > 0) {
								// Create a map for faster lookups
								const cachedMsgMap = new Map(cachedMessages.map((m) => [m.id, m]));

								childrenIds = [...childrenIds].sort((id1, id2) => {
									const msg1 = cachedMsgMap.get(id1);
									const msg2 = cachedMsgMap.get(id2);
									if (!msg1 || !msg2) return 0;

									// Sort by position first (ASC), then by created_at (ASC)
									// Backend: order_by(ChatMessage.position.asc(), ChatMessage.created_at.asc())
									// For legacy messages with null positions, treat null as coming before numeric positions
									// This ensures older messages (with null) come before newer messages (with 0)
									const pos1 = msg1.position;
									const pos2 = msg2.position;

									// Handle null positions: null comes before all numeric positions (for legacy compatibility)
									if (pos1 === null && pos2 === null) {
										// Both null - sort by created_at
										const created1 = msg1.created_at || 0;
										const created2 = msg2.created_at || 0;
										return created1 - created2;
									} else if (pos1 === null) {
										return -1; // pos1 is null, comes before pos2 (legacy message)
									} else if (pos2 === null) {
										return 1; // pos2 is null, comes before pos1 (legacy message)
									} else {
										// Both are numeric
										if (pos1 !== pos2) {
											return pos1 - pos2;
										}
										// If positions are equal, sort by created_at
										const created1 = msg1.created_at || 0;
										const created2 = msg2.created_at || 0;
										return created1 - created2;
									}
								});
							}

							// Extract merged from meta.merged if present (backend stores it in meta.merged)
							// Frontend expects it at root level, matching backend converter behavior
							let merged = null;
							if (
								cachedMsg.meta &&
								typeof cachedMsg.meta === 'object' &&
								'merged' in cachedMsg.meta
							) {
								merged = cachedMsg.meta.merged;
							}

							messagesMap[cachedMsg.id] = {
								id: cachedMsg.id,
								parentId: cachedMsg.parent_id,
								childrenIds: childrenIds,
								role: cachedMsg.role,
								content: cachedMsg.content,
								content_json: cachedMsg.content_json,
								model: cachedMsg.model_id,
								timestamp: cachedMsg.created_at,
								status: status, // Only set if status has meaningful content
								statusHistory: statusHistory, // Duplicate statusHistory at root level for frontend compatibility
								usage: cachedMsg.usage || null,
								meta: cachedMsg.meta || null,
								merged: merged, // Extract merged from meta.merged to root level
								annotation: cachedMsg.annotation,
								feedbackId: cachedMsg.feedback_id,
								selectedModelId: cachedMsg.selected_model_id,
								files: cachedMsg.files,
								sources: cachedMsg.sources,
								updated_at: cachedMsg.updated_at,
								position: cachedMsg.position,
								modelIdx: cachedMsg.modelIdx ?? null, // Root-level property, not in meta
								modelName: cachedMsg.modelName ?? null, // Root-level property, not in meta
								models: cachedMsg.models ?? null // Root-level property for side-by-side chats
							};
						}

						// Get currentId from sync data
						let currentId = syncData?.history?.currentId || null;

						// Validate currentId - if it's null or doesn't exist, find a valid leaf message
						if (!currentId || !messagesMap[currentId]) {
							if (currentId && !messagesMap[currentId]) {
								console.warn(`currentId ${currentId} not found in cached messages`);
							}
							// Find leaf messages (messages with no children or children that don't exist)
							const leafMessages = cachedMessages.filter((msg) => {
								const children = syncData?.history?.messages?.[msg.id]?.children_ids || [];
								if (children.length === 0) return true;
								// Check if all children exist in messagesMap
								return !children.some((childId: string) => messagesMap[childId]);
							});
							if (leafMessages.length > 0) {
								leafMessages.sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
								currentId = leafMessages[0].id;
							} else if (cachedMessages.length > 0) {
								cachedMessages.sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
								currentId = cachedMessages[0].id;
							} else {
								currentId = null;
							}
						}

						history = {
							messages: messagesMap,
							currentId: currentId
						};
					}
				} catch (e) {
					console.warn('Failed to load chat:', e);
					history = convertMessagesToHistory([]);
				}

				chatTitle.set(chatContent.title);

				const userSettings = await getUserSettings(localStorage.token);

				if (userSettings) {
					await settings.set(userSettings.ui);
				} else {
					await settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
				}

				params = chatContent?.params ?? {};
				chatFiles = chatContent?.files ?? [];

				autoScroll = true;
				await tick();

				if (history.currentId) {
					for (const message of Object.values(history.messages)) {
						if (message.role === 'assistant') {
							message.done = true;
						}
					}
				}

				const taskRes = await getTaskIdsByChatId(localStorage.token, $chatId).catch((error) => {
					return null;
				});

				if (taskRes) {
					taskIds = taskRes.task_ids;
				}

				await tick();

				return true;
			} else {
				return null;
			}
		} else {
			return null;
		}
	};

	const scrollToBottom = async () => {
		await tick();
		if (messagesContainerElement) {
			messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
		}
	};
	const chatCompletedHandler = async (chatId, modelId, responseMessageId, messages) => {
		const res = await chatCompleted(localStorage.token, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.usage ? { usage: m.usage } : {}),
				...(m.sources ? { sources: m.sources } : {})
			})),
			model_item: $models.find((m) => m.id === modelId),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };

			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				if (message?.id) {
					// Add null check for message and message.id
					history.messages[message.id] = {
						...history.messages[message.id],
						...(history.messages[message.id].content !== message.content
							? { originalContent: history.messages[message.id].content }
							: {}),
						...message
					};
					// Cache message in IndexedDB
					await cacheMessage(history.messages[message.id], chatId);
				}
			}
		}

		await tick();

		if (get(chatId) == chatId) {
			if (!get(temporaryChatEnabled)) {
				// Strip content, sources, and files from messages array to reduce bandwidth (backend will look them up from history.messages)
				const messagesWithoutContent = messages.map((m) => {
					const { content, sources, files, ...rest } = m;
					return rest;
				});
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: messagesWithoutContent,
					history: history,
					params: params,
					files: chatFiles
				});
				// Invalidate cache since chat was updated
				chatCache.update((cache) => {
					cache.delete(chatId);
					return cache;
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, get(currentChatPage)));
			}
		}

		taskIds = null;
	};

	const chatActionHandler = async (chatId, actionId, modelId, responseMessageId, event = null) => {
		const messages = createMessagesList(history, responseMessageId);

		const res = await chatAction(localStorage.token, actionId, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			...(event ? { event: event } : {}),
			model_item: $models.find((m) => m.id === modelId),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };
			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				history.messages[message.id] = {
					...history.messages[message.id],
					...(history.messages[message.id].content !== message.content
						? { originalContent: history.messages[message.id].content }
						: {}),
					...message
				};
			}
		}

		if (get(chatId) == chatId) {
			if (!get(temporaryChatEnabled)) {
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					params: params,
					files: chatFiles
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, get(currentChatPage)));
			}
		}
	};

	const getChatEventEmitter = async (modelId: string, chatId: string = '') => {
		return setInterval(() => {
			$socket?.emit('usage', {
				action: 'chat',
				model: modelId,
				chat_id: chatId
			});
		}, 1000);
	};

	const createMessagePair = async (userPrompt) => {
		prompt = '';
		if (selectedModels.length === 0) {
			toast.error($i18n.t('Model not selected'));
		} else {
			const modelId = selectedModels[0];
			const model = $models.filter((m) => m.id === modelId).at(0);

			const messages = createMessagesList(history, history.currentId);
			const parentMessage = messages.length !== 0 ? messages.at(-1) : null;

			const userMessageId = uuidv4();
			const responseMessageId = uuidv4();

			const userMessage = {
				id: userMessageId,
				parentId: parentMessage ? parentMessage.id : null,
				childrenIds: [responseMessageId],
				role: 'user',
				content: userPrompt ? userPrompt : `[PROMPT] ${userMessageId}`,
				timestamp: Math.floor(Date.now() / 1000)
			};

			const responseMessage = {
				id: responseMessageId,
				parentId: userMessageId,
				childrenIds: [],
				role: 'assistant',
				content: `[RESPONSE] ${responseMessageId}`,
				done: true,

				model: modelId,
				modelName: model.name ?? model.id,
				modelIdx: 0,
				timestamp: Math.floor(Date.now() / 1000)
			};

			if (parentMessage) {
				parentMessage.childrenIds.push(userMessageId);
				history.messages[parentMessage.id] = parentMessage;
				await cacheMessage(parentMessage, $chatId);
			}
			history.messages[userMessageId] = userMessage;
			history.messages[responseMessageId] = responseMessage;
			await cacheMessage(userMessage, $chatId);
			await cacheMessage(responseMessage, $chatId);

			history.currentId = responseMessageId;

			await tick();

			if (autoScroll) {
				scrollToBottom();
			}

			if (messages.length === 0) {
				await initChatHandler(history);
			} else {
				await saveChatHandler($chatId, history);
			}
		}
	};

	const addMessages = async ({ modelId, parentId, messages }) => {
		const model = $models.filter((m) => m.id === modelId).at(0);

		let parentMessage = history.messages[parentId];
		let currentParentId = parentMessage ? parentMessage.id : null;
		for (const message of messages) {
			let messageId = uuidv4();

			if (message.role === 'user') {
				const userMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = userMessage;
				parentMessage = userMessage;
				currentParentId = messageId;
			} else {
				const responseMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					done: true,
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: 0,
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = responseMessage;
				parentMessage = responseMessage;
				currentParentId = messageId;
			}
		}

		history.currentId = currentParentId;
		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler($chatId, history);
		}
	};

	const chatCompletionEventHandler = async (data, message, chatId) => {
		const { id, done, choices, content, sources, selected_model_id, error, usage } = data;

		if (error) {
			await handleOpenAIError(error, message);
		}

		if (sources) {
			message.sources = sources;
		}

		if (choices) {
			if (choices[0]?.message?.content) {
				// Non-stream response - timer was already started when request was made
				message.content += choices[0]?.message?.content;
			} else {
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				// Start timing on first received delta (even if it's just whitespace/newline)
				if (!firstTokenReceived) {
					firstTokenReceived = true;
					tokenTimerStart = performance.now();
					// Calculate time to first token for streaming responses
					if (isStreamingResponse && streamRequestStart > 0) {
						const ttft = (tokenTimerStart - streamRequestStart) / 1000; // Convert to seconds
						// Store TTFT in the message for later injection into usage
						message.time_to_first_token = parseFloat(ttft.toFixed(3));
					}
				}

				if (message.content == '' && value == '\n') {
					console.log('Empty response');
				} else {
					message.content += value;

					if (navigator.vibrate && (get(settings)?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}

					// Emit chat event for TTS
					const messageContentParts = getMessageContentParts(
						message.content,
						get(config)?.audio?.tts?.split_on ?? 'punctuation'
					);
					messageContentParts.pop();

					// dispatch only last sentence and make sure it hasn't been dispatched before
					if (
						messageContentParts.length > 0 &&
						messageContentParts[messageContentParts.length - 1] !== message.lastSentence
					) {
						message.lastSentence = messageContentParts[messageContentParts.length - 1];
						eventTarget.dispatchEvent(
							new CustomEvent('chat', {
								detail: {
									id: message.id,
									content: messageContentParts[messageContentParts.length - 1]
								}
							})
						);
					}
				}
			}
		}
		if (content) {
			// REALTIME_CHAT_SAVE is disabled

			if (isStreamingResponse) {
				// For streaming responses, start timing on first content
				if (!firstTokenReceived) {
					firstTokenReceived = true;
					tokenTimerStart = performance.now();

					// Calculate time to first token for streaming responses
					if (streamRequestStart > 0) {
						const ttft = (tokenTimerStart - streamRequestStart) / 1000; // Convert to seconds
						// Store TTFT in the message for later injection into usage
						message.time_to_first_token = parseFloat(ttft.toFixed(3));
					}
				}
			}
			// For non-streaming, timer was already started when request was made

			message.content = content;

			if (navigator.vibrate && (get(settings)?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}

			// Emit chat event for TTS
			const messageContentParts = getMessageContentParts(
				message.content,
				get(config)?.audio?.tts?.split_on ?? 'punctuation'
			);
			messageContentParts.pop();

			// dispatch only last sentence and make sure it hasn't been dispatched before
			if (
				messageContentParts.length > 0 &&
				messageContentParts[messageContentParts.length - 1] !== message.lastSentence
			) {
				message.lastSentence = messageContentParts[messageContentParts.length - 1];
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: {
							id: message.id,
							content: messageContentParts[messageContentParts.length - 1]
						}
					})
				);
			}
		}

		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
			message.arena = true;
		}
		if (usage) {
			// Check if this is an Ollama response that already has detailed metrics
			const hasOllamaMetrics =
				usage['response_token/s'] || usage.eval_duration || usage.prompt_eval_count;

			if (!hasOllamaMetrics) {
				// Calculate ESTIMATED tokens per second for non-Ollama responses
				let shouldCalculate = false;
				let elapsedSeconds = 0;
				usage.estimates = {};

				if (isStreamingResponse) {
					// For streaming: only calculate if we received the first token
					shouldCalculate = firstTokenReceived && tokenTimerStart > 0;
					elapsedSeconds = (performance.now() - tokenTimerStart) / 1000;
				} else {
					// For non-streaming: timer was started when request was made
					shouldCalculate = tokenTimerStart > 0;
					elapsedSeconds = (performance.now() - tokenTimerStart) / 1000;
				}

				if (shouldCalculate) {
					let completionTokens = usage.completion_tokens || 0;
					// If reasoning tokens are available, add them to completion tokens for a more accurate count
					if (usage.completion_tokens_details?.reasoning_tokens) {
						completionTokens += usage.completion_tokens_details.reasoning_tokens;
					}
					usage.estimates.tokens_per_second = parseFloat(
						(completionTokens / Math.max(elapsedSeconds, 0.001)).toFixed(2)
					);
					// console.log(
					// 	`Estimated tokens per second: ${usage.estimates.tokens_per_second} from ${elapsedSeconds}s and ${completionTokens} tokens`
					// );
					usage.estimates.generation_time = parseFloat(elapsedSeconds.toFixed(3));
				}

				// Skip cost estimation if usage.cost is already available
				if (!usage.cost) {
					// Calculate cost estimates if model pricing is available
					const model = get(models).find((m) => m.id === message.model);
					// console.log('Model for cost estimates:', model);
					const inputTokens = usage.prompt_tokens || 0;
					const outputTokens =
						(usage.completion_tokens || 0) +
						(usage.completion_tokens_details?.reasoning_tokens || 0);

					// Safely access pricing with proper null checking
					const inputPrice = model?.info?.meta?.model_details?.price_per_1m_input_tokens;
					const outputPrice = model?.info?.meta?.model_details?.price_per_1m_output_tokens;

					if (inputPrice && typeof inputPrice === 'number' && inputTokens > 0) {
						usage.estimates.input_cost = parseFloat(
							((inputTokens / 1_000_000) * inputPrice).toFixed(8)
						);
					}

					if (outputPrice && typeof outputPrice === 'number' && outputTokens > 0) {
						usage.estimates.output_cost = parseFloat(
							((outputTokens / 1_000_000) * outputPrice).toFixed(8)
						);
					}

					if (
						usage.estimates.input_cost !== undefined &&
						usage.estimates.output_cost !== undefined
					) {
						usage.estimates.total_cost = parseFloat(
							(usage.estimates.input_cost + usage.estimates.output_cost).toFixed(8)
						);
					} else if (usage.estimates.input_cost !== undefined) {
						usage.estimates.total_cost = usage.estimates.input_cost;
					} else if (usage.estimates.output_cost !== undefined) {
						usage.estimates.total_cost = usage.estimates.output_cost;
					}
				}

				// Add time to first token metric for streaming responses
				if (isStreamingResponse && message.time_to_first_token !== undefined) {
					usage.estimates.time_to_first_token = message.time_to_first_token;
				}
			}

			message.usage = usage;

			// Update the entire chat in database when we receive completion with tokens info
			if (done && get(chatId)) {
				// We need to update the entire chat record with the new usage data
				const chatToUpdate = JSON.parse(JSON.stringify(history));

				// Make sure the message with the updated usage info is included
				if (message.id) {
					chatToUpdate.messages[message.id] = message;
				}

				try {
					updateChatById(localStorage.token, get(chatId), {
						chat: {
							models: selectedModels,
							messages: createMessagesList(chatToUpdate, chatToUpdate.currentId),
							history: chatToUpdate,
							params: params,
							files: chatFiles
						}
					}).catch((err) => {
						console.error('Failed to update chat usage data:', err);
					});
				} catch (err) {
					console.error('Error updating chat with token speed data:', err);
				}
			}
		}

		history.messages[message.id] = message;

		if (done) {
			// Cache message in IndexedDB only when streaming is complete (for performance)
			await cacheMessage(message, chatId);

			message.done = true;

			if ($settings.responseAutoCopy) {
				copyToClipboard(message.content);
			}

			if ($settings.responseAutoPlayback && !$showCallOverlay) {
				await tick();
				document.getElementById(`speak-button-${message.id}`)?.click();
			}

			// Emit chat event for TTS
			let lastMessageContentPart =
				getMessageContentParts(message.content, $config?.audio?.tts?.split_on ?? 'punctuation')?.at(
					-1
				) ?? '';
			if (lastMessageContentPart) {
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: { id: message.id, content: lastMessageContentPart }
					})
				);
			}
			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			history.messages[message.id] = message;
			await chatCompletedHandler(
				chatId,
				message.model,
				message.id,
				createMessagesList(history, message.id)
			);
		}

		console.log(data);
		if (autoScroll) {
			scrollToBottom();
		}
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	const submitPrompt = async (userPrompt, { _raw = false } = {}) => {
		console.log('submitPrompt', userPrompt, $chatId);

		const messages = createMessagesList(history, history.currentId);
		const _selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);
		if (JSON.stringify(selectedModels) !== JSON.stringify(_selectedModels)) {
			selectedModels = _selectedModels;
		}

		if (userPrompt === '' && files.length === 0) {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}
		if (selectedModels.includes('')) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		// Determine the parent for the new user message
		// In side-by-side chats, if currentId is an assistant message, use it as parent
		// Otherwise, use the last message in the chain (standard behavior)
		let parentId = null;
		const currentMessage = history.currentId ? history.messages[history.currentId] : null;
		if (currentMessage && currentMessage.role === 'assistant') {
			// Side-by-side chat: continue from the selected assistant message
			parentId = history.currentId;
		} else if (messages.length !== 0) {
			// Standard chat: use the last message in the chain
			const lastMessage = messages.at(-1);
			if (lastMessage && lastMessage.id) {
				parentId = lastMessage.id;
			}
		}

		// Fallback: if parentId is still null, find the most recent leaf message
		// This can happen if currentId is invalid or messages list is empty
		if (parentId === null && Object.keys(history.messages).length > 0) {
			const allMessages = Object.values(history.messages) as any[];
			// Find leaf messages (messages with no children or children that don't exist)
			const leafMessages = allMessages.filter((msg) => {
				if (!msg.childrenIds || msg.childrenIds.length === 0) return true;
				return !msg.childrenIds.some((childId: string) => history.messages[childId]);
			});
			if (leafMessages.length > 0) {
				// Sort by timestamp descending and use the most recent
				leafMessages.sort(
					(a, b) => (b.timestamp || b.updated_at || 0) - (a.timestamp || a.updated_at || 0)
				);
				parentId = leafMessages[0].id;
			} else if (allMessages.length > 0) {
				// If no leaf messages found, use the most recent message overall
				allMessages.sort(
					(a, b) => (b.timestamp || b.updated_at || 0) - (a.timestamp || a.updated_at || 0)
				);
				parentId = allMessages[0].id;
			}
		}

		if (messages.length != 0) {
			const lastMessage = messages.at(-1);
			if (lastMessage.done != true) {
				// Response not done
				return;
			}
			if (lastMessage.error && !lastMessage.content) {
				// Error in response
				toast.error($i18n.t(`Oops! There was an error in the previous response.`));
				return;
			}
		}
		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}
		if (
			($config?.file?.max_count ?? null) !== null &&
			files.length + chatFiles.length > $config?.file?.max_count
		) {
			toast.error(
				$i18n.t(`You can only chat with a maximum of {{maxCount}} file(s) at a time.`, {
					maxCount: $config?.file?.max_count
				})
			);
			return;
		}

		prompt = '';

		// Reset chat input textarea
		if (!($settings?.richTextInput ?? true)) {
			const chatInputElement = document.getElementById('chat-input');

			if (chatInputElement) {
				await tick();
				chatInputElement.style.height = '';
			}
		}

		const _files = JSON.parse(JSON.stringify(files));
		// Strip files array and data.file_ids from collections before adding to chatFiles
		const strippedFiles = _files.map(stripCollectionFiles);
		chatFiles.push(
			...strippedFiles.filter((item) => ['doc', 'file', 'collection'].includes(item.type))
		);
		chatFiles = chatFiles.filter(
			// Remove duplicates
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		files = [];
		prompt = '';

		// Create user message
		let userMessageId = uuidv4();
		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			files: _files.length > 0 ? strippedFiles : undefined,
			timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			models: selectedModels
		};

		// Add message to history and Set currentId to messageId
		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;
		// Cache message in IndexedDB
		await cacheMessage(userMessage, $chatId);

		// Append messageId to childrenIds of parent message
		if (parentId !== null && history.messages[parentId]) {
			history.messages[parentId].childrenIds.push(userMessageId);
			await cacheMessage(history.messages[parentId], $chatId);
		}

		// focus on chat input
		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		saveSessionSelectedModels();

		await sendPrompt(history, userPrompt, userMessageId, { newChat: true });
	};

	const sendPrompt = async (
		_history,
		prompt: string,
		parentId: string,
		{ modelId = null, modelIdx = null, newChat = false } = {}
	) => {
		// Reset token timer flag for each new prompt
		firstTokenReceived = false;
		tokenTimerStart = 0;
		isStreamingResponse = false;
		streamRequestStart = 0;

		if (autoScroll) {
			scrollToBottom();
		}

		let _chatId = JSON.parse(JSON.stringify($chatId));
		_history = JSON.parse(JSON.stringify(_history));

		const responseMessageIds: Record<PropertyKey, string> = {};
		// If modelId is provided, use it, else use selected model
		let selectedModelIds = modelId
			? [modelId]
			: atSelectedModel !== undefined
				? [atSelectedModel.id]
				: selectedModels;

		// Create response messages for each selected model
		for (const [_modelIdx, modelId] of selectedModelIds.entries()) {
			const model = $models.filter((m) => m.id === modelId).at(0);

			if (model) {
				let responseMessageId = uuidv4();
				let responseMessage = {
					parentId: parentId,
					id: responseMessageId,
					childrenIds: [],
					role: 'assistant',
					content: '',
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: modelIdx ? modelIdx : _modelIdx,
					userContext: null,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				// Add message to history and Set currentId to messageId
				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// Cache message in IndexedDB
				await cacheMessage(responseMessage, _chatId || $chatId);

				// Append messageId to childrenIds of parent message
				if (parentId !== null && history.messages[parentId]) {
					// Add null check before accessing childrenIds
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
					await cacheMessage(history.messages[parentId], _chatId || $chatId);
				}

				responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`] = responseMessageId;
			}
		}
		history = history;

		// Create new chat if newChat is true and first user message
		if (newChat && _history.messages[_history.currentId].parentId === null) {
			_chatId = await initChatHandler(_history);
		}

		await tick();

		_history = JSON.parse(JSON.stringify(history));
		// Save chat after all messages have been created
		await saveChatHandler(_chatId, _history);

		await Promise.all(
			selectedModelIds.map(async (modelId, _modelIdx) => {
				console.log('modelId', modelId);
				const model = $models.filter((m) => m.id === modelId).at(0);

				if (model) {
					const messages = createMessagesList(_history, parentId);
					// If there are image files, check if model is vision capable
					const hasImages = messages.some((message) =>
						message.files?.some((file) => file.type === 'image')
					);

					if (hasImages && !(model.info?.meta?.capabilities?.vision ?? true)) {
						toast.error(
							$i18n.t('Model {{modelName}} is not vision capable', {
								modelName: model.name ?? model.id
							})
						);
					}

					let responseMessageId =
						responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`];
					let responseMessage = _history.messages[responseMessageId];

					let userContext = null;
					if ($settings?.memory ?? false) {
						if (userContext === null) {
							const res = await queryMemory(localStorage.token, prompt).catch((error) => {
								toast.error(`${error}`);
								return null;
							});
							if (res) {
								if (res.documents[0].length > 0) {
									userContext = res.documents[0].reduce((acc, doc, index) => {
										const createdAtTimestamp = res.metadatas[0][index].created_at;
										const createdAtDate = new Date(createdAtTimestamp * 1000)
											.toISOString()
											.split('T')[0];
										return `${acc}${index + 1}. [${createdAtDate}]. ${doc}\n`;
									}, '');
								}

								console.log(userContext);
							}
						}
					}
					responseMessage.userContext = userContext;

					const chatEventEmitter = await getChatEventEmitter(model.id, _chatId);

					scrollToBottom();
					await sendPromptSocket(_history, model, responseMessageId, _chatId);

					if (chatEventEmitter) clearInterval(chatEventEmitter);
				} else {
					toast.error($i18n.t(`Model {{modelId}} not found`, { modelId }));
				}
			})
		);

		currentChatPage.set(1);
		chats.set(await getChatList(localStorage.token, $currentChatPage));
	};

	const sendPromptSocket = async (_history, model, responseMessageId, _chatId) => {
		const responseMessage = _history.messages[responseMessageId];
		const userMessage = _history.messages[responseMessage.parentId];

		let files = JSON.parse(JSON.stringify(chatFiles)).map(stripCollectionFiles);
		files.push(
			...(userMessage?.files ?? [])
				.filter((item) => ['doc', 'file', 'collection'].includes(item.type))
				.map(stripCollectionFiles),
			...(responseMessage?.files ?? []).filter((item) => ['web_search_results'].includes(item.type))
		);
		// Remove duplicates
		files = files.filter(
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		scrollToBottom();
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick();

		const stream =
			model?.info?.params?.stream_response ??
			$settings?.params?.stream_response ??
			params?.stream_response ??
			true;

		// Track if this is a streaming response and start timer for non-streaming
		isStreamingResponse = stream;
		if (!isStreamingResponse) {
			// For non-streaming responses, start timer when request is made
			tokenTimerStart = performance.now();
		} else {
			// For streaming responses, start timer to measure time to first token
			streamRequestStart = performance.now();
		}

		let messages = [
			params?.system || $settings.system || (responseMessage?.userContext ?? null)
				? {
						role: 'system',
						content: `${promptTemplate(
							params?.system ?? $settings?.system ?? '',
							$user?.name,
							$settings?.userLocation
								? await getAndUpdateUserLocation(localStorage.token).catch((err) => {
										console.error(err);
										return undefined;
									})
								: undefined
						)}${
							(responseMessage?.userContext ?? null)
								? `\n\nUser Context:\n${responseMessage?.userContext ?? ''}`
								: ''
						}`
					}
				: undefined,
			...createMessagesList(_history, responseMessageId).map((message) => ({
				...message,
				content: processDetails(message.content)
			}))
		].filter((message) => message);

		messages = messages
			.map((message, idx, arr) => ({
				role: message.role,
				// Preserve the message ID so backend can use it when inserting into normalized storage
				...(message.id ? { id: message.id } : {}),
				...((message.files?.filter((file) => file.type === 'image').length > 0 ?? false) &&
				message.role === 'user'
					? {
							content: [
								{
									type: 'text',
									text: message?.merged?.content ?? message.content
								},
								...message.files
									.filter((file) => file.type === 'image')
									.map((file) => ({
										type: 'image_url',
										image_url: {
											url: file.url
										}
									}))
							]
						}
					: {
							content: message?.merged?.content ?? message.content
						})
			}))
			.filter((message) => message?.role === 'user' || message?.content?.trim());

		const res = await generateOpenAIChatCompletion(
			localStorage.token,
			{
				stream: stream,
				model: model.id,
				messages: messages,
				params: (() => {
					// Base merge of user/settings params
					const baseParams = { ...($settings?.params ?? {}), ...(params ?? {}) };
					// Normalize stop tokens
					const normalizedStop =
						(params?.stop ?? $settings?.params?.stop ?? undefined)
							? (params?.stop.split(',').map((token) => token.trim()) ?? $settings.params.stop).map(
									(str) => decodeURIComponent(JSON.parse('"' + str.replace(/\"/g, '\\"') + '"'))
								)
							: undefined;

					// Apply set_effort behavior override if configured on the model
					const details = (model?.info?.meta as any)?.model_details;
					if (details?.reasoning_behavior === 'set_effort') {
						const selectedEffort = history?.reasoningEffort ?? null;
						const existingReasoning = { ...(baseParams?.reasoning ?? {}) };

						if (selectedEffort === null) {
							// Remove effort key if present
							delete existingReasoning.effort;
						} else {
							existingReasoning.effort = selectedEffort;
						}

						// Remove null max_tokens to avoid edge cases
						if (existingReasoning.max_tokens === null) {
							delete existingReasoning.max_tokens;
						}

						// Apply verbosity if model supports it
						let finalParams = {
							...baseParams,
							...(Object.keys(existingReasoning).length > 0
								? { reasoning: existingReasoning }
								: {}),
							format: $settings.requestFormat ?? undefined,
							keep_alive: $settings.keepAlive ?? undefined,
							stop: normalizedStop
						};

						// Add verbosity parameter if supported
						if (model?.info?.meta?.capabilities?.verbosity && history?.verbosity) {
							finalParams.verbosity = history.verbosity;
						}

						return finalParams;
					}

					// Default case: let backend handle parameter merging
					let finalParams = {
						...baseParams,
						format: $settings.requestFormat ?? undefined,
						keep_alive: $settings.keepAlive ?? undefined,
						stop: normalizedStop
					};

					// Add verbosity parameter if supported
					if (model?.info?.meta?.capabilities?.verbosity && history?.verbosity) {
						finalParams.verbosity = history.verbosity;
					}

					return finalParams;
				})(),

				files: (files?.length ?? 0) > 0 ? files : undefined,
				tool_ids: selectedToolIds.length > 0 ? selectedToolIds : undefined,
				tool_servers: $toolServers,

				features: {
					image_generation:
						$config?.features?.enable_image_generation &&
						($user?.role === 'admin' || $user?.permissions?.features?.image_generation)
							? imageGenerationEnabled
							: false,
					code_interpreter:
						$config?.features?.enable_code_interpreter &&
						($user?.role === 'admin' || $user?.permissions?.features?.code_interpreter)
							? codeInterpreterEnabled
							: false,
					web_search:
						$config?.features?.enable_web_search &&
						($user?.role === 'admin' || $user?.permissions?.features?.web_search)
							? webSearchEnabled || ($settings?.webSearch ?? false) === 'always'
							: false
				},
				variables: {
					...getPromptVariables(
						$user?.name,
						$settings?.userLocation
							? await getAndUpdateUserLocation(localStorage.token).catch((err) => {
									console.error(err);
									return undefined;
								})
							: undefined
					)
				},
				model_item: $models.find((m) => m.id === model.id),

				session_id: $socket?.id,
				chat_id: $chatId,
				id: responseMessageId,

				...(!$temporaryChatEnabled &&
				(messages.length == 1 ||
					(messages.length == 2 &&
						messages.at(0)?.role === 'system' &&
						messages.at(1)?.role === 'user')) &&
				(selectedModels[0] === model.id || atSelectedModel !== undefined)
					? {
							background_tasks: {
								title_generation: $settings?.title?.auto ?? true,
								tags_generation: $settings?.autoTags ?? true
							}
						}
					: {}),

				...(stream && (model.info?.meta?.capabilities?.usage ?? false)
					? {
							stream_options: {
								include_usage: true
							}
						}
					: {})
			},
			`${WEBUI_BASE_URL}/api`
		).catch(async (error) => {
			toast.error(`${error}`);

			responseMessage.error = {
				content: error
			};
			responseMessage.done = true;

			history.messages[responseMessageId] = responseMessage;
			history.currentId = responseMessageId;
			return null;
		});

		if (res) {
			if (res.error) {
				await handleOpenAIError(res.error, responseMessage);
			} else {
				if (taskIds) {
					taskIds.push(res.task_id);
				} else {
					taskIds = [res.task_id];
				}
			}
		}

		await tick();
		scrollToBottom();
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		console.error(innerError);
		if ('detail' in innerError) {
			// FastAPI error
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			// OpenAI error
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			// OpenAI error
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		responseMessage.error = {
			content: $i18n.t(`Uh-oh! There was an issue with the response.`) + '\n' + errorMessage
		};
		responseMessage.done = true;

		if (responseMessage.statusHistory) {
			responseMessage.statusHistory = responseMessage.statusHistory.filter(
				(status) => status.action !== 'knowledge_search'
			);
		}

		history.messages[responseMessage.id] = responseMessage;
	};

	const stopResponse = async () => {
		if (taskIds) {
			for (const taskId of taskIds) {
				const res = await stopTask(localStorage.token, taskId).catch((error) => {
					toast.error(`${error}`);
					return null;
				});
			}

			taskIds = null;

			const responseMessage = history.messages[history.currentId];
			// Set all response messages to done
			for (const messageId of history.messages[responseMessage.parentId].childrenIds) {
				history.messages[messageId].done = true;
			}

			history.messages[history.currentId] = responseMessage;

			if (autoScroll) {
				scrollToBottom();
			}
		}
	};

	const submitMessage = async (parentId, prompt) => {
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		await sendPrompt(history, userPrompt, userMessageId);
	};

	const regenerateResponse = async (message) => {
		console.log('regenerateResponse');

		if (history.currentId) {
			let userMessage = history.messages[message.parentId];
			let userPrompt = userMessage.content;

			if (autoScroll) {
				scrollToBottom();
			}

			if ((userMessage?.models ?? [...selectedModels]).length == 1) {
				// If user message has only one model selected, sendPrompt automatically selects it for regeneration
				await sendPrompt(history, userPrompt, userMessage.id);
			} else {
				// If there are multiple models selected, use the model of the response message for regeneration
				// e.g. many model chat
				await sendPrompt(history, userPrompt, userMessage.id, {
					modelId: message.model,
					modelIdx: message.modelIdx
				});
			}
		}
	};

	const continueResponse = async () => {
		console.log('continueResponse');
		const _chatId = JSON.parse(JSON.stringify($chatId));

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = $models
				.filter((m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model))
				.at(0);

			if (model) {
				await sendPromptSocket(history, model, responseMessage.id, _chatId);
			}
		}
	};

	const mergeResponses = async (messageId, responses, _chatId) => {
		console.log('mergeResponses', messageId, responses);
		const message = history.messages[messageId];
		const mergedResponse = {
			status: true,
			content: ''
		};
		message.merged = mergedResponse;
		history.messages[messageId] = message;

		try {
			const [res, controller] = await generateMoACompletion(
				localStorage.token,
				message.model,
				history.messages[message.parentId].content,
				responses,
				_chatId,
				messageId
			);

			if (res && res.ok && res.body) {
				const textStream = await createOpenAITextStream(res.body, $settings.splitLargeChunks);
				for await (const update of textStream) {
					const { value, done, sources, error, usage } = update;
					if (error || done) {
						break;
					}

					if (mergedResponse.content == '' && value == '\n') {
						continue;
					} else {
						// Start timing on first meaningful token for merged responses
						if (!firstTokenReceived && value && value.trim()) {
							firstTokenReceived = true;
							tokenTimerStart = performance.now();

							// Calculate time to first token for merged streaming responses
							if (isStreamingResponse && streamRequestStart > 0) {
								const ttft = (tokenTimerStart - streamRequestStart) / 1000; // Convert to seconds
								// Store TTFT in the message for later injection into usage
								message.time_to_first_token = parseFloat(ttft.toFixed(3));
							}
						}

						mergedResponse.content += value;
						history.messages[messageId] = message;
					}

					if (autoScroll) {
						scrollToBottom();
					}
				}

				await saveChatHandler(_chatId, history);
				// Cache the merged message to IndexedDB
				await cacheMessage(message, _chatId);
			} else {
				console.error(res);
			}
		} catch (e) {
			console.error(e);
		}
	};

	const initChatHandler = async (history) => {
		let _chatId = $chatId;

		if (!$temporaryChatEnabled) {
			chat = await createNewChat(localStorage.token, {
				id: _chatId,
				title: $i18n.t('New Chat'),
				models: selectedModels,
				system: $settings.system ?? undefined,
				params: params,
				// no history/messages in new chat payload
				tags: [],
				timestamp: Math.floor(Date.now() / 1000) // Unix epoch in seconds
			});

			_chatId = chat.id;
			await chatId.set(_chatId);

			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			currentChatPage.set(1);

			window.history.replaceState(history.state, '', `/c/${_chatId}`);
		} else {
			_chatId = 'local';
			await chatId.set('local');
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		if (get(chatId) == _chatId) {
			if (!get(temporaryChatEnabled)) {
				// Lightweight update: do not send full history/messages anymore
				// But still send currentId to keep active_message_id in sync
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					params: params,
					files: chatFiles,
					history: {
						currentId: history.currentId
					}
				});
				// Invalidate cache since chat was updated
				chatCache.update((cache) => {
					cache.delete(_chatId);
					return cache;
				});
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, get(currentChatPage)));
			}
		}
	};

	let searchActive = $state(false);
	let searchQuery = $state('');
	let includeHidden = $state(false);
	// Each match is { messageId: string, occurrenceIndex: number }
	let matches: Array<{ messageId: string; occurrenceIndex: number }> = $state([]);
	let currentMatchIndex = $state(-1);

	function openSearch() {
		searchActive = true;
		tick().then(() => {
			document.getElementById('chat-search-input')?.focus();
		});
	}

	function closeSearch() {
		searchActive = false;
		searchQuery = '';
		matches = [];
		currentMatchIndex = -1;
	}

	function updateSearch() {
		if (!searchQuery) {
			matches = [];
			currentMatchIndex = -1;
			return;
		}
		const ids = Object.keys(history.messages);
		const q = searchQuery.toLowerCase();
		const found: Array<{ messageId: string; occurrenceIndex: number }> = [];
		for (const id of ids) {
			const msg = history.messages[id];
			if (msg.content?.toLowerCase().includes(q)) {
				if (includeHidden || document.getElementById(`message-${id}`)) {
					// Count all occurrences in this message
					const content = msg.content.toLowerCase();
					let searchIndex = content.indexOf(q);
					let occurrenceIndex = 0;
					while (searchIndex !== -1) {
						found.push({ messageId: id, occurrenceIndex });
						occurrenceIndex++;
						searchIndex = content.indexOf(q, searchIndex + 1);
					}
				}
			}
		}
		matches = found;
		currentMatchIndex = found.length ? 0 : -1;
		if (currentMatchIndex >= 0) navigateTo(found[0]);
	}

	function navigateTo(match: { messageId: string; occurrenceIndex: number } | string) {
		// Handle both old string format (for backwards compatibility) and new match format
		let messageId: string;
		let occurrenceIndex = 0;

		if (typeof match === 'string') {
			messageId = match;
			// Find first occurrence in this message
			const firstMatch = matches.find((m) => m.messageId === messageId);
			if (firstMatch) {
				occurrenceIndex = firstMatch.occurrenceIndex;
			}
		} else {
			messageId = match.messageId;
			occurrenceIndex = match.occurrenceIndex;
		}

		showMessage({ id: messageId }, { skipSave: true, scrollToHighlight: true, occurrenceIndex });
		currentMatchIndex = matches.findIndex(
			(m) => m.messageId === messageId && m.occurrenceIndex === occurrenceIndex
		);
		if (currentMatchIndex === -1) {
			// Fallback: find any match in this message
			currentMatchIndex = matches.findIndex((m) => m.messageId === messageId);
		}
	}

	function prevMatch() {
		if (matches.length) {
			if (currentMatchIndex > 0) {
				navigateTo(matches[currentMatchIndex - 1]);
			} else {
				// Wrap around to last result
				navigateTo(matches[matches.length - 1]);
			}
		}
	}

	function nextMatch() {
		if (matches.length) {
			if (currentMatchIndex < matches.length - 1) {
				navigateTo(matches[currentMatchIndex + 1]);
			} else {
				// Wrap around to first result
				navigateTo(matches[0]);
			}
		}
	}

	onMount(() => {
		document.addEventListener('keydown', (e) => {
			if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
				e.preventDefault();
				openSearch();
			}
			if (searchActive && e.key === 'Escape') {
				e.preventDefault();
				closeSearch();
			}
		});
	});
	run(() => {
		if (
			$models.length > 0 &&
			!chatIdProp &&
			!modelSelectionInProgress &&
			(selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === ''))
		) {
			// Models just loaded and we don't have a selected model yet
			// Re-run the model selection logic from initNewChat
			modelSelectionInProgress = true;
			let newSelectedModels: string[] = [];

			if ($page.url.searchParams.get('models')) {
				newSelectedModels = $page.url.searchParams.get('models')?.split(',') || [];
			} else if ($page.url.searchParams.get('model')) {
				const urlModels = $page.url.searchParams.get('model')?.split(',') || [];
				newSelectedModels = urlModels;
			} else {
				if (sessionStorage.selectedModels) {
					try {
						newSelectedModels = JSON.parse(sessionStorage.selectedModels);
					} catch (e) {
						newSelectedModels = [];
					}
				} else {
					if ($settings?.models) {
						newSelectedModels = $settings.models;
					} else if ($config?.default_models) {
						newSelectedModels = $config.default_models.split(',');
					}
				}
			}

			// Filter to only include models that exist
			newSelectedModels = newSelectedModels.filter((modelId) =>
				$models.map((m) => m.id).includes(modelId)
			);

			// If no valid models selected, use the first available model
			if (
				newSelectedModels.length === 0 ||
				(newSelectedModels.length === 1 && newSelectedModels[0] === '')
			) {
				if ($models.length > 0) {
					newSelectedModels = [$models[0].id];
				}
			}

			if (newSelectedModels.length > 0 && newSelectedModels[0] !== '') {
				selectedModels = newSelectedModels;
			}
			modelSelectionInProgress = false;
		}
	});
	run(() => {
		selectedModelIds = atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels;
	});
	// Reactive watcher: when chatIdProp changes, reload
	run(() => {
		if (chatIdProp && chatIdProp !== lastChatId) {
			lastChatId = chatIdProp;
			loadAndLink();
		}
	});
	run(() => {
		if (!chatIdProp && $page.url.pathname === '/') {
			const currentQuery = $page.url.searchParams.get('q') ?? '';
			// Only call initNewChat if query changed and we're on home page
			if (currentQuery !== lastUrlQuery) {
				lastUrlQuery = currentQuery;
				// Only call if there's a query or other params that need initNewChat
				if (
					currentQuery ||
					$page.url.searchParams.has('web-search') ||
					$page.url.searchParams.has('image-generation') ||
					$page.url.searchParams.has('knowledge-base')
				) {
					initNewChat();
				}
			}
		}
	});
	run(() => {
		if (selectedModels && chatIdProp !== '') {
			saveSessionSelectedModels();
		}
	});
	run(() => {
		if (atSelectedModel || selectedModels) {
			setToolIds();
		}
	});
</script>

<svelte:head>
	<title>
		{$chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} | ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

<audio id="audioElement" src="" style="display: none;"></audio>

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	on:confirm={(e) => {
		if (e.detail) {
			eventCallback(e.detail);
		} else {
			eventCallback(true);
		}
	}}
	on:cancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? '  md:max-w-[calc(100%-260px)]'
		: ' '} w-full max-w-full flex flex-col"
	id="chat-container"
>
	{#if !loading}
		{#if $settings?.backgroundImageUrl ?? null}
			<div
				class="absolute {$showSidebar
					? 'md:max-w-[calc(100%-260px)] md:translate-x-[260px]'
					: ''} top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
				style="background-image: url({$settings.backgroundImageUrl})  "
			></div>

			<div
				class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
			></div>
		{/if}

		<PaneGroup direction="horizontal" class="w-full h-full">
			<Pane defaultSize={50} class="h-full flex relative max-w-full flex-col">
				<Navbar
					bind:this={navbarElement}
					chat={{
						id: $chatId,
						chat: {
							title: $chatTitle,
							models: selectedModels,
							system: $settings.system ?? undefined,
							params: params,
							history: history,
							timestamp: Math.floor(Date.now() / 1000) // Unix epoch in seconds
						}
					}}
					{history}
					title={$chatTitle}
					bind:selectedModels
					shareEnabled={!!history.currentId}
					{initNewChat}
				/>

				{#if searchActive}
					<div
						class="absolute top-16 left-1/2 transform -translate-x-1/2 z-20
						bg-white dark:bg-gray-800 p-3 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700
						flex flex-col items-start space-y-3 min-w-[320px] max-w-[500px]"
					>
						<div class="flex items-center gap-2 w-full">
							<input
								id="chat-search-input"
								type="text"
								bind:value={searchQuery}
								placeholder="Search chat"
								oninput={updateSearch}
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										if (e.shiftKey) {
											prevMatch();
										} else {
											nextMatch();
										}
									}
								}}
								class="flex-1 px-3 py-1.5 text-sm bg-white dark:bg-gray-900
								text-gray-900 dark:text-gray-100
								border border-gray-200 dark:border-gray-700 rounded-lg
								focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600
								placeholder-gray-400 dark:placeholder-gray-500"
							/>
							<div class="flex items-center gap-1">
								<button
									onclick={prevMatch}
									disabled={matches.length === 0}
									class="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700
									disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent
									transition-colors text-gray-700 dark:text-gray-300"
									title="Previous match"
								>
									<ChevronLeft className="size-4" strokeWidth="2" />
								</button>
								<span
									class="text-xs font-medium whitespace-nowrap flex-shrink-0 text-center min-w-[3ch]
									text-gray-600 dark:text-gray-400"
								>
									{matches.length ? currentMatchIndex + 1 : 0}/{matches.length}
								</span>
								<button
									onclick={nextMatch}
									disabled={matches.length === 0}
									class="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700
									disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent
									transition-colors text-gray-700 dark:text-gray-300"
									title="Next match"
								>
									<ChevronRight className="size-4" strokeWidth="2" />
								</button>
							</div>
							<button
								onclick={closeSearch}
								class="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700
								transition-colors text-gray-600 dark:text-gray-400"
								title="Close search"
							>
								<XMark className="size-4" strokeWidth="2" />
							</button>
						</div>

						<!-- second row: toggle switch -->
						<div class="flex items-center justify-between w-full">
							<div class="text-xs font-medium text-gray-700 dark:text-gray-300">Include hidden</div>
							<Switch
								bind:state={includeHidden}
								on:change={() => {
									updateSearch();
								}}
							/>
						</div>
					</div>
				{/if}

				<div class="flex flex-col flex-auto z-10 w-full @container">
					{#if $settings?.landingPageMode === 'chat' || createMessagesList(history, history.currentId).length > 0}
						<div
							class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full z-10 scrollbar-hidden"
							id="messages-container"
							style={`--chat-font-scale: ${$settings?.chatFontScale ?? 1};`}
							bind:this={messagesContainerElement}
							onscroll={(e) => {
								autoScroll =
									messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
									messagesContainerElement.clientHeight + 5;
							}}
						>
							<div class=" h-full w-full flex flex-col">
								<Messages
									chatId={$chatId}
									bind:history
									bind:autoScroll
									bind:prompt
									{selectedModels}
									{atSelectedModel}
									{sendPrompt}
									{showMessage}
									{submitMessage}
									{continueResponse}
									{regenerateResponse}
									{mergeResponses}
									{chatActionHandler}
									{addMessages}
									bottomPadding={files.length > 0}
									searchMatches={matches.map((m) => m.messageId)}
									currentMatchId={matches[currentMatchIndex]?.messageId || ''}
									{searchQuery}
								/>
							</div>
						</div>

						<div class=" pb-[1rem]">
							<MessageInput
								{history}
								{taskIds}
								chatId={$chatId}
								bind:selectedModels
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:imageGenerationEnabled
								bind:codeInterpreterEnabled
								bind:webSearchEnabled
								bind:atSelectedModel
								toolServers={$toolServers}
								transparentBackground={$settings?.backgroundImageUrl ?? false}
								{stopResponse}
								{createMessagePair}
								onChange={(input) => {
									if (input.prompt) {
										localStorage.setItem(`chat-input-${$chatId}`, JSON.stringify(input));
									} else {
										localStorage.removeItem(`chat-input-${$chatId}`);
									}
								}}
								on:upload={async (e) => {
									const { type, data } = e.detail;

									if (type === 'web') {
										await uploadWeb(data);
									} else if (type === 'youtube') {
										await uploadYoutubeTranscription(data);
									} else if (type === 'google-drive') {
										await uploadGoogleDriveFile(data);
									}
								}}
								on:submit={async (e) => {
									if (e.detail || files.length > 0) {
										await tick();
										submitPrompt(
											($settings?.richTextInput ?? true)
												? e.detail.replaceAll('\n\n', '\n')
												: e.detail
										);
									}
								}}
							/>

							<div
								class="absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
							>
								<!-- {$i18n.t('LLMs can make mistakes. Verify important information.')} -->
							</div>
						</div>
					{:else}
						<div class="overflow-auto w-full h-full flex items-center">
							<Placeholder
								{history}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								bind:selectedToolIds
								bind:imageGenerationEnabled
								bind:codeInterpreterEnabled
								bind:webSearchEnabled
								bind:atSelectedModel
								transparentBackground={$settings?.backgroundImageUrl ?? false}
								toolServers={$toolServers}
								{stopResponse}
								{createMessagePair}
								on:upload={async (e) => {
									const { type, data } = e.detail;

									if (type === 'web') {
										await uploadWeb(data);
									} else if (type === 'youtube') {
										await uploadYoutubeTranscription(data);
									}
								}}
								on:submit={async (e) => {
									if (e.detail || files.length > 0) {
										await tick();
										submitPrompt(
											($settings?.richTextInput ?? true)
												? e.detail.replaceAll('\n\n', '\n')
												: e.detail
										);
									}
								}}
							/>
						</div>
					{/if}
				</div>
			</Pane>

			<ChatControls
				bind:this={controlPaneComponent}
				bind:history
				bind:chatFiles
				bind:params
				bind:files
				bind:pane={controlPane}
				chatId={$chatId}
				modelId={selectedModelIds?.at(0) ?? null}
				models={selectedModelIds.reduce((a, e, i, arr) => {
					const model = $models.find((m) => m.id === e);
					if (model) {
						return [...a, model];
					}
					return a;
				}, [])}
				{submitPrompt}
				{stopResponse}
				{showMessage}
				{eventTarget}
			/>
		</PaneGroup>
	{:else if loading}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner />
			</div>
		</div>
	{/if}
</div>
