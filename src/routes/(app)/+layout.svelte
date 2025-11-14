<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onDestroy, onMount, tick, getContext } from 'svelte';
	import { openDB, deleteDB } from 'idb';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;
	import mermaid from 'mermaid';

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { fade } from 'svelte/transition';

	import { getKnowledgeBases } from '$lib/apis/knowledge';
	import { getFunctions } from '$lib/apis/functions';
	import { getModels, getToolServersData, getVersionUpdates } from '$lib/apis';
	import { getAllTags } from '$lib/apis/chats';
	import { getPrompts } from '$lib/apis/prompts';
	import { getTools } from '$lib/apis/tools';
	import { getBanners } from '$lib/apis/configs';
	import { getUserSettings } from '$lib/apis/users';
	import { applyCustomThemeColors } from '$lib/utils/theme';

	import { WEBUI_VERSION } from '$lib/constants';
	import { compareVersion } from '$lib/utils';

	import {
		config,
		user,
		settings,
		models,
		prompts,
		knowledge,
		tools,
		functions,
		tags,
		banners,
		showSettings,
		showChangelog,
		chatTitle,
		temporaryChatEnabled,
		toolServers,
		commandPaletteQuery,
		commandPaletteSubmenu,
		isCommandPaletteOpen
	} from '$lib/stores';

	import Sidebar from '$lib/components/layout/Sidebar.svelte';
	import SettingsModal from '$lib/components/chat/SettingsModal.svelte';
	import ChangelogModal from '$lib/components/ChangelogModal.svelte';
	import AccountPending from '$lib/components/layout/Overlay/AccountPending.svelte';
	import UpdateInfoToast from '$lib/components/layout/UpdateInfoToast.svelte';
	import { get } from 'svelte/store';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { registerCoreCommands } from '$lib/utils/commandPalette/commands';
	import { addRecentChat } from '$lib/utils/commandPalette/recentChats';
	import CommandPalette from '$lib/components/common/CommandPalette/CommandPalette.svelte';

	const i18n = getContext('i18n');

	let loaded = false;
	let showSidebar = false;
	let DB = null;
	let localDBChats = [];

	let version;
	let paletteShortcut = 'cmd+p';
	let lastShiftPress = 0;
	let paletteShortcutUnsubscribe: (() => void) | null = null;

	page.subscribe(($page) => {
		if (typeof window === 'undefined') return;
		const match = /^\/c\/([^/]+)/.exec($page.url.pathname);
		if (match) {
			const currentTitle = get(chatTitle) ?? 'Chat';
			addRecentChat({ id: match[1], title: currentTitle });
		}
	});

	onMount(async () => {
		registerCoreCommands();

		paletteShortcutUnsubscribe = settings.subscribe(($settings) => {
			paletteShortcut = $settings?.commandPaletteShortcut ?? 'cmd+p';
		});

		if ($user === undefined || $user === null) {
			await goto('/auth');
		} else if (['user', 'admin'].includes($user?.role)) {
			// Load settings from localStorage immediately (non-blocking)
			let localStorageSettings = {} as Parameters<(typeof settings)['set']>[0];
			try {
				localStorageSettings = JSON.parse(localStorage.getItem('settings') ?? '{}');
			} catch (e: unknown) {
				console.error('Failed to parse settings from localStorage', e);
			}
			settings.set(localStorageSettings);

			// Apply custom theme if selected
			if (localStorage.theme === 'custom' && localStorageSettings?.customThemeColor) {
				applyCustomThemeColors(localStorageSettings.customThemeColor);
			}

			// Load models in parallel (non-blocking for initial render)
			// Models are needed for chat input, but we can render the input first
			getModels(
				localStorage.token,
				$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null)
			)
				.then((modelsData) => {
					models.set(modelsData);
				})
				.catch((error) => {
					console.error('Failed to load models:', error);
				});

			// Fetch user settings in background and update if different
			// Only update if server settings differ significantly to avoid overwriting user changes
			getUserSettings(localStorage.token)
				.then((userSettings) => {
					if (userSettings) {
						// Compare current settings with server settings
						const currentSettingsStr = JSON.stringify($settings);
						const serverSettingsStr = JSON.stringify(userSettings.ui);

						// Only update if they're different (avoid unnecessary updates)
						if (currentSettingsStr !== serverSettingsStr) {
							settings.set(userSettings.ui);

							// Apply custom theme if selected
							if (localStorage.theme === 'custom' && userSettings.ui?.customThemeColor) {
								applyCustomThemeColors(userSettings.ui.customThemeColor);
							}
						}
					}
				})
				.catch((error) => {
					console.error('Failed to load user settings:', error);
				});

			// Defer non-critical data loading to after initial render
			// Use requestIdleCallback if available, otherwise setTimeout
			const loadDeferredData = () => {
				// Load IndexedDB check
				openDB('Chats', 1)
					.then((db) => {
						DB = db;
						if (DB) {
							return DB.getAllFromIndex('chats', 'timestamp');
						}
						return [];
					})
					.then((chats) => {
						if (chats.length > 0) {
							localDBChats = chats.map((item, idx) => chats[chats.length - 1 - idx]);
						} else if (DB) {
							deleteDB('Chats');
						}
					})
					.catch(() => {
						// IndexedDB Not Found or error - ignore
					});

				// Load banners, tools, and toolServers in parallel
				Promise.all([
					getBanners(localStorage.token).catch(() => []),
					getTools(localStorage.token).catch(() => []),
					getToolServersData($i18n, $settings?.toolServers ?? []).catch(() => [])
				]).then(([bannersData, toolsData, toolServersData]) => {
					banners.set(bannersData);
					tools.set(toolsData);
					toolServers.set(toolServersData);
				});
			};

			if (typeof requestIdleCallback !== 'undefined') {
				requestIdleCallback(loadDeferredData, { timeout: 2000 });
			} else {
				setTimeout(loadDeferredData, 0);
			}

			document.addEventListener('keydown', async function (event) {
				if (handleCommandPaletteHotkey(event)) {
					return;
				}

				const isCtrlPressed = event.ctrlKey || event.metaKey; // metaKey is for Cmd key on Mac
				// Check if the Shift key is pressed
				const isShiftPressed = event.shiftKey;

				// Check if Ctrl + Shift + O is pressed
				if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 'o') {
					event.preventDefault();
					console.log('newChat');
					document.getElementById('sidebar-new-chat-button')?.click();
				}

				// Check if Shift + Esc is pressed
				if (isShiftPressed && event.key === 'Escape') {
					event.preventDefault();
					console.log('focusInput');
					document.getElementById('chat-input')?.focus();
				}

				// Check if Ctrl + Shift + ; is pressed
				if (isCtrlPressed && isShiftPressed && event.key === ';') {
					event.preventDefault();
					console.log('copyLastCodeBlock');
					const button = [...document.getElementsByClassName('copy-code-button')]?.at(-1);
					button?.click();
				}

				// Check if Ctrl + Shift + C is pressed
				if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 'c') {
					event.preventDefault();
					console.log('copyLastResponse');
					const button = [...document.getElementsByClassName('copy-response-button')]?.at(-1);
					console.log(button);
					button?.click();
				}

				// Check if Ctrl + Shift + S is pressed
				if (isCtrlPressed && isShiftPressed && event.key.toLowerCase() === 's') {
					event.preventDefault();
					console.log('toggleSidebar');
					document.getElementById('sidebar-toggle-button')?.click();
				}

				// Check if Ctrl + Shift + Backspace is pressed
				if (
					isCtrlPressed &&
					isShiftPressed &&
					(event.key === 'Backspace' || event.key === 'Delete')
				) {
					event.preventDefault();
					console.log('deleteChat');
					document.getElementById('delete-chat-button')?.click();
				}

				// Check if Ctrl + . is pressed
				if (isCtrlPressed && event.key === '.') {
					event.preventDefault();
					console.log('openSettings');
					showSettings.set(!$showSettings);
				}

				// Check if Ctrl + / is pressed
				if (isCtrlPressed && event.key === '/') {
					event.preventDefault();
					console.log('showShortcuts');
					document.getElementById('show-shortcuts-button')?.click();
				}

				// Check if Ctrl + Shift + ' is pressed
				if (
					isCtrlPressed &&
					isShiftPressed &&
					(event.key.toLowerCase() === `'` || event.key.toLowerCase() === `"`)
				) {
					event.preventDefault();
					console.log('temporaryChat');
					temporaryChatEnabled.set(!$temporaryChatEnabled);
					await goto('/');
					const newChatButton = document.getElementById('new-chat-button');
					setTimeout(() => {
						newChatButton?.click();
					}, 0);
				}
			});

			// TODO more thorough testing, and make this toggleable in settings?
			document.addEventListener('keydown', (e) => {
				// Check if modifier keys are pressed (but allow Shift for normal typing)
				if (e.ctrlKey || e.metaKey || e.altKey) {
					return;
				}

				const target = e.target as HTMLElement;

				// Check if the event target is an input, textarea, or contenteditable element
				if (
					target.tagName === 'INPUT' ||
					target.tagName === 'TEXTAREA' ||
					target.isContentEditable
				) {
					return;
				}

				// Check if the key is a single character and not a special key
				if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
					const chatInput = document.getElementById('chat-input') as HTMLTextAreaElement;

					if (chatInput) {
						chatInput.focus();
					}
				}
			});

			// Check changelog - use localStorage.version first (set when user dismisses modal)
			// This avoids the issue where settings load asynchronously
			const checkChangelog = () => {
				if ($user?.role === 'admin' && ($settings?.showChangelog ?? true)) {
					const dismissedVersion = localStorage.version;
					if (dismissedVersion === $config.version) {
						showChangelog.set(false);
					} else {
						// Check settings.version after it loads
						showChangelog.set($settings?.version !== $config.version);
					}
				}
			};

			// Check immediately (may be false if settings not loaded yet, but that's ok)
			checkChangelog();

			if ($user?.permissions?.chat?.temporary ?? true) {
				if ($page.url.searchParams.get('temporary-chat') === 'true') {
					temporaryChatEnabled.set(true);
				}

				if ($user?.permissions?.chat?.temporary_enforced) {
					temporaryChatEnabled.set(true);
				}
			}

			// Defer version updates check (admin only, non-critical)
			if ($user?.role === 'admin') {
				const checkVersionUpdates = () => {
					// Check if the user has dismissed the update toast in the last 24 hours
					if (localStorage.dismissedUpdateToast) {
						const dismissedUpdateToast = new Date(Number(localStorage.dismissedUpdateToast));
						const now = new Date();

						if (now - dismissedUpdateToast > 24 * 60 * 60 * 1000) {
							checkForVersionUpdates();
						}
					} else {
						checkForVersionUpdates();
					}
				};

				if (typeof requestIdleCallback !== 'undefined') {
					requestIdleCallback(checkVersionUpdates, { timeout: 5000 });
				} else {
					setTimeout(checkVersionUpdates, 100);
				}
			}
			await tick();
		}

		loaded = true;

		await tick();
		showSidebar = true;
	});

	function toggleCommandPalette() {
		if (get(isCommandPaletteOpen)) {
			isCommandPaletteOpen.set(false);
			lastShiftPress = 0;
		} else {
			commandPaletteSubmenu.set([]);
			commandPaletteQuery.set('');
			isCommandPaletteOpen.set(true);
		}
	}

	function handleCommandPaletteHotkey(event: KeyboardEvent): boolean {
		const target = event.target as HTMLElement | null;
		const isTextInput = Boolean(
			target && (target.closest('input, textarea') || target.isContentEditable === true)
		);

		if (paletteShortcut === 'double-shift') {
			if (isTextInput) {
				return false;
			}

			if (
				event.key === 'Shift' &&
				!event.ctrlKey &&
				!event.metaKey &&
				!event.altKey &&
				!event.repeat
			) {
				const now = Date.now();
				if (now - lastShiftPress < 400) {
					event.preventDefault();
					lastShiftPress = 0;
					toggleCommandPalette();
					return true;
				}
				lastShiftPress = now;
			}
			return false;
		}

		const key = event.key.toLowerCase();
		const isMeta = event.metaKey || event.ctrlKey;

		if (!isMeta || event.altKey || event.repeat) {
			return false;
		}

		if (isTextInput && paletteShortcut === 'cmd+e') {
			return false;
		}

		if (
			(paletteShortcut === 'cmd+p' && key === 'p') ||
			(paletteShortcut === 'cmd+k' && key === 'k') ||
			(paletteShortcut === 'cmd+e' && key === 'e')
		) {
			event.preventDefault();
			toggleCommandPalette();
			return true;
		}

		return false;
	}

	onDestroy(() => {
		paletteShortcutUnsubscribe?.();
	});

	const checkForVersionUpdates = async () => {
		version = await getVersionUpdates(localStorage.token).catch((error) => {
			return {
				current: WEBUI_VERSION,
				latest: WEBUI_VERSION
			};
		});
	};

	// Reactive: Update changelog check when settings change (after they load from server)
	$: if ($settings && $user?.role === 'admin') {
		const dismissedVersion = localStorage.version;
		if (dismissedVersion === $config.version) {
			showChangelog.set(false);
		} else {
			showChangelog.set($settings?.version !== $config.version);
		}
	}
