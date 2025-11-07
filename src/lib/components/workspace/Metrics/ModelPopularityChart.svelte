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
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

	export let data: Array<{
		model_id: string;
		model_name: string;
		chat_count: number;
		message_count: number;
	}> = [];
	export let loading: boolean = false;

	$: chartData = {
		labels: data && Array.isArray(data) ? data.map((d) => d.model_name || d.model_id) : [],
		datasets: [
			{
				label: 'Chat Count',
				data: data && Array.isArray(data) ? data.map((d) => d.chat_count || 0) : [],
				backgroundColor: 'rgb(59, 130, 246)'
			}
		]
	};

	$: chartOptions = {
		indexAxis: 'y',
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: {
				display: false
			},
			tooltip: {
				callbacks: {
					label: (context: any) => {
						const value = context.parsed.x || 0;
						return `Chats: ${new Intl.NumberFormat().format(value)}`;
					}
				}
			}
		},
		scales: {
			x: {
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
