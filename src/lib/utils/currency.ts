/**
 * Smart currency formatter that uses cents (¢) for small amounts and dollars ($) for larger amounts
 * @param value - The currency value in dollars
 * @param threshold - Threshold in dollars (default: 0.10, i.e., 10 cents)
 * @returns Formatted string with appropriate currency symbol
 */
export function formatSmartCurrency(value: number, threshold: number = 0.10): string {
	if (value < threshold) {
		// Use cents for small amounts
		const cents = value * 100;
		return `${new Intl.NumberFormat('en-US', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 8
		}).format(cents)}¢`;
	} else {
		// Use dollars for larger amounts
		return new Intl.NumberFormat('en-US', {
			style: 'currency',
			currency: 'USD',
			minimumFractionDigits: 2,
			maximumFractionDigits: 8
		}).format(value);
	}
}

