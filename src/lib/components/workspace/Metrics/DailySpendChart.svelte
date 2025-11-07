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

	export let data: Array<{ date: string; cost: number }> = [];

	$: chartData = {
		labels: data && Array.isArray(data) ? data.map((d) => d.date) : [],
		datasets: [
			{
				label: 'Cost',
				data: data && Array.isArray(data) ? data.map((d) => d.cost || 0) : [],
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
			tooltip: {
				callbacks: {
					label: (context: any) => {
						const value = context.parsed.y || 0;
						return `Cost: ${new Intl.NumberFormat('en-US', {
							style: 'currency',
							currency: 'USD',
							minimumFractionDigits: 8,
							maximumFractionDigits: 8
						}).format(value)}`;
					}
				}
			}
		},
		scales: {
			y: {
				beginAtZero: true,
				ticks: {
					callback: (value: any) => {
						return new Intl.NumberFormat('en-US', {
							style: 'currency',
							currency: 'USD',
							minimumFractionDigits: 8,
							maximumFractionDigits: 8
						}).format(value as number);
					}
				}
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
