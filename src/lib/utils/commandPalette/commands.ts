import { goto } from '$app/navigation';
import { get } from 'svelte/store';
import { toast } from 'svelte-sonner';
import Plus from '$lib/components/icons/Plus.svelte';
import Sparkles from '$lib/components/icons/Sparkles.svelte';
import MenuLines from '$lib/components/icons/MenuLines.svelte';
import HomeIcon from '$lib/components/icons/Home.svelte';
import ChartBar from '$lib/components/icons/ChartBar.svelte';
import BookOpen from '$lib/components/icons/BookOpen.svelte';
import Cube from '$lib/components/icons/Cube.svelte';
import Document from '$lib/components/icons/Document.svelte';
import Wrench from '$lib/components/icons/Wrench.svelte';
import Cog6 from '$lib/components/icons/Cog6.svelte';
import UsersSolid from '$lib/components/icons/UsersSolid.svelte';
import FaceSmile from '$lib/components/icons/FaceSmile.svelte';
import Pencil from '$lib/components/icons/Pencil.svelte';
import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
import AdjustmentsHorizontal from '$lib/components/icons/AdjustmentsHorizontal.svelte';
import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
import Bookmark from '$lib/components/icons/Bookmark.svelte';
import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
import LinkIcon from '$lib/components/icons/Link.svelte';
import SparklesSolid from '$lib/components/icons/SparklesSolid.svelte';
import Search from '$lib/components/icons/Search.svelte';
import {
	archiveChatById,
	cloneChatById,
	getChatList,
	getPinnedChatList,
	toggleChatPinnedStatusById,
	updateChatFolderIdById,
	updateChatById,
	getChatMetaById,
	getChatById
} from '$lib/apis/chats';
import { getFolders } from '$lib/apis/folders';
import {
	chatId,
	chats,
	chatTitle as chatTitleStore,
	currentChatPage,
	pinnedChats,
	showSidebar,
	temporaryChatEnabled,
	folders as foldersStore,
	models as modelsStore,
	chatCache,
	theme,
	settings
} from '$lib/stores';
import { createMessagesList } from '$lib/utils';
import { resetToDefaultGrayColors, applyCustomThemeColors } from '$lib/utils/theme';
import type { SubmenuItem } from '$lib/utils/commandPalette/types';
import { createSettingsCommands } from './settingsCommands';
import { registerCommands, registerCommand } from '$lib/utils/commandPalette/registry';
import type { Command, NavigationCommand, CommandContext } from '$lib/utils/commandPalette/types';
import { commandPaletteQuery } from '$lib/stores/commandPalette';

let coreRegistered = false;
let chatRegistered = false;

const NAVIGATION_PRIORITY = 60;
const ACTION_PRIORITY = 90;
const CHAT_PRIORITY = 80;

function applyThemeCommand(_theme: string): void {
	if (typeof window === 'undefined' || typeof document === 'undefined') {
		return;
	}

	try {
		const $settings = get(settings);
		let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		// Reset all CSS custom properties first
		resetToDefaultGrayColors();

		if (themeToApply === 'dark' && !_theme.includes('oled') && _theme !== 'custom') {
			document.documentElement.style.setProperty('--color-gray-800', '#333');
			document.documentElement.style.setProperty('--color-gray-850', '#262626');
			document.documentElement.style.setProperty('--color-gray-900', '#171717');
			document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
		}

		// Remove all theme classes first
		['dark', 'light', 'rose-pine', 'rose-pine-dawn', 'oled-dark', 'her', 'custom'].forEach(
			(cls) => {
				document.documentElement.classList.remove(cls);
			}
		);

		// Handle custom theme
		if (_theme === 'custom') {
			document.documentElement.classList.add('dark');
			document.documentElement.classList.add('custom');
			if ($settings?.customThemeColor) {
				applyCustomThemeColors($settings.customThemeColor);
			}
		} else {
			// Add the new theme classes
			themeToApply.split(' ').forEach((e) => {
				document.documentElement.classList.add(e);
			});

			// Add dark class for special themes
			if (['her'].includes(_theme)) {
				document.documentElement.classList.add('dark');
			}
		}

		const metaThemeColor = document.querySelector('meta[name="theme-color"]');
		if (metaThemeColor) {
			if (_theme.includes('system')) {
				const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
					? 'dark'
					: 'light';
				metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
			} else {
				metaThemeColor.setAttribute(
					'content',
					_theme === 'dark'
						? '#171717'
						: _theme === 'oled-dark'
							? '#000000'
							: _theme === 'her'
								? '#983724'
								: _theme === 'custom'
									? '#171717' // Will be overridden by custom color
									: '#ffffff'
				);
			}
		}

		if (typeof window !== 'undefined' && (window as any).applyTheme) {
			(window as any).applyTheme();
		}

		if (_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#101010');
			document.documentElement.style.setProperty('--color-gray-850', '#050505');
			document.documentElement.style.setProperty('--color-gray-900', '#000000');
			document.documentElement.style.setProperty('--color-gray-950', '#000000');
			document.documentElement.classList.add('dark');
		}

		// Update theme store and localStorage
		theme.set(_theme);
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem('theme', _theme);
		}
	} catch (error) {
		console.error('Failed to apply theme:', error);
	}
}

