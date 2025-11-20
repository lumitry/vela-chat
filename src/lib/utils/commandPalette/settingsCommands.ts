import { get } from 'svelte/store';
import { toast } from 'svelte-sonner';
import { config, models, settings } from '$lib/stores';
import { updateUserSettings, updateUserInfo } from '$lib/apis/users';
import { getModels as fetchModels } from '$lib/apis';
import { getUserPosition } from '$lib/utils';
import ChatBackgroundImageSetting from '$lib/components/chat/Settings/ChatBackgroundImageSetting.svelte';
import ImageCompressionSizeSetting from '$lib/components/chat/Settings/ImageCompressionSizeSetting.svelte';
import {
	buildInterfaceSettings,
	chatFontScaleOptions,
	commandPaletteShortcutOptions,
	type InterfaceSettingBindings,
	type SettingConfig
} from '$lib/components/chat/Settings/interfaceSettingsConfig';
import type { Command, SettingCommand, SubmenuItem } from './types';
import Cog6 from '$lib/components/icons/Cog6.svelte';

function getSettingsSnapshot(): Record<string, any> {
	return get(settings) ?? {};
}

async function saveUISettings(updated: Record<string, unknown>): Promise<void> {
	const currentSettings = getSettingsSnapshot();
	const nextSettings = { ...currentSettings, ...updated };

	settings.set(nextSettings);

	try {
		const $config = get(config);
		const connections =
			$config?.features?.enable_direct_connections && (nextSettings?.directConnections ?? null);

		const fetchedModels = await fetchModels(localStorage.token, connections);
		models.set(fetchedModels);
	} catch (error) {
		console.error('Failed to refresh models after settings update', error);
	}

	await updateUserSettings(localStorage.token, { ui: nextSettings });
}

