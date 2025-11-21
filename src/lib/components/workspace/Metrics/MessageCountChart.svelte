<script lang="ts">
	import { run } from 'svelte/legacy';

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
		TimeScale,
		type ChartConfiguration
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import { getTimeScaleConfig, getNumberTooltipConfig, transformToTimeSeriesData, getChartColors, getChartDefaults } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, BarController, CategoryScale, LinearScale, TimeScale);

	let canvasElement: HTMLCanvasElement = $state();
	let chartInstance: ChartJS<'bar'> | null = $state(null);

	interface Props {
		data?: Array<{ date: string; count: number }>;
		loading?: boolean;
	}

	let { data = [], loading = false }: Props = $props();

	let colors = $derived(getChartColors());
	let defaults = $derived(getChartDefaults());

	let chartData = $derived({
		datasets: [
			{
				label: 'Message Count',
				data: transformToTimeSeriesData(data, (d) => d.count),
				backgroundColor: colors.singleSeries.primary
			}
		]
	});

	let chartOptions = $derived({
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				display: false
			},
			tooltip: getNumberTooltipConfig('Messages')
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				...defaults.scales.y,
				beginAtZero: true
			}
		}
	});

	run(() => {
		if (canvasElement && data && data.length > 0) {
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
	});

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
			<div>No messages found for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period</div>
		</div>
	{/if}
</div>