const coreCommands: Command[] = [
	{
		id: 'core:new-chat',
		type: 'action',
		label: 'New Chat',
		keywords: ['chat', 'create', 'new'],
		priority: ACTION_PRIORITY,
		icon: Plus,
		execute: () => {
			const sidebarButton = document.getElementById('sidebar-new-chat-button');
			const mainButton = document.getElementById('new-chat-button');

			if (sidebarButton instanceof HTMLElement) {
				sidebarButton.click();
				return;
			}

			if (mainButton instanceof HTMLElement) {
				mainButton.click();
				return;
			}

			goto('/');
		}
	},
	{
		id: 'core:new-temp-chat',
		type: 'action',
		label: 'New Temporary Chat',
		keywords: ['chat', 'temporary', 'new'],
		priority: ACTION_PRIORITY - 5,
		icon: SparklesSolid,
		execute: async () => {
			temporaryChatEnabled.set(true);
			await goto('/');
			requestAnimationFrame(() => {
				document.getElementById('new-chat-button')?.click();
			});
		}
	},
	{
		id: 'core:toggle-sidebar',
		type: 'action',
		label: 'Toggle Sidebar',
		keywords: ['sidebar', 'layout'],
		priority: ACTION_PRIORITY - 10,
		icon: MenuLines,
		execute: () => {
			showSidebar.update((value) => !value);
		}
	},
	{
		id: 'core:switch-theme',
		type: 'submenu',
		label: 'Switch Theme',
		keywords: ['theme', 'appearance', 'dark', 'light', 'mode', 'color'],
		priority: ACTION_PRIORITY - 8,
		icon: AdjustmentsHorizontal,
		getSubmenuItems: async (query: string, context?: CommandContext): Promise<SubmenuItem[]> => {
			const currentTheme =
				get(theme) ||
				(typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null) ||
				'system';
			const lowerQuery = query.toLowerCase();

			const themes: Array<{ value: string; label: string; emoji: string }> = [
				{ value: 'system', label: 'System', emoji: '⚙️' },
				{ value: 'dark', label: 'Dark', emoji: '🌑' },
				{ value: 'oled-dark', label: 'OLED Dark', emoji: '🌃' },
				{ value: 'light', label: 'Light', emoji: '☀️' },
				{ value: 'her', label: 'Her', emoji: '🌷' },
				{ value: 'custom', label: 'Custom', emoji: '🎨' }
			];

			const themeItems: SubmenuItem[] = themes
				.filter((themeOption) => {
					return (
						!query ||
						themeOption.label.toLowerCase().includes(lowerQuery) ||
						themeOption.value.toLowerCase().includes(lowerQuery)
					);
				})
				.map((themeOption) => ({
					id: `theme:${themeOption.value}`,
					label: `${themeOption.emoji} ${themeOption.label}`,
					description: currentTheme === themeOption.value ? 'Current theme' : undefined,
					execute: async () => {
						applyThemeCommand(themeOption.value);
						toast.success(`Theme switched to ${themeOption.label}`);
					}
				}));

			return themeItems;
		}
	},
	{
		id: 'core:search-chats',
		type: 'action',
		label: 'Search Chats',
		keywords: ['search', 'chat', 'find', 'chat search'],
		priority: ACTION_PRIORITY - 5,
		icon: Search,
		execute: () => {
			commandPaletteQuery.set('>');
		}
	},
	createNavigationCommand('core:goto-home', 'Go to Home', '/', ['home', 'dashboard'], HomeIcon),
	createNavigationCommand(
		'core:goto-metrics',
		'Go to Metrics',
		'/workspace/metrics',
		['metrics', 'analytics', 'workspace'],
		ChartBar
	),
	createNavigationCommand(
		'core:goto-knowledge',
		'Go to Knowledge Bases',
		'/workspace/knowledge',
		['knowledge', 'workspace', 'kb'],
		BookOpen
	),
	createNavigationCommand(
		'core:goto-models',
		'Go to Models',
		'/workspace/models',
		['models', 'workspace'],
		Cube
	),
	createNavigationCommand(
		'core:goto-prompts',
		'Go to Prompts',
		'/workspace/prompts',
		['prompts', 'workspace'],
		Document
	),
	createNavigationCommand(
		'core:goto-tools',
		'Go to Tools',
		'/workspace/tools',
		['tools', 'workspace'],
		Wrench
	),
	createNavigationCommand(
		'core:goto-admin-settings',
		'Go to Admin Settings',
		'/admin/settings',
		['admin', 'settings'],
		Cog6
	),
	createNavigationCommand(
		'core:goto-admin-users',
		'Go to Admin Users',
		'/admin/users',
		['admin', 'users'],
		UsersSolid
	),
	createNavigationCommand(
		'core:goto-admin-functions',
		'Go to Admin Functions',
		'/admin/functions',
		['admin', 'functions'],
		AdjustmentsHorizontal
	),
	createNavigationCommand(
		'core:goto-admin-evaluations',
		'Go to Admin Evaluations',
		'/admin/evaluations',
		['admin', 'evaluations'],
		FaceSmile
	)
];

