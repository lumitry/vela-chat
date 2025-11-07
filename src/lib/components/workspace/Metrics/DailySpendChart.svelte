<script lang="ts">
	import { Bar } from 'svelte-chartjs';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		BarElement,
		CategoryScale,
		LinearScale,
		TimeScale
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import { formatSmartCurrency } from '$lib/utils/currency';
	import { getTimeScaleConfig, getCurrencyTooltipConfig, getCurrencyYTicks, transformToTimeSeriesData } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale);

	export let data: Array<{ date: string; cost: number }> = [];
	export let loading: boolean = false;

	$: chartData = {
		datasets: [
			{
				label: 'Cost',
				data: transformToTimeSeriesData(data, (d) => d.cost),
				backgroundColor: 'rgb(59, 130, 246)'
			}
		]
	};

	$: chartOptions = {
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				display: false
			},
			tooltip: getCurrencyTooltipConfig('Cost')
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				beginAtZero: true,
				ticks: getCurrencyYTicks()
			}
		}
	};
</script>

<div class="w-full h-64">
	{#if loading}
		<div class="flex items-center justify-center h-full">
			<Spinner />
		</div>
	{:else if data && data.length > 0}
		<Bar data={chartData} options={chartOptions} />
	{:else}
		<div class="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
			<div>No spending data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period or model type</div>
		</div>
	{/if}
</div>