const interfaceSettingBindingsForCommands: InterfaceSettingBindings = {
	landingPageMode: {
		getValue: () => getSettingsSnapshot().landingPageMode ?? '',
		getLabel: (val: string) => (val === '' ? 'Default' : 'Chat'),
		onClick: async () => {
			const current = getSettingsSnapshot().landingPageMode ?? '';
			const next = current === '' ? 'chat' : '';
			await saveUISettings({ landingPageMode: next });
		}
	},
	chatBubble: {
		get: () => (getSettingsSnapshot().chatBubble ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ chatBubble: value });
			return true;
		}
	},
	showUsername: {
		get: () => (getSettingsSnapshot().showUsername ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ showUsername: value });
			return true;
		}
	},
	widescreenMode: {
		get: () => (getSettingsSnapshot().widescreenMode ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ widescreenMode: value });
			return true;
		}
	},
	notificationSound: {
		get: () => (getSettingsSnapshot().notificationSound ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ notificationSound: value });
			return true;
		}
	},
	showUpdateToast: {
		get: () => (getSettingsSnapshot().showUpdateToast ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ showUpdateToast: value });
			return true;
		}
	},
	showChangelog: {
		get: () => (getSettingsSnapshot().showChangelog ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ showChangelog: value });
			return true;
		}
	},
	chatFontSize: {
		get: () => getSettingsSnapshot().chatFontScale ?? '1',
		set: async (value: string) => {
			const numValue = parseFloat(value);
			if (!Number.isNaN(numValue)) {
				await saveUISettings({ chatFontScale: value });
			}
		},
		options: chatFontScaleOptions
	},
	commandPaletteShortcut: {
		get: () => getSettingsSnapshot().commandPaletteShortcut ?? 'cmd+p',
		set: async (value: string) => {
			await saveUISettings({ commandPaletteShortcut: value });
		},
		options: commandPaletteShortcutOptions
	},
	titleAutoGenerate: {
		get: () => (getSettingsSnapshot().title?.auto ?? true) as boolean,
		set: async (value: boolean) => {
			const current = getSettingsSnapshot();
			await saveUISettings({
				title: {
					...(current.title ?? {}),
					auto: value
				}
			});
			return true;
		}
	},
	autoTags: {
		get: () => (getSettingsSnapshot().autoTags ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ autoTags: value });
			return true;
		}
	},
	detectArtifacts: {
		get: () => (getSettingsSnapshot().detectArtifacts ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ detectArtifacts: value });
			return true;
		}
	},
	responseAutoCopy: {
		get: () => (getSettingsSnapshot().responseAutoCopy ?? false) as boolean,
		set: async (value: boolean) => {
			if (value) {
				if (!navigator.clipboard) {
					toast.error('Clipboard API is not available. Please use HTTPS or localhost.');
					return false;
				}

				const permission = await navigator.clipboard
					.readText()
					.then(() => 'granted')
					.catch(() => '');

				if (permission !== 'granted') {
					toast.error(
						'Clipboard write permission denied. Please check your browser settings to grant the necessary access.'
					);
					return false;
				}
			}

			await saveUISettings({ responseAutoCopy: value });
			return true;
		}
	},
	richTextInput: {
		get: () => (getSettingsSnapshot().richTextInput ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ richTextInput: value });
			return true;
		}
	},
	promptAutocomplete: {
		get: () => (getSettingsSnapshot().promptAutocomplete ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ promptAutocomplete: value });
			return true;
		}
	},
	largeTextAsFile: {
		get: () => (getSettingsSnapshot().largeTextAsFile ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ largeTextAsFile: value });
			return true;
		}
	},
	pasteAsMarkdown: {
		get: () => (getSettingsSnapshot().pasteAsMarkdown ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ pasteAsMarkdown: value });
			return true;
		}
	},
	showHexColorSwatches: {
		get: () => (getSettingsSnapshot().showHexColorSwatches ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ showHexColorSwatches: value });
			return true;
		}
	},
	copyFormatted: {
		get: () => (getSettingsSnapshot().copyFormatted ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ copyFormatted: value });
			return true;
		}
	},
	collapseCodeBlocks: {
		get: () => (getSettingsSnapshot().collapseCodeBlocks ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ collapseCodeBlocks: value });
			return true;
		}
	},
	expandDetails: {
		get: () => (getSettingsSnapshot().expandDetails ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ expandDetails: value });
			return true;
		}
	},
	scrollOnBranchChange: {
		get: () => (getSettingsSnapshot().scrollOnBranchChange ?? true) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ scrollOnBranchChange: value });
			return true;
		}
	},
	hapticFeedback: {
		get: () => (getSettingsSnapshot().hapticFeedback ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ hapticFeedback: value });
			return true;
		}
	},
	voiceInterruption: {
		get: () => (getSettingsSnapshot().voiceInterruption ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ voiceInterruption: value });
			return true;
		}
	},
	showEmojiInCall: {
		get: () => (getSettingsSnapshot().showEmojiInCall ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ showEmojiInCall: value });
			return true;
		}
	},
	userLocation: {
		get: () => (getSettingsSnapshot().userLocation ?? false) as boolean,
		set: async (value: boolean) => {
			if (value) {
				const position = await getUserPosition().catch((error) => {
					toast.error(error.message);
					return null;
				});

				if (position) {
					await updateUserInfo(localStorage.token, { location: position });
					toast.success('User location successfully retrieved.');
				} else {
					return false;
				}
			}

			await saveUISettings({ userLocation: value });
			return true;
		}
	},
	chatBackgroundImage: {
		component: ChatBackgroundImageSetting
	},
	ctrlEnterToSend: {
		getValue: () => getSettingsSnapshot().ctrlEnterToSend ?? false,
		getLabel: (val: boolean) => (val ? 'Ctrl+Enter to Send' : 'Enter to Send'),
		onClick: async () => {
			const current = getSettingsSnapshot().ctrlEnterToSend ?? false;
			await saveUISettings({ ctrlEnterToSend: !current });
		}
	},
	webSearch: {
		getValue: () => getSettingsSnapshot().webSearch ?? null,
		getLabel: (val: string | null) => (val === 'always' ? 'Always' : 'Default'),
		onClick: async () => {
			const current = getSettingsSnapshot().webSearch ?? null;
			const next = current === 'always' ? null : 'always';
			await saveUISettings({ webSearch: next });
		}
	},
	iframeSandboxAllowSameOrigin: {
		get: () => (getSettingsSnapshot().iframeSandboxAllowSameOrigin ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ iframeSandboxAllowSameOrigin: value });
			return true;
		}
	},
	iframeSandboxAllowForms: {
		get: () => (getSettingsSnapshot().iframeSandboxAllowForms ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ iframeSandboxAllowForms: value });
			return true;
		}
	},
	imageCompression: {
		get: () => (getSettingsSnapshot().imageCompression ?? false) as boolean,
		set: async (value: boolean) => {
			await saveUISettings({ imageCompression: value });
			return true;
		}
	},
	imageCompressionSize: {
		component: ImageCompressionSizeSetting
	},
	chatDirection: {
		getValue: () => getSettingsSnapshot().chatDirection ?? 'auto',
		getLabel: (val: string) => {
			if (val === 'LTR') return 'LTR';
			if (val === 'RTL') return 'RTL';
			return 'Auto';
		},
		onClick: async () => {
			const current = getSettingsSnapshot().chatDirection ?? 'auto';
			const next = current === 'auto' ? 'LTR' : current === 'LTR' ? 'RTL' : 'auto';
			await saveUISettings({ chatDirection: next });
		}
	}
};

