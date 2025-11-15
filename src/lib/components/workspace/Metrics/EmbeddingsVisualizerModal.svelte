<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { browser } from '$app/environment';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getEmbeddingsVisualization } from '$lib/apis/metrics';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');

	export let show = false;

	let loading = false;
	let deckLoaded = false;
	let deck: any = null;
	let plotDiv: HTMLDivElement;
	let plotData: any = null;
	let deckInstance: any = null;
	let isDark = false;
	let darkModeObserver: MutationObserver | null = null;
	let tooltip: HTMLDivElement;
	let searchQuery = '';

	const COLOR_PALETTE = [
		[31, 119, 180],
		[255, 127, 14],
		[44, 160, 44],
		[214, 39, 40],
		[148, 103, 189],
		[140, 86, 75],
		[227, 119, 194],
		[127, 127, 127],
		[188, 189, 34],
		[23, 190, 207]
	];

	const OPACITY_ALPHA = {
		MATCH: 230, // 0.9 opacity
		NO_MATCH: 80, // ~0.31 opacity
		DEFAULT: 204 // 0.8 opacity
	};

	const checkDarkMode = () => {
		if (!browser) return false;
		return document.documentElement.classList.contains('dark');
	};

	const normalizeData = (data: any) => {
		const minX = Math.min(...data.x);
		const maxX = Math.max(...data.x);
		const minY = Math.min(...data.y);
		const maxY = Math.max(...data.y);
		const minZ = Math.min(...data.z);
		const maxZ = Math.max(...data.z);
		const centerX = (minX + maxX) / 2;
		const centerY = (minY + maxY) / 2;
		const centerZ = (minZ + maxZ) / 2;
		const range = Math.max(maxX - minX, maxY - minY, maxZ - minZ);
		const scale = range > 0 ? 2 / range : 1;

		return data.x.map((x: number, i: number) => ({
			position: [
				(x - centerX) * scale,
				(data.y[i] - centerY) * scale,
				(data.z[i] - centerZ) * scale
			],
			label: data.labels[i],
			collection: data.collection_names[i]
		}));
	};

	const createLayers = (normalizedPoints: any[], uniqueCollections: any[], queryLower: string) => {
		return uniqueCollections.map((collection, idx) => {
			const collectionPoints = normalizedPoints.filter((p: any) => p.collection === collection);
			const color = COLOR_PALETTE[idx % COLOR_PALETTE.length];
			const adjustedColor = isDark ? color.map((c) => Math.min(255, c + 30)) : color;

			const getFillColorWithOpacity = queryLower
				? (d: any) => {
						const labelMatch = d.label?.toLowerCase().includes(queryLower);
						const alpha = labelMatch ? OPACITY_ALPHA.MATCH : OPACITY_ALPHA.NO_MATCH;
						return [...adjustedColor, alpha];
					}
				: [...adjustedColor, OPACITY_ALPHA.DEFAULT];

			return new deck.ScatterplotLayer({
				id: `scatter-${idx}`,
				data: collectionPoints,
				pickable: true,
				opacity: 1.0,
				stroked: false,
				filled: true,
				radiusScale: 1,
				radiusMinPixels: 4,
				radiusMaxPixels: 8,
				radiusUnits: 'pixels',
				coordinateSystem: deck.COORDINATE_SYSTEM.IDENTITY,
				getPosition: (d: any) => d.position,
				getRadius: 1,
				getFillColor: getFillColorWithOpacity,
				updateTriggers: {
					getFillColor: queryLower
				}
			});
		});
	};

	const triggerRender = () => {
		if (!deckInstance || !plotDiv) return;
		const canvas = plotDiv.querySelector('canvas');
		if (canvas) {
			const wheelEvent = new WheelEvent('wheel', {
				bubbles: true,
				cancelable: true,
				clientX: plotDiv.offsetWidth / 2,
				clientY: plotDiv.offsetHeight / 2,
				deltaY: 0.1,
				deltaMode: 0
			});
			canvas.dispatchEvent(wheelEvent);
		}
	};

	// Dynamically import deck.gl
	const loadDeckGL = async () => {
		if (deckLoaded) return;

		try {
			// Dynamic imports - @vite-ignore tells Vite to skip analyzing these imports
			const [deckCore, deckLayers] = await Promise.all([
				import(/* @vite-ignore */ '@deck.gl/core'),
				import(/* @vite-ignore */ '@deck.gl/layers')
			]);

			deck = {
				Deck: deckCore.Deck,
				ScatterplotLayer: deckLayers.ScatterplotLayer,
				OrbitView: deckCore.OrbitView,
				COORDINATE_SYSTEM: deckCore.COORDINATE_SYSTEM
			};
			deckLoaded = true;
		} catch (error: any) {
			console.error('Error loading deck.gl:', error);
			toast.error(
				$i18n.t(
					'Failed to load visualization library. Please install: npm install @deck.gl/core @deck.gl/layers'
				)
			);
			throw error;
		}
	};

	const fetchAndVisualize = async () => {
		if (!show) return;

		loading = true;
		try {
			isDark = checkDarkMode();
			await loadDeckGL();

			const token = localStorage.token;
			const data = await getEmbeddingsVisualization(token);

			if (!data || data.x.length === 0) {
				toast.error($i18n.t('No embeddings found to visualize'));
				loading = false;
				plotData = null;
				return;
			}

			plotData = data;
			loading = false;

			// Wait for DOM to render
			await tick();

			// Wait for modal to fully render
			let attempts = 0;
			while ((!plotDiv || !tooltip) && attempts < 20) {
				await new Promise((resolve) => setTimeout(resolve, 50));
				attempts++;
			}

			if (!plotDiv || !tooltip) {
				console.error('[EmbeddingsVisualizer] DOM elements not available');
				return;
			}

			// Ensure modal is visible and has dimensions
			await new Promise((resolve) => setTimeout(resolve, 100));
			if (plotDiv.offsetWidth === 0 || plotDiv.offsetHeight === 0) {
				await new Promise((resolve) => setTimeout(resolve, 200));
			}

			if (plotDiv && deck) {
				if (deckInstance) {
					try {
						deckInstance.finalize();
					} catch (e) {
						// Ignore cleanup errors
					}
					deckInstance = null;
				}

				const uniqueCollections = [...new Set(data.collection_names)];
				const normalizedPoints = normalizeData(data);
				const queryLower = searchQuery.toLowerCase().trim();
				const normalizedLayers = createLayers(normalizedPoints, uniqueCollections, queryLower);

				// Create deck instance
				deckInstance = new deck.Deck({
					parent: plotDiv,
					width: plotDiv.offsetWidth,
					height: plotDiv.offsetHeight,
					initialViewState: {
						target: [0, 0, 0],
						rotationX: 30,
						rotationOrbit: 0,
						orbitAxis: 'Y',
						fov: 50,
						zoom: 8.0
					},
					controller: true,
					views: new deck.OrbitView({
						fov: 50,
						orbitAxis: 'Y'
					}),
					layers: normalizedLayers,
					style: {
						backgroundColor: 'transparent'
					},
					onHover: (info: any) => {
						if (info.object && tooltip) {
							// plotDiv.style.cursor = 'pointer';
							tooltip.style.display = 'block';
							tooltip.textContent = info.object.label;
							if (info.x !== undefined && info.y !== undefined) {
								tooltip.style.left = `${info.x + 15}px`;
								tooltip.style.top = `${info.y - 35}px`;
							}
						} else {
							// plotDiv.style.cursor = 'default';
							tooltip.style.display = 'none';
						}
					}
				});

				await tick();
				requestAnimationFrame(() => {
					requestAnimationFrame(() => {
						if (deckInstance) {
							deckInstance.setProps({ layers: normalizedLayers });
							setTimeout(triggerRender, 100);
						}
					});
				});
			}
		} catch (error: any) {
			console.error('[EmbeddingsVisualizer] Error:', error);
			toast.error(
				error?.detail || error?.message || $i18n.t('Failed to load embeddings visualization')
			);
			loading = false;
		}
	};

	const updateLayersForSearch = () => {
		if (!deckInstance || !plotData || !deck) return;

		const uniqueCollections = [...new Set(plotData.collection_names)];
		const normalizedPoints = normalizeData(plotData);
		const queryLower = searchQuery.toLowerCase().trim();
		const updatedLayers = createLayers(normalizedPoints, uniqueCollections, queryLower);

		deckInstance.setProps({ layers: updatedLayers });
		requestAnimationFrame(triggerRender);
	};

	const cleanup = () => {
		if (deckInstance) {
			try {
				deckInstance.finalize();
				deckInstance = null;
			} catch (e) {
				// Ignore cleanup errors
			}
		}
		plotData = null;
		searchQuery = '';
	};

	$: if (show) {
		fetchAndVisualize();
	} else {
		cleanup();
	}

	$: if (deckInstance && plotData && deck && searchQuery !== undefined) {
		updateLayersForSearch();
	}

	onMount(() => {
		if (!browser) return;

		darkModeObserver = new MutationObserver(() => {
			const newIsDark = checkDarkMode();
			if (newIsDark !== isDark && deckInstance && plotData) {
				isDark = newIsDark;
				fetchAndVisualize();
			}
		});

		darkModeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class']
		});
	});

	onDestroy(() => {
		if (darkModeObserver) {
			darkModeObserver.disconnect();
			darkModeObserver = null;
		}
		cleanup();
	});
