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
		PointElement
	} from 'chart.js';

	ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement);

	export let data: Array<{
		date: string;
		avg_cost_per_token: number;
		total_tokens: number;
		total_cost: number;
	}> = [];

	$: chartData = {
		labels: data && Array.isArray(data) ? data.map((d) => d.date) : [],
		datasets: [
			{
				label: 'Cost per Token',
				data: data && Array.isArray(data) ? data.map((d) => d.avg_cost_per_token || 0) : [],
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
			tooltip: {
				callbacks: {
					label: (context: any) => {
						const value = context.parsed.y || 0;
						return `Cost per Token: ${new Intl.NumberFormat('en-US', {
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
		<Line data={chartData} options={chartOptions} />
	{:else}
		<div class="flex items-center justify-center h-full text-gray-500">No data available</div>
	{/if}
</div>
