<script lang="ts">
	import { Line } from 'svelte-chartjs';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		LineElement,
		CategoryScale,
		LinearScale,
		PointElement,
		TimeScale
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import { formatSmartCurrency } from '$lib/utils/currency';
	import { getTimeScaleConfig, getCurrencyTooltipConfig, getCurrencyYTicks, transformToTimeSeriesData } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale);

	export let data: Array<{
		date: string;
		avg_cost_per_token: number;
		total_tokens: number;
		total_cost: number;
	}> = [];
	export let loading: boolean = false;

	$: chartData = {
		datasets: [
			{
				label: 'Cost per 1M Tokens',
				data: transformToTimeSeriesData(data, (d) => d.avg_cost_per_token),
				borderColor: 'rgb(59, 130, 246)',
				backgroundColor: 'rgba(59, 130, 246, 0.1)',
				fill: false,
				tension: 0.1
			}
		]
	};

	$: chartOptions = {
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				display: true
			},
			tooltip: getCurrencyTooltipConfig('Cost per 1M Tokens')
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
		<Line data={chartData} options={chartOptions} />
	{:else}
		<div class="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
			<div>No cost per token data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Cost data is only available for external models</div>
		</div>
	{/if}
</div>
