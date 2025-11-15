<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';
	import { createPicker, getAuthToken } from '$lib/utils/google-drive-picker';
	import { pickAndDownloadFile } from '$lib/utils/onedrive-file-picker';
	import TurndownService from 'turndown';

	import { onMount, tick, getContext, createEventDispatcher, onDestroy } from 'svelte';
	const dispatch = createEventDispatcher();
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';

	import {
		type Model,
		mobile,
		settings,
		showSidebar,
		models,
		config,
		showCallOverlay,
		tools,
		user as _user,
		showControls,
		TTSWorker
	} from '$lib/stores';

	import {
		blobToFile,
		compressImage,
		createMessagesList,
		extractCurlyBraceWords
	} from '$lib/utils';
	import { transcribeAudio } from '$lib/apis/audio';
	import { uploadFile } from '$lib/apis/files';
	import { generateAutoCompletion } from '$lib/apis';
	import { deleteFileById } from '$lib/apis/files';

	import { WEBUI_BASE_URL, WEBUI_API_BASE_URL, PASTED_TEXT_CHARACTER_LIMIT } from '$lib/constants';

	import InputMenu from './MessageInput/InputMenu.svelte';
	import VoiceRecording from './MessageInput/VoiceRecording.svelte';
	import FilesOverlay from './MessageInput/FilesOverlay.svelte';
	import Commands from './MessageInput/Commands.svelte';

	import RichTextInput from '../common/RichTextInput.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import FileItem from '../common/FileItem.svelte';
	import Image from '../common/Image.svelte';

	import XMark from '../icons/XMark.svelte';
	import Headphone from '../icons/Headphone.svelte';
	import GlobeAlt from '../icons/GlobeAlt.svelte';
	import PhotoSolid from '../icons/PhotoSolid.svelte';
	import Photo from '../icons/Photo.svelte';
	import CommandLine from '../icons/CommandLine.svelte';
	import LightBlub from '../icons/LightBlub.svelte';
	import { KokoroWorker } from '$lib/workers/KokoroWorker';
	import ToolServersModal from './ToolServersModal.svelte';
	import Wrench from '../icons/Wrench.svelte';
	import ChatBubbleOvalEllipsis from '../icons/ChatBubbleOvalEllipsis.svelte';

	import {
		isReasoningCapable,
		shouldIlluminateThinking,
		isThinkingClickable,
		getReasoningTargetModel,
		createReasoningState,
		persistReasoningState,
		loadReasoningState,
		type ReasoningState
	} from '$lib/utils/reasoning';

	const i18n = getContext('i18n');

	// Configure TurndownService for HTML to Markdown conversion
	const turndownService = new TurndownService({
		codeBlockStyle: 'fenced',
		headingStyle: 'atx'
	});
	turndownService.escape = (string) => string;

	export let transparentBackground = false;

	export let onChange: Function = () => {};
	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined = undefined;
	export let selectedModels: string[];

	let selectedModelIds = [];
	$: selectedModelIds = atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels;

	export let history;
	export let taskIds = null;
	export let chatId: string | undefined = undefined;

	export let prompt = '';
	export let files = [];

	export let toolServers = [];

	export let selectedToolIds = [];

	export let imageGenerationEnabled = false;
	export let webSearchEnabled = false;
	export let codeInterpreterEnabled = false;

	// Reasoning mode state
	let reasoningState: ReasoningState | null = null;
	let currentReasoningModel: Model | undefined = undefined;

	$: onChange({
		prompt,
		files,
		selectedToolIds,
		imageGenerationEnabled,
		webSearchEnabled,
		verbosity: history?.verbosity
	});

	// Load reasoning state when history changes
	$: if (history) {
		reasoningState = loadReasoningState(history);
	}

	// Handle model changes while in thinking mode
	$: if (currentModel && reasoningState?.isThinkingMode) {
		// If user switched to a different model while in thinking mode, update reasoning state accordingly
		if (
			currentModel.id !== reasoningState.reasoningModel &&
			currentModel.id !== reasoningState.baseModel
		) {
			// User switched to a completely different model, reset reasoning state
			reasoningState = null;
			persistReasoningState(history, null);
			// Also clear any effort selection when switching models
			if (history) {
				delete history.reasoningEffort;
			}
		}
	}

	// Clear reasoning state when switching between different reasoning behavior types
	// We need to track the previous model to detect actual model switches
	let previousModelId: string | undefined = undefined;
	$: if (currentModel) {
		const currentModelId = currentModel.id;

		// Only process if we have both a previous model and current model, and they're different
		if (previousModelId && previousModelId !== currentModelId && reasoningState) {
			const previousModel = $models.find((m) => m.id === previousModelId);

			if (previousModel) {
				const previousModelDetails = (previousModel?.info?.meta as any)?.model_details;
				const currentModelDetails = (currentModel?.info?.meta as any)?.model_details;

				// If we're switching from set_effort to non-set_effort or vice versa, clear the state
				const prevWasSetEffort = previousModelDetails?.reasoning_behavior === 'set_effort';
				const currentIsSetEffort = currentModelDetails?.reasoning_behavior === 'set_effort';

				if (prevWasSetEffort !== currentIsSetEffort) {
					reasoningState = null;
					persistReasoningState(history, null);
					if (history) {
						delete history.reasoningEffort;
					}
				}
			}
		}

		// Set default effort when switching models (only if model actually changed)
		if (history && previousModelId !== currentModelId) {
			const modelParams = currentModel?.info?.params as any;
			const defaultEffort = modelParams?.reasoning?.effort;
			if (defaultEffort && history.reasoningEffort === undefined) {
				history.reasoningEffort = defaultEffort;
			}
		}

		// Update the tracking variable for next time
		previousModelId = currentModelId;
	}

	// Get the current selected model
	$: currentModel =
		atSelectedModel ||
		(selectedModels?.[0] ? $models.find((m) => m.id === selectedModels[0]) : undefined);

	// Determine if thinking button should be illuminated
	$: isThinkingIlluminated = currentModel
		? shouldIlluminateThinking(
				currentModel,
				$models,
				reasoningState || undefined,
				history?.reasoningEffort
			)
		: false;

	// Determine if thinking button should be clickable
	$: isThinkingEnabled =
		(currentModel ? isThinkingClickable(currentModel, $models) : false) ||
		(reasoningState?.isThinkingMode ?? false);

	// Determine if thinking button should be visible
	$: shouldShowThinkingButton =
		(currentModel ? isReasoningCapable(currentModel, $models) : false) ||
		(reasoningState?.isThinkingMode ?? false) ||
		(currentModel?.info?.meta as any)?.model_details?.response_structure ===
			'Native Chain-of-Thought Reasoning' ||
		(currentModel?.info?.meta as any)?.model_details?.response_structure === 'Hybrid CoT Reasoning';

	// Debug reactive variables
	$: {
		// console.log('Reactive update:', {
		// 	currentModel: currentModel?.id,
		// 	isThinkingIlluminated,
		// 	isThinkingEnabled,
		// 	shouldShowThinkingButton,
		// 	reasoningState: reasoningState?.isThinkingMode ? 'thinking' : 'normal',
		// 	atSelectedModel: atSelectedModel?.id,
		// 	selectedModels: selectedModels?.[0]
		// });
	}

	// Helpers to detect behavior
	const currentModelDetails = () => (currentModel?.info?.meta as any)?.model_details;
	$: isSetEffortBehavior = currentModel
		? currentModelDetails()?.reasoning_behavior === 'set_effort'
		: false;

	// Get current effort display text
	$: currentEffortDisplay = ((currentModel) => {
		// including currentModel so that this updates on model change
		const effort = history?.reasoningEffort;
		if (!effort) return 'Default';
		return effort.charAt(0).toUpperCase() + effort.slice(1);
	})(currentModel); // Toggle reasoning mode or open effort menu

	// Verbosity functionality
	$: supportsVerbosity = currentModel?.info?.meta?.capabilities?.verbosity === true;

	// Initialize verbosity to medium if not set
	$: if (supportsVerbosity && history && !history.verbosity) {
		history.verbosity = 'medium';
	}

	// Get current verbosity display text
	$: currentVerbosityDisplay = ((currentModel) => {
		// including currentModel so that this updates on model change
		const verbosity = history?.verbosity ?? 'medium';
		return verbosity.charAt(0).toUpperCase() + verbosity.slice(1);
	})(currentModel);

	// Apply selected verbosity choice
	const applyVerbosityChoice = (verbosity: 'low' | 'medium' | 'high') => {
		if (!currentModel) return;

		// Update verbosity setting on history so message creation can add it to the request body
		if (history) {
			history.verbosity = verbosity;
		}
	};

	const toggleReasoningMode = () => {
		console.log('toggleReasoningMode called:', {
			currentModel: currentModel?.id,
			isThinkingEnabled,
			reasoningState,
			isSetEffort: isSetEffortBehavior
		});

		if (!currentModel || !isThinkingEnabled) {
			console.log('Early return - no current model or thinking not enabled');
			return;
		}

		// When behavior is set_effort, the dropdown will be handled by DropdownMenu component
		// So we just handle the toggle logic for non-set_effort behaviors
		if (isSetEffortBehavior) {
			console.log('Early return - set_effort behavior should not call toggleReasoningMode!');
			return; // DropdownMenu handles the UI
		}

		if (reasoningState?.isThinkingMode) {
			console.log('Exiting thinking mode');
			// Exit thinking mode - return to base model
			const baseModelId = reasoningState.baseModel;
			const baseModel = $models.find((m) => m.id === baseModelId);

			if (baseModel) {
				// Switch back to base model
				if (atSelectedModel) {
					atSelectedModel = baseModel;
				} else {
					selectedModels = [baseModelId];
				}
			}

			// Clear reasoning state
			reasoningState = null;
			persistReasoningState(history, null);
		} else {
			console.log('Entering thinking mode');
			// Enter thinking mode
			const models = getReasoningTargetModel(currentModel, $models);
			console.log('Reasoning models found:', models);

			if (models) {
				const { base, target } = models;

				// Create reasoning state
				reasoningState = createReasoningState(base, target);
				persistReasoningState(history, reasoningState);

				// Switch to reasoning model
				if (atSelectedModel) {
					atSelectedModel = target;
				} else {
					selectedModels = [target.id];
				}
			} else {
				console.log('No target model found or same model, using same model reasoning');
				// For non-switching behaviors (reasoning effort, etc.), just set the state
				reasoningState = {
					isThinkingMode: true,
					baseModel: currentModel.id,
					reasoningModel: currentModel.id
				};
				persistReasoningState(history, reasoningState);
			}
		}

		console.log('toggleReasoningMode finished:', { reasoningState });
	};

	// Apply selected effort choice
	const applyEffortChoice = (effort: 'minimal' | 'low' | 'medium' | 'high' | null) => {
		if (!currentModel) return;

		// Ensure we enter thinking mode state pinned to this model
		reasoningState = {
			isThinkingMode: effort !== null,
			baseModel: currentModel.id,
			reasoningModel: currentModel.id
		};
		persistReasoningState(history, reasoningState);

		// Update model details at runtime override (stored on history for request creation layer to read)
		// We persist the chosen effort on history so message creation can add it to the request body.
		if (history) {
			history.reasoningEffort = effort; // null clears, others set
		}
	};

	let showTools = false;

	let loaded = false;
	let recording = false;

	let isComposing = false;

	let chatInputContainerElement;
	let chatInputElement;

	let filesInputElement;
	let commandsElement;

	let inputFiles;
	let dragged = false;

	let user = null;
	export let placeholder = '';

	let visionCapableModels = [];
	$: visionCapableModels = [...(atSelectedModel ? [atSelectedModel] : selectedModels)].filter(
		(model) => $models.find((m) => m.id === model)?.info?.meta?.capabilities?.vision ?? true
	);

	const scrollToBottom = () => {
		const element = document.getElementById('messages-container');
		element.scrollTo({
			top: element.scrollHeight,
			behavior: 'smooth'
		});
	};

	const screenCaptureHandler = async () => {
		try {
			// Request screen media
			const mediaStream = await navigator.mediaDevices.getDisplayMedia({
				video: { cursor: 'never' },
				audio: false
			});
			// Once the user selects a screen, temporarily create a video element
			const video = document.createElement('video');
			video.srcObject = mediaStream;
			// Ensure the video loads without affecting user experience or tab switching
			await video.play();
			// Set up the canvas to match the video dimensions
			const canvas = document.createElement('canvas');
			canvas.width = video.videoWidth;
			canvas.height = video.videoHeight;
			// Grab a single frame from the video stream using the canvas
			const context = canvas.getContext('2d');
			context.drawImage(video, 0, 0, canvas.width, canvas.height);
			// Stop all video tracks (stop screen sharing) after capturing the image
			mediaStream.getTracks().forEach((track) => track.stop());

			// bring back focus to this current tab, so that the user can see the screen capture
			window.focus();

			// Convert the canvas to a Base64 image URL
			await new Promise<void>((resolve) =>
				canvas.toBlob(async (blob) => {
					if (blob) {
						const file = new File([blob], `capture-${Date.now()}.png`, { type: 'image/png' });
						const uploaded = await uploadFileHandler(file);
						if (uploaded) {
							files = files.map((item) =>
								item?.id === uploaded.id
									? {
											...item,
											type: 'image',
											url: `${WEBUI_API_BASE_URL}/files/${uploaded.id}/content`
										}
									: item
							);
						}
					}
					resolve();
				}, 'image/png')
			);
			// Clean memory: Clear video srcObject
			video.srcObject = null;
		} catch (error) {
			// Handle any errors (e.g., user cancels screen sharing)
			console.error('Error capturing screen:', error);
		}
	};

	const uploadFileHandler = async (file, fullContext: boolean = false) => {
		if ($_user?.role !== 'admin' && !($_user?.permissions?.chat?.file_upload ?? true)) {
			toast.error($i18n.t('You do not have permission to upload files.'));
			return null;
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: '',
			name: file.name,
			collection_name: '',
			status: 'uploading',
			size: file.size,
			error: '',
			itemId: tempItemId,
			...(fullContext ? { context: 'full' } : {})
		};

		if (fileItem.size == 0) {
			toast.error($i18n.t('You cannot upload an empty file.'));
			return null;
		}

		files = [...files, fileItem];

		try {
			// During the file upload, file content is automatically extracted.
			const uploadedFile = await uploadFile(localStorage.token, file);

			if (uploadedFile) {
				console.log('File upload completed:', {
					id: uploadedFile.id,
					name: fileItem.name,
					collection: uploadedFile?.meta?.collection_name
				});

				if (uploadedFile.error) {
					console.warn('File upload warning:', uploadedFile.error);
					toast.warning(uploadedFile.error);
				}

				fileItem.status = 'uploaded';
				fileItem.file = uploadedFile;
				fileItem.id = uploadedFile.id;
				fileItem.collection_name =
					uploadedFile?.meta?.collection_name || uploadedFile?.collection_name;
				fileItem.url = `${WEBUI_API_BASE_URL}/files/${uploadedFile.id}`;

				files = files;
				return uploadedFile;
			} else {
				files = files.filter((item) => item?.itemId !== tempItemId);
				return null;
			}
		} catch (e) {
			toast.error(`${e}`);
			files = files.filter((item) => item?.itemId !== tempItemId);
			return null;
		}
	};

	const inputFilesHandler = async (inputFiles) => {
		console.log('Input files handler called with:', inputFiles);
		inputFiles.forEach((file) => {
			console.log('Processing file:', {
				name: file.name,
				type: file.type,
				size: file.size,
				extension: file.name.split('.').at(-1)
			});

			if (
				($config?.file?.max_size ?? null) !== null &&
				file.size > ($config?.file?.max_size ?? 0) * 1024 * 1024
			) {
				console.log('File exceeds max size limit:', {
					fileSize: file.size,
					maxSize: ($config?.file?.max_size ?? 0) * 1024 * 1024
				});
				toast.error(
					$i18n.t(`File size should not exceed {{maxSize}} MB.`, {
						maxSize: $config?.file?.max_size
					})
				);
				return;
			}

			if (
				['image/gif', 'image/webp', 'image/jpeg', 'image/png', 'image/avif'].includes(file['type'])
			) {
				if (visionCapableModels.length === 0) {
					toast.error($i18n.t('Selected model(s) do not support image inputs'));
					return;
				}
				let processAndUpload = async () => {
					let toUpload: File = file;
					if ($settings?.imageCompression ?? false) {
						const width = $settings?.imageCompressionSize?.width ?? null;
						const height = $settings?.imageCompressionSize?.height ?? null;
						if (width || height) {
							// Compress to a data URL then convert to a File
							const compressedUrl = await compressImage(
								await new Promise<string>((resolve) => {
									const r = new FileReader();
									r.onload = (e) => resolve(String(e.target?.result || ''));
									r.readAsDataURL(file);
								}),
								width,
								height
							);
							const res = await fetch(compressedUrl);
							const blob = await res.blob();
							toUpload = new File([blob], file.name, { type: file.type });
						}
					}
					const uploaded = await uploadFileHandler(toUpload);
					if (uploaded) {
						// Convert the just-uploaded entry into an image item with direct content URL
						files = files.map((item) =>
							item?.id === uploaded.id
								? {
										...item,
										type: 'image',
										url: `${WEBUI_API_BASE_URL}/files/${uploaded.id}/content`
									}
								: item
						);
					}
				};
				processAndUpload();
			} else {
				uploadFileHandler(file);
			}
		});
	};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			console.log('Escape');
			dragged = false;
		}
	};

	const onDragOver = (e) => {
		e.preventDefault();

		// Check if a file is being dragged.
		if (e.dataTransfer?.types?.includes('Files')) {
			dragged = true;
		} else {
			dragged = false;
		}
	};

	const onDragLeave = () => {
		dragged = false;
	};

	const onDrop = async (e) => {
		e.preventDefault();
		console.log(e);

		if (e.dataTransfer?.files) {
			const inputFiles = Array.from(e.dataTransfer?.files);
			if (inputFiles && inputFiles.length > 0) {
				console.log(inputFiles);
				inputFilesHandler(inputFiles);
			}
		}

		dragged = false;
	};

	onMount(async () => {
		loaded = true;

		window.setTimeout(() => {
			const chatInput = document.getElementById('chat-input');
			chatInput?.focus();
		}, 0);

		window.addEventListener('keydown', handleKeyDown);

		await tick();

		const dropzoneElement = document.getElementById('chat-container');

		dropzoneElement?.addEventListener('dragover', onDragOver);
		dropzoneElement?.addEventListener('drop', onDrop);
		dropzoneElement?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		console.log('destroy');
		window.removeEventListener('keydown', handleKeyDown);

		const dropzoneElement = document.getElementById('chat-container');

		if (dropzoneElement) {
			dropzoneElement?.removeEventListener('dragover', onDragOver);
			dropzoneElement?.removeEventListener('drop', onDrop);
			dropzoneElement?.removeEventListener('dragleave', onDragLeave);
		}
	});
