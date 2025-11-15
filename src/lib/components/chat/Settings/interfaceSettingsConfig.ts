import type { CommandComponentSource } from '$lib/utils/commandPalette/types';

export type SwitchBinding = {
	get: () => boolean;
	set: (value: boolean) => boolean | Promise<boolean>;
};

export const chatFontScaleOptions: Array<{ value: string; label: string }> = [
	{ value: '0.875', label: 'Small' },
	{ value: '1', label: 'Default' },
	{ value: '1.125', label: 'Large' },
	{ value: '1.25', label: 'Extra Large' }
];

export const commandPaletteShortcutOptions: Array<{ value: string; label: string }> = [
	{ value: 'cmd+p', label: 'Command ⌘P / Ctrl+P' },
	{ value: 'cmd+k', label: 'Command ⌘K / Ctrl+K' },
	{ value: 'cmd+e', label: 'Command ⌘E / Ctrl+E' },
	{ value: 'double-shift', label: 'Double Shift' }
];

export type SelectBinding = {
	get: () => string;
	set: (value: string) => void | Promise<void>;
	options: Array<{ value: string; label: string }>;
};

export type ButtonBinding = {
	getValue: () => any;
	getLabel: (value: any) => string;
	onClick: () => void | Promise<void>;
};

export type CustomBinding = {
	component: CommandComponentSource;
	getProps?: () => Record<string, any>;
	dependsOn?: (context: SettingContext) => boolean;
};

export type CommandComponentSourceType = CommandComponentSource;

export type SettingContext = {
	chatBubble: boolean;
	richTextInput: boolean;
	imageCompression: boolean;
	config: any;
	user: any;
	settings: any;
	backgroundImageUrl?: string | null;
};

export type SettingConfig =
	| {
			type: 'switch';
			id: string;
			label: string;
			labelSuffix?: string;
			keywords: string[];
			get: SwitchBinding['get'];
			set: SwitchBinding['set'];
			requiresAdmin?: boolean;
			dependsOn?: (context: SettingContext) => boolean;
	  }
	| {
			type: 'select';
			id: string;
			label: string;
			keywords: string[];
			get: SelectBinding['get'];
			set: SelectBinding['set'];
			options: SelectBinding['options'];
			requiresAdmin?: boolean;
			dependsOn?: (context: SettingContext) => boolean;
	  }
	| {
			type: 'button';
			id: string;
			label: string;
			keywords: string[];
			getValue: ButtonBinding['getValue'];
			getLabel: ButtonBinding['getLabel'];
			onClick: ButtonBinding['onClick'];
			requiresAdmin?: boolean;
			dependsOn?: (context: SettingContext) => boolean;
	  }
	| {
			type: 'custom';
			id: string;
			label?: string;
			keywords: string[];
			component: CommandComponentSource;
			getProps?: () => Record<string, any>;
			requiresAdmin?: boolean;
			dependsOn?: (context: SettingContext) => boolean;
	  };

export type SettingSection = {
	section?: string;
	settings: SettingConfig[];
};

export type InterfaceSettingBindings = {
	landingPageMode: ButtonBinding;
	chatBubble: SwitchBinding;
	showUsername: SwitchBinding;
	widescreenMode: SwitchBinding;
	notificationSound: SwitchBinding;
	showUpdateToast: SwitchBinding;
	showChangelog: SwitchBinding;

	chatFontSize: SelectBinding;

	titleAutoGenerate: SwitchBinding;
	autoTags: SwitchBinding;
	detectArtifacts: SwitchBinding;
	responseAutoCopy: SwitchBinding;
	richTextInput: SwitchBinding;
	promptAutocomplete: SwitchBinding;
	largeTextAsFile: SwitchBinding;
	pasteAsMarkdown: SwitchBinding;
	showHexColorSwatches: SwitchBinding;
	copyFormatted: SwitchBinding;
	collapseCodeBlocks: SwitchBinding;
	expandDetails: SwitchBinding;
	scrollOnBranchChange: SwitchBinding;
	hapticFeedback: SwitchBinding;
	voiceInterruption: SwitchBinding;
	showEmojiInCall: SwitchBinding;
	userLocation: SwitchBinding;

	chatBackgroundImage: CustomBinding;

	ctrlEnterToSend: ButtonBinding;
	webSearch: ButtonBinding;

	iframeSandboxAllowSameOrigin: SwitchBinding;
	iframeSandboxAllowForms: SwitchBinding;

	imageCompression: SwitchBinding;
	imageCompressionSize: CustomBinding;

	chatDirection: ButtonBinding;
	commandPaletteShortcut: SelectBinding;
};

