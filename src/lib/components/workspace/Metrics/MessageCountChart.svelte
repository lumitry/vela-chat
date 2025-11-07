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
	import { getTimeScaleConfig, getNumberTooltipConfig, transformToTimeSeriesData } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale);

	export let data: Array<{ date: string; count: number }> = [];
	export let loading: boolean = false;

	$: chartData = {
		datasets: [
			{
				label: 'Message Count',
				data: transformToTimeSeriesData(data, (d) => d.count),
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
			tooltip: getNumberTooltipConfig('Messages')
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				beginAtZero: true
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
		<div class="flex items-center justify-center h-full text-gray-500">No data available</div>
	{/if}
</div>