</script>

<SettingsModal bind:show={$showSettings} />
<ChangelogModal bind:show={$showChangelog} />
<CommandPalette />

{#if version && compareVersion(version.latest, version.current) && ($settings?.showUpdateToast ?? true)}
	<div class=" absolute bottom-8 right-8 z-50" in:fade={{ duration: 100 }}>
		<UpdateInfoToast
			{version}
			on:close={() => {
				localStorage.setItem('dismissedUpdateToast', Date.now().toString());
				version = null;
			}}
		/>
	</div>
{/if}

<div class="app relative">
	<div
		class=" text-gray-700 dark:text-gray-100 bg-white dark:bg-gray-900 h-screen max-h-[100dvh] overflow-auto flex flex-row justify-end"
	>
		{#if !['user', 'admin'].includes($user?.role)}
			<AccountPending />
		{:else if localDBChats.length > 0}
			<div class="fixed w-full h-full flex z-50">
				<div
					class="absolute w-full h-full backdrop-blur-md bg-white/20 dark:bg-gray-900/50 flex justify-center"
				>
					<div class="m-auto pb-44 flex flex-col justify-center">
						<div class="max-w-md">
							<div class="text-center dark:text-white text-2xl font-medium z-50">
								Important Update<br /> Action Required for Chat Log Storage
							</div>

							<div class=" mt-4 text-center text-sm dark:text-gray-200 w-full">
								{$i18n.t(
									"Saving chat logs directly to your browser's storage is no longer supported. Please take a moment to download and delete your chat logs by clicking the button below. Don't worry, you can easily re-import your chat logs to the backend through"
								)}
								<span class="font-semibold dark:text-white"
									>{$i18n.t('Settings')} > {$i18n.t('Chats')} > {$i18n.t('Import Chats')}</span
								>. {$i18n.t(
									'This ensures that your valuable conversations are securely saved to your backend database. Thank you!'
								)}
							</div>

							<div class=" mt-6 mx-auto relative group w-fit">
								<button
									class="relative z-20 flex px-5 py-2 rounded-full bg-white border border-gray-100 dark:border-none hover:bg-gray-100 transition font-medium text-sm"
									on:click={async () => {
										let blob = new Blob([JSON.stringify(localDBChats)], {
											type: 'application/json'
										});
										saveAs(blob, `chat-export-${Date.now()}.json`);

										const tx = DB.transaction('chats', 'readwrite');
										await Promise.all([tx.store.clear(), tx.done]);
										await deleteDB('Chats');

										localDBChats = [];
									}}
								>
									Download & Delete
								</button>

								<button
									class="text-xs text-center w-full mt-2 text-gray-400 underline"
									on:click={async () => {
										localDBChats = [];
									}}>{$i18n.t('Close')}</button
								>
							</div>
						</div>
					</div>
				</div>
			</div>
		{/if}

		{#if showSidebar}
			<Sidebar />
		{/if}

		{#if loaded}
			<slot />
		{:else}
			<div class="w-full flex-1 h-full flex items-center justify-center">
				<Spinner />
			</div>
		{/if}
	</div>
</div>

<style>
	.loading {
		display: inline-block;
		clip-path: inset(0 1ch 0 0);
		animation: l 1s steps(3) infinite;
		letter-spacing: -0.5px;
	}

	@keyframes l {
		to {
			clip-path: inset(0 -1ch 0 0);
		}
	}

	pre[class*='language-'] {
		position: relative;
		overflow: auto;

		/* make space  */
		margin: 5px 0;
		padding: 1.75rem 0 1.75rem 1rem;
		border-radius: 10px;
	}

	pre[class*='language-'] button {
		position: absolute;
		top: 5px;
		right: 5px;

		font-size: 0.9rem;
		padding: 0.15rem;
		background-color: #828282;

		border: ridge 1px #7b7b7c;
		border-radius: 5px;
		text-shadow: #c4c4c4 0 0 2px;
	}

	pre[class*='language-'] button:hover {
		cursor: pointer;
		background-color: #bcbabb;
	}
</style>
