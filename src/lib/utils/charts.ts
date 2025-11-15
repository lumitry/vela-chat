import { formatSmartCurrency } from './currency';
import { browser } from '$app/environment';

/**
 * Common Chart.js configuration utilities for metrics charts
 */

export interface ChartDataPoint {
	x: string; // date string
	y: number;
}

/**
 * Check if dark mode is active
 */
function isDarkMode(): boolean {
	if (!browser) return true; // Default to dark mode for SSR
	return document.documentElement.classList.contains('dark');
}

/**
 * Get theme-aware chart colors
 * Returns muted, sophisticated colors that work well with dark UI
 */
export function getChartColors() {
	const dark = isDarkMode();
	
	// Muted, sophisticated color palette that works with dark theme
	// These are desaturated versions that feel more integrated
	const primary = dark ? 'rgba(99, 102, 241, 0.8)' : 'rgba(59, 130, 246, 0.8)'; // Muted indigo/blue
	const secondary = dark ? 'rgba(139, 92, 246, 0.8)' : 'rgba(139, 92, 246, 0.8)'; // Muted purple
	const accent = dark ? 'rgba(236, 72, 153, 0.8)' : 'rgba(236, 72, 153, 0.8)'; // Muted pink
	
	// For single-series charts - subtle gradient
	const singleSeries = {
		primary: dark ? 'rgba(99, 102, 241, 0.9)' : 'rgba(59, 130, 246, 0.9)',
		primaryLight: dark ? 'rgba(99, 102, 241, 0.5)' : 'rgba(59, 130, 246, 0.5)',
		primaryBg: dark ? 'rgba(99, 102, 241, 0.15)' : 'rgba(59, 130, 246, 0.15)'
	};
	
	// For multi-series line chart - carefully selected muted palette
	// Colors are distinguishable but not jarring
	const multiSeries = dark ? [
		'rgba(99, 102, 241, 0.85)',   // Muted indigo
		'rgba(16, 185, 129, 0.85)',  // Muted emerald (slightly brighter for contrast)
		'rgba(236, 72, 153, 0.85)',  // Muted pink
		'rgba(245, 158, 11, 0.85)',  // Muted amber
		'rgba(139, 92, 246, 0.85)',  // Muted purple
		'rgba(6, 182, 212, 0.85)',   // Muted cyan
		'rgba(251, 146, 60, 0.85)',  // Muted orange
		'rgba(34, 197, 94, 0.85)',   // Muted green
		'rgba(249, 115, 22, 0.85)',  // Muted orange-red
		'rgba(168, 85, 247, 0.85)'   // Muted violet
	] : [
		'rgba(59, 130, 246, 0.85)',  // Blue
		'rgba(16, 185, 129, 0.85)',   // Green
		'rgba(239, 68, 68, 0.85)',   // Red
		'rgba(245, 158, 11, 0.85)',  // Amber
		'rgba(139, 92, 246, 0.85)',  // Purple
		'rgba(6, 182, 212, 0.85)',   // Cyan
		'rgba(251, 146, 60, 0.85)',  // Orange
		'rgba(236, 72, 153, 0.85)',  // Pink
		'rgba(34, 197, 94, 0.85)',   // Green
		'rgba(249, 115, 22, 0.85)'   // Orange-red
	];
	
	// For stacked bar charts (input/output tokens)
	const stacked = {
		input: dark ? 'rgba(99, 102, 241, 0.75)' : 'rgba(59, 130, 246, 0.75)',
		output: dark ? 'rgba(16, 185, 129, 0.75)' : 'rgba(16, 185, 129, 0.75)'
	};
	
	return {
		singleSeries,
		multiSeries,
		stacked,
		primary,
		secondary,
		accent
	};
}

/**
 * Get Chart.js default configuration for dark mode compatibility
 */
export function getChartDefaults() {
	const dark = isDarkMode();
	const textColor = dark ? 'rgba(156, 163, 175, 0.9)' : 'rgba(75, 85, 99, 0.9)';
	const gridColor = dark ? 'rgba(75, 85, 99, 0.2)' : 'rgba(229, 231, 235, 0.8)';
	const borderColor = dark ? 'rgba(75, 85, 99, 0.3)' : 'rgba(229, 231, 235, 0.8)';
	
	return {
		color: textColor,
		font: {
			family: 'system-ui, -apple-system, sans-serif',
			size: 12
		},
		plugins: {
			legend: {
				labels: {
					color: textColor,
					padding: 12,
					usePointStyle: true,
					pointStyle: 'circle',
					font: {
						size: 11
					}
				}
			},
			tooltip: {
				backgroundColor: dark ? 'rgba(31, 41, 55, 0.95)' : 'rgba(255, 255, 255, 0.95)',
				titleColor: textColor,
				bodyColor: textColor,
				borderColor: borderColor,
				borderWidth: 1,
				padding: 10,
				cornerRadius: 6,
				displayColors: true,
				boxPadding: 6
			}
		},
		scales: {
			x: {
				grid: {
					color: gridColor,
					drawBorder: false
				},
				ticks: {
					color: textColor,
					font: {
						size: 11
					}
				}
			},
			y: {
				grid: {
					color: gridColor,
					drawBorder: false
				},
				ticks: {
					color: textColor,
					font: {
						size: 11
					}
				}
			}
		}
	};
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
	const defaults = getChartDefaults();
	return {
		type: 'time' as const,
		time: {
			unit: 'day' as const,
			displayFormats: {
				day: 'MMM d, yyyy'
			}
		},
		distribution: 'linear' as const,
		grid: defaults.scales.x.grid,
		ticks: {
			...defaults.scales.x.ticks,
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
	const defaults = getChartDefaults();
	
	return {
		...defaults.plugins.tooltip,
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
	const defaults = getChartDefaults();
	return {
		...defaults.scales.y.ticks,
		callback: (value: any) => {
			return formatSmartCurrency(value as number);
		}
	};
}

/**
 * Transform date-based data to Chart.js format with time scale
 * Note: Dates are in UTC as extracted by the backend. A UTC date represents
 * all activity during that calendar day in UTC timezone, which may span
 * two local calendar days depending on the user's timezone offset.
 */
export function transformToTimeSeriesData<T extends { date: string }>(
	data: T[],
	getValue: (item: T) => number
): ChartDataPoint[] {
	return data && Array.isArray(data) 
		? data.map((d) => ({ x: d.date, y: getValue(d) || 0 }))
		: [];
}

