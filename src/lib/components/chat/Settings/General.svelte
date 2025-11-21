<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { createEventDispatcher, onMount, getContext } from 'svelte';
	import { getLanguages, changeLanguage } from '$lib/i18n';
	import { applyCustomThemeColors, resetToDefaultGrayColors, hslToHex } from '$lib/utils/theme';
	const dispatch = createEventDispatcher();

	import { models, settings, theme, user } from '$lib/stores';

	const i18n = getContext('i18n');

	import AdvancedParams from './Advanced/AdvancedParams.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Switch from '$lib/components/common/Switch.svelte';

	interface Props {
		saveSettings: Function;
		getModels: Function;
	}

	let { saveSettings, getModels }: Props = $props();

	// General
	let selectedTheme = $state('system');
	let customThemeColor = $state('#6366f1'); // Default indigo color
	let pendingCustomColor = $state('#6366f1'); // Color being edited but not yet applied

	let languages: Awaited<ReturnType<typeof getLanguages>> = $state([]);
	let lang = $state($i18n.language);
	let notificationEnabled = $state(false);
	let system = $state('');

	let showAdvanced = $state(false);

	const toggleNotification = async () => {
		const permission = await Notification.requestPermission();

		if (permission === 'granted') {
			notificationEnabled = !notificationEnabled;
			saveSettings({ notificationEnabled: notificationEnabled });
		} else {
			toast.error(
				$i18n.t(
					'Response notifications cannot be activated as the website permissions have been denied. Please visit your browser settings to grant the necessary access.'
				)
			);
		}
	};

	// Advanced
	let requestFormat = $state(null);
	let keepAlive: string | null = $state(null);

	let params = $state({
		// Advanced
		stream_response: null,
		function_calling: null,
		seed: null,
		temperature: null,
		reasoning: {
			effort: null, // Reasoning effort for reasoning models
			max_tokens: null // Maximum tokens for reasoning models
		},
		logit_bias: null,
		frequency_penalty: null,
		presence_penalty: null,
		repeat_penalty: null,
		repeat_last_n: null,
		mirostat: null,
		mirostat_eta: null,
		mirostat_tau: null,
		top_k: null,
		top_p: null,
		min_p: null,
		stop: null,
		tfs_z: null,
		num_ctx: null,
		num_batch: null,
		num_keep: null,
		max_tokens: null,
		num_gpu: null,

		// ORT-specific
		provider: {
			order: null, // List of provider slugs to try in order (e.g. ["anthropic", "openai"]).
			allow_fallbacks: null, // Allow fallback to other providers if the first one fails. ORT default is true
			require_parameters: null, // Require parameters to be set for the provider. ORT default is false
			data_collection: null, // Control whether to use providers that may store data. ORT default is "allow", other opt is "deny".
			only: null, // String[] - List of provider slugs to allow for this request.
			ignore: null, // String[] - List of provider slugs to skip for this request.
			// quantizations // String[] - List of quantizations to allow for this request e.g. "int8" etc.
			sort: null // String - Sort providers by price or throughput. (e.g. "price" or "throughput" or "latency").
			// max_price: {prompt: null, completion: null, image: null}, // Maximum price per 1M tokens for prompt and completion.
		}
		// transforms: null, // ORT-specific. compress prompts > than max ctx length
		// plugins: null // ORT-specific. List of plugins to use for this request. Useful for web search via "plugins": [{ "id": "web" }]
		// web_search_options: null, // Options for web search plugins. if enabled, create an object with {search_context_size: "high"} (or "medium", "low") to set the search context size.
	});

	const validateJSON = (json) => {
		try {
			const obj = JSON.parse(json);

			if (obj && typeof obj === 'object') {
				return true;
			}
		} catch (e) {}
		return false;
	};

	const toggleRequestFormat = async () => {
		if (requestFormat === null) {
			requestFormat = 'json';
		} else {
			requestFormat = null;
		}

		saveSettings({ requestFormat: requestFormat !== null ? requestFormat : undefined });
	};

	const saveHandler = async () => {
		if (requestFormat !== null && requestFormat !== 'json') {
			if (validateJSON(requestFormat) === false) {
				toast.error($i18n.t('Invalid JSON schema'));
				return;
			} else {
				requestFormat = JSON.parse(requestFormat);
			}
		}

		saveSettings({
			system: system !== '' ? system : undefined,
			customThemeColor: customThemeColor,
			params: {
				stream_response: params.stream_response !== null ? params.stream_response : undefined,
				function_calling: params.function_calling !== null ? params.function_calling : undefined,
				seed: (params.seed !== null ? params.seed : undefined) ?? undefined,
				stop: params.stop ? params.stop.split(',').filter((e) => e) : undefined,
				temperature: params.temperature !== null ? params.temperature : undefined,
				reasoning: params.reasoning !== null ? params.reasoning : undefined,
				logit_bias: params.logit_bias !== null ? params.logit_bias : undefined,
				frequency_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				presence_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				repeat_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				repeat_last_n: params.repeat_last_n !== null ? params.repeat_last_n : undefined,
				mirostat: params.mirostat !== null ? params.mirostat : undefined,
				mirostat_eta: params.mirostat_eta !== null ? params.mirostat_eta : undefined,
				mirostat_tau: params.mirostat_tau !== null ? params.mirostat_tau : undefined,
				top_k: params.top_k !== null ? params.top_k : undefined,
				top_p: params.top_p !== null ? params.top_p : undefined,
				min_p: params.min_p !== null ? params.min_p : undefined,
				tfs_z: params.tfs_z !== null ? params.tfs_z : undefined,
				num_ctx: params.num_ctx !== null ? params.num_ctx : undefined,
				num_batch: params.num_batch !== null ? params.num_batch : undefined,
				num_keep: params.num_keep !== null ? params.num_keep : undefined,
				max_tokens: params.max_tokens !== null ? params.max_tokens : undefined,
				use_mmap: params.use_mmap !== null ? params.use_mmap : undefined,
				use_mlock: params.use_mlock !== null ? params.use_mlock : undefined,
				num_thread: params.num_thread !== null ? params.num_thread : undefined,
				num_gpu: params.num_gpu !== null ? params.num_gpu : undefined,
				provider: params.provider !== null ? params.provider : undefined
			},
			keepAlive: keepAlive ? (isNaN(keepAlive) ? keepAlive : parseInt(keepAlive)) : undefined,
			requestFormat: requestFormat !== null ? requestFormat : undefined
		});
		dispatch('save');

		requestFormat =
			typeof requestFormat === 'object' ? JSON.stringify(requestFormat, null, 2) : requestFormat;
	};
	onMount(async () => {
		selectedTheme = localStorage.theme ?? 'system';

		// Initialize custom theme color from settings
		customThemeColor = $settings.customThemeColor ?? '#6366f1';
		pendingCustomColor = customThemeColor;

		languages = await getLanguages();

		notificationEnabled = $settings.notificationEnabled ?? false;
		system = $settings.system ?? '';

		requestFormat = $settings.requestFormat ?? null;
		if (requestFormat !== null && requestFormat !== 'json') {
			requestFormat =
				typeof requestFormat === 'object' ? JSON.stringify(requestFormat, null, 2) : requestFormat;
		}

		keepAlive = $settings.keepAlive ?? null;

		params = { ...params, ...$settings.params };
		params.stop = $settings?.params?.stop ? ($settings?.params?.stop ?? []).join(',') : null;
	});

	const applyTheme = (_theme: string): void => {
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
			if ($settings.customThemeColor) {
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

		if (typeof window !== 'undefined' && window.applyTheme) {
			window.applyTheme();
		}

		if (_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#101010');
			document.documentElement.style.setProperty('--color-gray-850', '#050505');
			document.documentElement.style.setProperty('--color-gray-900', '#000000');
			document.documentElement.style.setProperty('--color-gray-950', '#000000');
			document.documentElement.classList.add('dark');
		}
	};
	const themeChangeHandler = (_theme: string): void => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		applyTheme(_theme);

		// Reset pending color when switching away from custom theme
		if (_theme !== 'custom') {
			pendingCustomColor = customThemeColor;
		}
	};

	const handleCustomColorChange = (color: string): void => {
		// Only update the pending color, don't apply yet
		pendingCustomColor = color;
	};

	const applyCustomTheme = async (): Promise<void> => {
		// Update the stored custom color
		customThemeColor = pendingCustomColor;

		// Update settings
		$settings.customThemeColor = customThemeColor;
		await saveSettings($settings);

		// Switch to custom theme if not already selected
		if (selectedTheme !== 'custom') {
			selectedTheme = 'custom';
			themeChangeHandler('custom');
		} else {
			// If already on custom theme, just apply the new color
			applyCustomThemeColors(customThemeColor);
		}
	};

	const randomizeThemeColor = (): void => {
		// Generate a random vibrant color using HSL for better control
		const hue = Math.floor(Math.random() * 360); // Full range of hues
		const saturation = 60 + Math.floor(Math.random() * 40); // 60-100% saturation for vibrant colors
		const lightness = 40 + Math.floor(Math.random() * 20); // 40-60% lightness for good contrast

		const randomColor = hslToHex(hue, saturation, lightness);
		pendingCustomColor = randomColor;
		applyCustomTheme();
	};

	// Check if the current pending color is different from applied color
	let isColorChanged = $derived(pendingCustomColor !== customThemeColor);
