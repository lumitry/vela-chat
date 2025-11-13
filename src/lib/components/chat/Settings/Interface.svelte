<script lang="ts">
	import { getBackendConfig } from '$lib/apis';
	import { setDefaultPromptSuggestions } from '$lib/apis/configs';
	import { config, models, settings, user } from '$lib/stores';
	import { createEventDispatcher, onMount, getContext } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import SettingRow from './SettingRow.svelte';
	import SwitchSetting from './SwitchSetting.svelte';
	import SelectSetting from './SelectSetting.svelte';
	import ButtonSetting from './ButtonSetting.svelte';
	import SettingRenderer from './SettingRenderer.svelte';
	import ChatBackgroundImageSetting from './ChatBackgroundImageSetting.svelte';
	import ImageCompressionSizeSetting from './ImageCompressionSizeSetting.svelte';
	import { updateUserInfo } from '$lib/apis/users';
	import { getUserPosition } from '$lib/utils';
	import { setInterfaceKeywords } from './interfaceKeywords';
	const dispatch = createEventDispatcher();

	const i18n = getContext('i18n');

	export let saveSettings: Function;
	export let searchQuery: string = '';

	let backgroundImageUrl = null;

	// Check if a setting matches the search query
	function settingMatchesSearch(setting: SettingConfig, query: string): boolean {
		if (!query || query.trim() === '') return false;
		const lowerQuery = query.toLowerCase().trim();

		// Check keywords
		if (setting.keywords.some((keyword) => keyword.toLowerCase().includes(lowerQuery))) {
			return true;
		}

		// Check label (using get() to access store value)
		const label = get(i18n).t(setting.label);
		if (label.toLowerCase().includes(lowerQuery)) {
			return true;
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
	function buildContext() {
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
	let inputFiles = null;
	let filesInputElement;

	// Reactively update backgroundImageUrl when settings store changes
	$: backgroundImageUrl = $settings.backgroundImageUrl ?? null;

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

	const chatFontScaleOptions = [
		{ value: '0.875', label: 'Small' },
		{ value: '1', label: 'Default' },
		{ value: '1.125', label: 'Large' },
		{ value: '1.25', label: 'Extra Large' }
	];
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

	let webSearch = null;

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

	type SettingContext = {
		chatBubble: boolean;
		richTextInput: boolean;
		imageCompression: boolean;
		config: any;
		user: any;
		settings: any;
	};

	type SettingConfig =
		| {
				type: 'switch';
				id: string;
				label: string;
				labelSuffix?: string;
				keywords: string[];
				get: () => boolean;
				set: (value: boolean) => boolean | Promise<boolean>;
				requiresAdmin?: boolean;
				dependsOn?: (context: SettingContext) => boolean;
		  }
		| {
				type: 'select';
				id: string;
				label: string;
				keywords: string[];
				get: () => string;
				set: (value: string) => void | Promise<void>;
				options: Array<{ value: string; label: string }>;
				requiresAdmin?: boolean;
				dependsOn?: (context: SettingContext) => boolean;
		  }
		| {
				type: 'button';
				id: string;
				label: string;
				keywords: string[];
				getValue: () => any;
				getLabel: (value: any) => string;
				onClick: () => void | Promise<void>;
				requiresAdmin?: boolean;
				dependsOn?: (context: SettingContext) => boolean;
		  }
		| {
				type: 'custom';
				id: string;
				label?: string;
				keywords: string[];
				component: any; // Svelte component class
				getProps?: () => Record<string, any>; // Function that returns props (reactive)
				requiresAdmin?: boolean;
				dependsOn?: (context: SettingContext) => boolean;
		  };

	const uiSwitchSettings: SettingConfig[] = [
		{
			type: 'switch',
			id: 'chatBubble',
			label: 'Chat Bubble UI',
			keywords: ['chat', 'bubble', 'layout', 'interface', 'ui'],
			get: () => chatBubble,
			set: async (value) => {
				chatBubble = value;
				await saveSettings({ chatBubble: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'showUsername',
			label: 'Display the username instead of You in the Chat',
			keywords: ['username', 'display', 'chat', 'interface', 'ui'],
			get: () => showUsername,
			set: async (value) => {
				showUsername = value;
				await saveSettings({ showUsername: value });
				return true;
			},
			dependsOn: ({ chatBubble }) => !chatBubble
		},
		{
			type: 'switch',
			id: 'widescreenMode',
			label: 'Widescreen Mode',
			keywords: ['widescreen', 'layout', 'interface', 'ui'],
			get: () => widescreenMode,
			set: async (value) => {
				widescreenMode = value;
				await saveSettings({ widescreenMode: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'notificationSound',
			label: 'Notification Sound',
			keywords: ['notification', 'sound', 'audio', 'interface'],
			get: () => notificationSound,
			set: async (value) => {
				notificationSound = value;
				await saveSettings({ notificationSound: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'showUpdateToast',
			label: 'Toast notifications for new updates',
			keywords: ['notification', 'updates', 'admin'],
			get: () => showUpdateToast,
			set: async (value) => {
				showUpdateToast = value;
				await saveSettings({ showUpdateToast: value });
				return true;
			},
			requiresAdmin: true
		},
		{
			type: 'switch',
			id: 'showChangelog',
			label: 'Show "What\'s New" modal on login',
			keywords: ['changelog', 'updates', 'modal', 'admin'],
			get: () => showChangelog,
			set: async (value) => {
				showChangelog = value;
				await saveSettings({ showChangelog: value });
				return true;
			},
			requiresAdmin: true
		}
	];

	const chatSwitchSettings: SettingConfig[] = [
		{
			type: 'switch',
			id: 'titleAutoGenerate',
			label: 'Title Auto-Generation',
			keywords: ['title', 'auto', 'chat'],
			get: () => titleAutoGenerate,
			set: async (value) => {
				titleAutoGenerate = value;
				await saveSettings({
					title: {
						...$settings.title,
						auto: value
					}
				});
				return true;
			}
		},
		{
			type: 'switch',
			id: 'autoTags',
			label: 'Chat Tags Auto-Generation',
			keywords: ['tags', 'auto', 'chat'],
			get: () => autoTags,
			set: async (value) => {
				autoTags = value;
				await saveSettings({ autoTags: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'detectArtifacts',
			label: 'Detect Artifacts Automatically',
			keywords: ['artifacts', 'chat'],
			get: () => detectArtifacts,
			set: async (value) => {
				detectArtifacts = value;
				await saveSettings({ detectArtifacts: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'responseAutoCopy',
			label: 'Auto-Copy Response to Clipboard',
			keywords: ['clipboard', 'copy', 'response'],
			get: () => responseAutoCopy,
			set: async (value) => {
				if (value) {
					// Check if clipboard API is available
					if (!navigator.clipboard) {
						toast.error(
							get(i18n).t('Clipboard API is not available. Please use HTTPS or localhost.')
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
							get(i18n).t(
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
		{
			type: 'switch',
			id: 'richTextInput',
			label: 'Rich Text Input for Chat',
			keywords: ['rich text', 'input', 'chat'],
			get: () => richTextInput,
			set: async (value) => {
				richTextInput = value;
				await saveSettings({ richTextInput: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'promptAutocomplete',
			label: 'Prompt Autocompletion',
			keywords: ['prompt', 'autocomplete', 'chat'],
			get: () => promptAutocomplete,
			set: async (value) => {
				promptAutocomplete = value;
				await saveSettings({ promptAutocomplete: value });
				return true;
			},
			dependsOn: ({ richTextInput, config }) =>
				richTextInput && (config?.features?.enable_autocomplete_generation ?? false)
		},
		{
			type: 'switch',
			id: 'largeTextAsFile',
			label: 'Paste Large Text as File',
			keywords: ['paste', 'file', 'chat'],
			get: () => largeTextAsFile,
			set: async (value) => {
				largeTextAsFile = value;
				await saveSettings({ largeTextAsFile: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'pasteAsMarkdown',
			label: 'Paste as Markdown',
			keywords: ['paste', 'markdown', 'chat'],
			get: () => pasteAsMarkdown,
			set: async (value) => {
				pasteAsMarkdown = value;
				await saveSettings({ pasteAsMarkdown: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'showHexColorSwatches',
			label: 'Show Hex Color Swatches',
			keywords: ['color', 'hex', 'swatches'],
			get: () => showHexColorSwatches,
			set: async (value) => {
				showHexColorSwatches = value;
				await saveSettings({ showHexColorSwatches: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'copyFormatted',
			label: 'Copy Formatted Text',
			keywords: ['copy', 'formatted', 'text'],
			get: () => copyFormatted,
			set: async (value) => {
				copyFormatted = value;
				await saveSettings({ copyFormatted: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'collapseCodeBlocks',
			label: 'Always Collapse Code Blocks',
			keywords: ['code', 'collapse', 'chat'],
			get: () => collapseCodeBlocks,
			set: async (value) => {
				collapseCodeBlocks = value;
				await saveSettings({ collapseCodeBlocks: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'expandDetails',
			label: 'Always Expand Details',
			keywords: ['details', 'expand', 'chat'],
			get: () => expandDetails,
			set: async (value) => {
				expandDetails = value;
				await saveSettings({ expandDetails: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'scrollOnBranchChange',
			label: 'Scroll to bottom when switching between branches',
			keywords: ['scroll', 'branches', 'chat'],
			get: () => scrollOnBranchChange,
			set: async (value) => {
				scrollOnBranchChange = value;
				await saveSettings({ scrollOnBranchChange: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'hapticFeedback',
			label: 'Haptic Feedback',
			labelSuffix: 'Android',
			keywords: ['haptic', 'feedback', 'android'],
			get: () => hapticFeedback,
			set: async (value) => {
				hapticFeedback = value;
				await saveSettings({ hapticFeedback: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'voiceInterruption',
			label: 'Allow Voice Interruption in Call',
			keywords: ['voice', 'call', 'interruption'],
			get: () => voiceInterruption,
			set: async (value) => {
				voiceInterruption = value;
				await saveSettings({ voiceInterruption: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'showEmojiInCall',
			label: 'Display Emoji in Call',
			keywords: ['emoji', 'call'],
			get: () => showEmojiInCall,
			set: async (value) => {
				showEmojiInCall = value;
				await saveSettings({ showEmojiInCall: value });
				return true;
			}
		},
		{
			type: 'switch',
			id: 'userLocation',
			label: 'Allow User Location',
			keywords: ['location', 'user'],
			get: () => userLocation,
			set: async (value) => {
				if (value) {
					const position = await getUserPosition().catch((error) => {
						toast.error(error.message);
						return null;
					});

					if (position) {
						await updateUserInfo(localStorage.token, { location: position });
						toast.success(get(i18n).t('User location successfully retrieved.'));
					} else {
						return false;
					}
				}

				userLocation = value;
				await saveSettings({ userLocation: value });
				return true;
			}
		}
	];

	// Unified settings configuration
	const allSettings: Array<{ section?: string; settings: SettingConfig[] }> = [
		{
			section: 'UI',
			settings: [
				{
					type: 'button',
					id: 'landingPageMode',
					label: 'Landing Page Mode',
					keywords: ['landing', 'page', 'mode', 'ui'],
					getValue: () => landingPageMode,
					getLabel: (val) => (val === '' ? 'Default' : 'Chat'),
					onClick: async () => {
						await toggleLandingPageMode();
					}
				},
				...uiSwitchSettings,
				{
					type: 'button',
					id: 'chatDirection',
					label: 'Chat direction',
					keywords: ['chat', 'direction', 'ltr', 'rtl', 'auto'],
					getValue: () => chatDirection,
					getLabel: (val) => {
						if (val === 'LTR') return 'LTR';
						if (val === 'RTL') return 'RTL';
						return 'Auto';
					},
					onClick: async () => {
						await toggleChangeChatDirection();
					}
				}
			]
		},
		{
			section: 'Chat',
			settings: [
				{
					type: 'select',
					id: 'chatFontSize',
					label: 'Chat Font Size',
					keywords: ['font', 'size', 'chat', 'text'],
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
				...chatSwitchSettings,
				{
					type: 'custom',
					id: 'chatBackgroundImage',
					keywords: ['background', 'image', 'chat'],
					component: ChatBackgroundImageSetting,
					getProps: () => ({
						backgroundImageUrl,
						filesInputElement,
						saveSettings
					})
				},
				{
					type: 'button',
					id: 'ctrlEnterToSend',
					label: 'Enter Key Behavior',
					keywords: ['enter', 'key', 'behavior', 'send'],
					getValue: () => ctrlEnterToSend,
					getLabel: (val) => (val ? 'Ctrl+Enter to Send' : 'Enter to Send'),
					onClick: async () => {
						await togglectrlEnterToSend();
					}
				},
				{
					type: 'button',
					id: 'webSearch',
					label: 'Web Search in Chat',
					keywords: ['web', 'search', 'chat'],
					getValue: () => webSearch,
					getLabel: (val) => (val === 'always' ? 'Always' : 'Default'),
					onClick: async () => {
						await toggleWebSearch();
					}
				},
				{
					type: 'switch',
					id: 'iframeSandboxAllowSameOrigin',
					label: 'iframe Sandbox Allow Same Origin',
					keywords: ['iframe', 'sandbox', 'same', 'origin'],
					get: () => iframeSandboxAllowSameOrigin,
					set: async (value) => {
						iframeSandboxAllowSameOrigin = value;
						await saveSettings({ iframeSandboxAllowSameOrigin: value });
						return true;
					}
				},
				{
					type: 'switch',
					id: 'iframeSandboxAllowForms',
					label: 'iframe Sandbox Allow Forms',
					keywords: ['iframe', 'sandbox', 'forms'],
					get: () => iframeSandboxAllowForms,
					set: async (value) => {
						iframeSandboxAllowForms = value;
						await saveSettings({ iframeSandboxAllowForms: value });
						return true;
					}
				}
			]
		},
		{
			section: 'Voice',
			settings: [
				{
					type: 'switch',
					id: 'voiceInterruption',
					label: 'Allow Voice Interruption in Call',
					keywords: ['voice', 'call', 'interruption'],
					get: () => voiceInterruption,
					set: async (value) => {
						voiceInterruption = value;
						await saveSettings({ voiceInterruption: value });
						return true;
					}
				},
				{
					type: 'switch',
					id: 'showEmojiInCall',
					label: 'Display Emoji in Call',
					keywords: ['emoji', 'call'],
					get: () => showEmojiInCall,
					set: async (value) => {
						showEmojiInCall = value;
						await saveSettings({ showEmojiInCall: value });
						return true;
					}
				}
			]
		},
		{
			section: 'File',
			settings: [
				{
					type: 'switch',
					id: 'imageCompression',
					label: 'Image Compression',
					keywords: ['image', 'compression', 'file'],
					get: () => imageCompression,
					set: async (value) => {
						imageCompression = value;
						await saveSettings({ imageCompression: value });
						return true;
					}
				},
				{
					type: 'custom',
					id: 'imageCompressionSize',
					keywords: ['image', 'compression', 'size', 'file'],
					dependsOn: ({ imageCompression }) => imageCompression,
					component: ImageCompressionSizeSetting,
					getProps: () => ({
						imageCompressionSize,
						saveSettings
					})
				}
			]
		}
	];

	onMount(async () => {
		// Update keywords cache when component mounts
		updateInterfaceKeywords();

		titleAutoGenerate = $settings?.title?.auto ?? true;
		autoTags = $settings.autoTags ?? true;

		detectArtifacts = $settings.detectArtifacts ?? true;
		responseAutoCopy = $settings.responseAutoCopy ?? false;

		showUsername = $settings.showUsername ?? false;
		showUpdateToast = $settings.showUpdateToast ?? true;
		showChangelog = $settings.showChangelog ?? true;

		showEmojiInCall = $settings.showEmojiInCall ?? false;
		voiceInterruption = $settings.voiceInterruption ?? false;

		richTextInput = $settings.richTextInput ?? true;
		promptAutocomplete = $settings.promptAutocomplete ?? false;
		largeTextAsFile = $settings.largeTextAsFile ?? false;
		pasteAsMarkdown = $settings.pasteAsMarkdown ?? true;
		showHexColorSwatches = $settings.showHexColorSwatches ?? true;
		copyFormatted = $settings.copyFormatted ?? false;
		chatFontScale = $settings.chatFontScale ?? 1;

		collapseCodeBlocks = $settings.collapseCodeBlocks ?? false;
		expandDetails = $settings.expandDetails ?? false;

		landingPageMode = $settings.landingPageMode ?? '';
		chatBubble = $settings.chatBubble ?? true;
		widescreenMode = $settings.widescreenMode ?? false;
		splitLargeChunks = $settings.splitLargeChunks ?? false;
		scrollOnBranchChange = $settings.scrollOnBranchChange ?? true;
		chatDirection = $settings.chatDirection ?? 'auto';
		userLocation = $settings.userLocation ?? false;

		notificationSound = $settings.notificationSound ?? true;

		hapticFeedback = $settings.hapticFeedback ?? false;
		ctrlEnterToSend = $settings.ctrlEnterToSend ?? false;

		imageCompression = $settings.imageCompression ?? false;
		imageCompressionSize = $settings.imageCompressionSize ?? { width: '', height: '' };

		defaultModelId = $settings?.models?.at(0) ?? '';
		if ($config?.default_models) {
			defaultModelId = $config.default_models.split(',')[0];
		}

		// backgroundImageUrl is now reactive to $settings, so no need to set it here
		webSearch = $settings.webSearch ?? null;
	});
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
		on:change={() => {
			let reader = new FileReader();
			reader.onload = (event) => {
				let originalImageUrl = `${event.target.result}`;

				backgroundImageUrl = originalImageUrl;
				saveSettings({ backgroundImageUrl });
			};

			if (
				inputFiles &&
				inputFiles.length > 0 &&
				['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(inputFiles[0]['type'])
			) {
				reader.readAsDataURL(inputFiles[0]);
			} else {
				toast.error(`Unsupported File Type '${inputFiles[0]['type']}'.`);
				inputFiles = null;
			}
		}}
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
