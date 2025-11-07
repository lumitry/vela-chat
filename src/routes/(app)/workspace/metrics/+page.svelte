<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_NAME, metricsCache, models } from '$lib/stores';

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
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Info from '$lib/components/icons/Info.svelte';

	const i18n = getContext('i18n');

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

	// Loading states for each component
	let loadingModels = false;
	let loadingTokens = false;
	let loadingSpend = false;
	let loadingModelTokens = false;
	let loadingCostPerMessage = false;
	let loadingMessageCount = false;
	let loadingPopularity = false;
	let loadingCostPerToken = false;

	// Generate cache key from params
	const getCacheKey = (endpoint: string, params: MetricsParams): string => {
		const keyParts = [
			endpoint,
			params.model_type || 'both',
			params.start_date || '',
			params.end_date || '',
			params.limit?.toString() || ''
		];
		return keyParts.join('|');
	};

	// Fetch a single metric endpoint
	const fetchMetric = async <T,>(
		endpoint: string,
		fetcher: (token: string, params: MetricsParams) => Promise<T>,
		params: MetricsParams,
		loadingSetter: (value: boolean) => void,
		dataSetter: (value: T) => void
	) => {
		const token = localStorage.token;
		const cacheKey = getCacheKey(endpoint, params);
		const cache = $metricsCache;
		const cached = cache.get(cacheKey);

		if (cached) {
			dataSetter(cached as T);
			loadingSetter(false);
			return;
		}

		loadingSetter(true);
		try {
			const data = await fetcher(token, params);
			dataSetter(data);
			const newCache = new Map(cache);
			newCache.set(cacheKey, data);
			metricsCache.set(newCache);
		} catch (error) {
			console.error(`Error fetching ${endpoint}:`, error);
			toast.error($i18n.t('Failed to load metrics'));
		} finally {
			loadingSetter(false);
		}
	};

	const fetchAllMetrics = async () => {
		const params: MetricsParams = {
			model_type: modelType,
			start_date: startDate,
			end_date: endDate
		};

		// Fetch all metrics independently
		fetchMetric(
			'models',
			getModelMetrics,
			{ ...params, limit: 15 },
			(v) => (loadingModels = v),
			(v) => (modelMetrics = v)
		);
		fetchMetric(
			'tokens/daily',
			getDailyTokenUsage,
			params,
			(v) => (loadingTokens = v),
			(v) => (dailyTokenUsage = v)
		);
		fetchMetric(
			'spend/daily',
			getDailySpend,
			params,
			(v) => (loadingSpend = v),
			(v) => (dailySpend = v)
		);
		fetchMetric(
			'tokens/model/daily',
			getModelDailyTokens,
			{ ...params, limit: 10 },
			(v) => (loadingModelTokens = v),
			(v) => (modelDailyTokens = v)
		);
		fetchMetric(
			'cost/message/daily',
			getCostPerMessageDaily,
			params,
			(v) => (loadingCostPerMessage = v),
			(v) => (costPerMessageDaily = v)
		);
		fetchMetric(
			'messages/daily',
			getMessageCountDaily,
			params,
			(v) => (loadingMessageCount = v),
			(v) => (messageCountDaily = v)
		);
		fetchMetric(
			'models/popularity',
			getModelPopularity,
			{ ...params, limit: 15 },
			(v) => (loadingPopularity = v),
			(v) => (modelPopularity = v)
		);
		fetchMetric(
			'cost/token/daily',
			getCostPerTokenDaily,
			params,
			(v) => (loadingCostPerToken = v),
			(v) => (costPerTokenDaily = v)
		);
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
		<div class="flex flex-wrap items-start gap-6">
			<DateRangeSelector bind:startDate bind:endDate on:change={handleDateRangeChange} />
			<div class="ml-auto">
				<ModelTypeFilter bind:modelType on:change={handleModelTypeChange} />
			</div>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<!-- Model Usage Table -->
			<div class="lg:col-span-2">
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Model Usage')}</h3>
				<ModelUsageTable models={modelMetrics} loading={loadingModels} />
			</div>

			<!-- Daily Token Usage -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Daily Token Usage')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<DailyTokenChart data={dailyTokenUsage} loading={loadingTokens} />
				</div>
			</div>

			<!-- Daily Spend -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Daily Spend')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<DailySpendChart data={dailySpend} loading={loadingSpend} />
				</div>
			</div>

			<!-- Tokens per Model per Day -->
			<div class="lg:col-span-2">
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Tokens per Model per Day')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<ModelDailyTokensChart data={modelDailyTokens} loading={loadingModelTokens} />
				</div>
			</div>

			<!-- Average Cost per Message -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Average Cost per Message')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<CostPerMessageChart data={costPerMessageDaily} loading={loadingCostPerMessage} />
				</div>
			</div>

			<!-- Message Count -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Message Count per Day')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<MessageCountChart data={messageCountDaily} loading={loadingMessageCount} />
				</div>
			</div>

			<!-- Model Popularity -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Model Popularity')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<ModelPopularityChart data={modelPopularity} loading={loadingPopularity} />
				</div>
			</div>

			<!-- Cost per Token -->
			<div>
				<div class="flex items-center gap-2 mb-2">
					<h3 class="text-lg font-semibold">{$i18n.t('Cost per 1M Tokens Trend')}</h3>
					<Tooltip
						content="This metric calculates cost per 1M total tokens (input + output combined). Note that actual LLM providers charge differently for input and output tokens. Currently, this calculation only includes messages with cost data (local models are excluded)."
						placement="top"
					>
						<Info className="w-4 h-4 text-gray-500 dark:text-gray-400 cursor-help" />
					</Tooltip>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<CostPerTokenChart data={costPerTokenDaily} loading={loadingCostPerToken} />
				</div>
			</div>
		</div>

		<!-- Disclaimer -->
		<div
			class="mt-6 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm text-gray-600 dark:text-gray-400"
		>
			<p>
				<strong>Note:</strong> For cloned chats and edited assistant messages created via "save as
				copy", cost is <em>not</em> included (the cost column is left null) but token usage
				<em>is</em> included in the metrics.
			</p>
		</div>
	</div>
</div>