</script>

<div class="flex flex-col h-full justify-between text-sm">
	<div class="  overflow-y-scroll max-h-[28rem] lg:max-h-full">
		<div class="">
			<div class=" mb-1 text-sm font-medium">{$i18n.t('WebUI Settings')}</div>

			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">{$i18n.t('Theme')}</div>
				<div class="flex items-center relative">
					<select
						class=" dark:bg-gray-900 w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent outline-hidden text-right"
						bind:value={selectedTheme}
						placeholder="Select a theme"
						onchange={() => themeChangeHandler(selectedTheme)}
					>
						<option value="system">⚙️ {$i18n.t('System')}</option>
						<option value="dark">🌑 {$i18n.t('Dark')}</option>
						<option value="oled-dark">🌃 {$i18n.t('OLED Dark')}</option>
						<option value="light">☀️ {$i18n.t('Light')}</option>
						<option value="her">🌷 Her</option>
						<option value="custom">� Custom</option>
						<!-- <option value="rose-pine dark">🪻 {$i18n.t('Rosé Pine')}</option>
						<option value="rose-pine-dawn light">� {$i18n.t('Rosé Pine Dawn')}</option> -->
					</select>
				</div>
			</div>

			<!-- Custom Theme Color Picker -->
			<div class="flex w-full justify-between items-center">
				<div class="self-center text-xs font-medium">Custom Color</div>
				<div class="flex items-center space-x-2">
					<button
						type="button"
						onclick={randomizeThemeColor}
						class="w-8 h-6 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition flex items-center justify-center text-sm"
						title="Randomize theme color"
					>
						🔄
					</button>
					<input
						type="color"
						bind:value={pendingCustomColor}
						oninput={(e) => handleCustomColorChange(e.target.value)}
						class="w-8 h-6 rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
						title="Choose custom theme color"
					/>
					<button
						type="button"
						onclick={applyCustomTheme}
						class="text-xs px-2 py-1 rounded-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
						class:opacity-50={!isColorChanged && selectedTheme === 'custom'}
						disabled={!isColorChanged && selectedTheme === 'custom'}
					>
						{selectedTheme === 'custom' && !isColorChanged ? 'Applied' : 'Apply'}
					</button>
				</div>
			</div>

			<div class=" flex w-full justify-between">
				<div class=" self-center text-xs font-medium">{$i18n.t('Language')}</div>
				<div class="flex items-center relative">
					<select
						class=" dark:bg-gray-900 w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent outline-hidden text-right"
						bind:value={lang}
						placeholder="Select a language"
						onchange={(e) => {
							changeLanguage(lang);
						}}
					>
						{#each languages as language}
							<option value={language['code']}>{language['title']}</option>
						{/each}
					</select>
				</div>
			</div>
			{#if $i18n.language === 'en-US'}
				<div class="mb-2 text-xs text-gray-400 dark:text-gray-500">
					Couldn't find your language?
					<a
						class=" text-gray-300 font-medium underline"
						href="https://github.com/open-webui/open-webui/blob/main/docs/CONTRIBUTING.md#-translations-and-internationalization"
						target="_blank"
					>
						Help us translate Open WebUI!
					</a>
				</div>
			{/if}

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Notifications')}</div>

					<Switch bind:state={notificationEnabled} on:change={() => saveSettings({ notificationEnabled })} />
				</div>
			</div>
		</div>

		{#if $user?.role === 'admin' || $user?.permissions.chat?.controls}
			<hr class="border-gray-50 dark:border-gray-850 my-3" />

			<div>
				<div class=" my-2.5 text-sm font-medium">{$i18n.t('System Prompt')}</div>
				<Textarea
					bind:value={system}
					className="w-full text-sm bg-white dark:text-gray-300 dark:bg-gray-900 outline-hidden resize-none"
					rows="4"
					placeholder={$i18n.t('Enter system prompt here')}
				/>
			</div>

			<div class="mt-2 space-y-3 pr-1.5">
				<div class="flex justify-between items-center text-sm">
					<div class="  font-medium">{$i18n.t('Advanced Parameters')}</div>
					<button
						class=" text-xs font-medium text-gray-500"
						type="button"
						onclick={() => {
							showAdvanced = !showAdvanced;
						}}>{showAdvanced ? $i18n.t('Hide') : $i18n.t('Show')}</button
					>
				</div>

				{#if showAdvanced}
					<AdvancedParams admin={$user?.role === 'admin'} bind:params />
					<hr class=" border-gray-100 dark:border-gray-850" />

					<div class=" w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Keep Alive')}</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								type="button"
								onclick={() => {
									keepAlive = keepAlive === null ? '5m' : null;
								}}
							>
								{#if keepAlive === null}
									<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
								{:else}
									<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
								{/if}
							</button>
						</div>

						{#if keepAlive !== null}
							<div class="flex mt-1 space-x-2">
								<input
									class="w-full text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="text"
									placeholder={$i18n.t("e.g. '30s','10m'. Valid time units are 's', 'm', 'h'.")}
									bind:value={keepAlive}
								/>
							</div>
						{/if}
					</div>

					<div>
						<div class=" flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Request Mode')}</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								onclick={() => {
									toggleRequestFormat();
								}}
							>
								{#if requestFormat === null}
									<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
								{:else}
									<!-- <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            class="w-4 h-4 self-center"
                        >
                            <path
                                d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06l-1.06-1.06a.75.75 0 10-1.061 1.06l1.06 1.06z"
                            />
                        </svg> -->
									<span class="ml-2 self-center"> {$i18n.t('JSON')} </span>
								{/if}
							</button>
						</div>

						{#if requestFormat !== null}
							<div class="flex mt-1 space-x-2">
								<Textarea
									className="w-full  text-sm dark:text-gray-300 dark:bg-gray-900 outline-hidden"
									placeholder={$i18n.t('e.g. "json" or a JSON schema')}
									bind:value={requestFormat}
								/>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			onclick={() => {
				saveHandler();
			}}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
