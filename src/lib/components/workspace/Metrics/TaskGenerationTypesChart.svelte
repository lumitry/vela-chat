<script lang="ts">
	import { run } from 'svelte/legacy';

	import { onMount, onDestroy } from 'svelte';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		BarElement,
		BarController,
		CategoryScale,
		LinearScale,
		TimeScale,
		type ChartConfiguration
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import {
		getTimeScaleConfig,
		getTooltipConfig,
		getChartColors,
		getChartDefaults
	} from '$lib/utils/charts';
	import Spinner from '$lib/components/common/Spinner.svelte';

	ChartJS.register(Title, Tooltip, Legend, BarElement, BarController, CategoryScale, LinearScale, TimeScale);

	let canvasElement: HTMLCanvasElement = $state();
	let chartInstance: ChartJS<'bar'> | null = $state(null);

	interface Props {
		data?: Array<{
		date: string;
		task_type: string;
		task_count: number;
	}>;
		loading?: boolean;
	}

	let { data = [], loading = false }: Props = $props();

	let colors = $derived(getChartColors());
	let defaults = $derived(getChartDefaults());

	// Group data by task type and create datasets
	let taskTypeMap = $derived((() => {
		const map = new Map<string, typeof data>();
		if (data && Array.isArray(data)) {
			data.forEach((d) => {
				if (d && d.task_type) {
					if (!map.has(d.task_type)) {
						map.set(d.task_type, []);
					}
					map.get(d.task_type)!.push(d);
				}
			});
		}
		return map;
	})());

	let allDates =
		$derived(data && Array.isArray(data) ? [...new Set(data.map((d) => d.date).filter(Boolean))].sort() : []);

	// Format task type names for display
	const formatTaskType = (taskType: string): string => {
		// Special handling for MoA response generation
		if (taskType === 'moa_response_generation') {
			return 'Multi-Response Merge';
		}

		return taskType
			.split('_')
			.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
			.join(' ');
	};

	let datasets = $derived((() => {
		if (!allDates.length || !taskTypeMap.size) {
			return [];
		}
		return Array.from(taskTypeMap.entries()).map(([taskType, taskData], index) => {
			const color = colors.multiSeries[index % colors.multiSeries.length];
			return {
				label: formatTaskType(taskType),
				data: allDates.map((dateStr) => {
					const dayEntry = taskData.find((d) => d.date === dateStr);
					const count = dayEntry ? dayEntry.task_count : 0;
					return {
						x: dateStr,
						y: count
					};
				}),
				backgroundColor: color,
				stack: 'tasks'
			};
		});
	})());

	let chartData = $derived({
		datasets
	} as any);

	let chartOptions = $derived({
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
				mode: 'index' as const,
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
	});

	run(() => {
		if (canvasElement && datasets.length > 0) {
			if (chartInstance) {
				chartInstance.data = chartData;
				chartInstance.options = chartOptions;
				chartInstance.update();
			} else {
				const config: ChartConfiguration<'bar'> = {
					type: 'bar',
					data: chartData,
					options: chartOptions
				};
				chartInstance = new ChartJS(canvasElement, config);
			}
		} else if (chartInstance) {
			chartInstance.destroy();
			chartInstance = null;
		}
	});

	onDestroy(() => {
		if (chartInstance) {
			chartInstance.destroy();
			chartInstance = null;
		}
	});
</script>

<div class="w-full h-64">
	{#if loading}
		<div class="flex items-center justify-center h-full">
			<Spinner />
		</div>
	{:else if datasets.length > 0}
		<canvas bind:this={canvasElement}></canvas>
	{:else}
		<div class="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
			<div>No task generation data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period or model type</div>
		</div>
	{/if}
</div>
