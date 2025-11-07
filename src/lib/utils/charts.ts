import { formatSmartCurrency } from './currency';

/**
 * Common Chart.js configuration utilities for metrics charts
 */

export interface ChartDataPoint {
	x: string; // date string
	y: number;
}

/**
 * Format date for tooltip title (without time)
 */
export function formatTooltipDate(tooltipItems: any[]): string {
	if (tooltipItems.length > 0) {
		const date = new Date(tooltipItems[0].parsed.x);
		return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
	return '';
}

/**
 * Get common time scale configuration for X-axis
 */
export function getTimeScaleConfig() {
	return {
		type: 'time' as const,
		time: {
			unit: 'day' as const,
			displayFormats: {
				day: 'MMM d, yyyy'
			}
		},
		distribution: 'linear' as const,
		ticks: {
			callback: function(value: any) {
				return new Date(value).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
			}
		}
	};
}

/**
 * Get common tooltip configuration with date formatting
 */
export function getTooltipConfig(options?: {
	includeTitle?: boolean;
	formatLabel?: (context: any) => string;
	formatFooter?: (tooltipItems: any[]) => string;
}) {
	const { includeTitle = true, formatLabel, formatFooter } = options || {};
	
	return {
		callbacks: {
			...(includeTitle && {
				title: formatTooltipDate
			}),
			...(formatLabel && {
				label: formatLabel
			}),
			...(formatFooter && {
				footer: formatFooter
			})
		}
	};
}

/**
 * Get tooltip config for currency values
 */
export function getCurrencyTooltipConfig(labelPrefix: string) {
	return getTooltipConfig({
		formatLabel: (context: any) => {
			const value = context.parsed.y || 0;
			return `${labelPrefix}: ${formatSmartCurrency(value)}`;
		}
	});
}

/**
 * Get tooltip config for number values
 */
export function getNumberTooltipConfig(labelPrefix: string, suffix: string = '') {
	return getTooltipConfig({
		formatLabel: (context: any) => {
			const value = context.parsed.y || 0;
			return `${labelPrefix}: ${new Intl.NumberFormat().format(value)}${suffix}`;
		}
	});
}

/**
 * Get Y-axis ticks config for currency
 */
export function getCurrencyYTicks() {
	return {
		callback: (value: any) => {
			return formatSmartCurrency(value as number);
		}
	};
}

/**
 * Transform date-based data to Chart.js format with time scale
 */
export function transformToTimeSeriesData<T extends { date: string }>(
	data: T[],
	getValue: (item: T) => number
): ChartDataPoint[] {
	return data && Array.isArray(data) 
		? data.map((d) => ({ x: d.date, y: getValue(d) || 0 }))
		: [];
}

