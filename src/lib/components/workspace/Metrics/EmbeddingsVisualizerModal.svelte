<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getEmbeddingsVisualization } from '$lib/apis/metrics';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');

	export let show = false;

	let loading = false;
	let plotlyLoaded = false;
	let plotly: any = null;
	let plotDiv: HTMLDivElement;
	let plotData: any = null;

	// Dynamically import Plotly.js
	const loadPlotly = async () => {
		if (plotlyLoaded) return;

		try {
			// Dynamic import - @vite-ignore tells Vite to skip analyzing this import
			// This allows the import to work even if the package isn't installed at build time
			const plotlyModule = await import(/* @vite-ignore */ 'plotly.js-dist-min');
			plotly = plotlyModule.default || plotlyModule;
			plotlyLoaded = true;
		} catch (error: any) {
			console.error('Error loading Plotly.js:', error);
			toast.error($i18n.t('Failed to load visualization library. Please install: npm install plotly.js-dist-min'));
			throw error;
		}
	};

	const fetchAndVisualize = async () => {
		if (!show) return;

		loading = true;
		try {
			// Load Plotly first
			console.log('[EmbeddingsVisualizer] Loading Plotly...');
			await loadPlotly();
			console.log('[EmbeddingsVisualizer] Plotly loaded:', !!plotly);

			// Fetch data from API
			const token = localStorage.token;
			console.log('[EmbeddingsVisualizer] Fetching data from API...');
			const data = await getEmbeddingsVisualization(token);
			console.log('[EmbeddingsVisualizer] Data received:', {
				hasData: !!data,
				xLength: data?.x?.length,
				yLength: data?.y?.length,
				zLength: data?.z?.length,
				labelsLength: data?.labels?.length,
				collectionsLength: data?.collection_names?.length
			});

			if (!data || data.x.length === 0) {
				console.error('[EmbeddingsVisualizer] No data or empty x array');
				toast.error($i18n.t('No embeddings found to visualize'));
				loading = false;
				plotData = null;
				return;
			}

			plotData = data;
			
			// Set loading to false FIRST so the conditional renders the plotDiv
			loading = false;
			
			// Wait for Svelte to update the DOM and render the plotDiv
			await tick();
			
			// Wait a bit more for the modal to fully render the div
			let attempts = 0;
			while (!plotDiv && attempts < 20) {
				await new Promise((resolve) => setTimeout(resolve, 50));
				attempts++;
			}
			
			// Double-check plotDiv is available
			if (!plotDiv) {
				console.error('[EmbeddingsVisualizer] plotDiv not available after wait, attempts:', attempts);
				return;
			}
			
			console.log('[EmbeddingsVisualizer] DOM ready, plotDiv:', {
				exists: !!plotDiv,
				width: plotDiv.offsetWidth,
				height: plotDiv.offsetHeight,
				plotly: !!plotly,
				attempts
			});

			// Create 3D scatter plot
			if (plotDiv && plotly) {
				console.log('[EmbeddingsVisualizer] Creating plot...');
				// Group by collection for color coding
				const uniqueCollections = [...new Set(data.collection_names)];
				// Use a simple color palette (Plotly's default colors)
				const colors = [
					'#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
					'#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
				];
				
				const traces = uniqueCollections.map((collection, idx) => {
					const indices = data.collection_names
						.map((name, i) => name === collection ? i : -1)
						.filter(i => i !== -1);

					return {
						x: indices.map(i => data.x[i]),
						y: indices.map(i => data.y[i]),
						z: indices.map(i => data.z[i]),
						mode: 'markers',
						type: 'scatter3d',
						name: collection,
						text: indices.map(i => data.labels[i]),
						hovertemplate: '<b>%{text}</b><br>' +
							'Collection: ' + collection + '<br>' +
							'X: %{x}<br>Y: %{y}<br>Z: %{z}<extra></extra>',
						marker: {
							size: 5,
							color: colors[idx % colors.length],
							opacity: 0.7
						}
					};
				});

				const layout = {
					title: {
						text: 'Embeddings 3D Visualization (t-SNE)',
						font: { size: 16 }
					},
					scene: {
						xaxis: { title: 'X' },
						yaxis: { title: 'Y' },
						zaxis: { title: 'Z' },
						camera: {
							eye: { x: 1.5, y: 1.5, z: 1.5 }
						}
					},
					margin: { l: 0, r: 0, t: 40, b: 0 },
					height: 600,
					showlegend: true,
					legend: {
						x: 0,
						y: 1,
						bgcolor: 'rgba(255, 255, 255, 0.8)'
					}
				};

				const config = {
					responsive: true,
					displayModeBar: true,
					displaylogo: false,
					modeBarButtonsToRemove: ['lasso2d', 'select2d']
				};

				console.log('[EmbeddingsVisualizer] Calling plotly.newPlot with', {
					tracesCount: traces.length,
					totalPoints: traces.reduce((sum, t) => sum + (t.x?.length || 0), 0),
					layout,
					config
				});

				await plotly.newPlot(plotDiv, traces, layout, config);
				console.log('[EmbeddingsVisualizer] Plot created successfully');
			} else {
				console.error('[EmbeddingsVisualizer] Missing plotDiv or plotly:', {
					plotDiv: !!plotDiv,
					plotly: !!plotly
				});
			}
		} catch (error: any) {
			console.error('[EmbeddingsVisualizer] Error visualizing embeddings:', error);
			toast.error(error?.detail || error?.message || $i18n.t('Failed to load embeddings visualization'));
			loading = false;
		}
	};

	// Clean up Plotly on close
	const cleanup = () => {
		if (plotDiv && plotly) {
			try {
				plotly.purge(plotDiv);
			} catch (e) {
				// Ignore cleanup errors
			}
		}
		plotData = null;
	};

	$: if (show) {
		fetchAndVisualize();
	} else {
		cleanup();
	}

	onDestroy(() => {
		cleanup();
	});
</script>

<Modal bind:show size="xl" className="bg-white dark:bg-gray-900 rounded-2xl p-6">
	<div class="flex flex-col h-full">
		<!-- Header -->
		<div class="flex justify-between items-center mb-4">
			<h2 class="text-xl font-semibold dark:text-gray-200">
				{$i18n.t('Embeddings Visualizer')}
			</h2>
			<button
				class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition"
				on:click={() => (show = false)}
			>
				<XMark className="w-5 h-5" />
			</button>
		</div>

		<!-- Content -->
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
				<!-- Plot container - always render when we have data -->
				<div bind:this={plotDiv} class="w-full" style="height: 600px; min-height: 600px; display: block;"></div>
			{:else}
				<div class="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
					<p class="text-sm">{$i18n.t('No embeddings data available')}</p>
				</div>
			{/if}
		</div>
	</div>
</Modal>

