<script lang="ts">
	import { run } from 'svelte/legacy';

	import { onMount, onDestroy } from 'svelte';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		LineElement,
		LineController,
		CategoryScale,
		LinearScale,
		PointElement,
		TimeScale,
		type ChartConfiguration
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import { formatSmartCurrency } from '$lib/utils/currency';
	import { getTimeScaleConfig, getCurrencyTooltipConfig, getCurrencyYTicks, transformToTimeSeriesData, getChartColors, getChartDefaults } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, LineElement, LineController, CategoryScale, LinearScale, PointElement, TimeScale);

	let canvasElement: HTMLCanvasElement = $state();
	let chartInstance: ChartJS<'line'> | null = $state(null);

	interface Props {
		data?: Array<{
		date: string;
		avg_cost: number;
		message_count: number;
		total_cost: number;
	}>;
		loading?: boolean;
	}

	let { data = [], loading = false }: Props = $props();

	let colors = $derived(getChartColors());
	let defaults = $derived(getChartDefaults());

	let chartData = $derived({
		datasets: [
			{
				label: 'Average Cost per Message',
				data: transformToTimeSeriesData(data, (d) => d.avg_cost),
				borderColor: colors.singleSeries.primary,
				backgroundColor: colors.singleSeries.primaryBg,
				fill: false,
				tension: 0.2,
				pointRadius: 3,
				pointHoverRadius: 5,
				pointBackgroundColor: colors.singleSeries.primary,
				pointBorderColor: colors.singleSeries.primary,
				pointBorderWidth: 2
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
			tooltip: getCurrencyTooltipConfig('Avg Cost')
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				...defaults.scales.y,
				beginAtZero: true,
				ticks: getCurrencyYTicks()
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
				const config: ChartConfiguration<'line'> = {
					type: 'line',
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
			<div>No cost data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Cost data is only available for external models</div>
		</div>
	{/if}
</div>
