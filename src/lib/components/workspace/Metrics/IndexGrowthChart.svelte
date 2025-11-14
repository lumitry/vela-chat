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
	import { getTimeScaleConfig, getTooltipConfig, transformToTimeSeriesData, getChartColors, getChartDefaults } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale);

	export let data: Array<{ date: string; vector_count: number }> = [];
	export let loading: boolean = false;

	$: colors = getChartColors();
	$: defaults = getChartDefaults();

	$: chartData = {
		datasets: [
			{
				label: 'Vector Count',
				data: transformToTimeSeriesData(data, (d) => d.vector_count),
				borderColor: colors.singleSeries.primary,
				backgroundColor: colors.singleSeries.primaryBg,
				fill: true,
				tension: 0.2,
				pointRadius: 3,
				pointHoverRadius: 5,
				pointBackgroundColor: colors.singleSeries.primary,
				pointBorderColor: colors.singleSeries.primary,
				pointBorderWidth: 2
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
			tooltip: getTooltipConfig({
				formatLabel: (context: any) => {
					const value = context.parsed.y || 0;
					return `Vectors: ${new Intl.NumberFormat().format(value)}`;
				}
			})
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				...defaults.scales.y,
				beginAtZero: true,
				ticks: {
					callback: function(value: any) {
						return new Intl.NumberFormat().format(value);
					}
				}
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
			<div>No index growth data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period</div>
		</div>
	{/if}
</div>

