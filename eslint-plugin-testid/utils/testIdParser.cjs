/**
 * Common parsing utilities for extracting testId patterns
 * Handles both regex-based and AST-based extraction
 */

const { partsToPattern } = require('./testIdExtractor.cjs');
const {
	DATA_TESTID_REGEX,
	PROP_TESTID_REGEX,
	ARGUMENT_EXTRACTOR_REGEX,
	STRING_LITERAL_REGEX
} = require('./regexPatterns.cjs');

/**
 * Parses arguments from a testId function call string
 * @param {string} argsStr - The arguments string (e.g., "'Part1', 'Part2', variable")
 * @param {Object} options - Parsing options
 * @param {boolean} options.onlyStringLiterals - If true, only extract string literals (skip variables)
 * @returns {string[]} - Array of parts (variables become '*')
 */
function parseTestIdArguments(argsStr, options = {}) {
	const parts = [];
	const regex = options.onlyStringLiterals ? STRING_LITERAL_REGEX : ARGUMENT_EXTRACTOR_REGEX;
	
	// Reset regex lastIndex to ensure fresh match
	regex.lastIndex = 0;
	
	let match;
	while ((match = regex.exec(argsStr)) !== null) {
		if (match[1]) {
			// String literal
			parts.push(match[1]);
		} else if (match[2] && !options.onlyStringLiterals) {
			// Variable - treat as wildcard
			parts.push('*');
		}
	}
	
	return parts;
}

/**
 * Extracts testId patterns from a Svelte file's content using regex
 * @param {string} content - File content
 * @param {Object} options - Extraction options
 * @param {boolean} options.includeProps - Whether to include testId props (not just data-testid)
 * @returns {Array<{pattern: string, type: 'data-testid'|'prop', match: RegExpMatchArray}>}
 */
function extractTestIdsFromSvelteContent(content, options = {}) {
	const results = [];
	const { includeProps = true } = options;
	
	// Extract data-testid patterns
	let match;
	DATA_TESTID_REGEX.lastIndex = 0;
	while ((match = DATA_TESTID_REGEX.exec(content)) !== null) {
		const argsStr = match[1];
		const parts = parseTestIdArguments(argsStr);
		
		if (parts.length > 0) {
			results.push({
				pattern: partsToPattern(parts),
				type: 'data-testid',
				match: match
			});
		}
	}
	
	// Extract testId prop patterns (if requested)
	if (includeProps) {
		PROP_TESTID_REGEX.lastIndex = 0;
		while ((match = PROP_TESTID_REGEX.exec(content)) !== null) {
			const argsStr = match[1];
			const parts = parseTestIdArguments(argsStr);
			
			if (parts.length > 0) {
				results.push({
					pattern: partsToPattern(parts),
					type: 'prop',
					match: match
				});
			}
		}
	}
	
	return results;
}

/**
 * Calculates line and column from a string index
 * @param {string} content - Full file content
 * @param {number} index - Character index
 * @returns {{line: number, column: number}} - Line and column (1-indexed)
 */
function indexToLineColumn(content, index) {
	const lines = content.split('\n');
	let currentIndex = 0;
	
	for (let i = 0; i < lines.length; i++) {
		const lineLength = lines[i].length + 1; // +1 for newline
		
		if (currentIndex + lineLength > index) {
			return {
				line: i + 1,
				column: index - currentIndex
			};
		}
		
		currentIndex += lineLength;
	}
	
	// Fallback: return last line
	return {
		line: lines.length,
		column: lines[lines.length - 1].length
	};
}

/**
 * Extracts testId patterns from Svelte content with location information
 * @param {string} content - File content
 * @param {Object} options - Extraction options
 * @returns {Array<{pattern: string, type: 'data-testid'|'prop', location: {line: number, column: number}}>}
 */
function extractTestIdsFromSvelteWithLocation(content, options = {}) {
	const extracted = extractTestIdsFromSvelteContent(content, options);
	
	return extracted.map(({ pattern, type, match }) => {
		const location = indexToLineColumn(content, match.index);
		return {
			pattern,
			type,
			location
		};
	});
}

module.exports = {
	parseTestIdArguments,
	extractTestIdsFromSvelteContent,
	extractTestIdsFromSvelteWithLocation,
	indexToLineColumn
};

