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
	import { getTimeScaleConfig, getTooltipConfig, transformToTimeSeriesData, getChartColors, getChartDefaults } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale);

	export let data: Array<{
		date: string;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
	}> = [];
	export let loading: boolean = false;

	$: colors = getChartColors();
	$: defaults = getChartDefaults();

	$: chartData = {
		datasets: [
			{
				label: 'Input Tokens',
				data: transformToTimeSeriesData(data, (d) => d.input_tokens),
				backgroundColor: colors.stacked.input,
				stack: 'tokens'
			},
			{
				label: 'Output Tokens',
				data: transformToTimeSeriesData(data, (d) => d.output_tokens),
				backgroundColor: colors.stacked.output,
				stack: 'tokens'
			}
		]
	};

	$: chartOptions = {
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				...defaults.plugins.legend,
				display: true
			},
			tooltip: {
				...getTooltipConfig({
					formatLabel: (context: any) => {
						const value = context.parsed.y || 0;
						return `${context.dataset.label}: ${new Intl.NumberFormat().format(value)}`;
					},
					formatFooter: (tooltipItems: any[]) => {
						const total = tooltipItems.reduce((sum, item) => sum + (item.parsed.y || 0), 0);
						return `Total: ${new Intl.NumberFormat().format(total)}`;
					}
				}),
				mode: 'index',
				intersect: false
			}
		},
		scales: {
			x: {
				...getTimeScaleConfig(),
				stacked: true
			},
			y: {
				...defaults.scales.y,
				stacked: true,
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
		<div class="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
			<div>No token usage data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period</div>
		</div>
	{/if}
</div>