function createNavigationCommand(
	id: string,
	label: string,
	route: string,
	keywords: string[],
	icon?: Command['icon']
): NavigationCommand {
	return {
		id,
		type: 'navigation',
		label,
		route,
		keywords,
		priority: NAVIGATION_PRIORITY,
		icon,
		execute: () => goto(route)
	};
}

export function registerCoreCommands(): void {
	if (coreRegistered) return;
	coreRegistered = true;

	try {
		for (const command of coreCommands) {
			registerCommand(command);
		}

		registerCommands(createSettingsCommands(), { replace: true });
		registerChatCommands();
	} catch (error) {
		console.error('Failed to register core commands:', error);
		throw error;
	}
}

const requiresPersistentChat = (context: CommandContext) =>
	Boolean(context.currentChatId && context.currentChatId !== 'local');

type SaveAsFn = (data: Blob | File, filename?: string, options?: unknown) => void;

async function getSaveAs(): Promise<SaveAsFn> {
	const mod = (await import('file-saver')) as any;
	if (typeof mod.saveAs === 'function') {
		return mod.saveAs as SaveAsFn;
	}
	if (typeof mod.default === 'function') {
		return mod.default as SaveAsFn;
	}
	if (mod.default && typeof mod.default === 'object' && typeof mod.default.saveAs === 'function') {
		return mod.default.saveAs as SaveAsFn;
	}
	throw new Error('file-saver module did not expose saveAs');
}