export function buildInterfaceSettings(bindings: InterfaceSettingBindings): SettingSection[] {
	const {
		landingPageMode,
		chatBubble,
		showUsername,
		widescreenMode,
		notificationSound,
		showUpdateToast,
		showChangelog,
		chatFontSize,
		titleAutoGenerate,
		autoTags,
		detectArtifacts,
		responseAutoCopy,
		richTextInput,
		promptAutocomplete,
		largeTextAsFile,
		pasteAsMarkdown,
		showHexColorSwatches,
		copyFormatted,
		collapseCodeBlocks,
		expandDetails,
		scrollOnBranchChange,
		hapticFeedback,
		voiceInterruption,
		showEmojiInCall,
		userLocation,
		chatBackgroundImage,
		ctrlEnterToSend,
		webSearch,
		iframeSandboxAllowSameOrigin,
		iframeSandboxAllowForms,
		imageCompression,
		imageCompressionSize,
		chatDirection,
		commandPaletteShortcut
	} = bindings;

	const uiSwitchSettings: SettingConfig[] = [
		{
			type: 'switch',
			id: 'chatBubble',
			label: 'Chat Bubble UI',
			keywords: ['chat', 'bubble', 'layout', 'interface', 'ui'],
			get: chatBubble.get,
			set: chatBubble.set
		},
		{
			type: 'switch',
			id: 'showUsername',
			label: 'Display the username instead of You in the Chat',
			keywords: ['username', 'display', 'chat', 'interface', 'ui'],
			get: showUsername.get,
			set: showUsername.set,
			dependsOn: ({ chatBubble }) => !chatBubble
		},
		{
			type: 'switch',
			id: 'widescreenMode',
			label: 'Widescreen Mode',
			keywords: ['widescreen', 'layout', 'interface', 'ui'],
			get: widescreenMode.get,
			set: widescreenMode.set
		},
		{
			type: 'switch',
			id: 'notificationSound',
			label: 'Notification Sound',
			keywords: ['notification', 'sound', 'audio', 'interface'],
			get: notificationSound.get,
			set: notificationSound.set
		},
		{
			type: 'switch',
			id: 'showUpdateToast',
			label: 'Toast notifications for new updates',
			keywords: ['notification', 'updates', 'admin'],
			get: showUpdateToast.get,
			set: showUpdateToast.set,
			requiresAdmin: true
		},
		{
			type: 'switch',
			id: 'showChangelog',
			label: 'Show "What\'s New" modal on login',
			keywords: ['changelog', 'updates', 'modal', 'admin'],
			get: showChangelog.get,
			set: showChangelog.set,
			requiresAdmin: true
		}
	];

	const chatSwitchSettings: SettingConfig[] = [
		{
			type: 'switch',
			id: 'titleAutoGenerate',
			label: 'Title Auto-Generation',
			keywords: ['title', 'auto', 'chat'],
			get: titleAutoGenerate.get,
			set: titleAutoGenerate.set
		},
		{
			type: 'switch',
			id: 'autoTags',
			label: 'Chat Tags Auto-Generation',
			keywords: ['tags', 'auto', 'chat'],
			get: autoTags.get,
			set: autoTags.set
		},
		{
			type: 'switch',
			id: 'detectArtifacts',
			label: 'Detect Artifacts Automatically',
			keywords: ['artifacts', 'chat'],
			get: detectArtifacts.get,
			set: detectArtifacts.set
		},
		{
			type: 'switch',
			id: 'responseAutoCopy',
			label: 'Auto-Copy Response to Clipboard',
			keywords: ['clipboard', 'copy', 'response'],
			get: responseAutoCopy.get,
			set: responseAutoCopy.set
		},
		{
			type: 'switch',
			id: 'richTextInput',
			label: 'Rich Text Input for Chat',
			keywords: ['rich text', 'input', 'chat'],
			get: richTextInput.get,
			set: richTextInput.set
		},
		{
			type: 'switch',
			id: 'promptAutocomplete',
			label: 'Prompt Autocompletion',
			keywords: ['prompt', 'autocomplete', 'chat'],
			get: promptAutocomplete.get,
			set: promptAutocomplete.set,
			dependsOn: ({ richTextInput, config }) =>
				richTextInput && (config?.features?.enable_autocomplete_generation ?? false)
		},
		{
			type: 'switch',
			id: 'largeTextAsFile',
			label: 'Paste Large Text as File',
			keywords: ['paste', 'file', 'chat'],
			get: largeTextAsFile.get,
			set: largeTextAsFile.set
		},
		{
			type: 'switch',
			id: 'pasteAsMarkdown',
			label: 'Paste as Markdown',
			keywords: ['paste', 'markdown', 'chat'],
			get: pasteAsMarkdown.get,
			set: pasteAsMarkdown.set
		},
		{
			type: 'switch',
			id: 'showHexColorSwatches',
			label: 'Show Hex Color Swatches',
			keywords: ['color', 'hex', 'swatches'],
			get: showHexColorSwatches.get,
			set: showHexColorSwatches.set
		},
		{
			type: 'switch',
			id: 'copyFormatted',
			label: 'Copy Formatted Text',
			keywords: ['copy', 'formatted', 'text'],
			get: copyFormatted.get,
			set: copyFormatted.set
		},
		{
			type: 'switch',
			id: 'collapseCodeBlocks',
			label: 'Always Collapse Code Blocks',
			keywords: ['code', 'collapse', 'chat'],
			get: collapseCodeBlocks.get,
			set: collapseCodeBlocks.set
		},
		{
			type: 'switch',
			id: 'expandDetails',
			label: 'Always Expand Details',
			keywords: ['details', 'expand', 'chat'],
			get: expandDetails.get,
			set: expandDetails.set
		},
		{
			type: 'switch',
			id: 'scrollOnBranchChange',
			label: 'Scroll to bottom when switching between branches',
			keywords: ['scroll', 'branches', 'chat'],
			get: scrollOnBranchChange.get,
			set: scrollOnBranchChange.set
		},
		{
			type: 'switch',
			id: 'hapticFeedback',
			label: 'Haptic Feedback',
			labelSuffix: 'Android',
			keywords: ['haptic', 'feedback', 'android'],
			get: hapticFeedback.get,
			set: hapticFeedback.set
		},
		{
			type: 'switch',
			id: 'voiceInterruption',
			label: 'Allow Voice Interruption in Call',
			keywords: ['voice', 'call', 'interruption'],
			get: voiceInterruption.get,
			set: voiceInterruption.set
		},
		{
			type: 'switch',
			id: 'showEmojiInCall',
			label: 'Display Emoji in Call',
			keywords: ['emoji', 'call'],
			get: showEmojiInCall.get,
			set: showEmojiInCall.set
		},
		{
			type: 'switch',
			id: 'userLocation',
			label: 'Allow User Location',
			keywords: ['location', 'user'],
			get: userLocation.get,
			set: userLocation.set
		}
	];

	return [
		{
			section: 'UI',
			settings: [
				{
					type: 'button',
					id: 'landingPageMode',
					label: 'Landing Page Mode',
					keywords: ['landing', 'page', 'mode', 'ui'],
					getValue: landingPageMode.getValue,
					getLabel: landingPageMode.getLabel,
					onClick: landingPageMode.onClick
				},
				...uiSwitchSettings,
				{
					type: 'select',
					id: 'commandPaletteShortcut',
					label: 'Command Palette Shortcut',
					keywords: ['command', 'palette', 'shortcut'],
					get: commandPaletteShortcut.get,
					set: commandPaletteShortcut.set,
					options: commandPaletteShortcut.options
				},
				{
					type: 'button',
					id: 'chatDirection',
					label: 'Chat direction',
					keywords: ['chat', 'direction', 'ltr', 'rtl', 'auto'],
					getValue: chatDirection.getValue,
					getLabel: chatDirection.getLabel,
					onClick: chatDirection.onClick
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
					get: chatFontSize.get,
					set: chatFontSize.set,
					options: chatFontSize.options
				},
				...chatSwitchSettings,
				{
					type: 'custom',
					id: 'chatBackgroundImage',
					keywords: ['background', 'image', 'chat'],
					component: chatBackgroundImage.component,
					getProps: chatBackgroundImage.getProps,
					dependsOn: chatBackgroundImage.dependsOn
				},
				{
					type: 'button',
					id: 'ctrlEnterToSend',
					label: 'Enter Key Behavior',
					keywords: ['enter', 'key', 'behavior', 'send'],
					getValue: ctrlEnterToSend.getValue,
					getLabel: ctrlEnterToSend.getLabel,
					onClick: ctrlEnterToSend.onClick
				},
				{
					type: 'button',
					id: 'webSearch',
					label: 'Web Search in Chat',
					keywords: ['web', 'search', 'chat'],
					getValue: webSearch.getValue,
					getLabel: webSearch.getLabel,
					onClick: webSearch.onClick
				},
				{
					type: 'switch',
					id: 'iframeSandboxAllowSameOrigin',
					label: 'iframe Sandbox Allow Same Origin',
					keywords: ['iframe', 'sandbox', 'same', 'origin'],
					get: iframeSandboxAllowSameOrigin.get,
					set: iframeSandboxAllowSameOrigin.set
				},
				{
					type: 'switch',
					id: 'iframeSandboxAllowForms',
					label: 'iframe Sandbox Allow Forms',
					keywords: ['iframe', 'sandbox', 'forms'],
					get: iframeSandboxAllowForms.get,
					set: iframeSandboxAllowForms.set
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
					get: voiceInterruption.get,
					set: voiceInterruption.set
				},
				{
					type: 'switch',
					id: 'showEmojiInCall',
					label: 'Display Emoji in Call',
					keywords: ['emoji', 'call'],
					get: showEmojiInCall.get,
					set: showEmojiInCall.set
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
					get: imageCompression.get,
					set: imageCompression.set
				},
				{
					type: 'custom',
					id: 'imageCompressionSize',
					keywords: ['image', 'compression', 'size', 'file'],
					component: imageCompressionSize.component,
					getProps: imageCompressionSize.getProps,
					dependsOn: ({ imageCompression }) => imageCompression
				}
			]
		}
	];
}

