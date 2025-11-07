<script lang="ts">
	import { Bar } from 'svelte-chartjs';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		BarElement,
		CategoryScale,
		LinearScale
	} from 'chart.js';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

	export let data: Array<{
		date: string;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
	}> = [];

	$: chartData = {
		labels: data && Array.isArray(data) ? data.map((d) => d.date) : [],
		datasets: [
			{
				label: 'Input Tokens',
				data: data && Array.isArray(data) ? data.map((d) => d.input_tokens || 0) : [],
				backgroundColor: 'rgb(59, 130, 246)',
				stack: 'tokens'
			},
			{
				label: 'Output Tokens',
				data: data && Array.isArray(data) ? data.map((d) => d.output_tokens || 0) : [],
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
				callbacks: {
					label: (context: any) => {
						const value = context.parsed.y || 0;
						return `${context.dataset.label}: ${new Intl.NumberFormat().format(value)}`;
					}
				}
			}
		},
		scales: {
			x: {
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
	{#if data && data.length > 0}
		<Bar data={chartData} options={chartOptions} />
	{:else}
		<div class="flex items-center justify-center h-full text-gray-500">No data available</div>
	{/if}
</div>
