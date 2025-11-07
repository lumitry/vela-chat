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
	import { getTimeScaleConfig, getTooltipConfig, transformToTimeSeriesData } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale);

	export let data: Array<{
		date: string;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
	}> = [];
	export let loading: boolean = false;

	$: chartData = {
		datasets: [
			{
				label: 'Input Tokens',
				data: transformToTimeSeriesData(data, (d) => d.input_tokens),
				backgroundColor: 'rgb(59, 130, 246)',
				stack: 'tokens'
			},
			{
				label: 'Output Tokens',
				data: transformToTimeSeriesData(data, (d) => d.output_tokens),
				backgroundColor: 'rgb(16, 185, 129)',
				stack: 'tokens'
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
			tooltip: {
				mode: 'index',
				intersect: false,
				...getTooltipConfig({
					formatLabel: (context: any) => {
						const value = context.parsed.y || 0;
						return `${context.dataset.label}: ${new Intl.NumberFormat().format(value)}`;
					},
					formatFooter: (tooltipItems: any[]) => {
						const total = tooltipItems.reduce((sum, item) => sum + (item.parsed.y || 0), 0);
						return `Total: ${new Intl.NumberFormat().format(total)}`;
					}
				})
			}
		},
		scales: {
			x: {
				...getTimeScaleConfig(),
				stacked: true
			},
			y: {
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
		<div class="flex items-center justify-center h-full text-gray-500">No data available</div>
	{/if}
</div>
