import { WEBUI_API_BASE_URL } from '$lib/constants';

export type MetricsParams = {
	limit?: number;
	model_type?: 'local' | 'external' | 'both';
	start_date?: string;
	end_date?: string;
};

type ModelMetrics = {
	model_id: string;
	model_name: string;
	spend: number;
	input_tokens: number;
	output_tokens: number;
	total_tokens: number;
	message_count: number;
};

type DailyTokenUsage = {
	date: string;
	input_tokens: number;
	output_tokens: number;
	total_tokens: number;
};

type DailySpend = {
	date: string;
	cost: number;
};

type ModelDailyTokens = {
	date: string;
	model_id: string;
	model_name: string;
	input_tokens: number;
	output_tokens: number;
	total_tokens: number;
};

type CostPerMessageDaily = {
	date: string;
	avg_cost: number;
	message_count: number;
	total_cost: number;
};

type MessageCountDaily = {
	date: string;
	count: number;
};

type ModelPopularity = {
	model_id: string;
	model_name: string;
	chat_count: number;
	message_count: number;
};

type CostPerTokenDaily = {
	date: string;
	avg_cost_per_token: number;
	total_tokens: number;
	total_cost: number;
};

const buildQueryString = (params: MetricsParams): string => {
	const searchParams = new URLSearchParams();
	if (params.limit !== undefined) {
		searchParams.append('limit', params.limit.toString());
	}
	if (params.model_type) {
		searchParams.append('model_type', params.model_type);
	}
	if (params.start_date) {
		searchParams.append('start_date', params.start_date);
	}
	if (params.end_date) {
		searchParams.append('end_date', params.end_date);
	}
	return searchParams.toString();
};

const fetchMetrics = async <T>(
	token: string,
	endpoint: string,
	params?: MetricsParams
): Promise<T> => {
	let error = null;

	const queryString = params ? buildQueryString(params) : '';
	const url = `${WEBUI_API_BASE_URL}/metrics/${endpoint}${queryString ? `?${queryString}` : ''}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail || err.message || 'Unknown error';
			console.error('Metrics API error:', err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelMetrics = async (
	token: string,
	params?: MetricsParams
): Promise<ModelMetrics[]> => {
	return fetchMetrics<ModelMetrics[]>(token, 'models', params);
};

export const getDailyTokenUsage = async (
	token: string,
	params?: MetricsParams
): Promise<DailyTokenUsage[]> => {
	return fetchMetrics<DailyTokenUsage[]>(token, 'tokens/daily', params);
};

export const getDailySpend = async (
	token: string,
	params?: MetricsParams
): Promise<DailySpend[]> => {
	return fetchMetrics<DailySpend[]>(token, 'spend/daily', params);
};

export const getModelDailyTokens = async (
	token: string,
	params?: MetricsParams
): Promise<ModelDailyTokens[]> => {
	return fetchMetrics<ModelDailyTokens[]>(token, 'tokens/model/daily', params);
};

export const getCostPerMessageDaily = async (
	token: string,
	params?: MetricsParams
): Promise<CostPerMessageDaily[]> => {
	return fetchMetrics<CostPerMessageDaily[]>(token, 'cost/message/daily', params);
};

export const getMessageCountDaily = async (
	token: string,
	params?: MetricsParams
): Promise<MessageCountDaily[]> => {
	return fetchMetrics<MessageCountDaily[]>(token, 'messages/daily', params);
};

export const getModelPopularity = async (
	token: string,
	params?: MetricsParams
): Promise<ModelPopularity[]> => {
	return fetchMetrics<ModelPopularity[]>(token, 'models/popularity', params);
};

export const getCostPerTokenDaily = async (
	token: string,
	params?: MetricsParams
): Promise<CostPerTokenDaily[]> => {
	return fetchMetrics<CostPerTokenDaily[]>(token, 'cost/token/daily', params);
};

