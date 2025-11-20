import { get } from 'svelte/store';
import { metricsCache } from '$lib/stores';
import {
	getModelMetrics,
	getDailyTokenUsage,
	getDailySpend,
	getMessageCountDaily,
	type MetricsParams
} from '$lib/apis/metrics';

// Generate cache key from params (same logic as in metrics page)
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

// Prefetch essential metrics for the default 30-day view
// This includes Model Usage table and summary statistics
export const prefetchMetrics = async (): Promise<void> => {
	const token = localStorage.token;
	if (!token) {
		return;
	}

	// Calculate default date range (last 30 days)
	const end = new Date();
	const start = new Date();
	start.setDate(start.getDate() - 30);
	const startDate = start.toISOString().split('T')[0];
	const endDate = end.toISOString().split('T')[0];

	const params: MetricsParams = {
		model_type: 'both',
		start_date: startDate,
		end_date: endDate
	};

	// Helper to safely update cache
	const updateCache = (key: string, data: any) => {
		const currentCache = get(metricsCache);
		// Double-check the key doesn't exist (another prefetch might have added it)
		if (!currentCache.has(key)) {
			const newCache = new Map(currentCache);
			newCache.set(key, data);
			metricsCache.set(newCache);
		}
	};

	// Prefetch Model Usage (for the table)
	const modelsCacheKey = getCacheKey('models', { ...params, limit: 15 });
	if (!get(metricsCache).has(modelsCacheKey)) {
		getModelMetrics(token, { ...params, limit: 15 }).then((data) => {
			updateCache(modelsCacheKey, data);
		}).catch((err) => {
			// Silently fail on prefetch - errors will be shown when user actually navigates
			console.debug('Metrics prefetch error (models):', err);
		});
	}

	// Prefetch Daily Token Usage (for summary: total tokens)
	const tokensCacheKey = getCacheKey('tokens/daily', params);
	if (!get(metricsCache).has(tokensCacheKey)) {
		getDailyTokenUsage(token, params).then((data) => {
			updateCache(tokensCacheKey, data);
		}).catch((err) => {
			console.debug('Metrics prefetch error (tokens):', err);
		});
	}

	// Prefetch Daily Spend (for summary: total spend)
	const spendCacheKey = getCacheKey('spend/daily', params);
	if (!get(metricsCache).has(spendCacheKey)) {
		getDailySpend(token, params).then((data) => {
			updateCache(spendCacheKey, data);
		}).catch((err) => {
			console.debug('Metrics prefetch error (spend):', err);
		});
	}

	// Prefetch Message Count (for summary: total messages)
	const messagesCacheKey = getCacheKey('messages/daily', params);
	if (!get(metricsCache).has(messagesCacheKey)) {
		getMessageCountDaily(token, params).then((data) => {
			updateCache(messagesCacheKey, data);
		}).catch((err) => {
			console.debug('Metrics prefetch error (messages):', err);
		});
	}
};