async function exportPdf(containerElement: HTMLElement, chat: any) {
	const html2canvasModule = (await import('html2canvas-pro')) as { default?: unknown };
	const html2canvas = html2canvasModule.default;
	if (typeof html2canvas !== 'function') {
		throw new Error('html2canvas-pro did not expose a default function');
	}
	const jsPDFModule = (await import('jspdf')) as any;
	const JsPDF = jsPDFModule.default;
	if (typeof JsPDF !== 'function') {
		throw new Error('jspdf did not expose a default constructor');
	}
	const saveAs = await getSaveAs();

	const isDarkMode = get(theme)?.includes('dark');
	const virtualWidth = 1024;
	const virtualHeight = 1400;

	const clonedElement = containerElement.cloneNode(true) as HTMLElement;
	clonedElement.style.width = `${virtualWidth}px`;
	clonedElement.style.height = 'auto';

	document.body.appendChild(clonedElement);

	const canvas = await html2canvas(clonedElement, {
		backgroundColor: isDarkMode ? '#000' : '#fff',
		useCORS: true,
		scale: 2,
		width: virtualWidth,
		windowWidth: virtualWidth,
		windowHeight: virtualHeight
	});

	document.body.removeChild(clonedElement);

	const imgData = canvas.toDataURL('image/png');
	const pdf = new (JsPDF as any)('p', 'mm', 'a4');
	const imgWidth = 210;
	const pageHeight = 297;
	const imgHeight = (canvas.height * imgWidth) / canvas.width;
	let heightLeft = imgHeight;
	let position = 0;

	if (isDarkMode) {
		pdf.setFillColor(0, 0, 0);
		pdf.rect(0, 0, imgWidth, pageHeight, 'F');
	}

	pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
	heightLeft -= pageHeight;

	while (heightLeft > 0) {
		position -= pageHeight;
		pdf.addPage();
		if (isDarkMode) {
			pdf.setFillColor(0, 0, 0);
			pdf.rect(0, 0, imgWidth, pageHeight, 'F');
		}
		pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
		heightLeft -= pageHeight;
	}

	saveAs(pdf.output('blob'), `chat-${chat.chat.title}.pdf`);
}

