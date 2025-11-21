<script lang="ts">
	import { run } from 'svelte/legacy';

	import { onMount, onDestroy } from 'svelte';
	import {
		Chart as ChartJS,
		Title,
		Tooltip,
		Legend,
		LineElement,
		LineController,
		CategoryScale,
		LinearScale,
		PointElement,
		TimeScale,
		type ChartConfiguration
	} from 'chart.js';
	import 'chartjs-adapter-date-fns';
	import {
		getTimeScaleConfig,
		getTooltipConfig,
		getCurrencyYTicks,
		getChartColors,
		getChartDefaults
	} from '$lib/utils/charts';
	import { formatSmartCurrency } from '$lib/utils/currency';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Switch from '$lib/components/common/Switch.svelte';

	ChartJS.register(
		Title,
		Tooltip,
		Legend,
		LineElement,
		LineController,
		CategoryScale,
		LinearScale,
		PointElement,
		TimeScale
	);

	let canvasElement: HTMLCanvasElement = $state();
	let chartInstance: ChartJS<'line'> | null = $state(null);

	interface Props {
		tokensData?: Array<{
		date: string;
		model_id: string;
		model_name: string;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
	}>;
		costData?: Array<{
		date: string;
		model_id: string;
		model_name: string;
		cost: number;
	}>;
		loading?: boolean;
		showCost?: boolean;
	}

	let {
		tokensData = [],
		costData = [],
		loading = false,
		showCost = false
	}: Props = $props();

	let chartColors = $derived(getChartColors());
	let defaults = $derived(getChartDefaults());
	let currentData = $derived(showCost ? costData : tokensData);

	// Group data by model and create datasets
	let modelMap = $derived((() => {
		const map = new Map<string, typeof currentData>();
		if (currentData && Array.isArray(currentData)) {
			currentData.forEach((d) => {
				if (d && d.model_id) {
					if (!map.has(d.model_id)) {
						map.set(d.model_id, []);
					}
					map.get(d.model_id)!.push(d);
				}
			});
		}
		return map;
	})());

	let allDates =
		$derived(currentData && Array.isArray(currentData)
			? [...new Set(currentData.map((d) => d.date).filter(Boolean))].sort()
			: []);

	let datasets = $derived((() => {
		if (!allDates.length || !modelMap.size) {
			return [];
		}
		return Array.from(modelMap.entries()).map(([modelId, modelData], index) => {
			const firstEntry = modelData[0];
			const color = chartColors.multiSeries[index % chartColors.multiSeries.length];
			// Use the color as-is for borderColor
			const borderColor = color;
			// Use a more transparent version for background (reduce opacity)
			const backgroundColor = color.replace(/0\.\d+\)$/, '0.08)');
			return {
				label: firstEntry?.model_name || modelId,
				data: allDates.map((dateStr) => {
					const dayEntry = modelData.find((d) => d.date === dateStr);
					if (showCost) {
						const cost = (dayEntry as any)?.cost || 0;
						return {
							x: dateStr,
							y: cost
						};
					} else {
						const tokens = (dayEntry as any)?.total_tokens || 0;
						return {
							x: dateStr,
							y: tokens
						};
					}
				}),
				borderColor: borderColor,
				backgroundColor: backgroundColor,
				fill: false,
				tension: 0.2,
				pointRadius: 2.5,
				pointHoverRadius: 4,
				pointBackgroundColor: borderColor,
				pointBorderColor: borderColor,
				pointBorderWidth: 1.5,
				borderWidth: 2
			};
		});
	})());

	let chartData = $derived({
		datasets
	});

	let chartOptions = $derived({
		responsive: true,
		maintainAspectRatio: false,
		interaction: {
			mode: 'index' as const,
			intersect: false
		},
		plugins: {
			legend: {
				...defaults.plugins.legend,
				display: true,
				position: 'right' as const
			},
			tooltip: showCost
				? {
						...getTooltipConfig({
							formatLabel: (context: any) => {
								const value = context.parsed.y || 0;
								return `${context.dataset.label}: ${formatSmartCurrency(value)}`;
							}
						}),
						filter: (tooltipItem: any) => {
							// Only show tooltip items with nonzero values
							return (tooltipItem.parsed?.y || 0) > 0;
						}
					}
				: {
						...getTooltipConfig({
							formatLabel: (context: any) => {
								const value = context.parsed.y || 0;
								return `${context.dataset.label}: ${new Intl.NumberFormat().format(value)} tokens`;
							}
						}),
						filter: (tooltipItem: any) => {
							// Only show tooltip items with nonzero values
							return (tooltipItem.parsed?.y || 0) > 0;
						}
					}
		},
		scales: {
			x: getTimeScaleConfig(),
			y: {
				...defaults.scales.y,
				beginAtZero: true,
				...(showCost ? { ticks: getCurrencyYTicks() } : {})
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
				const config: ChartConfiguration<'line'> = {
					type: 'line',
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
			<div>No model {showCost ? 'cost' : 'token usage'} data for this date range</div>
			<div class="text-xs mt-1 opacity-70">Try selecting a different time period or model type</div>
		</div>
	{/if}
</div>