</script>

<FilesOverlay show={dragged} />

<ToolServersModal bind:show={showTools} {selectedToolIds} />

{#if loaded}
	<div class="w-full font-primary">
		<div class=" mx-auto inset-x-0 bg-transparent flex justify-center">
			<div
				class="flex flex-col px-3 {($settings?.widescreenMode ?? null)
					? 'max-w-full'
					: 'max-w-6xl'} w-full"
			>
				<div class="relative">
					{#if autoScroll === false && history?.currentId}
						<div
							class=" absolute -top-12 left-0 right-0 flex justify-center z-30 pointer-events-none"
						>
							<button
								class=" bg-white border border-gray-100 dark:border-none dark:bg-white/20 p-1.5 rounded-full pointer-events-auto"
								on:click={() => {
									autoScroll = true;
									scrollToBottom();
								}}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-5 h-5"
								>
									<path
										fill-rule="evenodd"
										d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 111.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>
						</div>
					{/if}
				</div>

				<div class="w-full relative">
					{#if atSelectedModel !== undefined || selectedToolIds.length > 0 || webSearchEnabled || ($settings?.webSearch ?? false) === 'always' || imageGenerationEnabled || codeInterpreterEnabled}
						<div
							class="px-3 pb-0.5 pt-1.5 text-left w-full flex flex-col absolute bottom-0 left-0 right-0 bg-linear-to-t from-white dark:from-gray-900 z-10"
						>
							{#if atSelectedModel !== undefined}
								<div class="flex items-center justify-between w-full">
									<div class="pl-[1px] flex items-center gap-2 text-sm dark:text-gray-500">
										<img
											alt="model profile"
											class="size-3.5 max-w-[28px] object-cover rounded-full"
											src={$models.find((model) => model.id === atSelectedModel.id)?.info?.meta
												?.profile_image_url ??
												($i18n.language === 'dg-DG'
													? `/doge.png`
													: `${WEBUI_BASE_URL}/static/favicon.png`)}
										/>
										<div class="translate-y-[0.5px]">
											Talking to <span class=" font-medium">{atSelectedModel.name}</span>
										</div>
									</div>
									<div>
										<button
											class="flex items-center dark:text-gray-500"
											on:click={() => {
												atSelectedModel = undefined;
											}}
										>
											<XMark />
										</button>
									</div>
								</div>
							{/if}
						</div>
					{/if}

					<Commands
						bind:this={commandsElement}
						bind:prompt
						bind:files
						on:upload={(e) => {
							dispatch('upload', e.detail);
						}}
						on:select={(e) => {
							const data = e.detail;

							if (data?.type === 'model') {
								atSelectedModel = data.data;
							}

							const chatInputElement = document.getElementById('chat-input');
							chatInputElement?.focus();
						}}
					/>
				</div>
			</div>
		</div>

		<div class="{transparentBackground ? 'bg-transparent' : 'bg-white dark:bg-gray-900'} ">
			<div
				class="{($settings?.widescreenMode ?? null)
					? 'max-w-full'
					: 'max-w-6xl'} px-2.5 mx-auto inset-x-0"
			>
				<div class="">
					<input
						bind:this={filesInputElement}
						bind:files={inputFiles}
						type="file"
						hidden
						multiple
						on:change={async () => {
							if (inputFiles && inputFiles.length > 0) {
								const _inputFiles = Array.from(inputFiles);
								inputFilesHandler(_inputFiles);
							} else {
								toast.error($i18n.t(`File not found.`));
							}

							filesInputElement.value = '';
						}}
					/>

					{#if recording}
						<VoiceRecording
							bind:recording
							on:cancel={async () => {
								recording = false;

								await tick();
								document.getElementById('chat-input')?.focus();
							}}
							on:confirm={async (e) => {
								const { text, filename } = e.detail;
								prompt = `${prompt}${text} `;

								recording = false;

								await tick();
								document.getElementById('chat-input')?.focus();

								if ($settings?.speechAutoSend ?? false) {
									dispatch('submit', prompt);
								}
							}}
						/>
					{:else}
						<form
							class="w-full flex gap-1.5"
							on:submit|preventDefault={() => {
								// check if selectedModels support image input
								dispatch('submit', prompt);
							}}
						>
							<div
								class="flex-1 flex flex-col relative w-full shadow-lg rounded-3xl border border-gray-50 dark:border-gray-850 hover:border-gray-100 focus-within:border-gray-100 hover:dark:border-gray-800 focus-within:dark:border-gray-800 transition px-1 bg-white/90 dark:bg-gray-400/5 dark:text-gray-100"
								dir={$settings?.chatDirection ?? 'auto'}
							>
								{#if files.length > 0}
									<div class="mx-2 mt-2.5 -mb-1 flex items-center flex-wrap gap-2">
										{#each files as file, fileIdx}
											{#if file.type === 'image'}
												<div class=" relative group">
													<div class="relative flex items-center">
														<Image
															src={file.url}
															alt="input"
															imageClassName=" size-14 rounded-xl object-cover"
														/>
														{#if atSelectedModel ? visionCapableModels.length === 0 : selectedModels.length !== visionCapableModels.length}
															<Tooltip
																className=" absolute top-1 left-1"
																content={$i18n.t('{{ models }}', {
																	models: [
																		...(atSelectedModel ? [atSelectedModel] : selectedModels)
																	]
																		.filter((id) => !visionCapableModels.includes(id))
																		.join(', ')
																})}
															>
																<svg
																	xmlns="http://www.w3.org/2000/svg"
																	viewBox="0 0 24 24"
																	fill="currentColor"
																	class="size-4 fill-yellow-300"
																>
																	<path
																		fill-rule="evenodd"
																		d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003ZM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75Zm0 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z"
																		clip-rule="evenodd"
																	/>
																</svg>
															</Tooltip>
														{/if}
													</div>
													<div class=" absolute -top-1 -right-1">
														<button
															class=" bg-white text-black border border-white rounded-full group-hover:visible invisible transition"
															type="button"
															on:click={() => {
																files.splice(fileIdx, 1);
																files = files;
															}}
														>
															<svg
																xmlns="http://www.w3.org/2000/svg"
																viewBox="0 0 20 20"
																fill="currentColor"
																class="size-4"
															>
																<path
																	d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
																/>
															</svg>
														</button>
													</div>
												</div>
											{:else}
												<FileItem
													item={file}
													name={file.name}
													type={file.type}
													size={file?.size}
													loading={file.status === 'uploading'}
													dismissible={true}
													edit={true}
													on:dismiss={async () => {
														if (file.type !== 'collection' && !file?.collection) {
															if (file.id) {
																// This will handle both file deletion and Chroma cleanup
																await deleteFileById(localStorage.token, file.id);
															}
														}

														// Remove from UI state
														files.splice(fileIdx, 1);
														files = files;
													}}
													on:click={() => {
														console.log(file);
													}}
												/>
											{/if}
										{/each}
									</div>
								{/if}

								<div class="px-2.5">
									{#if $settings?.richTextInput ?? true}
										<div
											class="scrollbar-hidden text-left bg-transparent dark:text-gray-100 outline-hidden w-full pt-3 px-1 resize-none h-fit max-h-80 overflow-auto"
											id="chat-input-container"
										>
											<RichTextInput
												bind:this={chatInputElement}
												bind:value={prompt}
												id="chat-input"
												messageInput={true}
												shiftEnter={!($settings?.ctrlEnterToSend ?? false) &&
													(!$mobile ||
														!(
															'ontouchstart' in window ||
															navigator.maxTouchPoints > 0 ||
															navigator.msMaxTouchPoints > 0
														))}
												placeholder={placeholder ? placeholder : $i18n.t('Send a Message')}
												largeTextAsFile={$settings?.largeTextAsFile ?? false}
												autocomplete={$config?.features?.enable_autocomplete_generation &&
													($settings?.promptAutocomplete ?? false)}
												generateAutoCompletion={async (text) => {
													if (selectedModelIds.length === 0 || !selectedModelIds.at(0)) {
														toast.error($i18n.t('Please select a model first.'));
													}

													// Get the last user message ID for tracking
													let messageId = null;
													if (history?.currentId && history?.messages) {
														const currentMessage = history.messages[history.currentId];
														if (currentMessage && currentMessage.role === 'user') {
															messageId = currentMessage.id;
														} else if (currentMessage?.parentId) {
															const parentMessage = history.messages[currentMessage.parentId];
															if (parentMessage && parentMessage.role === 'user') {
																messageId = parentMessage.id;
															}
														}
													}

													const res = await generateAutoCompletion(
														localStorage.token,
														selectedModelIds.at(0),
														text,
														history?.currentId
															? createMessagesList(history, history.currentId)
															: null,
														'search query',
														chatId,
														messageId
													).catch((error) => {
														console.log(error);

														return null;
													});

													console.log(res);
													return res;
												}}
												oncompositionstart={() => (isComposing = true)}
												oncompositionend={() => (isComposing = false)}
												on:keydown={async (e) => {
													e = e.detail.event;

													const isCtrlPressed = e.ctrlKey || e.metaKey; // metaKey is for Cmd key on Mac
													const commandsContainerElement =
														document.getElementById('commands-container');

													if (e.key === 'Escape') {
														stopResponse();
													}

													// Command/Ctrl + Shift + Enter to submit a message pair
													if (isCtrlPressed && e.key === 'Enter' && e.shiftKey) {
														e.preventDefault();
														createMessagePair(prompt);
													}

													// Check if Ctrl + R is pressed
													// if (prompt === '' && isCtrlPressed && e.key.toLowerCase() === 'r') {
													// 	e.preventDefault();
													// 	console.log('regenerate');

													// 	const regenerateButton = [
													// 		...document.getElementsByClassName('regenerate-response-button')
													// 	]?.at(-1);

													// 	regenerateButton?.click();
													// }

													if (prompt === '' && e.key == 'ArrowUp') {
														e.preventDefault();

														const userMessageElement = [
															...document.getElementsByClassName('user-message')
														]?.at(-1);

														if (userMessageElement) {
															userMessageElement.scrollIntoView({ block: 'center' });
															const editButton = [
																...document.getElementsByClassName('edit-user-message-button')
															]?.at(-1);

															editButton?.click();
														}
													}

													if (commandsContainerElement) {
														if (commandsContainerElement && e.key === 'ArrowUp') {
															e.preventDefault();
															commandsElement.selectUp();

															const commandOptionButton = [
																...document.getElementsByClassName('selected-command-option-button')
															]?.at(-1);
															commandOptionButton.scrollIntoView({ block: 'center' });
														}

														if (commandsContainerElement && e.key === 'ArrowDown') {
															e.preventDefault();
															commandsElement.selectDown();

															const commandOptionButton = [
																...document.getElementsByClassName('selected-command-option-button')
															]?.at(-1);
															commandOptionButton.scrollIntoView({ block: 'center' });
														}

														if (commandsContainerElement && e.key === 'Tab') {
															e.preventDefault();

															const commandOptionButton = [
																...document.getElementsByClassName('selected-command-option-button')
															]?.at(-1);

															commandOptionButton?.click();
														}

														if (commandsContainerElement && e.key === 'Enter') {
															e.preventDefault();

															const commandOptionButton = [
																...document.getElementsByClassName('selected-command-option-button')
															]?.at(-1);

															if (commandOptionButton) {
																commandOptionButton?.click();
															} else {
																document.getElementById('send-message-button')?.click();
															}
														}
													} else {
														if (
															!$mobile ||
															!(
																'ontouchstart' in window ||
																navigator.maxTouchPoints > 0 ||
																navigator.msMaxTouchPoints > 0
															)
														) {
															if (isComposing) {
																return;
															}

															// Uses keyCode '13' for Enter key for chinese/japanese keyboards.
															//
															// Depending on the user's settings, it will send the message
															// either when Enter is pressed or when Ctrl+Enter is pressed.
															const enterPressed =
																($settings?.ctrlEnterToSend ?? false)
																	? (e.key === 'Enter' || e.keyCode === 13) && isCtrlPressed
																	: (e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey;

															if (enterPressed) {
																e.preventDefault();
																if (prompt !== '' || files.length > 0) {
																	dispatch('submit', prompt);
																}
															}
														}
													}

													if (e.key === 'Escape') {
														console.log('Escape');
														atSelectedModel = undefined;
														selectedToolIds = [];
														webSearchEnabled = false;
														imageGenerationEnabled = false;
													}
												}}
												on:paste={async (e) => {
													e = e.detail.event;
													console.log(e);

													const clipboardData = e.clipboardData || window.clipboardData;

													if (clipboardData && clipboardData.items) {
														for (const item of clipboardData.items) {
															if (item.type.indexOf('image') !== -1) {
																const blob = item.getAsFile();
																const reader = new FileReader();

																reader.onload = function (e) {
																	files = [
																		...files,
																		{
																			type: 'image',
																			url: `${e.target.result}`
																		}
																	];
																};

																reader.readAsDataURL(blob);
															} else if (item.type === 'text/plain') {
																if ($settings?.largeTextAsFile ?? false) {
																	const text = clipboardData.getData('text/plain');

																	if (text.length > PASTED_TEXT_CHARACTER_LIMIT) {
																		e.preventDefault();
																		const blob = new Blob([text], { type: 'text/plain' });
																		const file = new File([blob], `Pasted_Text_${Date.now()}.txt`, {
																			type: 'text/plain'
																		});

																		await uploadFileHandler(file, true);
																	}
																}
															}
														}
													}
												}}
											/>
										</div>
									{:else}
										<textarea
											id="chat-input"
											dir="auto"
											bind:this={chatInputElement}
											class="scrollbar-hidden bg-transparent dark:text-gray-100 outline-hidden w-full pt-3 px-1 resize-none"
											placeholder={placeholder ? placeholder : $i18n.t('Send a Message')}
											bind:value={prompt}
											on:compositionstart={() => (isComposing = true)}
											on:compositionend={() => (isComposing = false)}
											on:keydown={async (e) => {
												const isCtrlPressed = e.ctrlKey || e.metaKey; // metaKey is for Cmd key on Mac

												// Handle Ctrl+B, Ctrl+I, Ctrl+E for formatting
												if (isCtrlPressed && ['b', 'i', 'e'].includes(e.key.toLowerCase())) {
													e.preventDefault();
													const textarea = e.target;
													const start = textarea.selectionStart;
													const end = textarea.selectionEnd;
													const selectedText = prompt.substring(start, end);

													let prefix = '';
													let suffix = '';

													switch (e.key.toLowerCase()) {
														case 'b':
															prefix = '**';
															suffix = '**';
															break;
														case 'i':
															prefix = '_';
															suffix = '_';
															break;
														case 'e':
															prefix = '`';
															suffix = '`';
															break;
													}

													const textBefore = prompt.substring(start - prefix.length, start);
													const textAfter = prompt.substring(end, end + suffix.length);

													if (textBefore === prefix && textAfter === suffix) {
														// Remove formatting
														prompt =
															prompt.substring(0, start - prefix.length) +
															selectedText +
															prompt.substring(end + suffix.length);

														await tick();
														textarea.focus();
														textarea.selectionStart = start - prefix.length;
														textarea.selectionEnd = end - prefix.length;
													} else {
														// Add formatting
														prompt =
															prompt.substring(0, start) +
															prefix +
															selectedText +
															suffix +
															prompt.substring(end);

														await tick();
														textarea.focus();
														textarea.selectionStart = start + prefix.length;
														textarea.selectionEnd = end + prefix.length;
													}
													return;
												}

												const commandsContainerElement =
													document.getElementById('commands-container');

												if (e.key === 'Escape') {
													stopResponse();
												}

												// Command/Ctrl + Shift + Enter to submit a message pair
												if (isCtrlPressed && e.key === 'Enter' && e.shiftKey) {
													e.preventDefault();
													createMessagePair(prompt);
												}

												// Check if Ctrl + R is pressed
												if (prompt === '' && isCtrlPressed && e.key.toLowerCase() === 'r') {
													e.preventDefault();
													console.log('regenerate');

													const regenerateButton = [
														...document.getElementsByClassName('regenerate-response-button')
													]?.at(-1);

													regenerateButton?.click();
												}

												if (prompt === '' && e.key == 'ArrowUp') {
													e.preventDefault();

													const userMessageElement = [
														...document.getElementsByClassName('user-message')
													]?.at(-1);

													const editButton = [
														...document.getElementsByClassName('edit-user-message-button')
													]?.at(-1);

													console.log(userMessageElement);

													userMessageElement.scrollIntoView({ block: 'center' });
													editButton?.click();
												}

												if (commandsContainerElement) {
													if (commandsContainerElement && e.key === 'ArrowUp') {
														e.preventDefault();
														commandsElement.selectUp();

														const commandOptionButton = [
															...document.getElementsByClassName('selected-command-option-button')
														]?.at(-1);
														commandOptionButton.scrollIntoView({ block: 'center' });
													}

													if (commandsContainerElement && e.key === 'ArrowDown') {
														e.preventDefault();
														commandsElement.selectDown();

														const commandOptionButton = [
															...document.getElementsByClassName('selected-command-option-button')
														]?.at(-1);
														commandOptionButton.scrollIntoView({ block: 'center' });
													}

													if (commandsContainerElement && e.key === 'Enter') {
														e.preventDefault();

														const commandOptionButton = [
															...document.getElementsByClassName('selected-command-option-button')
														]?.at(-1);

														if (e.shiftKey) {
															prompt = `${prompt}\n`;
														} else if (commandOptionButton) {
															commandOptionButton?.click();
														} else {
															document.getElementById('send-message-button')?.click();
														}
													}

													if (commandsContainerElement && e.key === 'Tab') {
														e.preventDefault();

														const commandOptionButton = [
															...document.getElementsByClassName('selected-command-option-button')
														]?.at(-1);

														commandOptionButton?.click();
													}
												} else {
													if (
														!$mobile ||
														!(
															'ontouchstart' in window ||
															navigator.maxTouchPoints > 0 ||
															navigator.msMaxTouchPoints > 0
														)
													) {
														if (isComposing) {
															return;
														}

														// Prevent Enter key from creating a new line
														const isCtrlPressed = e.ctrlKey || e.metaKey;
														const enterPressed =
															($settings?.ctrlEnterToSend ?? false)
																? (e.key === 'Enter' || e.keyCode === 13) && isCtrlPressed
																: (e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey;

														console.log('Enter pressed:', enterPressed);

														if (enterPressed) {
															e.preventDefault();
														}

														// Submit the prompt when Enter key is pressed
														if ((prompt !== '' || files.length > 0) && enterPressed) {
															dispatch('submit', prompt);
														}
													}
												}

												if (e.key === 'Tab') {
													const words = extractCurlyBraceWords(prompt);

													if (words.length > 0) {
														const word = words.at(0);
														const fullPrompt = prompt;

														prompt = prompt.substring(0, word?.endIndex + 1);
														await tick();

														e.target.scrollTop = e.target.scrollHeight;
														prompt = fullPrompt;
														await tick();

														e.preventDefault();
														e.target.setSelectionRange(word?.startIndex, word.endIndex + 1);
													}

													e.target.style.height = '';
													e.target.style.height = Math.min(e.target.scrollHeight, 320) + 'px';
												}

												if (e.key === 'Escape') {
													console.log('Escape');
													atSelectedModel = undefined;
													selectedToolIds = [];
													webSearchEnabled = false;
													imageGenerationEnabled = false;
												}
											}}
											rows="1"
											on:input={async (e) => {
												e.target.style.height = '';
												e.target.style.height = Math.min(e.target.scrollHeight, 320) + 'px';
											}}
											on:focus={async (e) => {
												e.target.style.height = '';
												e.target.style.height = Math.min(e.target.scrollHeight, 320) + 'px';
											}}
											on:paste={async (e) => {
												const clipboardData = e.clipboardData || window.clipboardData;

												if (clipboardData && clipboardData.items) {
													let hasImage = false;
													let hasHtml = false;
													let htmlContent = '';

													// First pass: check what types of content we have
													for (const item of clipboardData.items) {
														if (item.type.indexOf('image') !== -1) {
															hasImage = true;
														} else if (item.type === 'text/html') {
															hasHtml = true;
															htmlContent = clipboardData.getData('text/html');
														}
													}

													// Process content based on what we found
													for (const item of clipboardData.items) {
														if (item.type.indexOf('image') !== -1) {
															const blob = item.getAsFile();
															const reader = new FileReader();

															reader.onload = function (e) {
																files = [
																	...files,
																	{
																		type: 'image',
																		url: `${e.target.result}`
																	}
																];
															};

															reader.readAsDataURL(blob);
														} else if (
															item.type === 'text/html' &&
															hasHtml &&
															($settings?.pasteAsMarkdown ?? true)
														) {
															// Convert HTML to Markdown and insert at cursor position (only if enabled)
															e.preventDefault();
															const textarea = e.target;

															try {
																// Convert HTML to markdown
																const markdownText = turndownService.turndown(htmlContent);

																// Use document.execCommand to maintain undo functionality
																// First, focus the textarea to ensure it's the active element
																textarea.focus();

																// Insert the markdown text using execCommand for proper undo support
																if (
																	document.execCommand &&
																	document.execCommand('insertText', false, markdownText)
																) {
																	// execCommand worked, update the prompt binding
																	prompt = textarea.value;
																} else {
																	// Fallback for browsers that don't support execCommand
																	const startPos = textarea.selectionStart;
																	const endPos = textarea.selectionEnd;
																	const beforeText = prompt.substring(0, startPos);
																	const afterText = prompt.substring(endPos);
																	prompt = beforeText + markdownText + afterText;

																	// Set cursor position after inserted text
																	setTimeout(() => {
																		const newPos = startPos + markdownText.length;
																		textarea.setSelectionRange(newPos, newPos);
																	}, 0);
																}

																// Trigger textarea resize
																setTimeout(() => {
																	textarea.style.height = '';
																	textarea.style.height =
																		Math.min(textarea.scrollHeight, 320) + 'px';
																}, 0);
															} catch (error) {
																console.error('Error converting HTML to markdown:', error);
																// Fall back to plain text if conversion fails
																const plainText = clipboardData.getData('text/plain');
																if (plainText) {
																	textarea.focus();
																	if (
																		document.execCommand &&
																		document.execCommand('insertText', false, plainText)
																	) {
																		prompt = textarea.value;
																	} else {
																		const startPos = textarea.selectionStart;
																		const endPos = textarea.selectionEnd;
																		const beforeText = prompt.substring(0, startPos);
																		const afterText = prompt.substring(endPos);
																		prompt = beforeText + plainText + afterText;

																		setTimeout(() => {
																			const newPos = startPos + plainText.length;
																			textarea.setSelectionRange(newPos, newPos);
																		}, 0);
																	}

																	// Trigger textarea resize
																	setTimeout(() => {
																		textarea.style.height = '';
																		textarea.style.height =
																			Math.min(textarea.scrollHeight, 320) + 'px';
																	}, 0);
																}
															}
														} else if (
															item.type === 'text/plain' &&
															(!hasHtml || !($settings?.pasteAsMarkdown ?? true))
														) {
															// Only process plain text if there's no HTML content
															if ($settings?.largeTextAsFile ?? false) {
																const text = clipboardData.getData('text/plain');

																if (text.length > PASTED_TEXT_CHARACTER_LIMIT) {
																	e.preventDefault();
																	const blob = new Blob([text], { type: 'text/plain' });
																	const file = new File([blob], `Pasted_Text_${Date.now()}.txt`, {
																		type: 'text/plain'
																	});

																	await uploadFileHandler(file, true);
																}
															}
														}
													}
												}
											}}
										/>
									{/if}
								</div>

								<div class=" flex justify-between mt-1 mb-2.5 mx-0.5 max-w-full" dir="ltr">
									<div class="ml-1 self-end flex items-center flex-1 max-w-[80%] gap-0.5">
										<InputMenu
											bind:selectedToolIds
											{screenCaptureHandler}
											{inputFilesHandler}
											uploadFilesHandler={() => {
												filesInputElement.click();
											}}
											uploadGoogleDriveHandler={async () => {
												try {
													const fileData = await createPicker();
													if (fileData) {
														const file = new File([fileData.blob], fileData.name, {
															type: fileData.blob.type
														});
														await uploadFileHandler(file);
													} else {
														console.log('No file was selected from Google Drive');
													}
												} catch (error) {
													console.error('Google Drive Error:', error);
													toast.error(
														$i18n.t('Error accessing Google Drive: {{error}}', {
															error: error.message
														})
													);
												}
											}}
											uploadOneDriveHandler={async () => {
												try {
													const fileData = await pickAndDownloadFile();
													if (fileData) {
														const file = new File([fileData.blob], fileData.name, {
															type: fileData.blob.type || 'application/octet-stream'
														});
														await uploadFileHandler(file);
													} else {
														console.log('No file was selected from OneDrive');
													}
												} catch (error) {
													console.error('OneDrive Error:', error);
												}
											}}
											onClose={async () => {
												await tick();

												const chatInput = document.getElementById('chat-input');
												chatInput?.focus();
											}}
										>
											<button
												class="bg-transparent hover:bg-gray-100 text-gray-800 dark:text-white dark:hover:bg-gray-800 transition rounded-full p-1.5 outline-hidden focus:outline-hidden"
												type="button"
												aria-label="More"
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 20 20"
													fill="currentColor"
													class="size-5"
												>
													<path
														d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z"
													/>
												</svg>
											</button>
										</InputMenu>

										<div class="flex gap-1 items-center overflow-x-auto scrollbar-none flex-1">
											{#if toolServers.length + selectedToolIds.length > 0}
												<Tooltip
													content={$i18n.t('{{COUNT}} Available Tools', {
														COUNT: toolServers.length + selectedToolIds.length
													})}
												>
													<button
														class="translate-y-[0.5px] flex gap-1 items-center text-gray-600 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg p-1 self-center transition"
														aria-label="Available Tools"
														type="button"
														on:click={() => {
															showTools = !showTools;
														}}
													>
														<Wrench className="size-4" strokeWidth="1.75" />

														<span class="text-sm font-medium text-gray-600 dark:text-gray-300">
															{toolServers.length + selectedToolIds.length}
														</span>
													</button>
												</Tooltip>
											{/if}

											{#if $_user}
												{#if $config?.features?.enable_web_search && ($_user.role === 'admin' || $_user?.permissions?.features?.web_search)}
													<Tooltip content={$i18n.t('Search the internet')} placement="top">
														<button
															on:click|preventDefault={() => (webSearchEnabled = !webSearchEnabled)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border {webSearchEnabled ||
															($settings?.webSearch ?? false) === 'always'
																? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400/20 text-blue-500 dark:text-blue-400'
																: 'bg-transparent border-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
														>
															<GlobeAlt className="size-5" strokeWidth="1.75" />
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																>{$i18n.t('Web Search')}</span
															>
														</button>
													</Tooltip>
												{/if}

												{#if $config?.features?.enable_image_generation && ($_user.role === 'admin' || $_user?.permissions?.features?.image_generation)}
													<Tooltip content={$i18n.t('Generate an image')} placement="top">
														<button
															on:click|preventDefault={() =>
																(imageGenerationEnabled = !imageGenerationEnabled)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border {imageGenerationEnabled
																? 'bg-gray-50 dark:bg-gray-400/10 border-gray-100 dark:border-gray-700 text-gray-600 dark:text-gray-400'
																: 'bg-transparent border-transparent text-gray-600 dark:text-gray-300  hover:bg-gray-100 dark:hover:bg-gray-800 '}"
														>
															<Photo className="size-5" strokeWidth="1.75" />
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																>{$i18n.t('Image')}</span
															>
														</button>
													</Tooltip>
												{/if}

												{#if $config?.features?.enable_code_interpreter && ($_user.role === 'admin' || $_user?.permissions?.features?.code_interpreter)}
													<Tooltip content={$i18n.t('Execute code for analysis')} placement="top">
														<button
															on:click|preventDefault={() =>
																(codeInterpreterEnabled = !codeInterpreterEnabled)}
															type="button"
															class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border {codeInterpreterEnabled
																? 'bg-gray-50 dark:bg-gray-400/10 border-gray-100  dark:border-gray-700 text-gray-600 dark:text-gray-400  '
																: 'bg-transparent border-transparent text-gray-600 dark:text-gray-300  hover:bg-gray-100 dark:hover:bg-gray-800 '}"
														>
															<CommandLine className="size-5" strokeWidth="1.75" />
															<span
																class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																>{$i18n.t('Code Interpreter')}</span
															>
														</button>
													</Tooltip>
												{/if}

												<!-- Thinking button -->
												{#if shouldShowThinkingButton}
													{#if isSetEffortBehavior}
														<!-- Set effort behavior - show dropdown -->
														<DropdownMenu.Root>
															<DropdownMenu.Trigger asChild let:builder>
																<Tooltip
																	content={$i18n.t('Select reasoning effort')}
																	placement="top"
																>
																	<button
																		use:builder.action
																		{...builder}
																		type="button"
																		disabled={!isThinkingEnabled}
																		class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border {isThinkingIlluminated
																			? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400/20 text-blue-500 dark:text-blue-400'
																			: !isThinkingEnabled
																				? 'bg-transparent border-transparent text-gray-400 dark:text-gray-600 cursor-not-allowed'
																				: 'bg-transparent border-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
																	>
																		<LightBlub className="size-5" strokeWidth="1.75" />
																		<span
																			class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																			>{currentEffortDisplay}...</span
																		>
																	</button>
																</Tooltip>
															</DropdownMenu.Trigger>

															<DropdownMenu.Content
																class="w-44 rounded-xl px-1 py-1 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
																sideOffset={10}
																alignOffset={0}
																side="top"
																align="end"
																transition={flyAndScale}
															>
																<DropdownMenu.Item
																	class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {!history?.reasoningEffort
																		? 'bg-gray-50 dark:bg-gray-700/50'
																		: ''}"
																	on:click={() => applyEffortChoice(null)}
																>
																	<div class="w-4 h-4 flex items-center justify-center">
																		{#if !history?.reasoningEffort}
																			<svg
																				class="w-3 h-3 text-grey-900"
																				fill="currentColor"
																				viewBox="0 0 20 20"
																			>
																				<path
																					fill-rule="evenodd"
																					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																		{/if}
																	</div>
																	Default
																</DropdownMenu.Item>
																<DropdownMenu.Item
																	class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.reasoningEffort ===
																	'minimal'
																		? 'bg-gray-50 dark:bg-gray-700/50'
																		: ''}"
																	on:click={() => applyEffortChoice('minimal')}
																>
																	<div class="w-4 h-4 flex items-center justify-center">
																		{#if history?.reasoningEffort === 'minimal'}
																			<svg
																				class="w-3 h-3 text-grey-900"
																				fill="currentColor"
																				viewBox="0 0 20 20"
																			>
																				<path
																					fill-rule="evenodd"
																					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																		{/if}
																	</div>
																	Minimal
																</DropdownMenu.Item>
																<DropdownMenu.Item
																	class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.reasoningEffort ===
																	'low'
																		? 'bg-gray-50 dark:bg-gray-700/50'
																		: ''}"
																	on:click={() => applyEffortChoice('low')}
																>
																	<div class="w-4 h-4 flex items-center justify-center">
																		{#if history?.reasoningEffort === 'low'}
																			<svg
																				class="w-3 h-3 text-grey-900"
																				fill="currentColor"
																				viewBox="0 0 20 20"
																			>
																				<path
																					fill-rule="evenodd"
																					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																		{/if}
																	</div>
																	Low
																</DropdownMenu.Item>
																<DropdownMenu.Item
																	class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.reasoningEffort ===
																	'medium'
																		? 'bg-gray-50 dark:bg-gray-700/50'
																		: ''}"
																	on:click={() => applyEffortChoice('medium')}
																>
																	<div class="w-4 h-4 flex items-center justify-center">
																		{#if history?.reasoningEffort === 'medium'}
																			<svg
																				class="w-3 h-3 text-grey-900"
																				fill="currentColor"
																				viewBox="0 0 20 20"
																			>
																				<path
																					fill-rule="evenodd"
																					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																		{/if}
																	</div>
																	Medium
																</DropdownMenu.Item>
																<DropdownMenu.Item
																	class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.reasoningEffort ===
																	'high'
																		? 'bg-gray-50 dark:bg-gray-700/50'
																		: ''}"
																	on:click={() => applyEffortChoice('high')}
																>
																	<div class="w-4 h-4 flex items-center justify-center">
																		{#if history?.reasoningEffort === 'high'}
																			<svg
																				class="w-3 h-3 text-grey-900"
																				fill="currentColor"
																				viewBox="0 0 20 20"
																			>
																				<path
																					fill-rule="evenodd"
																					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																					clip-rule="evenodd"
																				/>
																			</svg>
																		{/if}
																	</div>
																	High
																</DropdownMenu.Item>
															</DropdownMenu.Content>
														</DropdownMenu.Root>
													{:else}
														<!-- Regular toggle behavior -->
														<Tooltip content={$i18n.t('Toggle reasoning mode')} placement="top">
															<button
																on:click|preventDefault={toggleReasoningMode}
																type="button"
																disabled={!isThinkingEnabled}
																class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border {isThinkingIlluminated
																	? 'bg-blue-100 dark:bg-blue-500/20 border-blue-400/20 text-blue-500 dark:text-blue-400'
																	: !isThinkingEnabled
																		? 'bg-transparent border-transparent text-gray-400 dark:text-gray-600 cursor-not-allowed'
																		: 'bg-transparent border-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
															>
																<LightBlub className="size-5" strokeWidth="1.75" />
																<span
																	class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																	>{$i18n.t('Thinking')}</span
																>
															</button>
														</Tooltip>
													{/if}
												{/if}

												<!-- Verbosity dropdown -->
												{#if supportsVerbosity}
													<DropdownMenu.Root>
														<DropdownMenu.Trigger asChild let:builder>
															<Tooltip content={$i18n.t('Select verbosity level')} placement="top">
																<button
																	use:builder.action
																	{...builder}
																	type="button"
																	class="px-1.5 @xl:px-2.5 py-1.5 flex gap-1.5 items-center text-sm rounded-full font-medium transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden border bg-transparent border-transparent text-gray-600 dark:text-gray-300 border-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
																>
																	<ChatBubbleOvalEllipsis className="size-5" strokeWidth="1.75" />
																	<span
																		class="hidden @xl:block whitespace-nowrap overflow-hidden text-ellipsis translate-y-[0.5px]"
																		>{currentVerbosityDisplay}...</span
																	>
																</button>
															</Tooltip>
														</DropdownMenu.Trigger>

														<DropdownMenu.Content
															class="w-44 rounded-xl px-1 py-1 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
															sideOffset={10}
															alignOffset={0}
															side="top"
															align="end"
															transition={flyAndScale}
														>
															<DropdownMenu.Item
																class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.verbosity ===
																'low'
																	? 'bg-gray-50 dark:bg-gray-700/50'
																	: ''}"
																on:click={() => applyVerbosityChoice('low')}
															>
																<div class="w-4 h-4 flex items-center justify-center">
																	{#if history?.verbosity === 'low'}
																		<svg
																			class="w-3 h-3 text-grey-900"
																			fill="currentColor"
																			viewBox="0 0 20 20"
																		>
																			<path
																				fill-rule="evenodd"
																				d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																				clip-rule="evenodd"
																			/>
																		</svg>
																	{/if}
																</div>
																Low
															</DropdownMenu.Item>
															<DropdownMenu.Item
																class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.verbosity ===
																'medium'
																	? 'bg-gray-50 dark:bg-gray-700/50'
																	: ''}"
																on:click={() => applyVerbosityChoice('medium')}
															>
																<div class="w-4 h-4 flex items-center justify-center">
																	{#if history?.verbosity === 'medium'}
																		<svg
																			class="w-3 h-3 text-grey-900"
																			fill="currentColor"
																			viewBox="0 0 20 20"
																		>
																			<path
																				fill-rule="evenodd"
																				d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																				clip-rule="evenodd"
																			/>
																		</svg>
																	{/if}
																</div>
																Medium
															</DropdownMenu.Item>
															<DropdownMenu.Item
																class="flex gap-2 items-center px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl {history?.verbosity ===
																'high'
																	? 'bg-gray-50 dark:bg-gray-700/50'
																	: ''}"
																on:click={() => applyVerbosityChoice('high')}
															>
																<div class="w-4 h-4 flex items-center justify-center">
																	{#if history?.verbosity === 'high'}
																		<svg
																			class="w-3 h-3 text-grey-900"
																			fill="currentColor"
																			viewBox="0 0 20 20"
																		>
																			<path
																				fill-rule="evenodd"
																				d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
																				clip-rule="evenodd"
																			/>
																		</svg>
																	{/if}
																</div>
																High
															</DropdownMenu.Item>
														</DropdownMenu.Content>
													</DropdownMenu.Root>
												{/if}
											{/if}
										</div>
									</div>

									<div class="self-end flex space-x-1 mr-1 shrink-0">
										{#if (!history?.currentId || history.messages[history.currentId]?.done == true) && ($_user?.role === 'admin' || ($_user?.permissions?.chat?.stt ?? true))}
											<Tooltip content={$i18n.t('Record voice')}>
												<button
													id="voice-input-button"
													class=" text-gray-600 dark:text-gray-300 hover:text-gray-700 dark:hover:text-gray-200 transition rounded-full p-1.5 mr-0.5 self-center"
													type="button"
													on:click={async () => {
														try {
															let stream = await navigator.mediaDevices
																.getUserMedia({ audio: true })
																.catch(function (err) {
																	toast.error(
																		$i18n.t(
																			`Permission denied when accessing microphone: {{error}}`,
																			{
																				error: err
																			}
																		)
																	);
																	return null;
																});

															if (stream) {
																recording = true;
																const tracks = stream.getTracks();
																tracks.forEach((track) => track.stop());
															}
															stream = null;
														} catch {
															toast.error($i18n.t('Permission denied when accessing microphone'));
														}
													}}
													aria-label="Voice Input"
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="w-5 h-5 translate-y-[0.5px]"
													>
														<path d="M7 4a3 3 0 016 0v6a3 3 0 11-6 0V4z" />
														<path
															d="M5.5 9.643a.75.75 0 00-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-1.5v-1.546A6.001 6.001 0 0016 10v-.357a.75.75 0 00-1.5 0V10a4.5 4.5 0 01-9 0v-.357z"
														/>
													</svg>
												</button>
											</Tooltip>
										{/if}

										{#if (taskIds && taskIds.length > 0) || (history.currentId && history.messages[history.currentId]?.done != true)}
											<div class=" flex items-center">
												<Tooltip content={$i18n.t('Stop')}>
													<button
														class="bg-white hover:bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-800 transition rounded-full p-1.5"
														on:click={() => {
															stopResponse();
														}}
													>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															viewBox="0 0 24 24"
															fill="currentColor"
															class="size-5"
														>
															<path
																fill-rule="evenodd"
																d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm6-2.438c0-.724.588-1.312 1.313-1.312h4.874c.725 0 1.313.588 1.313 1.313v4.874c0 .725-.588 1.313-1.313 1.313H9.564a1.312 1.312 0 01-1.313-1.313V9.564z"
																clip-rule="evenodd"
															/>
														</svg>
													</button>
												</Tooltip>
											</div>
										{:else if prompt === '' && files.length === 0 && ($_user?.role === 'admin' || ($_user?.permissions?.chat?.call ?? true))}
											<div class=" flex items-center">
												<Tooltip content={$i18n.t('Call')}>
													<button
														class=" bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full p-1.5 self-center"
														type="button"
														on:click={async () => {
															if (selectedModels.length > 1) {
																toast.error($i18n.t('Select only one model to call'));

																return;
															}

															if ($config.audio.stt.engine === 'web') {
																toast.error(
																	$i18n.t('Call feature is not supported when using Web STT engine')
																);

																return;
															}
															// check if user has access to getUserMedia
															try {
																let stream = await navigator.mediaDevices.getUserMedia({
																	audio: true
																});
																// If the user grants the permission, proceed to show the call overlay

																if (stream) {
																	const tracks = stream.getTracks();
																	tracks.forEach((track) => track.stop());
																}

																stream = null;

																if ($settings.audio?.tts?.engine === 'browser-kokoro') {
																	// If the user has not initialized the TTS worker, initialize it
																	if (!$TTSWorker) {
																		await TTSWorker.set(
																			new KokoroWorker({
																				dtype: $settings.audio?.tts?.engineConfig?.dtype ?? 'fp32'
																			})
																		);

																		await $TTSWorker.init();
																	}
																}

																showCallOverlay.set(true);
																showControls.set(true);
															} catch (err) {
																// If the user denies the permission or an error occurs, show an error message
																toast.error(
																	$i18n.t('Permission denied when accessing media devices')
																);
															}
														}}
														aria-label="Call"
													>
														<Headphone className="size-5" />
													</button>
												</Tooltip>
											</div>
										{:else}
											<div class=" flex items-center">
												<Tooltip content={$i18n.t('Send message')}>
													<button
														id="send-message-button"
														class="{!(prompt === '' && files.length === 0)
															? 'bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 '
															: 'text-white bg-gray-200 dark:text-gray-900 dark:bg-gray-700 disabled'} transition rounded-full p-1.5 self-center"
														type="submit"
														disabled={prompt === '' && files.length === 0}
													>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															viewBox="0 0 16 16"
															fill="currentColor"
															class="size-5"
														>
															<path
																fill-rule="evenodd"
																d="M8 14a.75.75 0 01-.75-.75V4.56L4.03 7.78a.75.75 0 01-1.06-1.06l4.5-4.5a.75.75 0 01 1.06 0l4.5 4.5a.75.75 0 01-1.06 1.06L8.75 4.56v8.69A.75.75 0 018 14Z"
																clip-rule="evenodd"
															/>
														</svg>
													</button>
												</Tooltip>
											</div>
										{/if}
									</div>
								</div>
							</div>
						</form>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
