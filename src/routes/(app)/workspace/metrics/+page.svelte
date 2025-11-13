<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { WEBUI_NAME, metricsCache, models } from '$lib/stores';

	import {
		getModelMetrics,
		getDailyTokenUsage,
		getDailySpend,
		getModelDailyTokens,
		getModelDailyCost,
		getCostPerMessageDaily,
		getMessageCountDaily,
		getModelPopularity,
		getCostPerTokenDaily,
		getTaskGenerationTypesDaily,
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
	import TaskGenerationTypesChart from '$lib/components/workspace/Metrics/TaskGenerationTypesChart.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import { formatSmartCurrency } from '$lib/utils/currency';

	const i18n = getContext('i18n');

	// Calculate summary statistics
	$: totalSpend = dailySpend.reduce((sum, d) => sum + (d.cost || 0), 0);
	$: totalInputTokens = dailyTokenUsage.reduce((sum, d) => sum + (d.input_tokens || 0), 0);
	$: totalOutputTokens = dailyTokenUsage.reduce((sum, d) => sum + (d.output_tokens || 0), 0);
	$: totalTokens = totalInputTokens + totalOutputTokens;
	$: totalMessages = messageCountDaily.reduce((sum, d) => sum + (d.count || 0), 0);
	$: avgCostPerMessage = totalMessages > 0 ? totalSpend / totalMessages : 0;
	$: uniqueModels = new Set(modelMetrics.map((m) => m.model_id)).size;

	// Export functions
	const exportToCSV = (data: any[], filename: string, headers: string[]) => {
		if (!data || data.length === 0) {
			toast.error($i18n.t('No data to export'));
			return;
		}

		const csvRows = [headers.join(',')];
		for (const row of data) {
			const values = headers.map((header) => {
				const value = row[header] ?? '';
				// Escape commas and quotes in CSV
				if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
					return `"${value.replace(/"/g, '""')}"`;
				}
				return value;
			});
			csvRows.push(values.join(','));
		}

		const csvContent = csvRows.join('\n');
		const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = filename;
		link.click();
		URL.revokeObjectURL(url);
	};

	const exportModelUsage = () => {
		exportToCSV(modelMetrics, `model-usage-${startDate}-to-${endDate}.csv`, [
			'model_name',
			'spend',
			'input_tokens',
			'output_tokens',
			'total_tokens',
			'message_count'
		]);
	};

	const exportDailyData = (data: any[], filename: string) => {
		if (!data || data.length === 0) {
			toast.error($i18n.t('No data to export'));
			return;
		}
		const headers = Object.keys(data[0]);
		exportToCSV(data, filename, headers);
	};

	let startDate = '';
	let endDate = '';
	let modelType: 'local' | 'external' | 'both' = 'both';
	let showCost = false;

	// Data stores
	let modelMetrics: any[] = [];
	let dailyTokenUsage: any[] = [];
	let dailySpend: any[] = [];
	let modelDailyTokens: any[] = [];
	let modelDailyCost: any[] = [];
	let costPerMessageDaily: any[] = [];
	let messageCountDaily: any[] = [];
	let modelPopularity: any[] = [];
	let costPerTokenDaily: any[] = [];
	let taskGenerationTypesDaily: any[] = [];

	// Loading states for each component
	let loadingModels = false;
	let loadingTokens = false;
	let loadingSpend = false;
	let loadingModelTokens = false;
	let loadingModelCost = false;
	let loadingCostPerMessage = false;
	let loadingMessageCount = false;
	let loadingPopularity = false;
	let loadingCostPerToken = false;
	let loadingTaskGenerationTypes = false;

	// Track request IDs to prevent race conditions
	let currentRequestId = 0;

	// Track if we're updating URL to avoid reactive loop
	let isUpdatingURL = false;
	let isInitialized = false;

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

	// Fetch a single metric endpoint with race condition protection
	const fetchMetric = async <T,>(
		endpoint: string,
		fetcher: (token: string, params: MetricsParams) => Promise<T>,
		params: MetricsParams,
		loadingSetter: (value: boolean) => void,
		dataSetter: (value: T) => void,
		requestId: number
	) => {
		const token = localStorage.token;
		const cacheKey = getCacheKey(endpoint, params);
		const cache = $metricsCache;
		const cached = cache.get(cacheKey);

		if (cached) {
			// Only set data if this is still the current request
			if (requestId === currentRequestId) {
				dataSetter(cached as T);
				loadingSetter(false);
			}
			return;
		}

		loadingSetter(true);
		try {
			const data = await fetcher(token, params);
			// Only set data if this is still the current request (prevents stale data)
			if (requestId === currentRequestId) {
				dataSetter(data);
				const newCache = new Map(cache);
				newCache.set(cacheKey, data);
				metricsCache.set(newCache);
			}
		} catch (error) {
			// Only show error if this is still the current request
			if (requestId === currentRequestId) {
				console.error(`Error fetching ${endpoint}:`, error);
				toast.error($i18n.t('Failed to load metrics'));
			}
		} finally {
			// Only update loading state if this is still the current request
			if (requestId === currentRequestId) {
				loadingSetter(false);
			}
		}
	};

	const fetchAllMetrics = async () => {
		// Validate dates before fetching
		if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
			toast.error($i18n.t('Start date must be before end date'));
			return;
		}

		// Increment request ID to invalidate any in-flight requests
		currentRequestId++;
		const requestId = currentRequestId;

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
			(v) => (modelMetrics = v),
			requestId
		);
		fetchMetric(
			'tokens/daily',
			getDailyTokenUsage,
			params,
			(v) => (loadingTokens = v),
			(v) => (dailyTokenUsage = v),
			requestId
		);
		fetchMetric(
			'spend/daily',
			getDailySpend,
			params,
			(v) => (loadingSpend = v),
			(v) => (dailySpend = v),
			requestId
		);
		fetchMetric(
			'tokens/model/daily',
			getModelDailyTokens,
			{ ...params, limit: 10 },
			(v) => (loadingModelTokens = v),
			(v) => (modelDailyTokens = v),
			requestId
		);
		fetchMetric(
			'cost/model/daily',
			getModelDailyCost,
			{ ...params, limit: 10 },
			(v) => (loadingModelCost = v),
			(v) => (modelDailyCost = v),
			requestId
		);
		fetchMetric(
			'cost/message/daily',
			getCostPerMessageDaily,
			params,
			(v) => (loadingCostPerMessage = v),
			(v) => (costPerMessageDaily = v),
			requestId
		);
		fetchMetric(
			'messages/daily',
			getMessageCountDaily,
			params,
			(v) => (loadingMessageCount = v),
			(v) => (messageCountDaily = v),
			requestId
		);
		fetchMetric(
			'models/popularity',
			getModelPopularity,
			{ ...params, limit: 15 },
			(v) => (loadingPopularity = v),
			(v) => (modelPopularity = v),
			requestId
		);
		fetchMetric(
			'cost/token/daily',
			getCostPerTokenDaily,
			params,
			(v) => (loadingCostPerToken = v),
			(v) => (costPerTokenDaily = v),
			requestId
		);
		fetchMetric(
			'tasks/types/daily',
			getTaskGenerationTypesDaily,
			params,
			(v) => (loadingTaskGenerationTypes = v),
			(v) => (taskGenerationTypesDaily = v),
			requestId
		);
	};

	// Update URL query parameters
	const updateURL = () => {
		isUpdatingURL = true;
		const params = new URLSearchParams();
		if (startDate) params.set('start_date', startDate);
		if (endDate) params.set('end_date', endDate);
		if (modelType && modelType !== 'both') params.set('model_type', modelType);

		const queryString = params.toString();
		const newUrl = queryString ? `${$page.url.pathname}?${queryString}` : $page.url.pathname;

		// Use replaceState to avoid adding to browser history
		goto(newUrl, { replaceState: true, noScroll: true }).then(() => {
			// Reset flag after a brief delay to allow URL to update
			setTimeout(() => {
				isUpdatingURL = false;
			}, 0);
		});
	};

	const handleDateRangeChange = (event: CustomEvent<{ startDate: string; endDate: string }>) => {
		startDate = event.detail.startDate;
		endDate = event.detail.endDate;
		updateURL();
		fetchAllMetrics();
	};

	const handleModelTypeChange = (event: CustomEvent<'local' | 'external' | 'both'>) => {
		modelType = event.detail;
		updateURL();
		fetchAllMetrics();
	};

	// Initialize from URL query parameters or defaults
	const initializeFromURL = (skipFetch = false) => {
		const params = $page.url.searchParams;
		let needsURLUpdate = false;

		// Read date range from URL or use default (last 30 days)
		if (params.has('start_date') && params.has('end_date')) {
			startDate = params.get('start_date') || '';
			endDate = params.get('end_date') || '';
		} else {
			const end = new Date();
			const start = new Date();
			start.setDate(start.getDate() - 30);
			startDate = start.toISOString().split('T')[0];
			endDate = end.toISOString().split('T')[0];
			needsURLUpdate = true;
		}

		// Read model type from URL or use default
		const urlModelType = params.get('model_type');
		if (urlModelType && ['local', 'external', 'both'].includes(urlModelType)) {
			modelType = urlModelType as 'local' | 'external' | 'both';
		} else {
			modelType = 'both';
			// Only update URL if model_type was explicitly set to something invalid
			// (not if it's just missing, since 'both' is the default)
		}

		// Update URL with defaults if needed (only on initial load)
		if (needsURLUpdate && !skipFetch) {
			updateURL();
		}

		if (!skipFetch) {
			fetchAllMetrics();
		}
	};

	// Watch for URL changes (e.g., browser back/forward)
	$: if ($page.url.searchParams && !isUpdatingURL && isInitialized) {
		const params = $page.url.searchParams;
		const urlStartDate = params.get('start_date') || '';
		const urlEndDate = params.get('end_date') || '';
		const urlModelType = params.get('model_type') || 'both';

		// Check if URL params differ from current state
		if (urlStartDate !== startDate || urlEndDate !== endDate || urlModelType !== modelType) {
			initializeFromURL();
		}
	}

	onMount(() => {
		initializeFromURL();
		isInitialized = true;
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

		<!-- Summary Statistics Card -->
		<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">{$i18n.t('Total Spend')}</div>
				<div class="text-xl font-semibold tabular-nums">{formatSmartCurrency(totalSpend)}</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">{$i18n.t('Total Tokens')}</div>
				<div class="text-xl font-semibold tabular-nums">
					{new Intl.NumberFormat().format(totalTokens)}
				</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">{$i18n.t('Input Tokens')}</div>
				<div class="text-xl font-semibold tabular-nums">
					{new Intl.NumberFormat().format(totalInputTokens)}
				</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">{$i18n.t('Output Tokens')}</div>
				<div class="text-xl font-semibold tabular-nums">
					{new Intl.NumberFormat().format(totalOutputTokens)}
				</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">{$i18n.t('Total Messages')}</div>
				<div class="text-xl font-semibold tabular-nums">
					{new Intl.NumberFormat().format(totalMessages)}
				</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
				<div class="text-sm text-gray-600 dark:text-gray-400 mb-1">
					{$i18n.t('Avg Cost/Message')}
				</div>
				<div class="text-xl font-semibold tabular-nums">
					{formatSmartCurrency(avgCostPerMessage)}
				</div>
			</div>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<!-- Model Usage Table -->
			<div class="lg:col-span-2">
				<div class="flex justify-between items-center mb-2">
					<h3 class="text-lg font-semibold">{$i18n.t('Model Usage')}</h3>
					{#if !loadingModels && modelMetrics.length > 0}
						<button
							class="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition"
							on:click={exportModelUsage}
						>
							<Download className="w-4 h-4" strokeWidth="1.5" />
							{$i18n.t('Export CSV')}
						</button>
					{/if}
				</div>
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
				<div class="flex items-center justify-between mb-2">
					<h3 class="text-lg font-semibold">{$i18n.t('Tokens per Model per Day')}</h3>
					<div class="flex items-center gap-2">
						<span class="text-sm text-gray-600 dark:text-gray-400">{$i18n.t('Cost')}</span>
						<Switch
							bind:state={showCost}
							on:change={(e) => {
								showCost = e.detail;
							}}
						/>
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<ModelDailyTokensChart
						tokensData={modelDailyTokens}
						costData={modelDailyCost}
						loading={loadingModelTokens || loadingModelCost}
						bind:showCost
					/>
				</div>
			</div>

			<!-- Average Cost per Message -->
			<div>
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Average Cost per Message')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<CostPerMessageChart data={costPerMessageDaily} loading={loadingCostPerMessage} />
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

			<!-- Task Generation Types -->
			<div class="lg:col-span-2">
				<h3 class="text-lg font-semibold mb-2">{$i18n.t('Task Generation Types')}</h3>
				<div class="bg-white dark:bg-gray-800 rounded-xl p-4">
					<TaskGenerationTypesChart
						data={taskGenerationTypesDaily}
						loading={loadingTaskGenerationTypes}
					/>
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
			<br />
			<p>
				Additionally, note that <strong>arena models</strong> are flattened to the actual model used
				for each generation. However, workspace models are <em>not</em> flattened to their base models.
			</p>
			<br />
			<!-- (Irrelevant now that task model generations show up as metrics)<p>
				<strong>Task model generations</strong> are included in the metrics.
			</p>
			<br /> -->
			<p>All dates are in UTC timezone, so a date may span multiple local calendar days.</p>
		</div>
	</div>
</div>