function flattenSettings(): SettingConfig[] {
	const sections = buildInterfaceSettings(interfaceSettingBindingsForCommands);
	return sections.flatMap((section) => section.settings);
}

function settingToCommand(setting: SettingConfig): Command | null {
	const baseKeywords = new Set<string>(setting.keywords ?? []);

	switch (setting.type) {
		case 'switch': {
			// Add "Toggle" prefix to switch settings
			const label = setting.label.startsWith('Toggle ') 
				? setting.label 
				: `Toggle ${setting.label}`;
			return {
				id: `setting:${setting.id}`,
				type: 'setting',
				label,
				keywords: Array.from(baseKeywords),
				description: 'Toggle setting on/off',
				settingId: setting.id,
				settingType: 'switch',
				icon: Cog6,
				getValue: () => setting.get(),
				execute: async () => {
					const current = setting.get();
					await setting.set(!current);
				}
			};
		}
		case 'select': {
			// Convert select settings to submenu commands with options
			// Add "..." suffix to indicate submenu
			const label = setting.label.endsWith('...') 
				? setting.label 
				: `${setting.label}...`;
			return {
				id: `setting:${setting.id}`,
				type: 'submenu',
				label,
				keywords: Array.from(baseKeywords),
				description: 'Adjust setting',
				icon: Cog6,
				getSubmenuItems: async (query: string): Promise<SubmenuItem[]> => {
					const currentValue = setting.get();
					const lowerQuery = query.toLowerCase();
					
					return (setting.options || [])
						.filter(option => 
							!query || 
							option.label.toLowerCase().includes(lowerQuery) ||
							option.value.toLowerCase().includes(lowerQuery)
						)
						.map(option => ({
							id: `setting:${setting.id}:${option.value}`,
							label: option.label,
							description: currentValue === option.value ? 'Current value' : undefined,
							execute: async () => {
								await setting.set(option.value);
							}
						}));
				}
			};
		}
		case 'button': {
			// Add "..." suffix to button settings that lead to submenus (they cycle through states)
			const label = setting.label.endsWith('...') 
				? setting.label 
				: `${setting.label}...`;
			return {
				id: `setting:${setting.id}`,
				type: 'setting',
				label,
				keywords: Array.from(baseKeywords),
				description: 'Trigger setting action',
				settingId: setting.id,
				settingType: 'button',
				icon: Cog6,
				getValue: () => setting.getValue(),
				execute: async () => {
					await setting.onClick();
				}
			};
		}
		default:
			return null;
	}
}

export function createSettingsCommands(): Command[] {
	const settingsList = flattenSettings();

	return settingsList
		.map((setting) => settingToCommand(setting))
		.filter((command): command is Command => command !== null);
}

