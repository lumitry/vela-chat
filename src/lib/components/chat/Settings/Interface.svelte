<script lang="ts">
	import { getBackendConfig } from '$lib/apis';
	import { setDefaultPromptSuggestions } from '$lib/apis/configs';
	import { config, models, settings, user } from '$lib/stores';
	import { createEventDispatcher, onMount, getContext } from 'svelte';
	import { get } from 'svelte/store';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import SettingRow from './SettingRow.svelte';
	import SwitchSetting from './SwitchSetting.svelte';
	import SelectSetting from './SelectSetting.svelte';
	import ButtonSetting from './ButtonSetting.svelte';
	import SettingRenderer from './SettingRenderer.svelte';
	import ChatBackgroundImageSetting from './ChatBackgroundImageSetting.svelte';
	import ImageCompressionSizeSetting from './ImageCompressionSizeSetting.svelte';
	import {
		buildInterfaceSettings,
		chatFontScaleOptions,
		commandPaletteShortcutOptions,
		type InterfaceSettingBindings,
		type SettingConfig,
		type SettingContext
	} from './interfaceSettingsConfig';
	import { updateUserInfo } from '$lib/apis/users';
	import { getUserPosition } from '$lib/utils';
	import { setInterfaceKeywords } from './interfaceKeywords';
	const dispatch = createEventDispatcher();

	const i18n = getContext<Writable<any>>('i18n');

	const translate = (key: string): string => {
		const storeValue = get(i18n);
		return storeValue?.t ? storeValue.t(key) : key;
	};

	export let saveSettings: Function;
	export let searchQuery: string = '';

	let backgroundImageUrl: string | null = null;

	// Check if a setting matches the search query
	function settingMatchesSearch(setting: SettingConfig, query: string): boolean {
		if (!query || query.trim() === '') return false;
		const lowerQuery = query.toLowerCase().trim();

		// Check keywords
		if (setting.keywords.some((keyword) => keyword.toLowerCase().includes(lowerQuery))) {
			return true;
		}

		// Check label (using get() to access store value)
		if ('label' in setting && setting.label) {
			const label = translate(setting.label);
			if (label.toLowerCase().includes(lowerQuery)) {
				return true;
			}
		}

		return false;
	}

	// Function to update the module-level cache with all keywords
	function updateInterfaceKeywords() {
		const keywords: string[] = [];
		for (const sectionGroup of allSettings) {
			for (const setting of sectionGroup.settings) {
				keywords.push(...setting.keywords);
			}
		}
		setInterfaceKeywords(keywords);
	}

	// Helper function to build context object
	function buildContext(): SettingContext {
		return {
			chatBubble,
			richTextInput,
			imageCompression,
			backgroundImageUrl,
			config: $config,
			user: $user,
			settings: $settings
		};
	}

	// Scroll to first match when search changes
	$: if (searchQuery && searchQuery.trim() !== '') {
		// Find first matching setting
		const context = buildContext();
		let found = false;
		for (const sectionGroup of allSettings) {
			if (found) break;
			for (const setting of sectionGroup.settings) {
				if (
					(!setting.requiresAdmin || $user?.role === 'admin') &&
					(!setting.dependsOn || setting.dependsOn(context)) &&
					settingMatchesSearch(setting, searchQuery)
				) {
					// Scroll to this setting after a brief delay to allow rendering
					setTimeout(() => {
						const element = document.querySelector(`[data-setting-id="${setting.id}"]`);
						if (element) {
							element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
						}
					}, 100);
					found = true;
					break;
				}
			}
		}
	}
	let inputFiles: FileList | null = null;
	let filesInputElement: HTMLInputElement;

	// Reactively update backgroundImageUrl when settings store changes
	$: backgroundImageUrl = (($settings as Record<string, any>) ?? {}).backgroundImageUrl ?? null;

	// Addons
	let titleAutoGenerate = true;
	let autoTags = true;

	let responseAutoCopy = false;
	let widescreenMode = false;
	let splitLargeChunks = false;
	let scrollOnBranchChange = true;
	let userLocation = false;

	// Interface
	let defaultModelId = '';
	let showUsername = false;
	let notificationSound = true;

	let detectArtifacts = true;

	let richTextInput = true;
	let promptAutocomplete = false;

	let largeTextAsFile = false;
	let pasteAsMarkdown = true;
	let showHexColorSwatches = true;

	let landingPageMode = '';
	let chatBubble = true;
	let chatDirection: 'LTR' | 'RTL' | 'auto' = 'auto';
	let ctrlEnterToSend = false;
	let copyFormatted = false;
	let commandPaletteShortcut = 'cmd+p';

	let chatFontScale = 1;

	// Find the matching option value string for the current chatFontScale
	function getChatFontScaleString(scale: number): string {
		const option = chatFontScaleOptions.find(
			(opt) => Math.abs(parseFloat(opt.value) - scale) < 0.001
		);
		return option ? option.value : '1';
	}

	let chatFontScaleString = getChatFontScaleString(chatFontScale);
	$: chatFontScaleString = getChatFontScaleString(chatFontScale);

	let collapseCodeBlocks = false;
	let expandDetails = false;

	let imageCompression = false;
	let imageCompressionSize = {
		width: '',
		height: ''
	};

	// Admin - Show Update Available Toast
	let showUpdateToast = true;
	let showChangelog = true;

	let showEmojiInCall = false;
	let voiceInterruption = false;
	let hapticFeedback = false;

	let webSearch: string | null = null;

	let iframeSandboxAllowSameOrigin = false;
	let iframeSandboxAllowForms = false;

	const toggleLandingPageMode = async () => {
		landingPageMode = landingPageMode === '' ? 'chat' : '';
		saveSettings({ landingPageMode: landingPageMode });
	};

	const toggleChangeChatDirection = async () => {
		if (chatDirection === 'auto') {
			chatDirection = 'LTR';
		} else if (chatDirection === 'LTR') {
			chatDirection = 'RTL';
		} else if (chatDirection === 'RTL') {
			chatDirection = 'auto';
		}
		saveSettings({ chatDirection });
	};

	const togglectrlEnterToSend = async () => {
		ctrlEnterToSend = !ctrlEnterToSend;
		saveSettings({ ctrlEnterToSend });
	};

	const updateInterfaceHandler = async () => {
		saveSettings({
			models: [defaultModelId],
			imageCompressionSize: imageCompressionSize
		});
	};

	const toggleWebSearch = async () => {
		webSearch = webSearch === null ? 'always' : null;
		saveSettings({ webSearch: webSearch });
	};

	function handleBackgroundImageChange() {
		const reader = new FileReader();
		reader.onload = (event) => {
			const target = event.target as FileReader | null;
			const originalImageUrl = `${target?.result ?? ''}`;

			backgroundImageUrl = originalImageUrl;
			saveSettings({ backgroundImageUrl });
		};

		const file = inputFiles?.item(0);

		if (file && ['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(file.type)) {
			reader.readAsDataURL(file);
		} else if (file) {
			toast.error(`Unsupported File Type '${file.type}'.`);
			inputFiles = null;
		}
	}

	const interfaceSettingBindings: InterfaceSettingBindings = {
		landingPageMode: {
			getValue: () => landingPageMode,
			getLabel: (val: string) => (val === '' ? 'Default' : 'Chat'),
			onClick: async () => {
				await toggleLandingPageMode();
			}
		},
		chatBubble: {
			get: () => chatBubble,
			set: async (value: boolean) => {
				chatBubble = value;
				await saveSettings({ chatBubble: value });
				return true;
			}
		},
		showUsername: {
			get: () => showUsername,
			set: async (value: boolean) => {
				showUsername = value;
				await saveSettings({ showUsername: value });
				return true;
			}
		},
		widescreenMode: {
			get: () => widescreenMode,
			set: async (value: boolean) => {
				widescreenMode = value;
				await saveSettings({ widescreenMode: value });
				return true;
			}
		},
		notificationSound: {
			get: () => notificationSound,
			set: async (value: boolean) => {
				notificationSound = value;
				await saveSettings({ notificationSound: value });
				return true;
			}
		},
		showUpdateToast: {
			get: () => showUpdateToast,
			set: async (value: boolean) => {
				showUpdateToast = value;
				await saveSettings({ showUpdateToast: value });
				return true;
			}
		},
		showChangelog: {
			get: () => showChangelog,
			set: async (value: boolean) => {
				showChangelog = value;
				await saveSettings({ showChangelog: value });
				return true;
			}
		},
		chatFontSize: {
			get: () => getChatFontScaleString(chatFontScale),
			set: async (value: string) => {
				const numValue = parseFloat(value);
				if (!Number.isNaN(numValue)) {
					chatFontScale = numValue;
					await saveSettings({ chatFontScale: value });
				}
			},
			options: chatFontScaleOptions
		},
		commandPaletteShortcut: {
			get: () => commandPaletteShortcut,
			set: async (value: string) => {
				commandPaletteShortcut = value;
				await saveSettings({ commandPaletteShortcut: value });
			},
			options: commandPaletteShortcutOptions
		},
		titleAutoGenerate: {
			get: () => titleAutoGenerate,
			set: async (value: boolean) => {
				const currentSettings = ($settings as Record<string, any>) ?? {};
				titleAutoGenerate = value;
				await saveSettings({
					title: {
						...(currentSettings.title ?? {}),
						auto: value
					}
				});
				return true;
			}
		},
		autoTags: {
			get: () => autoTags,
			set: async (value: boolean) => {
				autoTags = value;
				await saveSettings({ autoTags: value });
				return true;
			}
		},
		detectArtifacts: {
			get: () => detectArtifacts,
			set: async (value: boolean) => {
				detectArtifacts = value;
				await saveSettings({ detectArtifacts: value });
				return true;
			}
		},
		responseAutoCopy: {
			get: () => responseAutoCopy,
			set: async (value: boolean) => {
				if (value) {
					if (!navigator.clipboard) {
						toast.error(
							translate('Clipboard API is not available. Please use HTTPS or localhost.')
						);
						return false;
					}

					const permission = await navigator.clipboard
						.readText()
						.then(() => {
							return 'granted';
						})
						.catch(() => {
							return '';
						});

					if (permission !== 'granted') {
						toast.error(
							translate(
								'Clipboard write permission denied. Please check your browser settings to grant the necessary access.'
							)
						);
						return false;
					}
				}

				responseAutoCopy = value;
				await saveSettings({ responseAutoCopy: value });
				return true;
			}
		},
		richTextInput: {
			get: () => richTextInput,
			set: async (value: boolean) => {
				richTextInput = value;
				await saveSettings({ richTextInput: value });
				return true;
			}
		},
		promptAutocomplete: {
			get: () => promptAutocomplete,
			set: async (value: boolean) => {
				promptAutocomplete = value;
				await saveSettings({ promptAutocomplete: value });
				return true;
			}
		},
		largeTextAsFile: {
			get: () => largeTextAsFile,
			set: async (value: boolean) => {
				largeTextAsFile = value;
				await saveSettings({ largeTextAsFile: value });
				return true;
			}
		},
		pasteAsMarkdown: {
			get: () => pasteAsMarkdown,
			set: async (value: boolean) => {
				pasteAsMarkdown = value;
				await saveSettings({ pasteAsMarkdown: value });
				return true;
			}
		},
		showHexColorSwatches: {
			get: () => showHexColorSwatches,
			set: async (value: boolean) => {
				showHexColorSwatches = value;
				await saveSettings({ showHexColorSwatches: value });
				return true;
			}
		},
		copyFormatted: {
			get: () => copyFormatted,
			set: async (value: boolean) => {
				copyFormatted = value;
				await saveSettings({ copyFormatted: value });
				return true;
			}
		},
		collapseCodeBlocks: {
			get: () => collapseCodeBlocks,
			set: async (value: boolean) => {
				collapseCodeBlocks = value;
				await saveSettings({ collapseCodeBlocks: value });
				return true;
			}
		},
		expandDetails: {
			get: () => expandDetails,
			set: async (value: boolean) => {
				expandDetails = value;
				await saveSettings({ expandDetails: value });
				return true;
			}
		},
		scrollOnBranchChange: {
			get: () => scrollOnBranchChange,
			set: async (value: boolean) => {
				scrollOnBranchChange = value;
				await saveSettings({ scrollOnBranchChange: value });
				return true;
			}
		},
		hapticFeedback: {
			get: () => hapticFeedback,
			set: async (value: boolean) => {
				hapticFeedback = value;
				await saveSettings({ hapticFeedback: value });
				return true;
			}
		},
		voiceInterruption: {
			get: () => voiceInterruption,
			set: async (value: boolean) => {
				voiceInterruption = value;
				await saveSettings({ voiceInterruption: value });
				return true;
			}
		},
		showEmojiInCall: {
			get: () => showEmojiInCall,
			set: async (value: boolean) => {
				showEmojiInCall = value;
				await saveSettings({ showEmojiInCall: value });
				return true;
			}
		},
		userLocation: {
			get: () => userLocation,
			set: async (value: boolean) => {
				if (value) {
					const position = await getUserPosition().catch((error) => {
						toast.error(error.message);
						return null;
					});

					if (position) {
						await updateUserInfo(localStorage.token, { location: position });
						toast.success(translate('User location successfully retrieved.'));
					} else {
						return false;
					}
				}

				userLocation = value;
				await saveSettings({ userLocation: value });
				return true;
			}
		},
		chatBackgroundImage: {
			component: ChatBackgroundImageSetting,
			getProps: () => ({
				backgroundImageUrl,
				filesInputElement,
				saveSettings
			})
		},
		ctrlEnterToSend: {
			getValue: () => ctrlEnterToSend,
			getLabel: (val: boolean) => (val ? 'Ctrl+Enter to Send' : 'Enter to Send'),
			onClick: async () => {
				await togglectrlEnterToSend();
			}
		},
		webSearch: {
			getValue: () => webSearch,
			getLabel: (val: string | null) => (val === 'always' ? 'Always' : 'Default'),
			onClick: async () => {
				await toggleWebSearch();
			}
		},
		iframeSandboxAllowSameOrigin: {
			get: () => iframeSandboxAllowSameOrigin,
			set: async (value: boolean) => {
				iframeSandboxAllowSameOrigin = value;
				await saveSettings({ iframeSandboxAllowSameOrigin: value });
				return true;
			}
		},
		iframeSandboxAllowForms: {
			get: () => iframeSandboxAllowForms,
			set: async (value: boolean) => {
				iframeSandboxAllowForms = value;
				await saveSettings({ iframeSandboxAllowForms: value });
				return true;
			}
		},
		imageCompression: {
			get: () => imageCompression,
			set: async (value: boolean) => {
				imageCompression = value;
				await saveSettings({ imageCompression: value });
				return true;
			}
		},
		imageCompressionSize: {
			component: ImageCompressionSizeSetting,
			getProps: () => ({
				imageCompressionSize,
				saveSettings
			})
		},
		chatDirection: {
			getValue: () => chatDirection,
			getLabel: (val: string) => {
				if (val === 'LTR') return 'LTR';
				if (val === 'RTL') return 'RTL';
				return 'Auto';
			},
			onClick: async () => {
				await toggleChangeChatDirection();
			}
		}
	};

	const allSettings = buildInterfaceSettings(interfaceSettingBindings);

	// Function to initialize local variables from settings store
	function initializeFromSettings() {
		const settingsAny = ($settings as Record<string, any>) ?? {};

		titleAutoGenerate = settingsAny?.title?.auto ?? true;
		autoTags = settingsAny.autoTags ?? true;

		detectArtifacts = settingsAny.detectArtifacts ?? true;
		responseAutoCopy = settingsAny.responseAutoCopy ?? false;

		showUsername = settingsAny.showUsername ?? false;
		showUpdateToast = settingsAny.showUpdateToast ?? true;
		showChangelog = settingsAny.showChangelog ?? true;

		showEmojiInCall = settingsAny.showEmojiInCall ?? false;
		voiceInterruption = settingsAny.voiceInterruption ?? false;

		richTextInput = settingsAny.richTextInput ?? true;
		promptAutocomplete = settingsAny.promptAutocomplete ?? false;
		largeTextAsFile = settingsAny.largeTextAsFile ?? false;
		pasteAsMarkdown = settingsAny.pasteAsMarkdown ?? true;
		showHexColorSwatches = settingsAny.showHexColorSwatches ?? true;
		copyFormatted = settingsAny.copyFormatted ?? false;
		chatFontScale = settingsAny.chatFontScale ?? 1;

		collapseCodeBlocks = settingsAny.collapseCodeBlocks ?? false;
		expandDetails = settingsAny.expandDetails ?? false;

		landingPageMode = settingsAny.landingPageMode ?? '';
		chatBubble = settingsAny.chatBubble ?? true;
		widescreenMode = settingsAny.widescreenMode ?? false;
		splitLargeChunks = settingsAny.splitLargeChunks ?? false;
		scrollOnBranchChange = settingsAny.scrollOnBranchChange ?? true;
		chatDirection = settingsAny.chatDirection ?? 'auto';
		userLocation = settingsAny.userLocation ?? false;

		notificationSound = settingsAny.notificationSound ?? true;

		hapticFeedback = settingsAny.hapticFeedback ?? false;
		ctrlEnterToSend = settingsAny.ctrlEnterToSend ?? false;

		imageCompression = settingsAny.imageCompression ?? false;
		imageCompressionSize = settingsAny.imageCompressionSize ?? { width: '', height: '' };

		defaultModelId = settingsAny?.models?.at(0) ?? '';
		if ($config?.default_models) {
			defaultModelId = $config.default_models.split(',')[0];
		}

		commandPaletteShortcut = settingsAny.commandPaletteShortcut ?? 'cmd+p';

		// backgroundImageUrl is now reactive to $settings, so no need to set it here
		const settingsState = ($settings as Record<string, any>) ?? {};
		webSearch = settingsState.webSearch ?? null;
	}

	onMount(async () => {
		// Update keywords cache when component mounts
		updateInterfaceKeywords();
		initializeFromSettings();
	});

	// Reactively update local variables when settings store changes
	// This ensures the component stays in sync when settings are reloaded from the server
	$: if ($settings) {
		initializeFromSettings();
	}
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={() => {
		updateInterfaceHandler();
		dispatch('save');
	}}
>
	<input
		bind:this={filesInputElement}
		bind:files={inputFiles}
		type="file"
		hidden
		accept="image/*"
		on:change={handleBackgroundImageChange}
	/>

	<div class=" space-y-1 overflow-y-scroll max-h-[28rem] lg:max-h-full">
		{#each allSettings as sectionGroup}
			<div>
				{#if sectionGroup.section}
					<div class=" mb-1.5 text-sm font-medium">{$i18n.t(sectionGroup.section)}</div>
				{/if}

				{#each sectionGroup.settings as setting (setting.id)}
					{@const context = buildContext()}
					{@const isMatch = settingMatchesSearch(setting, searchQuery)}
					{#if (!setting.requiresAdmin || $user?.role === 'admin') && (!setting.dependsOn || setting.dependsOn(context))}
						<div
							data-setting-id={setting.id}
							class="transition-colors {isMatch
								? 'bg-yellow-100 dark:bg-yellow-900/30 rounded px-1 py-0.5 -mx-1 -my-0.5'
								: ''}"
						>
							<SettingRenderer {setting} i18n={$i18n} {context} />
						</div>
					{/if}
				{/each}
			</div>
		{/each}
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