</script>

<Modal bind:show size="xl" className="bg-white dark:bg-gray-900 rounded-2xl p-6">
	<div class="flex flex-col h-full">
		<div class="flex justify-between items-center mb-4">
			<h2 class="text-xl font-semibold dark:text-gray-200">
				{$i18n.t('Embeddings Visualizer')}
			</h2>
			<button
				class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition"
				on:click={() => (show = false)}
			>
				<XMark className="w-5 h-5 text-gray-500 dark:text-gray-400" />
			</button>
		</div>
		<span
			class="text-xs text-gray-500 dark:text-gray-400 ml-1 mt-0.5"
			style="margin-top: -0.5rem; display: block;"
		>
			{$i18n.t(
				'Each point represents a chunk of text, so you may see multiple points from the same document.'
			)}
		</span>

		<div class="mt-3 mb-3">
			<div class="relative">
				<div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
					<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
						/>
					</svg>
				</div>
				<input
					type="text"
					bind:value={searchQuery}
					on:input={() => {
						if (deckInstance && plotData && deck) {
							updateLayersForSearch();
						}
					}}
					placeholder={$i18n.t('Search documents by name...')}
					class="w-full pl-10 pr-4 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
				/>
			</div>
		</div>

		<div class="flex-1 min-h-0" style="min-height: 600px;">
			{#if loading}
				<div class="flex flex-col items-center justify-center h-full">
					<Spinner />
					<p class="mt-4 text-sm text-gray-600 dark:text-gray-400">
						{$i18n.t('Loading embeddings and generating visualization...')}
					</p>
					<p class="mt-2 text-xs text-gray-500 dark:text-gray-500">
						{$i18n.t('This may take a moment for large datasets')}
					</p>
				</div>
			{:else if plotData && plotData.x.length > 0}
				<div class="relative w-full rounded-lg overflow-hidden" style="height: 600px;">
					<div bind:this={plotDiv} class="w-full h-full"></div>
					<div
						bind:this={tooltip}
						class="absolute pointer-events-none z-10 px-2 py-1 text-xs rounded shadow-lg bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 hidden whitespace-nowrap"
						style="left: 0; top: 0;"
					></div>
				</div>
			{:else}
				<div
					class="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400"
				>
					<p class="text-sm">{$i18n.t('No embeddings data available')}</p>
				</div>
			{/if}
		</div>
	</div>
</Modal>
