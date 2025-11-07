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
	import { getTimeScaleConfig, getTooltipConfig } from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale);

	export let data: Array<{
		date: string;
		model_id: string;
		model_name: string;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
	}> = [];
	export let loading: boolean = false;

	// Group data by model and create datasets
	$: modelMap = (() => {
		const map = new Map<string, typeof data>();
		if (data && Array.isArray(data)) {
			data.forEach((d) => {
				if (d && d.model_id) {
					if (!map.has(d.model_id)) {
						map.set(d.model_id, []);
					}
					map.get(d.model_id)!.push(d);
				}
			});
		}
		return map;
	})();

	$: allDates = data && Array.isArray(data) ? [...new Set(data.map((d) => d.date).filter(Boolean))].sort() : [];

	// Color palette for multiple series
	const colors = [
		'rgb(59, 130, 246)',
		'rgb(16, 185, 129)',
		'rgb(239, 68, 68)',
		'rgb(245, 158, 11)',
		'rgb(139, 92, 246)',
		'rgb(6, 182, 212)',
		'rgb(251, 146, 60)',
		'rgb(236, 72, 153)',
		'rgb(34, 197, 94)',
		'rgb(249, 115, 22)'
	];

	$: datasets = (() => {
		if (!allDates.length || !modelMap.size) {
			return [];
		}
		return Array.from(modelMap.entries()).map(([modelId, modelData], index) => {
			const firstEntry = modelData[0];
			const color = colors[index % colors.length];
			return {
				label: firstEntry?.model_name || modelId,
				data: allDates.map((dateStr) => {
					const dayEntry = modelData.find((d) => d.date === dateStr);
					const tokens = dayEntry ? dayEntry.total_tokens : 0;
					return {
						x: dateStr,
						y: tokens
					};
				}),
				borderColor: color,
				backgroundColor: color.replace('rgb', 'rgba').replace(')', ', 0.1)'),
				fill: false,
				tension: 0.1
			};
		});
	})();

	$: chartData = {
		datasets
	};

	$: chartOptions = {
		responsive: true,
		maintainAspectRatio: false,
		interaction: {
			mode: 'index' as const,
			intersect: false
		},
		plugins: {
			legend: {
				display: true,
				position: 'right' as const
			},
			tooltip: {
				filter: (tooltipItem: any) => {
					// Only show tooltip items with nonzero values
					return (tooltipItem.parsed?.y || 0) > 0;
				},
				...getTooltipConfig({
					formatLabel: (context: any) => {
						const value = context.parsed.y || 0;
						return `${context.dataset.label}: ${new Intl.NumberFormat().format(value)} tokens`;
					}
				})
			}
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
	{:else if datasets.length > 0}
		<Line data={chartData} options={chartOptions} />
	{:else}
		<div class="flex items-center justify-center h-full text-gray-500">No data available</div>
	{/if}
</div>
