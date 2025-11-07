<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_NAME } from '$lib/stores';

	import {
		getModelMetrics,
		getDailyTokenUsage,
		getDailySpend,
		getModelDailyTokens,
		getCostPerMessageDaily,
		getMessageCountDaily,
		getModelPopularity,
		getCostPerTokenDaily,
		type MetricsParams
	} from '$lib/apis/metrics';

	import DateRangeSelector from '$lib/components/workspace/Metrics/DateRangeSelector.svelte';
	import ModelTypeFilter from '$lib/components/workspace/Metrics/ModelTypeFilter.svelte';
	import ModelUsageTable from '$lib/components/workspace/Metrics/ModelUsageTable.svelte';
	import DailyTokenChart from '$lib/components/workspace/Metrics/DailyTokenChart.svelte';
	import DailySpendChart from '$lib/components/workspace/Metrics/DailySpendChart.svelte';
	import ModelDailyTokensChart from '$lib/components/workspace/Metrics/ModelDailyTokensChart.svelte';
	import CostPerMessageChart from '$lib/components/workspace/Metrics/CostPerMessageChart.svelte';
	import MessageCountChart from '$lib/components/workspace/Metrics/MessageCountChart.svelte';
	import ModelPopularityChart from '$lib/components/workspace/Metrics/ModelPopularityChart.svelte';
	import CostPerTokenChart from '$lib/components/workspace/Metrics/CostPerTokenChart.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');

	let loading = true;
	let startDate = '';
	let endDate = '';
	let modelType: 'local' | 'external' | 'both' = 'both';

	// Data stores
	let modelMetrics: any[] = [];
	let dailyTokenUsage: any[] = [];
	let dailySpend: any[] = [];
	let modelDailyTokens: any[] = [];
	let costPerMessageDaily: any[] = [];
	let messageCountDaily: any[] = [];
	let modelPopularity: any[] = [];
	let costPerTokenDaily: any[] = [];

	const fetchAllMetrics = async () => {
		loading = true;
		const token = localStorage.token;
		const params: MetricsParams = {
			model_type: modelType,
			start_date: startDate,
			end_date: endDate
		};

		try {
			const [
				models,
				tokens,
				spend,
				modelTokens,
				costPerMessage,
				messageCount,
				popularity,
				costPerToken
			] = await Promise.all([
				getModelMetrics(token, { ...params, limit: 15 }),
				getDailyTokenUsage(token, params),
				getDailySpend(token, params),
				getModelDailyTokens(token, { ...params, limit: 10 }),
				getCostPerMessageDaily(token, params),
				getMessageCountDaily(token, params),
				getModelPopularity(token, { ...params, limit: 15 }),
				getCostPerTokenDaily(token, params)
			]);

			modelMetrics = models || [];
			dailyTokenUsage = tokens || [];
			dailySpend = spend || [];
			modelDailyTokens = modelTokens || [];
			costPerMessageDaily = costPerMessage || [];
			messageCountDaily = messageCount || [];
			modelPopularity = popularity || [];
			costPerTokenDaily = costPerToken || [];
		} catch (error) {
			console.error('Error fetching metrics:', error);
			toast.error($i18n.t('Failed to load metrics'));
		} finally {
			loading = false;
		}
	};

	const handleDateRangeChange = (event: CustomEvent<{ startDate: string; endDate: string }>) => {
		startDate = event.detail.startDate;
		endDate = event.detail.endDate;
		fetchAllMetrics();
	};

	const handleModelTypeChange = (event: CustomEvent<'local' | 'external' | 'both'>) => {
		modelType = event.detail;
		fetchAllMetrics();
	};

	onMount(() => {
		// Initialize with default date range (last 30 days)
		const end = new Date();
		const start = new Date();
		start.setDate(start.getDate() - 30);
		startDate = start.toISOString().split('T')[0];
		endDate = end.toISOString().split('T')[0];
		fetchAllMetrics();
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Metrics')} | {$WEBUI_NAME}
	</title>
</svelte:head>

<div class="flex flex-col gap-4 my-1.5">
	<div class="flex justify-between items-center">
		<div class="flex md:self-center text-xl font-medium px-0.5 items-center">
			{$i18n.t('Metrics')}
		</div>
	</div>

	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-center gap-4">
			<DateRangeSelector
				bind:startDate
				bind:endDate
				on:change={handleDateRangeChange}
			/>
			<ModelTypeFilter bind:modelType on:change={handleModelTypeChange} />
		</div>

		{#if loading}
			<div class="w-full h-64 flex justify-center items-center">
				<Spinner />
			</div>
		{:else}
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
				<!-- Model Usage Table -->
				<div class="lg:col-span-2">
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Model Usage')}</h3>
					<ModelUsageTable models={modelMetrics} />
				</div>

				<!-- Daily Token Usage -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Daily Token Usage')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<DailyTokenChart data={dailyTokenUsage} />
					</div>
				</div>

				<!-- Daily Spend -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Daily Spend')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<DailySpendChart data={dailySpend} />
					</div>
				</div>

				<!-- Tokens per Model per Day -->
				<div class="lg:col-span-2">
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Tokens per Model per Day')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<ModelDailyTokensChart data={modelDailyTokens} />
					</div>
				</div>

				<!-- Average Cost per Message -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Average Cost per Message')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<CostPerMessageChart data={costPerMessageDaily} />
					</div>
				</div>

				<!-- Message Count -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Message Count per Day')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<MessageCountChart data={messageCountDaily} />
					</div>
				</div>

				<!-- Model Popularity -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Model Popularity')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<ModelPopularityChart data={modelPopularity} />
					</div>
				</div>

				<!-- Cost per Token -->
				<div>
					<h3 class="text-lg font-semibold mb-2">{$i18n.t('Cost per Token Trend')}</h3>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
						<CostPerTokenChart data={costPerTokenDaily} />
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>

