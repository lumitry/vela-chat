/**
 * Shared cache for testId tracking across ESLint rule executions
 * This allows rules to share data across file boundaries
 */

class TestIdCache {
	constructor() {
		// Map of file path -> Map of pattern -> location info
		// location info: { line: number, column: number, node?: AST node }
		this.svelteTestIds = new Map(); // .svelte files -> Map<pattern, location>
		this.sveltePropTestIds = new Map(); // .svelte files -> Map<pattern, location> (testIds passed as props)
		this.pageObjectTestIds = new Map(); // page object files -> Map<pattern, location>
		this.initialized = false; // Track if we've done the initial scan
		this.reset();
	}

	reset() {
		this.svelteTestIds.clear();
		this.sveltePropTestIds.clear();
		this.pageObjectTestIds.clear();
		this.initialized = false;
	}

	/**
	 * Clear testIds for a specific file (used when file is being re-processed)
	 */
	clearFileTestIds(filePath) {
		this.svelteTestIds.delete(filePath);
		this.sveltePropTestIds.delete(filePath);
		this.pageObjectTestIds.delete(filePath);
	}

	/**
	 * Add a testId pattern found in a .svelte file (as data-testid attribute)
	 */
	addSvelteTestId(filePath, pattern, location = null) {
		if (!this.svelteTestIds.has(filePath)) {
			this.svelteTestIds.set(filePath, new Map());
		}
		const patterns = this.svelteTestIds.get(filePath);
		// Always update with new location if provided, or use existing
		if (location) {
			patterns.set(pattern, location);
		} else if (!patterns.has(pattern)) {
			patterns.set(pattern, null);
		}
	}

	/**
	 * Add a testId pattern found as a prop in a .svelte file (e.g., testId={testId(...)})
	 */
	addSveltePropTestId(filePath, pattern, location = null) {
		if (!this.sveltePropTestIds.has(filePath)) {
			this.sveltePropTestIds.set(filePath, new Map());
		}
		const patterns = this.sveltePropTestIds.get(filePath);
		// Always update with new location if provided, or use existing
		if (location) {
			patterns.set(pattern, location);
		} else if (!patterns.has(pattern)) {
			patterns.set(pattern, null);
		}
	}

	/**
	 * Add a testId pattern found in a page object file
	 */
	addPageObjectTestId(filePath, pattern, location = null) {
		if (!this.pageObjectTestIds.has(filePath)) {
			this.pageObjectTestIds.set(filePath, new Map());
		}
		const patterns = this.pageObjectTestIds.get(filePath);
		// Always update with new location if provided, or use existing
		if (location) {
			patterns.set(pattern, location);
		} else if (!patterns.has(pattern)) {
			patterns.set(pattern, null);
		}
	}

	/**
	 * Get all testId patterns from all .svelte files
	 */
	getAllSvelteTestIds() {
		const all = new Set();
		for (const patterns of this.svelteTestIds.values()) {
			for (const pattern of patterns.keys()) {
				all.add(pattern);
			}
		}
		return all;
	}

	/**
	 * Get all testId patterns from all page object files
	 */
	getAllPageObjectTestIds() {
		const all = new Set();
		for (const patterns of this.pageObjectTestIds.values()) {
			for (const pattern of patterns.keys()) {
				all.add(pattern);
			}
		}
		return all;
	}

	/**
	 * Check if a pattern is used in any page object file
	 */
	isUsedInPageObjects(pattern) {
		const { matchesWildcardPattern } = require('./testIdExtractor.cjs');

		// Check exact matches
		for (const patterns of this.pageObjectTestIds.values()) {
			for (const pagePattern of patterns.keys()) {
				if (pattern === pagePattern) {
					return true;
				}
				// Check if pattern matches a wildcard pattern
				// Only match if the wildcard pattern is more specific (has more segments)
				if (pagePattern.includes('*')) {
					// Count segments (parts separated by _)
					const patternSegments = pattern.split('_').length;
					const pagePatternSegments = pagePattern.split('_').length;
					// Only match if the wildcard pattern has the same or more segments
					// This prevents Chat_* from matching Chat_InfoModal_ThisIsNeverUsed
					if (pagePatternSegments >= patternSegments && matchesWildcardPattern(pattern, pagePattern)) {
						return true;
					}
				}
				// Check if wildcard pattern matches the page pattern
				if (pattern.includes('*') && matchesWildcardPattern(pagePattern, pattern)) {
					return true;
				}
			}
		}
		return false;
	}

	/**
	 * Check if a pattern is defined in any .svelte file (either as data-testid or as a prop)
	 */
	isDefinedInSvelte(pattern) {
		const { matchesWildcardPattern } = require('./testIdExtractor.cjs');

		// Check both data-testid testIds and prop testIds
		const allSvelteTestIds = [
			...Array.from(this.svelteTestIds.values()),
			...Array.from(this.sveltePropTestIds.values())
		];

		// Check exact matches
		for (const patterns of allSvelteTestIds) {
			for (const sveltePattern of patterns.keys()) {
				if (pattern === sveltePattern) {
					return true;
				}
				// Check if pattern matches a wildcard pattern
				// Only match if the wildcard pattern is more specific (has more segments)
				if (sveltePattern.includes('*')) {
					const patternSegments = pattern.split('_').length;
					const sveltePatternSegments = sveltePattern.split('_').length;
					if (sveltePatternSegments >= patternSegments && matchesWildcardPattern(pattern, sveltePattern)) {
						return true;
					}
				}
				// Check if wildcard pattern matches the svelte pattern
				if (pattern.includes('*') && matchesWildcardPattern(sveltePattern, pattern)) {
					return true;
				}
			}
		}
		return false;
	}
}

// Singleton instance shared across all rule executions
let cacheInstance = null;

function getCache() {
	if (!cacheInstance) {
		cacheInstance = new TestIdCache();
	}
	return cacheInstance;
}

function resetCache() {
	cacheInstance = new TestIdCache();
}

function markInitialized() {
	const cache = getCache();
	cache.initialized = true;
}

function isInitialized() {
	const cache = getCache();
	return cache.initialized;
}

module.exports = {
	getCache,
	resetCache,
	markInitialized,
	isInitialized
};

