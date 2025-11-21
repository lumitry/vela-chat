<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		BarElement,
		BarController,
		CategoryScale,
		LinearScale,
		type ChartConfiguration
	} from 'chart.js';
	import { getChartColors, getChartDefaults } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, BarController, CategoryScale, LinearScale);

	let canvasElement: HTMLCanvasElement;
	let chartInstance: ChartJS<'bar'> | null = null;

	export let data: Array<{
		model_id: string;
		model_name: string;
		chat_count: number;
		message_count: number;
	}> = [];
	export let loading: boolean = false;

	$: colors = getChartColors();
	$: defaults = getChartDefaults();

	$: chartData = {
		labels: data && Array.isArray(data) ? data.map((d) => d.model_name || d.model_id) : [],
		datasets: [
			{
				label: 'Chat Count',
				data: data && Array.isArray(data) ? data.map((d) => d.chat_count || 0) : [],
				backgroundColor: colors.singleSeries.primary
			}
		]
	};

	$: chartOptions = {
		indexAxis: 'y' as const,
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				display: false
			},
			tooltip: {
				...defaults.plugins.tooltip,
				callbacks: {
					label: (context: any) => {
						const value = context.parsed.x || 0;
						return `Chats: ${new Intl.NumberFormat().format(value)}`;
					}
				}
			}
		},
		scales: {
			x: {
				...defaults.scales.x,
				beginAtZero: true
			},
			y: {
				...defaults.scales.y
			}
		}
	};

	$: if (canvasElement && data && data.length > 0) {
		if (chartInstance) {
			chartInstance.data = chartData;
			chartInstance.options = chartOptions;
			chartInstance.update();
		} else {
			const config: ChartConfiguration<'bar'> = {
				type: 'bar',
				data: chartData,
				options: chartOptions
			};
			chartInstance = new ChartJS(canvasElement, config);
		}
	} else if (chartInstance) {
		chartInstance.destroy();
		chartInstance = null;
	}

	onDestroy(() => {
		if (chartInstance) {
			chartInstance.destroy();
			chartInstance = null;
		}
	});
</script>

<div class="w-full h-64">
	{#if loading}
		<div class="flex items-center justify-center h-full">
			<Spinner />
		</div>
	{:else if data && data.length > 0}
		<canvas bind:this={canvasElement}></canvas>
	{:else}
		<div class="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
			<div>No model popularity data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period or model type</div>
		</div>
	{/if}
</div>