const chatCommands: Command[] = [
	{
		id: 'chat:rename',
		type: 'action',
		label: 'Rename Current Chat',
		keywords: ['rename', 'title'],
		priority: CHAT_PRIORITY + 5,
		condition: requiresPersistentChat,
		icon: Pencil,
		execute: async () => {
			// This is handled specially in CommandPalette.svelte triggerCommand
			// The command palette will enter rename mode
		}
	},
	{
		id: 'chat:move-to-folder',
		type: 'submenu',
		label: 'Move Current Chat to Folder…',
		keywords: ['move', 'folder', 'organize'],
		priority: CHAT_PRIORITY,
		condition: requiresPersistentChat,
		icon: FolderOpen,
		getSubmenuItems: async (query: string, context?: CommandContext): Promise<SubmenuItem[]> => {
			const currentChatId = context?.currentChatId || get(chatId);
			if (!currentChatId) return [];

			// Ensure folders are loaded - always fetch to get latest
			let folders = get(foldersStore);
			const fetched = await getFolders(localStorage.token);
			if (fetched) {
				foldersStore.set(fetched);
				folders = fetched;
			} else if (!folders || Object.keys(folders).length === 0) {
				folders = {};
			}

			// Get current folder
			let currentFolderId: string | null = null;
			try {
				const meta = await getChatMetaById(localStorage.token, currentChatId);
				currentFolderId = meta?.folder_id ?? null;
			} catch (error) {
				console.error('Failed to fetch chat metadata', error);
			}

			const folderItems: SubmenuItem[] = [
				{
					id: 'folder:none',
					label: 'No folder',
					description: 'Remove from folder',
					execute: async () => {
						await updateChatFolderIdById(localStorage.token, currentChatId, undefined);
						await refreshChats();
						toast.success('Chat updated.');
					}
				}
			];

			const lowerQuery = query.toLowerCase();
			for (const folder of Object.values(folders)) {
				const folderName = (folder as any).name || '';
				if (!query || folderName.toLowerCase().includes(lowerQuery)) {
					folderItems.push({
						id: `folder:${(folder as any).id}`,
						label: folderName,
						description: currentFolderId === (folder as any).id ? 'Current folder' : undefined,
						execute: async () => {
							await updateChatFolderIdById(localStorage.token, currentChatId, (folder as any).id);
							await refreshChats();
							toast.success('Chat updated.');
						}
					});
				}
			}

			return folderItems;
		}
	},
	{
		id: 'chat:change-model',
		type: 'submenu',
		label: 'Change Chat Model…',
		keywords: ['model', 'switch', 'change'],
		priority: CHAT_PRIORITY - 5,
		condition: requiresPersistentChat,
		icon: AdjustmentsHorizontal,
		getSubmenuItems: async (query: string, context?: CommandContext): Promise<SubmenuItem[]> => {
			const currentChatId = context?.currentChatId || get(chatId);
			if (!currentChatId) return [];

			const models = get(modelsStore) ?? [];
			const lowerQuery = query.toLowerCase();

			// Get current model
			let currentModelId = '';
			try {
				const chat = await getChatById(localStorage.token, currentChatId);
				currentModelId = chat?.chat?.models?.[0] ?? '';
			} catch (error) {
				console.error('Failed to fetch chat', error);
			}

			const modelItems: SubmenuItem[] = models
				.filter((model: any) => {
					const name = model.name ?? model.id;
					return !query || name.toLowerCase().includes(lowerQuery);
				})
				.map((model: any) => ({
					id: `model:${model.id}`,
					label: model.name ?? model.id,
					description: currentModelId === model.id ? 'Current model' : undefined,
					execute: async () => {
						await updateChatById(localStorage.token, currentChatId, { models: [model.id] });
						chatCache.update((cache) => {
							cache.delete(currentChatId);
							return cache;
						});
						await refreshChats();

						// Dispatch event to update current chat view if we're viewing this chat
						const event = new CustomEvent('chat-model-updated', {
							detail: { chatId: currentChatId, models: [model.id] }
						});
						window.dispatchEvent(event);

						toast.success('Model updated.');
					}
				}));

			return modelItems;
		}
	},
	{
		id: 'chat:export',
		type: 'submenu',
		label: 'Export Current Chat…',
		keywords: ['export', 'download', 'chat'],
		priority: CHAT_PRIORITY - 10,
		condition: requiresPersistentChat,
		icon: ArrowDownTray,
		getSubmenuItems: async (query: string, context?: CommandContext): Promise<SubmenuItem[]> => {
			const currentChatId = context?.currentChatId || get(chatId);
			if (!currentChatId) return [];

			const lowerQuery = query.toLowerCase();
			const exportTypes: SubmenuItem[] = [
				{
					id: 'export:json',
					label: 'JSON (.json)',
					description: 'Export as JSON file',
					execute: async () => {
						try {
							const saveAs = await getSaveAs();
							const chat = await getChatById(localStorage.token, currentChatId, undefined, true);
							if (!chat) {
								toast.error('Failed to load chat.');
								return;
							}
							const blob = new Blob([JSON.stringify([chat])], { type: 'application/json' });
							saveAs(blob, `chat-export-${Date.now()}.json`);
							toast.success('Chat exported as JSON.');
						} catch (error) {
							console.error(error);
							toast.error('Failed to export chat.');
						}
					}
				},
				{
					id: 'export:text',
					label: 'Plain text (.txt)',
					description: 'Export as text file',
					execute: async () => {
						try {
							const saveAs = await getSaveAs();
							const chat = await getChatById(localStorage.token, currentChatId);
							if (!chat) {
								toast.error('Failed to load chat.');
								return;
							}
							const history = chat.chat.history;
							const messages = createMessagesList(history, history.currentId) as any[];
							const chatText = messages
								.reduce<string>((acc: string, message: any) => {
									return `${acc}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
								}, '')
								.trim();
							const blob = new Blob([chatText], { type: 'text/plain' });
							saveAs(blob, `chat-${chat.chat.title}.txt`);
							toast.success('Chat exported as text.');
						} catch (error) {
							console.error(error);
							toast.error('Failed to export chat.');
						}
					}
				},
				{
					id: 'export:pdf',
					label: 'PDF document (.pdf)',
					description: 'Export as PDF file',
					execute: async () => {
						try {
							const chat = await getChatById(localStorage.token, currentChatId);
							if (!chat) {
								toast.error('Failed to load chat.');
								return;
							}
							const containerElement = document.getElementById('messages-container');
							if (!containerElement) {
								toast.error('Messages container not found.');
								return;
							}
							await exportPdf(containerElement, chat);
							toast.success('Chat exported as PDF.');
						} catch (error) {
							console.error('Error generating PDF', error);
							toast.error('Failed to export PDF.');
						}
					}
				}
			];

			return exportTypes.filter(
				(item) =>
					!query ||
					item.label.toLowerCase().includes(lowerQuery) ||
					item.description?.toLowerCase().includes(lowerQuery)
			);
		}
	},
	{
		id: 'chat:toggle-pin',
		type: 'action',
		label: 'Toggle Pin for Current Chat',
		keywords: ['pin', 'unpin', 'chat'],
		priority: CHAT_PRIORITY - 2,
		condition: requiresPersistentChat,
		icon: Bookmark,
		execute: async () => {
			const id = await getActiveChatId();
			if (!id) return;

			await toggleChatPinnedStatusById(localStorage.token, id);
			await refreshPinnedChats();
		}
	},
	{
		id: 'chat:clone',
		type: 'action',
		label: 'Clone Current Chat',
		keywords: ['clone', 'duplicate', 'chat'],
		priority: CHAT_PRIORITY - 4,
		condition: requiresPersistentChat,
		icon: DocumentDuplicate,
		execute: async () => {
			const id = await getActiveChatId();
			if (!id) return;

			const title = get(chatTitleStore);
			try {
				const cloned = await cloneChatById(localStorage.token, id, `Clone of ${title ?? ''}`);
				if (cloned?.id) {
					await refreshChats();
					await goto(`/c/${cloned.id}`);
				}
			} catch (error) {
				console.error(error);
				toast.error('Failed to clone chat.');
			}
		}
	},
	{
		id: 'chat:archive',
		type: 'action',
		label: 'Archive Current Chat',
		keywords: ['archive', 'chat'],
		priority: CHAT_PRIORITY - 6,
		condition: requiresPersistentChat,
		icon: ArchiveBox,
		execute: async () => {
			const id = await getActiveChatId();
			if (!id) return;

			await archiveChatById(localStorage.token, id);
			await refreshChats();
			toast.success('Chat archived.');
		}
	},
	{
		id: 'chat:copy-link',
		type: 'action',
		label: 'Copy Link to Current Chat',
		keywords: ['copy', 'link', 'chat'],
		priority: CHAT_PRIORITY - 8,
		condition: requiresPersistentChat,
		icon: LinkIcon,
		execute: async () => {
			const id = await getActiveChatId();
			if (!id || id === 'local') {
				toast.error('Cannot copy link for a local chat.');
				return;
			}

			if (!navigator?.clipboard) {
				toast.error('Clipboard API is not available.');
				return;
			}

			const origin = window.location.origin;
			const url = `${origin}/c/${id}`;
			await navigator.clipboard.writeText(url);
			toast.success('Chat link copied to clipboard.');
		}
	}
];

async function getActiveChatId(): Promise<string | null> {
	const id = get(chatId);
	if (!id || id === 'local') {
		toast.error('Open a saved chat to use this command.');
		return null;
	}
	return id;
}

async function refreshChats() {
	currentChatPage.set(1);
	const updatedChats = await getChatList(localStorage.token, get(currentChatPage));
	chats.set(updatedChats);
	await refreshPinnedChats();
}

async function refreshPinnedChats() {
	pinnedChats.set(await getPinnedChatList(localStorage.token));
}

export function registerChatCommands(): void {
	if (chatRegistered) return;
	chatRegistered = true;

	for (const command of chatCommands) {
		registerCommand(command);
	}
}
